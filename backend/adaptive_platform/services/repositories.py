from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from adaptive_platform.config.settings import Settings
from adaptive_platform.database.models import (
    RelationshipRecord,
    RepositoryFileRecord,
    RepositoryLanguageProfileRecord,
    RepositoryLanguageStatisticRecord,
    RepositoryRecord,
    RepositoryScanRecord,
    SymbolRecord,
    TraceEventRecord,
)
from adaptive_platform.domain.models import DirtyTreePolicy
from adaptive_platform.extraction import (
    ExtractionRequest,
    ExtractionResult,
    ExtractorRegistry,
    SourceSnapshotError,
    default_extractor_registry,
    load_extraction_documents,
)
from adaptive_platform.languages import profile_repository_languages
from adaptive_platform.repository.scanner import (
    RepositoryValidationError,
    repository_default_branch,
    scan_repository,
    validate_repository,
)
from adaptive_platform.retrieval import persist_context_documents


class ServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(UTC)


def _trace(
    session: Session,
    *,
    task_id: str,
    category: str,
    event_type: str,
    summary: str,
    repository_id: UUID | None = None,
    scan_id: UUID | None = None,
    rationale_summary: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        TraceEventRecord(
            task_id=task_id,
            repository_id=repository_id,
            scan_id=scan_id,
            category=category,
            event_type=event_type,
            actor_type="SYSTEM",
            occurred_at=_now(),
            summary=summary,
            rationale_summary=rationale_summary,
            input_refs=[],
            output_refs=[],
            event_metadata=metadata or {},
        )
    )


def _persist_extraction_result(
    session: Session,
    scan_id: UUID,
    result: ExtractionResult,
) -> tuple[int, int]:
    symbol_ids = {item.qualified_name: uuid4() for item in result.symbols}
    for item in result.symbols:
        session.add(
            SymbolRecord(
                id=symbol_ids[item.qualified_name],
                scan_id=scan_id,
                file_id=item.file_id,
                parent_symbol_id=(
                    symbol_ids.get(item.parent_qualified_name)
                    if item.parent_qualified_name is not None
                    else None
                ),
                name=item.name,
                qualified_name=item.qualified_name,
                symbol_type=item.symbol_type.value,
                signature=item.signature,
                docstring=item.docstring,
                start_line=item.start_line,
                start_column=item.start_column,
                end_line=item.end_line,
                end_column=item.end_column,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
                extension_metadata=item.extension_metadata or {},
            )
        )
    session.flush()

    for item in result.relationships:
        source_id = symbol_ids.get(item.source_qualified_name)
        if source_id is None:
            raise ValueError(f"Relationship source was not extracted: {item.source_qualified_name}")
        target_id = (
            symbol_ids.get(item.target_qualified_name)
            if item.target_qualified_name is not None
            else None
        )
        unresolved_target = item.unresolved_target
        if target_id is None and unresolved_target is None:
            unresolved_target = item.target_qualified_name
        if target_id is None and unresolved_target is None:
            raise ValueError("Relationship has neither a resolved nor an unresolved target")
        session.add(
            RelationshipRecord(
                scan_id=scan_id,
                source_kind="SYMBOL",
                source_id=source_id,
                target_kind="SYMBOL",
                target_id=target_id,
                unresolved_target=unresolved_target,
                relationship_type=item.relationship_type.value,
                resolution_status=item.resolution_status.value,
                resolution_reason=item.resolution_reason,
                confidence=item.confidence,
                evidence_type=item.evidence_type,
                provenance=item.provenance,
                evidence_file_id=item.evidence_file_id,
                evidence_start_line=item.evidence_start_line,
                evidence_start_column=item.evidence_start_column,
                evidence_end_line=item.evidence_end_line,
                evidence_end_column=item.evidence_end_column,
                extractor_name=item.extractor_name,
                extractor_version=item.extractor_version,
                extension_metadata=item.extension_metadata or {},
            )
        )
    return len(result.symbols), len(result.relationships)


class RepositoryService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    def register(self, path: str, name: str | None = None) -> RepositoryRecord:
        policy = self.settings.scan_policy()
        root = validate_repository(path, policy)
        now = _now()
        record = RepositoryRecord(
            name=name or root.name,
            canonical_path=str(root),
            default_branch=repository_default_branch(root, policy),
            created_at=now,
            updated_at=now,
        )
        self.session.add(record)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback()
            raise ServiceError(
                "REPOSITORY_ALREADY_REGISTERED",
                "Repository path is already registered",
                409,
            ) from exc
        _trace(
            self.session,
            task_id=f"repository:{record.id}",
            category="REPOSITORY",
            event_type="repository_registered",
            summary="Registered a local Git repository.",
            repository_id=record.id,
            metadata={"canonical_path": str(root), "default_branch": record.default_branch},
        )
        self.session.commit()
        return record

    def get(self, repository_id: UUID) -> RepositoryRecord:
        record = self.session.get(RepositoryRecord, repository_id)
        if record is None:
            raise ServiceError("REPOSITORY_NOT_FOUND", "Repository was not found", 404)
        return record


class ScanService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        extractor_registry: ExtractorRegistry | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.extractor_registry = extractor_registry or default_extractor_registry()

    def request(self, repository_id: UUID) -> RepositoryScanRecord:
        repository = self.session.get(RepositoryRecord, repository_id)
        if repository is None:
            raise ServiceError("REPOSITORY_NOT_FOUND", "Repository was not found", 404)
        scan = RepositoryScanRecord(
            repository_id=repository_id,
            status="PENDING",
            scanner_version="inventory-v2",
            configuration_version=self.settings.scanner_configuration_version,
            started_at=_now(),
            file_count=0,
            total_bytes=0,
        )
        self.session.add(scan)
        self.session.flush()
        _trace(
            self.session,
            task_id=f"scan:{scan.id}",
            category="REPOSITORY",
            event_type="scan_requested",
            summary="Created a pending immutable repository scan.",
            repository_id=repository_id,
            scan_id=scan.id,
        )
        self.session.commit()
        return scan

    def execute(
        self,
        scan_id: UUID,
        dirty_tree_policy: DirtyTreePolicy | None = None,
    ) -> RepositoryScanRecord:
        scan = self.session.get(RepositoryScanRecord, scan_id)
        if scan is None:
            raise ServiceError("SCAN_NOT_FOUND", "Repository scan was not found", 404)
        if scan.status != "PENDING":
            raise ServiceError("SCAN_NOT_PENDING", "Only pending scans can be executed", 409)
        repository = self.session.get(RepositoryRecord, scan.repository_id)
        if repository is None:
            raise ServiceError("REPOSITORY_NOT_FOUND", "Repository was not found", 404)

        scan.status = "RUNNING"
        _trace(
            self.session,
            task_id=f"scan:{scan.id}",
            category="EXECUTION",
            event_type="scan_started",
            summary="Started safe repository inventory.",
            repository_id=repository.id,
            scan_id=scan.id,
        )
        self.session.commit()

        policy = self.settings.scan_policy()
        if dirty_tree_policy is not None:
            policy = replace(policy, dirty_tree_policy=dirty_tree_policy)
        try:
            result = scan_repository(repository.canonical_path, policy)
            file_records: list[RepositoryFileRecord] = []
            for item in result.files:
                file_record = RepositoryFileRecord(
                    repository_id=repository.id,
                    scan_id=scan.id,
                    path=item.path.as_posix(),
                    language=item.language,
                    category=item.category,
                    content_hash=item.content_hash,
                    size=item.size,
                    encoding=item.encoding,
                    is_generated=item.is_generated,
                    is_vendored=item.is_vendored,
                    detection_signal=item.detection_signal,
                    secret_finding_count=item.secret_finding_count,
                )
                self.session.add(file_record)
                file_records.append(file_record)
            for notice in result.notices:
                _trace(
                    self.session,
                    task_id=f"scan:{scan.id}",
                    category="DECISION",
                    event_type="file_excluded",
                    summary="Excluded a repository artifact from the inventory.",
                    repository_id=repository.id,
                    scan_id=scan.id,
                    rationale_summary=notice.reason,
                    metadata={"path": notice.path.as_posix(), **notice.metadata},
                )

            language_profile = profile_repository_languages(
                result.files,
                self.extractor_registry,
                configuration_version=self.settings.language_profiler_configuration_version,
                polyglot_threshold_percent=self.settings.polyglot_threshold_percent,
            )
            profile_record = RepositoryLanguageProfileRecord(
                scan_id=scan.id,
                repository_type=language_profile.repository_type.value,
                primary_language=language_profile.primary_language,
                profiler_name=language_profile.profiler_name,
                profiler_version=language_profile.profiler_version,
                configuration_version=language_profile.configuration_version,
                first_party_source_files=language_profile.first_party_source_files,
                first_party_source_bytes=language_profile.first_party_source_bytes,
                unprofiled_file_count=language_profile.unprofiled_file_count,
                created_at=_now(),
            )
            self.session.add(profile_record)
            self.session.flush()
            statistic_records: dict[str, RepositoryLanguageStatisticRecord] = {}
            for language in language_profile.languages:
                statistic_record = RepositoryLanguageStatisticRecord(
                    profile_id=profile_record.id,
                    language=language.language,
                    source_file_count=language.source_file_count,
                    source_bytes=language.source_bytes,
                    source_byte_percentage=language.source_byte_percentage,
                    generated_file_count=language.generated_file_count,
                    generated_bytes=language.generated_bytes,
                    vendored_file_count=language.vendored_file_count,
                    vendored_bytes=language.vendored_bytes,
                    extractor_status=language.extractor_status.value,
                    extractor_name=language.extractor_name,
                    extractor_version=language.extractor_version,
                    detection_signals=list(language.detection_signals),
                    diagnostics=list(language.diagnostics),
                )
                self.session.add(statistic_record)
                statistic_records[language.language] = statistic_record
                _trace(
                    self.session,
                    task_id=f"scan:{scan.id}",
                    category="DECISION",
                    event_type="extractor_coverage_classified",
                    summary="Classified extractor coverage for a detected language.",
                    repository_id=repository.id,
                    scan_id=scan.id,
                    metadata={
                        "language": language.language,
                        "extractor_status": language.extractor_status.value,
                        "extractor_name": language.extractor_name,
                    },
                )
            _trace(
                self.session,
                task_id=f"scan:{scan.id}",
                category="REPOSITORY",
                event_type="language_profile_created",
                summary="Created a scan-bound repository language profile.",
                repository_id=repository.id,
                scan_id=scan.id,
                metadata={
                    "repository_type": language_profile.repository_type.value,
                    "primary_language": language_profile.primary_language,
                    "languages": [item.language for item in language_profile.languages],
                    "unprofiled_file_count": language_profile.unprofiled_file_count,
                    "profiler_version": language_profile.profiler_version,
                },
            )

            # IDs are required to bind extracted evidence to the immutable inventory.
            self.session.flush()
            for language in language_profile.languages:
                adapter = self.extractor_registry.adapter_for(language.language)
                if adapter is None:
                    continue
                documents = load_extraction_documents(
                    Path(repository.canonical_path),
                    file_records,
                    language.language,
                )
                _trace(
                    self.session,
                    task_id=f"scan:{scan.id}",
                    category="EXECUTION",
                    event_type="extractor_started",
                    summary="Started a scan-bound language evidence extractor.",
                    repository_id=repository.id,
                    scan_id=scan.id,
                    metadata={
                        "language": language.language,
                        "extractor_name": adapter.descriptor.name,
                        "extractor_version": adapter.descriptor.version,
                        "document_count": len(documents),
                    },
                )
                extraction_result = adapter.extract(
                    ExtractionRequest(
                        repository_id=repository.id,
                        scan_id=scan.id,
                        documents=documents,
                    )
                )
                symbol_count, relationship_count = _persist_extraction_result(
                    self.session,
                    scan.id,
                    extraction_result,
                )
                statistic_record = statistic_records[language.language]
                statistic_record.extractor_status = extraction_result.status.value
                statistic_record.diagnostics = list(extraction_result.diagnostics)
                _trace(
                    self.session,
                    task_id=f"scan:{scan.id}",
                    category="VERIFICATION",
                    event_type="extractor_completed",
                    summary="Completed scan-bound structural evidence extraction.",
                    repository_id=repository.id,
                    scan_id=scan.id,
                    metadata={
                        "language": language.language,
                        "extractor_status": extraction_result.status.value,
                        "symbol_count": symbol_count,
                        "relationship_count": relationship_count,
                        "diagnostics": list(extraction_result.diagnostics),
                    },
                )

            context_index = persist_context_documents(
                self.session,
                repository_root=Path(repository.canonical_path),
                scan_id=scan.id,
                files=file_records,
            )
            _trace(
                self.session,
                task_id=f"scan:{scan.id}",
                category="VERIFICATION",
                event_type="context_documents_created",
                summary="Created bounded scan-bound documents for lexical retrieval.",
                repository_id=repository.id,
                scan_id=scan.id,
                metadata={
                    "document_count": len(context_index.documents),
                    "exclusions": context_index.exclusions,
                    "search_configuration": "simple",
                },
            )

            # Persist the inventory and profile while the scan is RUNNING, then
            # seal the parent. Later artifact inserts are rejected by guards.
            self.session.flush()
            scan.commit_hash = result.commit_hash
            scan.is_dirty = result.is_dirty
            scan.working_tree_fingerprint = result.working_tree_fingerprint
            scan.scanner_version = result.extractor_version
            scan.configuration_version = result.configuration_version
            scan.file_count = len(result.files)
            scan.total_bytes = sum(item.size for item in result.files)
            scan.completed_at = _now()
            scan.status = "COMPLETED"
            _trace(
                self.session,
                task_id=f"scan:{scan.id}",
                category="VERIFICATION",
                event_type="scan_completed",
                summary="Completed and sealed an immutable repository scan.",
                repository_id=repository.id,
                scan_id=scan.id,
                metadata={
                    "commit_hash": result.commit_hash,
                    "is_dirty": result.is_dirty,
                    "working_tree_fingerprint": result.working_tree_fingerprint,
                    "file_count": len(result.files),
                    "total_bytes": scan.total_bytes,
                    "context_document_count": len(context_index.documents),
                },
            )
            self.session.commit()
            return scan
        except Exception as exc:
            self.session.rollback()
            scan = self.session.get(RepositoryScanRecord, scan_id)
            if scan is None:
                raise
            if isinstance(exc, (RepositoryValidationError, SourceSnapshotError)):
                failure_code = exc.code
                failure_message = str(exc)
            else:
                failure_code = "SCAN_FAILED"
                failure_message = "Repository scan failed"
            scan.status = "FAILED"
            scan.failure_code = failure_code
            scan.failure_message = failure_message
            scan.completed_at = _now()
            _trace(
                self.session,
                task_id=f"scan:{scan.id}",
                category="VERIFICATION",
                event_type="scan_failed",
                summary="Repository scan failed and stored no partial inventory.",
                repository_id=scan.repository_id,
                scan_id=scan.id,
                rationale_summary=failure_code,
            )
            self.session.commit()
            return scan

    def get(self, repository_id: UUID, scan_id: UUID) -> RepositoryScanRecord:
        statement = select(RepositoryScanRecord).where(
            RepositoryScanRecord.id == scan_id,
            RepositoryScanRecord.repository_id == repository_id,
        )
        scan = self.session.scalar(statement)
        if scan is None:
            raise ServiceError("SCAN_NOT_FOUND", "Repository scan was not found", 404)
        return scan

    def list(self, repository_id: UUID) -> list[RepositoryScanRecord]:
        statement = (
            select(RepositoryScanRecord)
            .where(RepositoryScanRecord.repository_id == repository_id)
            .order_by(RepositoryScanRecord.started_at.desc())
        )
        return list(self.session.scalars(statement))

    def files(self, repository_id: UUID, scan_id: UUID) -> list[RepositoryFileRecord]:
        scan = self.get(repository_id, scan_id)
        if scan.status != "COMPLETED":
            raise ServiceError("SCAN_NOT_COMPLETE", "Repository scan is not complete", 409)
        statement = (
            select(RepositoryFileRecord)
            .where(RepositoryFileRecord.scan_id == scan_id)
            .order_by(RepositoryFileRecord.path)
        )
        return list(self.session.scalars(statement))

    def language_profile(
        self,
        repository_id: UUID,
        scan_id: UUID,
    ) -> RepositoryLanguageProfileRecord:
        scan = self.get(repository_id, scan_id)
        if scan.status != "COMPLETED":
            raise ServiceError("SCAN_NOT_COMPLETE", "Repository scan is not complete", 409)
        statement = select(RepositoryLanguageProfileRecord).where(
            RepositoryLanguageProfileRecord.scan_id == scan_id
        )
        profile = self.session.scalar(statement)
        if profile is None:
            raise ServiceError(
                "LANGUAGE_PROFILE_UNAVAILABLE",
                "The scan predates language profiling; create a new scan",
                409,
            )
        profile.languages.sort(key=lambda item: item.language)
        return profile

    def symbols(self, repository_id: UUID, scan_id: UUID) -> list[SymbolRecord]:
        scan = self.get(repository_id, scan_id)
        if scan.status != "COMPLETED":
            raise ServiceError("SCAN_NOT_COMPLETE", "Repository scan is not complete", 409)
        statement = (
            select(SymbolRecord)
            .where(SymbolRecord.scan_id == scan_id)
            .order_by(SymbolRecord.qualified_name, SymbolRecord.start_line)
        )
        return list(self.session.scalars(statement))

    def relationships(
        self,
        repository_id: UUID,
        scan_id: UUID,
    ) -> list[RelationshipRecord]:
        scan = self.get(repository_id, scan_id)
        if scan.status != "COMPLETED":
            raise ServiceError("SCAN_NOT_COMPLETE", "Repository scan is not complete", 409)
        statement = (
            select(RelationshipRecord)
            .where(RelationshipRecord.scan_id == scan_id)
            .order_by(
                RelationshipRecord.relationship_type,
                RelationshipRecord.evidence_file_id,
                RelationshipRecord.evidence_start_line,
            )
        )
        return list(self.session.scalars(statement))


def execute_scan_task(
    factory: sessionmaker[Session],
    settings: Settings,
    scan_id: UUID,
    dirty_tree_policy: DirtyTreePolicy | None,
    extractor_registry: ExtractorRegistry | None = None,
) -> None:
    with factory() as session:
        ScanService(session, settings, extractor_registry).execute(scan_id, dirty_tree_policy)
