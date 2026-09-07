from uuid import UUID

import pytest
from adaptive_platform.context import (
    QueryClass,
    QueryClassificationError,
    QueryClassifier,
    QueryIntent,
    RetrievalMethod,
    ScanBinding,
    SlotName,
)

BINDING = ScanBinding(
    repository_id=UUID("00000000-0000-0000-0000-000000000001"),
    scan_id=UUID("00000000-0000-0000-0000-000000000002"),
)


@pytest.mark.parametrize(
    ("question", "query_class", "intent", "slots", "methods"),
    [
        (
            "Where is CustomerService defined?",
            QueryClass.EXACT_SYMBOL,
            QueryIntent.LOCATE_DEFINITION,
            (SlotName.UNIQUE_TARGET,),
            (RetrievalMethod.EXACT,),
        ),
        (
            "Which files import `PaymentService`, and which are tests?",
            QueryClass.STRUCTURAL,
            QueryIntent.FIND_IMPORTERS,
            (SlotName.UNIQUE_TARGET, SlotName.IMPORT_EDGES, SlotName.FILE_CATEGORIES),
            (RetrievalMethod.EXACT, RetrievalMethod.GRAPH),
        ),
        (
            "Which classes inherit from BaseRepository?",
            QueryClass.STRUCTURAL,
            QueryIntent.FIND_INHERITORS,
            (SlotName.UNIQUE_TARGET, SlotName.INHERITANCE_EDGES),
            (RetrievalMethod.EXACT, RetrievalMethod.GRAPH),
        ),
        (
            "Which routes are defined?",
            QueryClass.STRUCTURAL,
            QueryIntent.LIST_ROUTES,
            (SlotName.ROUTE_SYMBOLS,),
            (RetrievalMethod.EXACT,),
        ),
        (
            "Where is the FastAPI application created?",
            QueryClass.LOCATION,
            QueryIntent.LOCATE_FRAMEWORK_CONSTRUCTION,
            (SlotName.FRAMEWORK_CONSTRUCTION, SlotName.CONTAINING_MODULE),
            (RetrievalMethod.FULL_TEXT,),
        ),
        (
            "Which functions exist in module app.main?",
            QueryClass.GENERAL_STRUCTURAL,
            QueryIntent.FUNCTIONS_IN_MODULE,
            (SlotName.UNIQUE_MODULE, SlotName.FUNCTION_SYMBOLS),
            (RetrievalMethod.EXACT, RetrievalMethod.EXACT),
        ),
        (
            "Which concrete adapter is loaded at runtime?",
            QueryClass.UNSUPPORTED,
            QueryIntent.UNSUPPORTED_RUNTIME,
            (SlotName.RUNTIME_OBSERVATION,),
            (),
        ),
        (
            "Does the TypeScript frontend call the Python service?",
            QueryClass.UNSUPPORTED,
            QueryIntent.UNSUPPORTED_CAPABILITY,
            (SlotName.UNSUPPORTED_CAPABILITY,),
            (),
        ),
        (
            "Why did the team choose FastAPI?",
            QueryClass.UNSUPPORTED,
            QueryIntent.UNSUPPORTED_RATIONALE,
            (SlotName.RECORDED_DECISION,),
            (),
        ),
    ],
)
def test_classifier_builds_frozen_query_contracts(question, query_class, intent, slots, methods):
    contract = QueryClassifier().classify(BINDING, question)

    assert contract.query_class is query_class
    assert contract.intent is intent
    assert contract.required_slots == slots
    assert tuple(step.method for step in contract.retrieval_plan) == methods
    assert contract.supported is (query_class is not QueryClass.UNSUPPORTED)
    assert all(step.order == index for index, step in enumerate(contract.retrieval_plan, 1))


def test_import_plan_declares_alias_constraints_and_unique_target_dependency():
    contract = QueryClassifier().classify(BINDING, "Which files import PaymentService?")

    graph_step = contract.retrieval_plan[1]
    assert graph_step.depends_on_slot is SlotName.UNIQUE_TARGET
    assert ("alias_aware", "true") in graph_step.constraints


def test_route_and_framework_plans_project_to_correct_evidence_slots():
    routes = QueryClassifier().classify(BINDING, "Which routes are defined?")
    location = QueryClassifier().classify(BINDING, "Where is FastAPI created?")

    assert routes.retrieval_plan[0].constraints == (
        ("symbol_type", "ROUTE"),
        ("match_mode", "TYPE_SCAN"),
    )
    assert location.retrieval_plan[0].additional_slots == (SlotName.CONTAINING_MODULE,)


def test_classifier_is_whitespace_stable_and_scan_bound():
    classifier = QueryClassifier()
    first = classifier.classify(BINDING, "Where  is\n CustomerService defined?")
    second = classifier.classify(BINDING, "Where is CustomerService defined?")
    other_scan = classifier.classify(
        ScanBinding(BINDING.repository_id, UUID("00000000-0000-0000-0000-000000000003")),
        "Where is CustomerService defined?",
    )

    assert first.contract_hash == second.contract_hash
    assert first.canonical_question == second.canonical_question
    assert first.contract_hash != other_scan.contract_hash
    assert first.extracted_subject == "CustomerService"


@pytest.mark.parametrize("question", ["", "  ", "x" * 513, "bad\x00query"])
def test_classifier_rejects_unbounded_or_invalid_questions(question):
    with pytest.raises(QueryClassificationError):
        QueryClassifier().classify(BINDING, question)
