from dataclasses import replace

import pytest
from adaptive_platform.agents import (
    EVIDENCE_REVIEWER,
    REPOSITORY_ANALYST,
    AgentGateEvidence,
    AgentHandoff,
    AgentInvocationError,
    AgentStatus,
    ModelResult,
    invoke_model_agent,
    m4_agent_profiles,
)


def _gate_evidence(profile):
    return tuple(
        AgentGateEvidence(gate, f"evaluation:{gate}", True)
        for gate in profile.required_gates
    )


def test_m4_agent_profiles_are_versioned_read_only_and_disabled_until_gates_pass():
    profiles = m4_agent_profiles()

    assert profiles == (REPOSITORY_ANALYST, EVIDENCE_REVIEWER)
    assert all(profile.status is AgentStatus.DISABLED for profile in profiles)
    assert all(not profile.direct_repository_access for profile in profiles)
    assert all(not profile.command_access for profile in profiles)
    assert all(not profile.source_write_access for profile in profiles)
    assert all(not profile.secret_access for profile in profiles)
    assert all(not profile.network_access for profile in profiles)
    assert all(not profile.external_side_effect_access for profile in profiles)
    assert all(not profile.approval_authority for profile in profiles)
    assert all(len(profile.profile_hash) == 64 for profile in profiles)


def test_profile_hash_changes_with_contract():
    assert REPOSITORY_ANALYST.profile_hash != EVIDENCE_REVIEWER.profile_hash


class FakeGateway:
    def __init__(self, result=None) -> None:
        self.calls = 0
        self.result = result or ModelResult({}, "fake", "fake-model", "request-1", 1, 1)

    def invoke(self, profile, handoff):
        self.calls += 1
        return self.result


def test_disabled_agent_fails_closed_without_calling_gateway():
    gateway = FakeGateway()
    handoff = AgentHandoff.create(
        "repository-analysis-request-v1",
        {"query_contract": {}, "context_package": {}},
    )

    with pytest.raises(AgentInvocationError, match="not enabled"):
        invoke_model_agent(REPOSITORY_ANALYST, handoff, gateway)

    assert gateway.calls == 0


def test_enabled_test_profile_accepts_only_verified_typed_handoff():
    gateway = FakeGateway()
    profile = replace(REPOSITORY_ANALYST, status=AgentStatus.ENABLED)
    handoff = AgentHandoff.create(
        "repository-analysis-request-v1",
        {"query_contract": {}, "context_package": {}},
    )

    result = invoke_model_agent(
        profile,
        handoff,
        gateway,
        gate_evidence=_gate_evidence(profile),
    )

    assert result.provider == "fake"
    assert gateway.calls == 1


def test_enabled_profile_rejects_missing_payload_contract_before_gateway_call():
    gateway = FakeGateway()
    profile = replace(REPOSITORY_ANALYST, status=AgentStatus.ENABLED)
    handoff = AgentHandoff.create(
        "repository-analysis-request-v1",
        {"context_package": {}},
    )

    with pytest.raises(AgentInvocationError, match="query_contract"):
        invoke_model_agent(
            profile,
            handoff,
            gateway,
            gate_evidence=_gate_evidence(profile),
        )

    assert gateway.calls == 0


def test_enabled_profile_rejects_incomplete_activation_evidence():
    gateway = FakeGateway()
    profile = replace(REPOSITORY_ANALYST, status=AgentStatus.ENABLED)
    handoff = AgentHandoff.create(
        "repository-analysis-request-v1",
        {"query_contract": {}, "context_package": {}},
    )

    with pytest.raises(AgentInvocationError, match="activation evidence is incomplete"):
        invoke_model_agent(
            profile,
            handoff,
            gateway,
            gate_evidence=(AgentGateEvidence("coverage_ready", "evaluation:m4", True),),
        )

    assert gateway.calls == 0


def test_enabled_profile_rejects_tampered_handoff_before_gateway_call():
    gateway = FakeGateway()
    profile = replace(REPOSITORY_ANALYST, status=AgentStatus.ENABLED)
    handoff = AgentHandoff.create(
        "repository-analysis-request-v1",
        {"query_contract": {}, "context_package": {}},
    )
    handoff.payload["context_package"] = {"tampered": True}

    with pytest.raises(AgentInvocationError, match="hash verification failed"):
        invoke_model_agent(
            profile,
            handoff,
            gateway,
            gate_evidence=_gate_evidence(profile),
        )

    assert gateway.calls == 0


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (ModelResult({}, "", "model", "request", 1, 1), "provider metadata"),
        (ModelResult({}, "provider", "", "request", 1, 1), "provider metadata"),
        (ModelResult({}, "provider", "model", "", 1, 1), "provider metadata"),
        (ModelResult({}, "provider", "model", "request", -1, 1), "token counts"),
        (ModelResult({}, "provider", "model", "request", 1, -1), "token counts"),
    ],
)
def test_enabled_profile_rejects_invalid_gateway_metadata(result, message):
    gateway = FakeGateway(result)
    profile = replace(REPOSITORY_ANALYST, status=AgentStatus.ENABLED)
    handoff = AgentHandoff.create(
        "repository-analysis-request-v1",
        {"query_contract": {}, "context_package": {}},
    )

    with pytest.raises(AgentInvocationError, match=message):
        invoke_model_agent(
            profile,
            handoff,
            gateway,
            gate_evidence=_gate_evidence(profile),
        )

    assert gateway.calls == 1
