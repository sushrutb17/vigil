from pathlib import Path

import pytest

from agents import orchestrate
from agents.critic import strip_uncited_claims
from pipeline.ingest import load_parquet
from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.risk import FrozenRiskPolicy
from pipeline.run_batch import demo_reports
from pipeline.store import MemoryStore


def test_critic_strips_uncited_claims() -> None:
    result = strip_uncited_claims("# Brief\nSupported [ACN 1234567]\nUnsupported conclusion")
    assert result.cleaned_brief == "# Brief\nSupported [ACN 1234567]"
    assert result.removed_claims == ("Unsupported conclusion",)


def test_gate_removes_citations_to_reports_not_in_the_cluster() -> None:
    """A fabricated citation must not survive just because it is well-formed.

    ACN_CITATION matches any 4+ digit number, so before provenance checking the
    gate enforced "looks cited", not "is sourced". A Risk agent that had been told
    to cite but given no ACNs invented [ACN 1000001]..[ACN 1000005], and all of it
    passed into a brief presented to a human reviewer. That is worse than an
    uncited claim: an uncited sentence is stripped and disappears, while a
    fabricated citation survives carrying false authority.
    """
    brief = (
        "# Draft\n"
        "Real and invented sources mixed [ACN 1044401] [ACN 1000001]\n"
        "Entirely invented [ACN 1000002] [ACN 1000003]\n"
    )
    result = strip_uncited_claims(brief, allowed_acns=["1044401"])

    # The genuine source is kept; only the invented one is cut out of the line.
    assert "[ACN 1044401]" in result.cleaned_brief
    assert "1000001" not in result.cleaned_brief
    # A claim whose every source was invented has nothing supporting it.
    assert "Entirely invented" not in result.cleaned_brief
    assert result.removed_claims == ("Entirely invented [ACN 1000002] [ACN 1000003]",)
    assert set(result.fabricated_citations) == {"1000001", "1000002", "1000003"}
    assert not result.passed


def test_gate_without_an_allowlist_still_checks_citation_shape() -> None:
    """Callers that cannot supply the cluster's ACNs keep the original behaviour
    rather than silently dropping every citation as unverifiable."""
    brief = "# Draft\nSupported [ACN 1234567]\nUnsupported"
    result = strip_uncited_claims(brief)
    assert result.cleaned_brief == "# Draft\nSupported [ACN 1234567]"
    assert result.fabricated_citations == ()


def test_risk_agent_is_given_the_acns_its_instruction_tells_it_to_cite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RISK_INSTRUCTION says to cite "the ACNs supplied with the cluster". If none
    are supplied the model invents plausible ones, which is exactly what happened
    on the first real 5,000-report run."""
    from agents import prompts

    assert "ACNs supplied with the cluster" in prompts.RISK_INSTRUCTION

    sent: dict[str, str] = {}

    def fake_run_llm_agent(agent, *, message, model, store):  # noqa: ANN001, ANN202, ARG001
        sent[agent] = message
        return message if agent == "critic" else "Fine [ACN 1000001]."

    monkeypatch.setattr(orchestrate, "run_llm_agent", fake_run_llm_agent)
    orchestrate.live_draft_brief(
        _assessment(),
        demo_reports()[:2],
        demo_reports()[:2],
        precedent="precedent",
        risk="risk",
        brief_writer="brief_writer",
        critic="critic",
        model="fake",
        brief_writer_model="fake",
        store=MemoryStore(),
    )

    assert "[ACN 1000001]" in sent["risk"] and "[ACN 1000002]" in sent["risk"]


def test_brief_contributing_prompts_demand_the_bracketed_citation_form() -> None:
    """Every agent whose prose flows into a brief must be told the exact bracketed
    citation format the deterministic gate matches.

    strip_uncited_claims keys on ACN_CITATION (``[ACN 1234567]``, square brackets
    required). An agent told only to "cite ACNs" writes bare "ACN 1234567", and the
    gate then deletes 100% of its output — the agent burns tokens on every run and
    contributes nothing, with no error to show for it. That is exactly how the
    Precedent and Risk sections shipped empty in the first live Cloud Run execution.
    """
    from agents import prompts

    for name in ("PRECEDENT_INSTRUCTION", "RISK_INSTRUCTION", "BRIEF_WRITER_INSTRUCTION"):
        instruction = getattr(prompts, name)
        assert "[ACN " in instruction, f"{name} must show the bracketed [ACN ...] form"
        # A sentence the prompt itself models must survive the real gate.
        sample = "Component driven by two reports [ACN 1000001] [ACN 1000002]."
        assert strip_uncited_claims(sample).cleaned_brief == sample


def test_critic_prompt_forbids_adding_its_own_wrapper() -> None:
    """live_draft_brief uses the Critic's entire response verbatim as the brief, so
    any title or commentary it adds lands in front of a human reviewer."""
    from agents import prompts

    assert "ONLY the cleaned brief" in prompts.CRITIC_INSTRUCTION


def _assessment(member_acns: tuple[str, ...] = ("1000001", "1000002")) -> ClusterAssessment:
    return ClusterAssessment(
        cluster_id="cluster-test",
        name="Uncommanded Engine Shutdown",
        hazard_statement="Crews saw uncommanded shutdown indications on rollout",
        risk=RiskScore(severity=1.0, frequency=0.3, trend=0.5, total=0.69, escalated=True),
        member_acns=member_acns,
        facets={"component": ("Engine Control",)},
    )


def _run_draft(
    monkeypatch: pytest.MonkeyPatch,
    replies: dict[str, str],
    assessment: ClusterAssessment,
    batch: list[ASRSReport],
) -> tuple[str, list[str]]:
    """Draft a brief with every live agent call replaced by a canned reply.

    The Critic is special-cased to echo the draft it was handed: live_draft_brief
    uses the Critic's whole response verbatim, so a stub returning a fixed string
    would replace the document under test rather than review it.
    """
    called: list[str] = []

    def fake_run_llm_agent(agent, *, message, model, store):  # noqa: ANN001, ANN202, ARG001
        called.append(agent)
        return message if agent == "critic" else replies[agent]

    monkeypatch.setattr(orchestrate, "run_llm_agent", fake_run_llm_agent)
    brief = orchestrate.live_draft_brief(
        assessment,
        batch,
        batch,
        precedent="precedent",
        risk="risk",
        brief_writer="brief_writer",
        critic="critic",
        model="fake",
        brief_writer_model="fake",
        store=MemoryStore(),
    )
    return brief, called


def _section(brief: str, heading: str) -> str:
    return brief.split(f"{heading}\n", 1)[1].split("\n##", 1)[0].strip()


def test_gate_emptied_section_is_backfilled_with_a_cited_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A section the gate empties must not survive as a bare heading.

    strip_uncited_claims keeps headings and drops uncited body lines, so an agent
    that succeeds but writes uncited prose leaves "## Risk Assessment" followed by
    nothing - byte-identical to an agent that never ran, with no error raised
    anywhere. That is exactly how the Precedent section reached production empty
    across three live Cloud Run executions.
    """
    # One non-member report shares the component, so a Precedent call does happen.
    outsider = ASRSReport(
        acn="1000003",
        narrative="Earlier rollout shutdown indication.",
        anomaly_labels=("Aircraft Equipment Problem Critical",),
        aircraft_type="Regional Jet",
        flight_phase="Landing Rollout",
        component="Engine Control",
        results=("Flight Crew Inflight Shutdown",),
        date_yyyymm="202201",
    )
    brief, called = _run_draft(
        monkeypatch,
        {
            "precedent": "Comparable rollout event [ACN 1000003].",
            # No citation anywhere, so the gate deletes every line of it.
            "risk": "The score is high and the trend is worsening.",
            "brief_writer": "Crews completed the checklist [ACN 1000001].",
        },
        _assessment(),
        [*demo_reports()[:2], outsider],
    )

    assert "precedent" in called
    risk_section = _section(brief, "## Risk Assessment")
    assert risk_section, "the emptied section must be repaired, not left as a bare heading"
    # The repair must itself satisfy the gate it is repairing.
    assert strip_uncited_claims(risk_section).cleaned_brief.strip() == risk_section
    # The surviving cited sections must be untouched by the repair.
    assert "[ACN 1000003]" in _section(brief, "## Precedent")


def test_absent_precedent_skips_the_call_and_does_not_mark_the_run_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The demo fixture has no precedent candidates: every report sharing the
    cluster's component is a cluster member. Asking the model anyway spends a live
    call whose only honest answer ("none found in this batch") carries no ACN and
    the gate deletes in full. Skipping it is not a sub-agent failure and must not
    stamp the brief DEGRADED.
    """
    reports = demo_reports()
    brief, called = _run_draft(
        monkeypatch,
        {
            "risk": "Score 0.69 driven by both reports [ACN 1000001] [ACN 1000002].",
            "brief_writer": "Crews completed the checklist [ACN 1000001].",
        },
        _assessment(member_acns=tuple(r.acn for r in reports)),
        reports,
    )

    assert "precedent" not in called, "no candidates means no Precedent call should be made"
    assert "DEGRADED" not in brief, "a skipped Precedent call is not a sub-agent failure"
    section = _section(brief, "## Precedent")
    assert "No comparable reports" in section
    assert strip_uncited_claims(section).cleaned_brief.strip() == section


def test_frozen_policy_has_no_mutable_clustering_mapping() -> None:
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    with pytest.raises(TypeError):
        policy.clustering["min_cluster_size"] = 99  # type: ignore[index]


def test_live_ingest_refuses_holdout_reads() -> None:
    with pytest.raises(PermissionError):
        load_parquet(Path("data/holdout/test.parquet"))
