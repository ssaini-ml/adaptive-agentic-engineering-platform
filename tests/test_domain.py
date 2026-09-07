from dataclasses import FrozenInstanceError
from pathlib import PurePosixPath

import pytest
from adaptive_platform.domain.models import RepositoryFile


def test_repository_file_is_immutable() -> None:
    record = RepositoryFile(
        path=PurePosixPath("app/main.py"),
        language="Python",
        category="source",
        content_hash="a" * 64,
        size=42,
    )

    with pytest.raises(FrozenInstanceError):
        record.size = 100  # type: ignore[misc]
