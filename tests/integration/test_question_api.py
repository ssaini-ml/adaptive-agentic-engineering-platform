from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from adaptive_platform.app import create_app
from adaptive_platform.config import Settings
from adaptive_platform.database import Base, create_database_engine
from fastapi.testclient import TestClient


def git(root: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(root), *arguments], check=True, capture_output=True)


@pytest.fixture
def question_client(tmp_path: Path):
    root = tmp_path / "grounded-repository"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.email", "fixture@example.test")
    git(root, "config", "user.name", "Fixture")
    (root / "service.py").write_text("class CustomerService:\n    pass\n")
    (root / "main.py").write_text(
        "from fastapi import FastAPI\n"
        "from service import CustomerService\n\n"
        "app = FastAPI()\n\n"
        "@app.get('/customers')\n"
        "def customers() -> list[str]:\n"
        "    return []\n"
    )
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_service.py").write_text(
        "from service import CustomerService\n\n"
        "def test_service() -> None:\n"
        "    assert CustomerService()\n"
    )
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "question fixture")

    settings = Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'questions.db'}",
        allowed_repository_roots=str(tmp_path),
    )
    engine = create_database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    app = create_app(settings, engine=engine)
    with TestClient(app) as client:
        repository_id = client.post("/repositories", json={"path": str(root)}).json()["id"]
        scan_id = client.post(f"/repositories/{repository_id}/scans", json={}).json()["id"]
        yield client, repository_id, scan_id


def ask(client: TestClient, repository_id: str, scan_id: str, question: str):
    return client.post(
        f"/repositories/{repository_id}/scans/{scan_id}/questions",
        json={"question": question},
    )


@pytest.mark.parametrize(
    ("question", "intent", "resource"),
    [
        ("Where is CustomerService defined?", "LOCATE_DEFINITION", "service.py"),
        ("Which files import CustomerService?", "FIND_IMPORTERS", "main.py"),
        ("Which routes are defined?", "LIST_ROUTES", "main.py"),
        (
            "Where is the FastAPI application created?",
            "LOCATE_FRAMEWORK_CONSTRUCTION",
            "main.py",
        ),
    ],
)
def test_supported_questions_return_validated_cited_answers(
    question_client, question: str, intent: str, resource: str
) -> None:
    client, repository_id, scan_id = question_client

    response = ask(client, repository_id, scan_id, question)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ANSWERED", payload
    assert payload["query_intent"] == intent
    assert payload["confidence"] == "DETERMINISTIC"
    assert payload["claims"]
    assert all(claim["verdict"] == "SUPPORTED" for claim in payload["claims"])
    assert resource in {item["path"] for claim in payload["claims"] for item in claim["evidence"]}
    trace = client.get(payload["trace_url"])
    assert trace.status_code == 200
    event_types = {event["event_type"] for event in trace.json()}
    assert {"task_classified", "context_assembled", "coverage_passed", "claims_validated"} <= event_types


def test_unsupported_question_abstains_before_model_and_is_cached(question_client) -> None:
    client, repository_id, scan_id = question_client
    question = "Why did the team choose Python?"

    first = ask(client, repository_id, scan_id, question)
    repeated = ask(client, repository_id, scan_id, question)

    assert first.status_code == 200
    assert first.json() == repeated.json()
    assert first.json()["status"] == "ABSTAINED"
    assert first.json()["answer"] is None
    assert first.json()["confidence"] == "NONE"
    assert first.json()["claims"] == []
    trace = client.get(first.json()["trace_url"]).json()
    failed = next(event for event in trace if event["event_type"] == "coverage_failed")
    assert failed["metadata"]["model_call_count"] == 0
    assert any(event["event_type"] == "cache_hit" for event in trace)


def test_feedback_appends_correction_without_mutating_answer(question_client) -> None:
    client, repository_id, scan_id = question_client
    response = ask(client, repository_id, scan_id, "Where is CustomerService defined?")
    payload = response.json()
    trace = client.get(payload["trace_url"]).json()
    corrected = next(event for event in trace if event["event_type"] == "claims_validated")

    feedback = client.post(
        f"/tasks/{payload['task_id']}/feedback",
        json={
            "summary": "A reviewer requested a wording correction.",
            "disposition": "CORRECTION_REQUESTED",
            "author_role": "HUMAN_REVIEWER",
            "corrected_event_id": corrected["id"],
        },
    )

    assert feedback.status_code == 200
    assert feedback.json()["actor_type"] == "HUMAN"
    assert feedback.json()["correction_of"] == corrected["id"]
    assert client.get(f"/tasks/{payload['task_id']}").json() == payload


def test_agent_profiles_are_exposed_but_disabled(question_client) -> None:
    client, _, _ = question_client
    profiles = client.get("/agent-profiles")

    assert profiles.status_code == 200
    assert {item["role"] for item in profiles.json()} == {
        "REPOSITORY_ANALYST",
        "EVIDENCE_REVIEWER",
    }
    assert all(item["status"] == "DISABLED" for item in profiles.json())
    assert all(not item["source_write_access"] for item in profiles.json())
    assert all(not item["network_access"] for item in profiles.json())
    assert all(not item["external_side_effect_access"] for item in profiles.json())
    assert all(not item["approval_authority"] for item in profiles.json())
    assert all(item["required_payload_keys"] for item in profiles.json())


def test_review_surface_lists_abstentions_and_unresolved_references(question_client) -> None:
    client, repository_id, scan_id = question_client
    response = ask(client, repository_id, scan_id, "Why did the team choose Python?")

    review = client.get("/review")

    assert response.status_code == 200
    assert review.status_code == 200
    assert {item["task_id"] for item in review.json()["abstentions"]} == {
        response.json()["task_id"]
    }
    assert review.json()["candidate_rules_status"] == "DISABLED_UNTIL_V0.4"


def test_visual_review_console_is_local_and_no_store(question_client) -> None:
    client, _, _ = question_client

    response = client.get("/review/ui")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert "Evidence review" in response.text
    assert "fetch('/review'" in response.text
