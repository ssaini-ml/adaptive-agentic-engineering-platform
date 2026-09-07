from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class AgentRole(StrEnum):
    REPOSITORY_ANALYST = "REPOSITORY_ANALYST"
    EVIDENCE_REVIEWER = "EVIDENCE_REVIEWER"


class AgentStatus(StrEnum):
    DISABLED = "DISABLED"
    ENABLED = "ENABLED"
    RETIRED = "RETIRED"


class AgentPermission(StrEnum):
    CONTEXT_PACKAGE_READ = "CONTEXT_PACKAGE_READ"
    PROPOSED_ANSWER_READ = "PROPOSED_ANSWER_READ"
    EVIDENCE_REFERENCE_READ = "EVIDENCE_REFERENCE_READ"
    MODEL_GATEWAY_CALL = "MODEL_GATEWAY_CALL"


@dataclass(frozen=True, slots=True)
class AgentProfile:
    """Code-versioned authority contract; it does not imply a running model."""

    profile_id: str
    version: str
    role: AgentRole
    status: AgentStatus
    input_schema: str
    output_schema: str
    permissions: tuple[AgentPermission, ...]
    required_gates: tuple[str, ...]
    max_model_calls: int
    direct_repository_access: bool = False
    command_access: bool = False
    source_write_access: bool = False
    secret_access: bool = False

    @property
    def profile_hash(self) -> str:
        payload = asdict(self)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode()).hexdigest()


REPOSITORY_ANALYST = AgentProfile(
    profile_id="repository-analyst-structural",
    version="1.0.0",
    role=AgentRole.REPOSITORY_ANALYST,
    status=AgentStatus.DISABLED,
    input_schema="context-package-v1",
    output_schema="proposed-answer-v1",
    permissions=(AgentPermission.CONTEXT_PACKAGE_READ, AgentPermission.MODEL_GATEWAY_CALL),
    required_gates=("coverage_ready", "provider_specific_eval", "human_holdout_review"),
    max_model_calls=1,
)

EVIDENCE_REVIEWER = AgentProfile(
    profile_id="evidence-reviewer-structural",
    version="1.0.0",
    role=AgentRole.EVIDENCE_REVIEWER,
    status=AgentStatus.DISABLED,
    input_schema="proposed-answer-v1+evidence-refs-v1",
    output_schema="review-opinion-v1",
    permissions=(
        AgentPermission.PROPOSED_ANSWER_READ,
        AgentPermission.EVIDENCE_REFERENCE_READ,
        AgentPermission.MODEL_GATEWAY_CALL,
    ),
    required_gates=("deterministic_validation_complete", "human_holdout_review"),
    max_model_calls=1,
)


def m4_agent_profiles() -> tuple[AgentProfile, ...]:
    return (REPOSITORY_ANALYST, EVIDENCE_REVIEWER)
