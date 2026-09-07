from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict

from adaptive_platform.context.models import (
    QueryClass,
    QueryContract,
    QueryIntent,
    RetrievalMethod,
    RetrievalStep,
    ScanBinding,
    SlotName,
)

CLASSIFIER_VERSION = "query-classifier-v1"
QUERY_CONTRACT_VERSION = "query-contract-v1"
MAX_QUESTION_CHARACTERS = 512

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_.]*"


class QueryClassificationError(ValueError):
    """The supplied question cannot form a bounded query contract."""


class QueryClassifier:
    """Rule-based V0.1 classifier. It never invokes a model."""

    def classify(self, binding: ScanBinding, question: str) -> QueryContract:
        canonical = _canonical_question(question)
        lowered = canonical.casefold()
        subject = _extract_subject(canonical)

        if re.search(r"\bwhy\b|\brationale\b|\bdecision\b|\bhistory\b", lowered):
            query_class = QueryClass.UNSUPPORTED
            intent = QueryIntent.UNSUPPORTED_RATIONALE
            slots = (SlotName.RECORDED_DECISION,)
            plan: tuple[RetrievalStep, ...] = ()
            reason = "Rationale and historical intent are outside V0.1 recorded evidence."
        elif re.search(r"\bruntime\b|\bloaded\s+at\s+run", lowered):
            query_class = QueryClass.UNSUPPORTED
            intent = QueryIntent.UNSUPPORTED_RUNTIME
            slots = (SlotName.RUNTIME_OBSERVATION,)
            plan = ()
            reason = "Runtime behavior is outside static V0.1 repository evidence."
        elif re.search(r"\bcall(?:s|ed|ing)?\b", lowered):
            query_class = QueryClass.UNSUPPORTED
            intent = QueryIntent.UNSUPPORTED_CAPABILITY
            slots = (SlotName.UNSUPPORTED_CAPABILITY,)
            plan = ()
            reason = "Call-edge and cross-language behavior require a later capability."
        elif re.search(r"\b(routes?|endpoints?)\b", lowered):
            query_class = QueryClass.STRUCTURAL
            intent = QueryIntent.LIST_ROUTES
            slots = (SlotName.ROUTE_SYMBOLS,)
            plan = (
                RetrievalStep(
                    order=1,
                    method=RetrievalMethod.EXACT,
                    fills_slot=SlotName.ROUTE_SYMBOLS,
                    query="ROUTE",
                    limit=100,
                    constraints=(("symbol_type", "ROUTE"), ("match_mode", "TYPE_SCAN")),
                    reason="Select recorded ROUTE symbols from the scan-bound symbol index.",
                ),
            )
            reason = "Route wording selects recorded route symbols, not graph edges."
        elif re.search(r"\b(imports?|imported by|references?|referenced by)\b", lowered):
            query_class = QueryClass.STRUCTURAL
            intent = QueryIntent.FIND_IMPORTERS
            slots = (SlotName.UNIQUE_TARGET, SlotName.IMPORT_EDGES)
            if re.search(r"\btests?\b", lowered):
                slots += (SlotName.FILE_CATEGORIES,)
            plan = (
                _exact_step(1, subject or canonical),
                _graph_step(
                    2,
                    SlotName.IMPORT_EDGES,
                    subject or canonical,
                    ("IMPORTS", "EXPOSES"),
                    depends_on=SlotName.UNIQUE_TARGET,
                    constraints=(("alias_aware", "true"), ("include_type_checking", "true")),
                ),
            )
            reason = "Importer/reference wording selects exact identity then incoming graph evidence."
        elif re.search(r"\b(inherits?|subclasses?|extends?)\b", lowered):
            query_class = QueryClass.STRUCTURAL
            intent = QueryIntent.FIND_INHERITORS
            slots = (SlotName.UNIQUE_TARGET, SlotName.INHERITANCE_EDGES)
            plan = (
                _exact_step(1, subject or canonical),
                _graph_step(
                    2,
                    SlotName.INHERITANCE_EDGES,
                    subject or canonical,
                    ("INHERITS",),
                    depends_on=SlotName.UNIQUE_TARGET,
                    constraints=(("alias_aware", "true"),),
                ),
            )
            reason = "Inheritance wording selects exact identity then inheritance graph evidence."
        elif re.search(r"\bwhere\b.*\b(defined|declared)\b", lowered):
            query_class = QueryClass.EXACT_SYMBOL
            intent = QueryIntent.LOCATE_DEFINITION
            slots = (SlotName.UNIQUE_TARGET,)
            plan = (_exact_step(1, subject or canonical),)
            reason = "Definition wording selects exact symbol retrieval."
        elif re.search(r"\bwhere\b.*\b(created|implemented|located|configured)\b", lowered):
            query_class = QueryClass.LOCATION
            intent = QueryIntent.LOCATE_FRAMEWORK_CONSTRUCTION
            slots = (SlotName.FRAMEWORK_CONSTRUCTION, SlotName.CONTAINING_MODULE)
            plan = (
                _full_text_step(
                    1,
                    SlotName.FRAMEWORK_CONSTRUCTION,
                    subject or canonical,
                    additional_slots=(SlotName.CONTAINING_MODULE,),
                ),
            )
            reason = "Implementation-location wording selects exact then lexical evidence."
        elif re.search(r"\bfunctions?\b.*\bmodule\b", lowered):
            query_class = QueryClass.GENERAL_STRUCTURAL
            intent = QueryIntent.FUNCTIONS_IN_MODULE
            subject = _module_subject(canonical)
            slots = (SlotName.UNIQUE_MODULE, SlotName.FUNCTION_SYMBOLS)
            plan = (
                RetrievalStep(
                    order=1,
                    method=RetrievalMethod.EXACT,
                    fills_slot=SlotName.UNIQUE_MODULE,
                    query=subject or canonical,
                    limit=20,
                    constraints=(("symbol_type", "MODULE"),),
                    reason="Resolve one exact containing module.",
                ),
                RetrievalStep(
                    order=2,
                    method=RetrievalMethod.EXACT,
                    fills_slot=SlotName.FUNCTION_SYMBOLS,
                    query=subject or canonical,
                    limit=100,
                    depends_on_slot=SlotName.UNIQUE_MODULE,
                    constraints=(("symbol_type", "FUNCTION"), ("parent", "UNIQUE_MODULE")),
                    reason="Select direct FUNCTION children of the resolved module.",
                ),
            )
            reason = "Module/function wording selects exact parent and child symbol evidence."
        elif re.search(r"\b(classes|modules|symbols)\b", lowered):
            query_class = QueryClass.GENERAL_STRUCTURAL
            intent = QueryIntent.LIST_SYMBOLS
            slots = (SlotName.FULL_TEXT_EVIDENCE,)
            plan = (_full_text_step(1, SlotName.FULL_TEXT_EVIDENCE, canonical),)
            reason = "General inventory wording selects bounded lexical repository evidence."
        else:
            query_class = QueryClass.UNSUPPORTED
            intent = QueryIntent.UNSUPPORTED_UNKNOWN
            slots = (SlotName.UNSUPPORTED_CAPABILITY,)
            plan = ()
            reason = "Question does not match a supported deterministic V0.1 query class."

        supported = query_class is not QueryClass.UNSUPPORTED
        values = {
            "binding": {
                "repository_id": str(binding.repository_id),
                "scan_id": str(binding.scan_id),
            },
            "canonical_question": canonical,
            "query_class": query_class.value,
            "intent": intent.value,
            "extracted_subject": subject,
            "required_slots": [slot.value for slot in slots],
            "retrieval_plan": [_canonical_dataclass(step) for step in plan],
            "supported": supported,
            "classifier_version": CLASSIFIER_VERSION,
            "contract_version": QUERY_CONTRACT_VERSION,
        }
        contract_hash = _stable_hash(values)
        return QueryContract(
            contract_version=QUERY_CONTRACT_VERSION,
            classifier_version=CLASSIFIER_VERSION,
            binding=binding,
            question=question,
            canonical_question=canonical,
            query_class=query_class,
            intent=intent,
            extracted_subject=subject,
            required_slots=slots,
            retrieval_plan=plan,
            supported=supported,
            classification_reason=reason,
            contract_hash=contract_hash,
        )


def _canonical_question(question: str) -> str:
    if not isinstance(question, str) or not question.strip():
        raise QueryClassificationError("question must not be empty")
    if len(question) > MAX_QUESTION_CHARACTERS:
        raise QueryClassificationError(
            f"question must be at most {MAX_QUESTION_CHARACTERS} characters"
        )
    if "\x00" in question:
        raise QueryClassificationError("question contains an invalid character")
    return " ".join(question.split())


def _extract_subject(question: str) -> str | None:
    quoted = re.search(r"[`'\"](" + _IDENTIFIER + r")[`'\"]", question)
    if quoted:
        return quoted.group(1)
    patterns = (
        r"(?:where\s+is|where\s+are)\s+(?:the\s+)?(" + _IDENTIFIER + r")",
        r"(?:imports?|references?|inherits?\s+from|extends?)\s+(" + _IDENTIFIER + r")",
    )
    ignored = {"the", "which", "what", "where"}
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if match and match.group(1).casefold() not in ignored:
            return match.group(1).rstrip("?.")
    identifiers = re.findall(r"\b[A-Z][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b", question)
    return identifiers[-1] if identifiers else None


def _module_subject(question: str) -> str | None:
    match = re.search(
        r"\bmodule\s+[`'\"]?([A-Za-z_][A-Za-z0-9_.]*)[`'\"]?",
        question,
        flags=re.IGNORECASE,
    )
    return match.group(1).rstrip("?.") if match else _extract_subject(question)


def _exact_step(order: int, query: str) -> RetrievalStep:
    return RetrievalStep(
        order=order,
        method=RetrievalMethod.EXACT,
        fills_slot=SlotName.EXACT_SYMBOL,
        query=query,
        limit=20,
        reason="Resolve the subject to scan-bound exact symbol identity.",
    )


def _graph_step(
    order: int,
    slot: SlotName,
    query: str,
    relationship_types: tuple[str, ...],
    *,
    depends_on: SlotName | None = None,
    constraints: tuple[tuple[str, str], ...] = (),
) -> RetrievalStep:
    return RetrievalStep(
        order=order,
        method=RetrievalMethod.GRAPH,
        fills_slot=slot,
        query=query,
        limit=100,
        direction="INCOMING",
        relationship_types=relationship_types,
        depends_on_slot=depends_on,
        constraints=constraints,
        reason="Traverse only the relationship types required by the question.",
    )


def _full_text_step(
    order: int,
    slot: SlotName,
    query: str,
    *,
    additional_slots: tuple[SlotName, ...] = (),
) -> RetrievalStep:
    return RetrievalStep(
        order=order,
        method=RetrievalMethod.FULL_TEXT,
        fills_slot=slot,
        query=query,
        limit=20,
        additional_slots=additional_slots,
        reason="Use bounded lexical evidence after structural retrieval.",
    )


def _canonical_dataclass(value: object) -> dict[str, object]:
    raw = asdict(value)
    return {
        key: item.value if hasattr(item, "value") else item
        for key, item in raw.items()
    }


def _stable_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
