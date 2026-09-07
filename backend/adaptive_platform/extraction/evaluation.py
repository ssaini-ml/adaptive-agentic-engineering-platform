from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from adaptive_platform.evaluation.loader import discover_fixture_dirs, load_json, validate_fixture
from adaptive_platform.evaluation.runner import evaluate_predictions
from adaptive_platform.extraction.models import RelationshipType, SymbolType
from adaptive_platform.extraction.protocol import ExtractionDocument, ExtractionRequest
from adaptive_platform.extraction.python_ast import PythonAstExtractor
from adaptive_platform.traces import ActorType, JsonlTraceRecorder, TraceCategory, TraceEvent


def _documents(repository: Path) -> tuple[ExtractionDocument, ...]:
    documents: list[ExtractionDocument] = []
    for source in sorted(repository.rglob("*.py")):
        relative = source.relative_to(repository)
        content = source.read_bytes()
        documents.append(
            ExtractionDocument(
                file_id=uuid5(NAMESPACE_URL, relative.as_posix()),
                path=relative,
                language="Python",
                content_hash=hashlib.sha256(content).hexdigest(),
                content=content.decode("utf-8"),
            )
        )
    return tuple(documents)


def extract_fixture(repository: Path) -> dict[str, Any]:
    documents = _documents(repository)
    path_by_id = {document.file_id: document.path.as_posix() for document in documents}
    result = PythonAstExtractor().extract(
        ExtractionRequest(
            repository_id=uuid5(NAMESPACE_URL, repository.as_posix()),
            scan_id=uuid5(NAMESPACE_URL, f"scan:{repository.as_posix()}"),
            documents=documents,
        )
    )
    symbols = [
        {
            "qualified_name": item.qualified_name,
            "type": item.symbol_type.value,
            "path": path_by_id[item.file_id],
            "start_line": item.start_line,
            "end_line": item.end_line,
        }
        for item in result.symbols
    ]
    imports: list[dict[str, Any]] = []
    exposes: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    inherits: list[dict[str, Any]] = []
    for item in result.relationships:
        path = path_by_id[item.evidence_file_id]
        target = item.target_qualified_name or item.unresolved_target
        metadata = item.extension_metadata or {}
        if item.relationship_type is RelationshipType.IMPORTS:
            imports.append(
                {
                    "source_unit": item.source_qualified_name,
                    "imported_name": target,
                    "alias": metadata.get("alias"),
                    "path": path,
                    "line": item.evidence_start_line,
                    "type_checking": metadata.get("type_checking", False),
                }
            )
        elif item.relationship_type is RelationshipType.EXPOSES:
            exposes.append(
                {
                    "source_unit": item.source_qualified_name,
                    "target": target,
                    "path": path,
                    "line": item.evidence_start_line,
                }
            )
        elif item.relationship_type is RelationshipType.REFERENCES and item.unresolved_target:
            unresolved.append(
                {
                    "source_unit": item.source_qualified_name,
                    "expression": item.unresolved_target,
                    "reason": item.resolution_reason,
                    "path": path,
                    "line": item.evidence_start_line,
                }
            )
        elif item.relationship_type is RelationshipType.INHERITS:
            inherits.append(
                {
                    "source": item.source_qualified_name,
                    "target": target,
                    "path": path,
                    "line": item.evidence_start_line,
                }
            )
    routes = [
        {
            "method": item.extension_metadata["method"],
            "path": item.extension_metadata["path"],
            "handler": item.extension_metadata["handler"],
            "source_path": path_by_id[item.file_id],
            "decorator_line": item.extension_metadata["decorator_line"],
            "handler_line": item.extension_metadata["handler_line"],
        }
        for item in result.symbols
        if item.symbol_type is SymbolType.ROUTE and item.extension_metadata is not None
    ]
    return {
        "extractor": {"name": "python-ast", "version": "1.0.0", "status": result.status},
        "symbols": symbols,
        "imports": imports,
        "routes": routes,
        "exposes": exposes,
        "unresolved": unresolved,
        "inherits": inherits,
        "diagnostics": list(result.diagnostics),
    }


def build_report(evaluation_root: Path, predictions_dir: Path) -> dict[str, Any]:
    fixture_results: dict[str, Any] = {}
    gates: list[dict[str, Any]] = []
    for fixture_dir in discover_fixture_dirs(evaluation_root / "fixtures"):
        manifest = load_json(fixture_dir / "manifest.json")
        if manifest["evaluator_profile"] != "structural-v1":
            continue
        validate_fixture(fixture_dir)
        prediction = extract_fixture(fixture_dir / manifest.get("source_root", "repository"))
        predictions_dir.mkdir(parents=True, exist_ok=True)
        (predictions_dir / f"{fixture_dir.name}.json").write_text(
            json.dumps(prediction, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        metrics = evaluate_predictions(load_json(fixture_dir / "golden.json"), prediction)
        fixture_results[fixture_dir.name] = metrics

        for metric in ("precision", "recall"):
            value = metrics["symbols"][metric]
            gates.append(
                {
                    "gate": f"{fixture_dir.name}.symbols.{metric}",
                    "value": value,
                    "threshold": 0.95,
                    "status": "PASS" if value >= 0.95 else "FAIL",
                }
            )
        import_recall = metrics["imports"]["recall"]
        gates.append(
            {
                "gate": f"{fixture_dir.name}.imports.recall",
                "value": import_recall,
                "threshold": 0.90,
                "status": "PASS" if import_recall >= 0.90 else "FAIL",
            }
        )
        if fixture_dir.name == "fx-fastapi":
            for metric in ("precision", "recall"):
                value = metrics["routes"][metric]
                gates.append(
                    {
                        "gate": f"fx-fastapi.routes.{metric}",
                        "value": value,
                        "threshold": 0.95,
                        "status": "PASS" if value >= 0.95 else "FAIL",
                    }
                )
    review = load_json(evaluation_root / "review.json")
    return {
        "schema_version": "1.0.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "milestone": "M2B_PYTHON_EVIDENCE_EXTRACTION",
        "technical_status": "PASS" if all(item["status"] == "PASS" for item in gates) else "FAIL",
        "human_label_review": review["status"],
        "extractor": {"language": "Python", "name": "python-ast", "version": "1.0.0"},
        "fixtures": fixture_results,
        "gates": gates,
        "holdout": {"status": "POLICY_DEFINED_SELECTION_PENDING"},
    }


def main() -> int:
    project_root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="Run Milestone 2B Python structural evaluation")
    parser.add_argument("--evaluation-root", type=Path, default=project_root / "evaluation")
    parser.add_argument(
        "--predictions-dir", type=Path, default=project_root / "evaluation" / "predictions"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone2b.json",
    )
    parser.add_argument(
        "--trace-output",
        type=Path,
        default=project_root / "evaluation" / "baselines" / "milestone2b.trace.jsonl",
    )
    args = parser.parse_args()
    report = build_report(args.evaluation_root, args.predictions_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    recorder = JsonlTraceRecorder(args.trace_output)
    correlation_id = str(uuid4())
    task_id = f"evaluation:milestone2b:{report['generated_at']}"
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.EXECUTION,
            event_type="python_extraction_evaluation_started",
            actor_type=ActorType.SYSTEM,
            summary="Started Milestone 2B Python structural evaluation.",
            input_refs=("evaluation/fixtures",),
            metadata={"extractor": report["extractor"]},
        )
    )
    recorder.append(
        TraceEvent(
            task_id=task_id,
            correlation_id=correlation_id,
            category=TraceCategory.VERIFICATION,
            event_type="python_extraction_gates_evaluated",
            actor_type=ActorType.SYSTEM,
            summary="Evaluated Python symbols, imports and routes against golden labels.",
            output_refs=("evaluation/baselines/milestone2b.json", "evaluation/predictions"),
            metadata={"technical_status": report["technical_status"], "gates": report["gates"]},
        )
    )
    print(
        f"evaluated {len(report['fixtures'])} structural fixtures; "
        f"technical_status={report['technical_status']}; "
        f"human_review={report['human_label_review']}"
    )
    return 0 if report["technical_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
