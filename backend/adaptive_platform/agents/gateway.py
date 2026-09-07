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
) -> ModelResult:
    """The only M4 model-agent boundary; disabled profiles fail closed."""
    if profile.status is not AgentStatus.ENABLED:
        raise AgentInvocationError(f"Agent profile is not enabled: {profile.profile_id}")
    if handoff.schema_name != profile.input_schema:
        raise AgentInvocationError("Agent handoff schema does not match the profile contract")
    if handoff.content_hash != _payload_hash(handoff.payload):
        raise AgentInvocationError("Agent handoff hash verification failed")
    return gateway.invoke(profile, handoff)


def _payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
