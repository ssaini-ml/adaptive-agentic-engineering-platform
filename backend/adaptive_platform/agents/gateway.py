from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Protocol

from adaptive_platform.agents.profiles import AgentProfile, AgentStatus


class AgentInvocationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AgentHandoff:
    schema_name: str
    content_hash: str
    payload: dict[str, Any]

    @classmethod
    def create(cls, schema_name: str, payload: dict[str, Any]) -> AgentHandoff:
        return cls(schema_name, _payload_hash(payload), payload)


@dataclass(frozen=True, slots=True)
class AgentGateEvidence:
    gate_name: str
    evidence_ref: str
    passed: bool


@dataclass(frozen=True, slots=True)
class ModelResult:
    output: dict[str, Any]
    provider: str
    model: str
    request_id: str
    input_tokens: int
    output_tokens: int


class ModelGateway(Protocol):
    def invoke(self, profile: AgentProfile, handoff: AgentHandoff) -> ModelResult: ...


def invoke_model_agent(
    profile: AgentProfile,
    handoff: AgentHandoff,
    gateway: ModelGateway,
    *,
    gate_evidence: tuple[AgentGateEvidence, ...] = (),
) -> ModelResult:
    """The only M4 model-agent boundary; disabled profiles fail closed."""
    if profile.status is not AgentStatus.ENABLED:
        raise AgentInvocationError(f"Agent profile is not enabled: {profile.profile_id}")
    if handoff.schema_name != profile.input_schema:
        raise AgentInvocationError("Agent handoff schema does not match the profile contract")
    if handoff.content_hash != _payload_hash(handoff.payload):
        raise AgentInvocationError("Agent handoff hash verification failed")
    missing_keys = sorted(set(profile.required_payload_keys) - handoff.payload.keys())
    if missing_keys:
        raise AgentInvocationError(
            f"Agent handoff is missing required payload keys: {', '.join(missing_keys)}"
        )
    evidenced_gates = {
        item.gate_name
        for item in gate_evidence
        if item.passed and item.evidence_ref.strip()
    }
    missing_gates = sorted(set(profile.required_gates) - evidenced_gates)
    if missing_gates:
        raise AgentInvocationError(
            f"Agent activation evidence is incomplete: {', '.join(missing_gates)}"
        )
    result = gateway.invoke(profile, handoff)
    if not result.provider or not result.model or not result.request_id:
        raise AgentInvocationError("Model gateway returned incomplete provider metadata")
    if result.input_tokens < 0 or result.output_tokens < 0:
        raise AgentInvocationError("Model gateway returned invalid token counts")
    return result


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
