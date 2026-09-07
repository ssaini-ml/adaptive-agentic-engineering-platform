from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from adaptive_platform.repository.scanner import RepositoryValidationError, scan_repository


def git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "fixture_repository"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "app.py").write_text("def hello() -> str:\n    return 'hello'\n")
    (root / "README.md").write_text("# Fixture\n")
    ignored = root / ".venv"
    ignored.mkdir()
    (ignored / "ignored.py").write_text("raise RuntimeError('must never run')\n")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "fixture")
    return root


def test_scan_creates_commit_bound_inventory(repository: Path) -> None:
    scan = scan_repository(repository)

    paths = {str(record.path) for record in scan.files}
    app = next(record for record in scan.files if str(record.path) == "app.py")

    assert scan.commit_hash
    assert scan.is_dirty is False
    assert scan.extractor_version == "inventory-v2"
    assert paths == {"README.md", "app.py"}
    assert app.language == "Python"
    assert app.category == "SOURCE"
    assert len(scan.working_tree_fingerprint) == 64
    assert len(app.content_hash) == 64


def test_scan_records_dirty_worktree(repository: Path) -> None:
    (repository / "app.py").write_text("value = 2\n")

    assert scan_repository(repository).is_dirty is True


def test_scan_rejects_non_git_directory(tmp_path: Path) -> None:
    with pytest.raises(RepositoryValidationError, match="Git worktree"):
        scan_repository(tmp_path)
