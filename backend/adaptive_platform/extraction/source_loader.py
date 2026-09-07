from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path, PurePosixPath
from typing import Protocol
from uuid import UUID

from adaptive_platform.extraction.protocol import ExtractionDocument


class InventoryFile(Protocol):
    id: UUID
    path: str
    language: str | None
    category: str
    content_hash: str
    encoding: str | None
    is_generated: bool
    is_vendored: bool


class SourceSnapshotError(RuntimeError):
    def __init__(self, code: str, path: str) -> None:
        super().__init__(f"{code}: {path}")
        self.code = code
        self.path = path


def load_extraction_documents(
    repository_root: Path,
    files: Iterable[InventoryFile],
    language: str,
) -> tuple[ExtractionDocument, ...]:
    root = repository_root.resolve(strict=True)
    documents: list[ExtractionDocument] = []
    for item in sorted(files, key=lambda value: value.path):
        if (
            item.language != language
            or item.category not in {"SOURCE", "TEST"}
            or item.is_generated
            or item.is_vendored
        ):
            continue
        relative = PurePosixPath(item.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise SourceSnapshotError("UNSAFE_SOURCE_PATH", item.path)
        candidate = root.joinpath(*relative.parts)
        if candidate.is_symlink():
            raise SourceSnapshotError("SYMLINK_SOURCE_REJECTED", item.path)
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root)
            content = resolved.read_bytes()
        except (OSError, ValueError) as exc:
            raise SourceSnapshotError("SOURCE_UNAVAILABLE_DURING_EXTRACTION", item.path) from exc
        if hashlib.sha256(content).hexdigest() != item.content_hash:
            raise SourceSnapshotError("SOURCE_CHANGED_DURING_EXTRACTION", item.path)
        try:
            text = content.decode(item.encoding or "utf-8")
        except (LookupError, UnicodeDecodeError) as exc:
            raise SourceSnapshotError("SOURCE_DECODE_FAILED", item.path) from exc
        documents.append(
            ExtractionDocument(
                file_id=item.id,
                path=relative,
                language=language,
                content_hash=item.content_hash,
                content=text,
            )
        )
    return tuple(documents)
