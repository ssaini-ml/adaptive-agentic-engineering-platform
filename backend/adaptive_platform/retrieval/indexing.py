from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.orm import Session

from adaptive_platform.database.models import ContextDocumentRecord, SymbolRecord
from adaptive_platform.extraction import SourceSnapshotError
from adaptive_platform.retrieval.models import ContextDocumentType

MAX_DOCUMENT_CHARACTERS = 20_000
MAX_DOCUMENT_LINES = 200
INDEXED_CATEGORIES = frozenset(
    {"SOURCE", "TEST", "DOCUMENTATION", "CONFIGURATION", "DEPENDENCY"}
)


class ContextFile(Protocol):
    id: UUID
    path: str
    language: str | None
    category: str
    content_hash: str
    encoding: str | None
    is_generated: bool
    is_vendored: bool
    secret_finding_count: int


@dataclass(frozen=True, slots=True)
class ContextDocumentDraft:
    id: UUID
    scan_id: UUID
    file_id: UUID
    symbol_id: UUID | None
    document_type: ContextDocumentType
    content: str
    content_hash: str
    start_line: int
    end_line: int
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class ContextIndexBuild:
    documents: tuple[ContextDocumentDraft, ...]
    exclusions: dict[str, int]


def build_context_documents(
    repository_root: Path,
    scan_id: UUID,
    files: Iterable[ContextFile],
    symbols: Iterable[SymbolRecord],
) -> ContextIndexBuild:
    root = repository_root.resolve(strict=True)
    symbols_by_file: dict[UUID, list[SymbolRecord]] = {}
    for symbol in symbols:
        symbols_by_file.setdefault(symbol.file_id, []).append(symbol)

    documents: list[ContextDocumentDraft] = []
    exclusions: Counter[str] = Counter()
    for item in sorted(files, key=lambda value: value.path):
        reason = _exclusion_reason(item)
        if reason is not None:
            exclusions[reason] += 1
            continue
        content = _read_verified_text(root, item)
        file_type = _file_document_type(item.category)
        documents.extend(
            _drafts_for_text(
                scan_id=scan_id,
                file=item,
                symbol_id=None,
                document_type=file_type,
                content=content,
                base_line=1,
                identity="file",
            )
        )
        if item.category != "SOURCE":
            continue
        source_lines = content.splitlines(keepends=True)
        for symbol in sorted(
            symbols_by_file.get(item.id, ()),
            key=lambda value: (value.start_line, value.end_line, value.qualified_name, value.id),
        ):
            document_type = _symbol_document_type(symbol.symbol_type)
            if document_type is None:
                continue
            if not 1 <= symbol.start_line <= symbol.end_line <= max(1, len(source_lines)):
                raise SourceSnapshotError("INVALID_SYMBOL_SPAN", item.path)
            symbol_content = "".join(source_lines[symbol.start_line - 1 : symbol.end_line])
            documents.extend(
                _drafts_for_text(
                    scan_id=scan_id,
                    file=item,
                    symbol_id=symbol.id,
                    document_type=document_type,
                    content=symbol_content,
                    base_line=symbol.start_line,
                    identity=f"symbol:{symbol.id}",
                )
            )
    return ContextIndexBuild(tuple(documents), dict(sorted(exclusions.items())))


def persist_context_documents(
    session: Session,
    *,
    repository_root: Path,
    scan_id: UUID,
    files: Iterable[ContextFile],
) -> ContextIndexBuild:
    file_records = tuple(files)
    symbols = tuple(
        session.scalars(
            select(SymbolRecord)
            .where(SymbolRecord.scan_id == scan_id)
            .order_by(SymbolRecord.file_id, SymbolRecord.start_line, SymbolRecord.id)
        )
    )
    build = build_context_documents(repository_root, scan_id, file_records, symbols)
    dialect = session.get_bind().dialect.name
    for document in build.documents:
        session.add(
            ContextDocumentRecord(
                id=document.id,
                scan_id=document.scan_id,
                file_id=document.file_id,
                symbol_id=document.symbol_id,
                document_type=document.document_type.value,
                content=document.content,
                content_hash=document.content_hash,
                search_vector=(
                    _normalized_test_vector(document.content) if dialect == "sqlite" else None
                ),
                document_metadata=document.metadata,
                start_line=document.start_line,
                end_line=document.end_line,
            )
        )
    session.flush()
    if dialect == "postgresql" and build.documents:
        normalized_code = func.regexp_replace(
            func.regexp_replace(
                ContextDocumentRecord.content,
                r"([a-z0-9])([A-Z])",
                r"\1 \2",
                "g",
            ),
            r"[._:/-]+",
            " ",
            "g",
        )
        search_text = ContextDocumentRecord.content.concat(" ").concat(normalized_code)
        session.execute(
            update(ContextDocumentRecord)
            .where(ContextDocumentRecord.scan_id == scan_id)
            .values(
                search_vector=func.to_tsvector(
                    literal_column("'simple'::regconfig"),
                    search_text,
                )
            )
        )
    return build


def _exclusion_reason(item: ContextFile) -> str | None:
    if item.category not in INDEXED_CATEGORIES:
        return "UNAPPROVED_CATEGORY"
    if item.is_generated:
        return "GENERATED"
    if item.is_vendored:
        return "VENDORED"
    if item.secret_finding_count:
        return "SECRET_FLAGGED"
    return None


def _read_verified_text(root: Path, item: ContextFile) -> str:
    relative = PurePosixPath(item.path)
    if relative.is_absolute() or ".." in relative.parts:
        raise SourceSnapshotError("UNSAFE_SOURCE_PATH", item.path)
    candidate = root.joinpath(*relative.parts)
    if candidate.is_symlink():
        raise SourceSnapshotError("SYMLINK_SOURCE_REJECTED", item.path)
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        raw = resolved.read_bytes()
    except (OSError, ValueError) as exc:
        raise SourceSnapshotError("SOURCE_UNAVAILABLE_DURING_INDEXING", item.path) from exc
    if hashlib.sha256(raw).hexdigest() != item.content_hash:
        raise SourceSnapshotError("SOURCE_CHANGED_DURING_INDEXING", item.path)
    try:
        return raw.decode(item.encoding or "utf-8")
    except (LookupError, UnicodeDecodeError) as exc:
        raise SourceSnapshotError("SOURCE_DECODE_FAILED", item.path) from exc


def _file_document_type(category: str) -> ContextDocumentType:
    if category == "TEST":
        return ContextDocumentType.TEST
    if category == "DOCUMENTATION":
        return ContextDocumentType.DOCUMENTATION_SECTION
    if category in {"CONFIGURATION", "DEPENDENCY"}:
        return ContextDocumentType.CONFIGURATION_SECTION
    return ContextDocumentType.MODULE


def _symbol_document_type(symbol_type: str) -> ContextDocumentType | None:
    mapping = {
        "CLASS": ContextDocumentType.CLASS,
        "MODEL": ContextDocumentType.CLASS,
        "FUNCTION": ContextDocumentType.FUNCTION,
        "ROUTE": ContextDocumentType.FUNCTION,
        "METHOD": ContextDocumentType.METHOD,
    }
    return mapping.get(symbol_type)


def _drafts_for_text(
    *,
    scan_id: UUID,
    file: ContextFile,
    symbol_id: UUID | None,
    document_type: ContextDocumentType,
    content: str,
    base_line: int,
    identity: str,
) -> list[ContextDocumentDraft]:
    drafts: list[ContextDocumentDraft] = []
    for chunk_index, (chunk, start_line, end_line) in enumerate(_bounded_chunks(content, base_line)):
        if not chunk.strip():
            continue
        digest = hashlib.sha256(chunk.encode()).hexdigest()
        document_id = uuid5(
            NAMESPACE_URL,
            f"context:{scan_id}:{file.id}:{identity}:{chunk_index}:{start_line}:{end_line}:{digest}",
        )
        drafts.append(
            ContextDocumentDraft(
                id=document_id,
                scan_id=scan_id,
                file_id=file.id,
                symbol_id=symbol_id,
                document_type=document_type,
                content=chunk,
                content_hash=digest,
                start_line=start_line,
                end_line=end_line,
                metadata={
                    "path": file.path,
                    "language": file.language,
                    "category": file.category,
                    "source_content_hash": file.content_hash,
                    "chunk_index": chunk_index,
                    "max_characters": MAX_DOCUMENT_CHARACTERS,
                    "max_lines": MAX_DOCUMENT_LINES,
                },
            )
        )
    return drafts


def _bounded_chunks(content: str, base_line: int) -> list[tuple[str, int, int]]:
    lines = content.splitlines(keepends=True)
    if not lines and content:
        lines = [content]
    chunks: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_chars = 0
    current_start = base_line
    current_end = base_line

    def flush() -> None:
        nonlocal current, current_chars
        if current:
            chunks.append(("".join(current), current_start, current_end))
        current = []
        current_chars = 0

    for offset, line in enumerate(lines):
        line_number = base_line + offset
        parts = [line[index : index + MAX_DOCUMENT_CHARACTERS] for index in range(0, len(line), MAX_DOCUMENT_CHARACTERS)] or [""]
        for part in parts:
            line_span = line_number - current_start + 1 if current else 1
            if current and (
                current_chars + len(part) > MAX_DOCUMENT_CHARACTERS
                or line_span > MAX_DOCUMENT_LINES
            ):
                flush()
            if not current:
                current_start = line_number
            current.append(part)
            current_chars += len(part)
            current_end = line_number
    flush()
    return chunks


def _normalized_test_vector(content: str) -> str:
    camel_split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", content)
    normalized_code = re.sub(r"[._:/-]+", " ", camel_split)
    original = re.findall(r"[A-Za-z0-9_]+", content.casefold())
    aliases = re.findall(r"[A-Za-z0-9]+", normalized_code.casefold())
    return " ".join([*original, *aliases])
