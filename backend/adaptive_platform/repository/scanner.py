from __future__ import annotations

import hashlib
import re
import subprocess
import time
from pathlib import Path, PurePosixPath

from adaptive_platform.domain.models import (
    DirtyTreePolicy,
    RepositoryFile,
    RepositoryScan,
    ScanNotice,
    ScanPolicy,
)
from adaptive_platform.languages import detect_language, is_generated_path, is_vendored_path

EXTRACTOR_VERSION = "inventory-v2"

IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "venv",
    }
)

DEPENDENCY_FILES = frozenset(
    {
        "package-lock.json",
        "package.json",
        "Cargo.lock",
        "Cargo.toml",
        "go.mod",
        "go.sum",
        "poetry.lock",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "uv.lock",
    }
)

DOCUMENTATION_SUFFIXES = frozenset({".md", ".mdx", ".rst", ".txt"})
CONFIGURATION_SUFFIXES = frozenset({".ini", ".json", ".toml", ".yaml", ".yml"})
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(
        r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"\n]{8,}['\"]"
    ),
)


class RepositoryValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ScanLimitExceeded(RepositoryValidationError):
    pass


def _git(root: Path, timeout: int, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.stdout.strip()


def _is_allowed(path: Path, allowed_roots: tuple[Path, ...]) -> bool:
    for configured_root in allowed_roots:
        allowed = configured_root.expanduser().resolve(strict=False)
        if path == allowed or path.is_relative_to(allowed):
            return True
    return False


def validate_repository(path: str | Path, policy: ScanPolicy) -> Path:
    try:
        root = Path(path).expanduser().resolve(strict=True)
    except OSError as exc:
        raise RepositoryValidationError("REPOSITORY_NOT_FOUND", "Repository path does not exist") from exc
    if not root.is_dir():
        raise RepositoryValidationError("REPOSITORY_NOT_READABLE", "Repository path is not a directory")
    if not _is_allowed(root, policy.allowed_roots):
        raise RepositoryValidationError("PATH_NOT_ALLOWED", "Repository path is outside allowed roots")
    try:
        worktree = _git(root, policy.git_timeout_seconds, "rev-parse", "--show-toplevel")
        commit = _git(root, policy.git_timeout_seconds, "rev-parse", "--verify", "HEAD")
    except subprocess.TimeoutExpired as exc:
        raise RepositoryValidationError("REPOSITORY_GIT_TIMEOUT", "Git inspection timed out") from exc
    except (subprocess.CalledProcessError, OSError) as exc:
        raise RepositoryValidationError(
            "REPOSITORY_NOT_GIT",
            "Path is not a readable Git worktree with a valid HEAD",
        ) from exc
    if Path(worktree).resolve() != root:
        raise RepositoryValidationError(
            "REPOSITORY_ROOT_REQUIRED",
            "Path must be the root of the Git worktree",
        )
    if len(commit) not in {40, 64}:
        raise RepositoryValidationError("REPOSITORY_HAS_NO_HEAD", "Repository HEAD is invalid")
    return root


def repository_default_branch(root: Path, policy: ScanPolicy) -> str | None:
    try:
        return _git(root, policy.git_timeout_seconds, "symbolic-ref", "--short", "HEAD") or None
    except (subprocess.SubprocessError, OSError):
        return None


def _category(relative_path: PurePosixPath, language: str | None) -> str:
    name = relative_path.name
    lowered_parts = {part.lower() for part in relative_path.parts}
    if name in DEPENDENCY_FILES:
        return "DEPENDENCY"
    if "test" in name.lower() or "tests" in lowered_parts:
        return "TEST"
    if language is not None:
        return "SOURCE"
    if relative_path.suffix.lower() in DOCUMENTATION_SUFFIXES:
        return "DOCUMENTATION"
    if relative_path.suffix.lower() in CONFIGURATION_SUFFIXES or name.startswith("Dockerfile"):
        return "CONFIGURATION"
    return "OTHER"


def _looks_binary(content: bytes) -> bool:
    return b"\x00" in content[:8192]


def _decode(content: bytes, fallback: str | None) -> tuple[str | None, str | None]:
    try:
        return content.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        if fallback is None:
            return None, None
        try:
            return content.decode(fallback), fallback
        except (UnicodeDecodeError, LookupError):
            return None, None


def _secret_count(text: str | None) -> int:
    if text is None:
        return 0
    return sum(len(pattern.findall(text)) for pattern in SECRET_PATTERNS)


def _discover_files(
    root: Path,
    policy: ScanPolicy,
) -> tuple[tuple[RepositoryFile, ...], tuple[ScanNotice, ...]]:
    records: list[RepositoryFile] = []
    notices: list[ScanNotice] = []
    total_bytes = 0
    encountered_files = 0
    deadline = time.monotonic() + policy.max_scan_seconds

    for candidate in sorted(root.rglob("*")):
        if time.monotonic() > deadline:
            raise ScanLimitExceeded("SCAN_TIMEOUT", "Repository scan time limit exceeded")
        relative = candidate.relative_to(root)
        relative_posix = PurePosixPath(relative.as_posix())
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        if candidate.is_symlink():
            notices.append(ScanNotice(relative_posix, "SYMLINK_EXCLUDED"))
            continue
        if not candidate.is_file():
            continue

        encountered_files += 1
        size = candidate.stat().st_size
        if size > policy.max_file_size_bytes:
            notices.append(
                ScanNotice(
                    relative_posix,
                    "FILE_SIZE_EXCLUDED",
                    {"size": size, "limit": policy.max_file_size_bytes},
                )
            )
            continue
        if encountered_files > policy.max_file_count:
            raise ScanLimitExceeded("SCAN_LIMIT_EXCEEDED", "Repository file-count limit exceeded")
        if total_bytes + size > policy.max_total_bytes:
            raise ScanLimitExceeded("SCAN_LIMIT_EXCEEDED", "Repository total-byte limit exceeded")

        total_bytes += size
        content = candidate.read_bytes()
        if _looks_binary(content):
            notices.append(ScanNotice(relative_posix, "BINARY_EXCLUDED", {"size": size}))
            continue
        text, encoding = _decode(content, policy.encoding_fallback)
        if text is None:
            notices.append(ScanNotice(relative_posix, "ENCODING_EXCLUDED", {"size": size}))
            continue

        detection = detect_language(relative_posix, text)
        records.append(
            RepositoryFile(
                path=relative_posix,
                language=detection.language,
                category=_category(relative_posix, detection.language),
                content_hash=hashlib.sha256(content).hexdigest(),
                size=size,
                encoding=encoding,
                is_generated=is_generated_path(relative_posix),
                is_vendored=is_vendored_path(relative_posix),
                detection_signal=detection.signal,
                secret_finding_count=_secret_count(text),
            )
        )
    return tuple(records), tuple(notices)


def _fingerprint(commit_hash: str, files: tuple[RepositoryFile, ...]) -> str:
    digest = hashlib.sha256(commit_hash.encode())
    for record in files:
        digest.update(record.path.as_posix().encode())
        digest.update(record.content_hash.encode())
    return digest.hexdigest()


def scan_repository(path: str | Path, policy: ScanPolicy | None = None) -> RepositoryScan:
    """Create an immutable inventory snapshot without executing repository code."""
    selected_policy = policy or ScanPolicy(allowed_roots=(Path(path).expanduser().parent,))
    root = validate_repository(path, selected_policy)
    commit_hash = _git(root, selected_policy.git_timeout_seconds, "rev-parse", "HEAD")
    is_dirty = bool(
        _git(
            root,
            selected_policy.git_timeout_seconds,
            "status",
            "--porcelain",
            "--untracked-files=normal",
        )
    )
    if is_dirty and selected_policy.dirty_tree_policy is DirtyTreePolicy.REJECT:
        raise RepositoryValidationError("DIRTY_TREE_REJECTED", "Repository working tree is dirty")

    files, notices = _discover_files(root, selected_policy)
    return RepositoryScan(
        repository_path=str(root),
        commit_hash=commit_hash,
        is_dirty=is_dirty,
        working_tree_fingerprint=_fingerprint(commit_hash, files),
        extractor_version=EXTRACTOR_VERSION,
        configuration_version=selected_policy.configuration_version,
        files=files,
        notices=notices,
    )
