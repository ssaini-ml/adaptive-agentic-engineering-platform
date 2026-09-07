from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from adaptive_platform.domain.models import DirtyTreePolicy, ScanPolicy


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AAEP_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://adaptive:adaptive@localhost:5432/adaptive"
    allowed_repository_roots: str = "."
    dirty_tree_policy: DirtyTreePolicy = DirtyTreePolicy.CAPTURE
    max_file_size_bytes: int = 2 * 1024 * 1024
    max_file_count: int = 50_000
    max_total_bytes: int = 512 * 1024 * 1024
    max_scan_seconds: int = 60
    git_timeout_seconds: int = 10
    encoding_fallback: str | None = "latin-1"
    scanner_configuration_version: str = "scanner-v1"
    language_profiler_configuration_version: str = "language-profiler-v1"
    polyglot_threshold_percent: float = 5.0

    def scan_policy(self) -> ScanPolicy:
        roots = tuple(
            Path(value).expanduser().resolve(strict=False)
            for value in self.allowed_repository_roots.split(os.pathsep)
            if value.strip()
        )
        if not roots:
            raise ValueError("At least one allowed repository root is required")
        return ScanPolicy(
            allowed_roots=roots,
            dirty_tree_policy=self.dirty_tree_policy,
            max_file_size_bytes=self.max_file_size_bytes,
            max_file_count=self.max_file_count,
            max_total_bytes=self.max_total_bytes,
            max_scan_seconds=self.max_scan_seconds,
            git_timeout_seconds=self.git_timeout_seconds,
            encoding_fallback=self.encoding_fallback,
            configuration_version=self.scanner_configuration_version,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
