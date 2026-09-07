from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4


class ScanStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DirtyTreePolicy(StrEnum):
    REJECT = "REJECT"
    CAPTURE = "CAPTURE"


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: PurePosixPath
    language: str | None
    category: str
    content_hash: str
    size: int
    encoding: str | None = None
    is_generated: bool = False
    is_vendored: bool = False
    detection_signal: str | None = None
    secret_finding_count: int = 0


@dataclass(frozen=True, slots=True)
class ScanNotice:
    path: PurePosixPath
    reason: str
    metadata: dict[str, str | int | bool] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScanPolicy:
    allowed_roots: tuple[Path, ...]
    dirty_tree_policy: DirtyTreePolicy = DirtyTreePolicy.CAPTURE
    max_file_size_bytes: int = 2 * 1024 * 1024
    max_file_count: int = 50_000
    max_total_bytes: int = 512 * 1024 * 1024
    max_scan_seconds: int = 60
    git_timeout_seconds: int = 10
    encoding_fallback: str | None = "latin-1"
    configuration_version: str = "scanner-v1"


@dataclass(frozen=True, slots=True)
class RepositoryScan:
    repository_path: str
    commit_hash: str
    is_dirty: bool
    working_tree_fingerprint: str
    extractor_version: str
    configuration_version: str
    files: tuple[RepositoryFile, ...]
    notices: tuple[ScanNotice, ...] = ()
    id: UUID = field(default_factory=uuid4)
    status: ScanStatus = ScanStatus.COMPLETED
    scanned_at: datetime = field(default_factory=lambda: datetime.now(UTC))
