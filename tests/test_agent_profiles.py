from dataclasses import replace

import pytest
from adaptive_platform.agents import (
    EVIDENCE_REVIEWER,
    REPOSITORY_ANALYST,
    AgentHandoff,
    AgentInvocationError,
    AgentStatus,
    ModelResult,
    invoke_model_agent,
    m4_agent_profiles,
)


def test_m4_agent_profiles_are_versioned_read_only_and_disabled_until_gates_pass():
    profiles = m4_agent_profiles()

    assert profiles == (REPOSITORY_ANALYST, EVIDENCE_REVIEWER)
    assert all(profile.status is AgentStatus.DISABLED for profile in profiles)
    assert all(not profile.direct_repository_access for profile in profiles)
    assert all(not profile.command_access for profile in profiles)
    assert all(not profile.source_write_access for profile in profiles)
    assert all(not profile.secret_access for profile in profiles)
    assert all(len(profile.profile_hash) == 64 for profile in profiles)


def test_profile_hash_changes_with_contract():
    assert REPOSITORY_ANALYST.profile_hash != EVIDENCE_REVIEWER.profile_hash


class FakeGateway:
    def __init__(self) -> None:
        self.calls = 0

    def invoke(self, profile, handoff):
        self.calls += 1
        return ModelResult({}, "fake", "fake-model", "request-1", 1, 1)


def test_disabled_agent_fails_closed_without_calling_gateway():
    gateway = FakeGateway()
    handoff = AgentHandoff.create("context-package-v1", {"context_hash": "abc"})

    with pytest.raises(AgentInvocationError, match="not enabled"):
        invoke_model_agent(REPOSITORY_ANALYST, handoff, gateway)

    assert gateway.calls == 0


def test_enabled_test_profile_accepts_only_verified_typed_handoff():
    gateway = FakeGateway()
    profile = replace(REPOSITORY_ANALYST, status=AgentStatus.ENABLED)
    handoff = AgentHandoff.create("context-package-v1", {"context_hash": "abc"})

    result = invoke_model_agent(profile, handoff, gateway)

    assert result.provider == "fake"
    assert gateway.calls == 1
