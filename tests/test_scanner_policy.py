from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from adaptive_platform.domain.models import DirtyTreePolicy, ScanPolicy
from adaptive_platform.repository.scanner import RepositoryValidationError, scan_repository


def git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)


def create_repository(root: Path) -> Path:
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "main.py").write_text("value = 1\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "fixture")
    return root


def test_file_count_limit_fails_loudly(tmp_path: Path) -> None:
    root = create_repository(tmp_path / "repository")
    (root / "second.py").write_text("value = 2\n")
    policy = ScanPolicy(allowed_roots=(tmp_path,), max_file_count=1)

    with pytest.raises(RepositoryValidationError) as captured:
        scan_repository(root, policy)

    assert captured.value.code == "SCAN_LIMIT_EXCEEDED"


def test_excluded_binary_files_still_count_toward_limits(tmp_path: Path) -> None:
    root = create_repository(tmp_path / "repository")
    (root / "binary.bin").write_bytes(b"\x00binary")
    policy = ScanPolicy(allowed_roots=(tmp_path,), max_file_count=1)

    with pytest.raises(RepositoryValidationError) as captured:
        scan_repository(root, policy)

    assert captured.value.code == "SCAN_LIMIT_EXCEEDED"


def test_scan_timeout_fails_loudly(tmp_path: Path) -> None:
    root = create_repository(tmp_path / "repository")
    policy = ScanPolicy(allowed_roots=(tmp_path,), max_scan_seconds=0)

    with pytest.raises(RepositoryValidationError) as captured:
        scan_repository(root, policy)

    assert captured.value.code == "SCAN_TIMEOUT"


def test_dirty_tree_capture_is_fingerprinted(tmp_path: Path) -> None:
    root = create_repository(tmp_path / "repository")
    (root / "main.py").write_text("value = 2\n")
    policy = ScanPolicy(
        allowed_roots=(tmp_path,),
        dirty_tree_policy=DirtyTreePolicy.CAPTURE,
    )

    scan = scan_repository(root, policy)

    assert scan.is_dirty is True
    assert len(scan.working_tree_fingerprint) == 64
