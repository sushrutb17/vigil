"""Fan-out partial-failure behavior (Phase 6), exercised without live calls."""

import pytest

from agents import orchestrate
from agents.orchestrate import CoordinatorFailure, live_draft_brief
from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.store import MemoryStore

MEMBERS = [
    ASRSReport(
        acn=str(2000 + index),
        narrative=f"Engine anomaly narrative {index}.",
        component="Engine Control",
    )
    for index in range(3)
]
OUTSIDER = ASRSReport(
    acn="2999", narrative="A comparable historic engine event.", component="Engine Control"
)


def _assessment() -> ClusterAssessment:
    return ClusterAssessment(
        cluster_id="cluster-test",
        name="Engine Control Anomalies",
        hazard_statement="Repeated engine control anomalies during rollout.",
        member_acns=tuple(report.acn for report in MEMBERS),
        facets={"component": ("Engine Control",)},
        risk=RiskScore(severity=0.8, frequency=0.6, trend=0.5, total=0.69, escalated=True),
    )


@pytest.fixture
def fake_agents(monkeypatch):
    """Replace the ADK call with a per-agent canned, ACN-citing response."""

    def fake_run_llm_agent(agent, *, message, model, store):
        citation = f"[ACN {MEMBERS[0].acn}]"
        if agent == "critic":
            # A real critic returns the assembled draft, edited. Notably it does
            # NOT reliably echo the DEGRADED banner, which is why the
            # orchestrator re-asserts that itself.
            return message.replace("DEGRADED\n", "")
        return f"{agent} says something factual {citation}"

    monkeypatch.setattr(orchestrate, "run_llm_agent", fake_run_llm_agent)


def _draft(fail_agents: set[str]) -> str:
    return live_draft_brief(
        _assessment(),
        MEMBERS,
        [*MEMBERS, OUTSIDER],
        precedent="precedent",
        risk="risk",
        brief_writer="brief_writer",
        critic="critic",
        model="m",
        brief_writer_model="m",
        store=MemoryStore(),
        fail_agents=frozenset(fail_agents),
    )


def test_all_agents_succeeding_is_not_degraded(fake_agents) -> None:
    assert "DEGRADED" not in _draft(set())


def test_killing_one_sub_agent_yields_a_degraded_brief(fake_agents) -> None:
    """ARCHITECTURE.md's demo beat: one agent dies, a brief still ships."""
    brief = _draft({"risk"})
    assert "DEGRADED" in brief
    assert "## Risk Assessment" in brief
    # The lost section is backfilled with a cited deterministic line, not left bare.
    assert "Deterministic risk score 0.69" in brief


def test_killing_two_sub_agents_raises_coordinator_failure(fake_agents) -> None:
    """Below 2 survivors the caller falls back to the deterministic template."""
    with pytest.raises(CoordinatorFailure):
        _draft({"risk", "brief_writer"})


def test_degraded_survives_a_critic_that_drops_the_banner(fake_agents) -> None:
    """The banner is derived from what the orchestrator knows, not from the model."""
    assert "DEGRADED" in _draft({"risk"})


def test_citation_gate_still_holds_when_the_critic_is_dead(fake_agents) -> None:
    """Guardrail #4 does not depend on the LLM critic having run."""
    brief = _draft({"critic"})
    assert "DEGRADED" not in brief  # the critic is outside the 3-way fan-out
    for line in brief.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            assert "[ACN " in stripped
