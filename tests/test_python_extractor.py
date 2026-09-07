from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from adaptive_platform.evaluation.loader import load_json
from adaptive_platform.evaluation.runner import evaluate_predictions
from adaptive_platform.extraction import (
    ExtractionDocument,
    ExtractionRequest,
    ExtractorStatus,
    PythonAstExtractor,
    RelationshipType,
    ResolutionStatus,
    SourceSnapshotError,
    SymbolType,
    load_extraction_documents,
)
from adaptive_platform.extraction.evaluation import extract_fixture

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("fixture_id", ["fx-small", "fx-fastapi", "fx-messy"])
def test_python_extractor_matches_structural_golden_labels(fixture_id: str) -> None:
    fixture = PROJECT_ROOT / "evaluation" / "fixtures" / fixture_id
    prediction = extract_fixture(fixture / "repository")
    metrics = evaluate_predictions(load_json(fixture / "golden.json"), prediction)

    assert metrics["symbols"]["precision"] == 1.0
    assert metrics["symbols"]["recall"] == 1.0
    assert metrics["imports"]["precision"] == 1.0
    assert metrics["imports"]["recall"] == 1.0
    assert metrics["routes"]["precision"] == 1.0
    assert metrics["routes"]["recall"] == 1.0


def test_python_extractor_preserves_metadata_and_uncertainty() -> None:
    fixture = PROJECT_ROOT / "evaluation" / "fixtures" / "fx-messy" / "repository"
    prediction = extract_fixture(fixture)

    assert prediction["extractor"]["status"] == ExtractorStatus.SUPPORTED
    assert prediction["unresolved"] == [
        {
            "source_unit": "package.dynamic",
            "expression": "importlib.import_module(module_name)",
            "reason": "dynamic_import_target",
            "path": "package/dynamic.py",
            "line": 5,
        }
    ]

    source = """from external import Base as Parent

class Service(Parent):
    \"\"\"Service documentation.\"\"\"

    @staticmethod
    def execute(value: str = \"x\") -> str:
        return value
"""
    document = ExtractionDocument(
        file_id=uuid4(),
        path=Path("service.py"),
        language="Python",
        content_hash=hashlib.sha256(source.encode()).hexdigest(),
        content=source,
    )
    result = PythonAstExtractor().extract(
        ExtractionRequest(repository_id=uuid4(), scan_id=uuid4(), documents=(document,))
    )
    service = next(item for item in result.symbols if item.symbol_type is SymbolType.CLASS)
    method = next(item for item in result.symbols if item.symbol_type is SymbolType.METHOD)
    inheritance = next(
        item for item in result.relationships if item.relationship_type is RelationshipType.INHERITS
    )

    assert service.docstring == "Service documentation."
    assert service.extension_metadata == {"decorators": [], "bases": ["Parent"]}
    assert method.signature == "(value: str='x') -> str"
    assert method.extension_metadata == {"decorators": ["staticmethod"], "is_async": False}
    assert inheritance.resolution_status is ResolutionStatus.UNRESOLVED
    assert inheritance.unresolved_target == "external.Base"


def test_syntax_failure_is_partial_and_diagnostic() -> None:
    content = "def broken(:\n"
    document = ExtractionDocument(
        file_id=uuid4(),
        path=Path("broken.py"),
        language="Python",
        content_hash=hashlib.sha256(content.encode()).hexdigest(),
        content=content,
    )

    result = PythonAstExtractor().extract(
        ExtractionRequest(repository_id=uuid4(), scan_id=uuid4(), documents=(document,))
    )

    assert result.status is ExtractorStatus.PARTIAL
    assert result.symbols == ()
    assert result.relationships == ()
    assert result.diagnostics == ("broken.py:1:syntax_error",)


def test_source_loader_rejects_content_changed_after_inventory(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text("value = 1\n")
    inventory = SimpleNamespace(
        id=uuid4(),
        path="module.py",
        language="Python",
        category="SOURCE",
        content_hash=hashlib.sha256(source.read_bytes()).hexdigest(),
        encoding="utf-8",
        is_generated=False,
        is_vendored=False,
    )
    source.write_text("value = 2\n")

    with pytest.raises(SourceSnapshotError) as error:
        load_extraction_documents(tmp_path, [inventory], "Python")

    assert error.value.code == "SOURCE_CHANGED_DURING_EXTRACTION"
