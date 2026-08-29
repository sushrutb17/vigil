"""Live-agent replacements for pipeline/run_batch.py's deterministic stand-ins.

Only used when the batch is run with ``--live``; the deterministic stand-ins in
``pipeline/run_batch.py`` stay the default so the no-credentials demo path is
never affected by this module. Kept out of ``pipeline/`` since it depends on
``agents/live.py``'s ADK plumbing, not just plain Python.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

from agents import contracts
from agents.critic import strip_uncited_claims
from agents.live import run_llm_agent
from agents.runtime import parse_structured_response
from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.run_batch import cluster_facets
from pipeline.store import TriageStore


def live_assess_cluster(
    cluster_id: str,
    reports: Sequence[ASRSReport],
    risk: RiskScore,
    *,
    analyst: object,
    model: str,
    store: TriageStore,
    max_evidence: int = 20,
) -> ClusterAssessment:
    """Name a cluster and write its hazard statement with a live Analyst call.

    Risk stays fully deterministic — ``pipeline.risk.score_cluster`` already
    computed it before this is called. The Analyst only supplies the name and
    prose hazard statement, per ARCHITECTURE.md's stage 3.

    Only the first ``max_evidence`` member narratives go in the prompt,
    regardless of cluster size. Found the hard way: a real 629-member cluster
    sent every member's full narrative in one call and blew past the model's
    1,048,576-token context limit, and the retries on that oversized request
    (plus the other 22 calls in the same run) exhausted the per-minute input
    token quota too. ``member_acns``/``facets`` on the returned assessment still
    reflect the full membership — only what the model sees is capped.
    """
    sample = reports[:max_evidence]
    evidence = "\n".join(f"[ACN {report.acn}] {report.narrative}" for report in sample)
    size_note = (
        f"(showing {len(sample)} representative examples)" if len(reports) > len(sample) else ""
    )
    message = (
        f"Cluster of {len(reports)} public aviation safety reports {size_note}:\n{evidence}\n\n"
        "Name the shared hazard and write one bounded hazard statement citing "
        "supporting member ACNs."
    )
    raw = run_llm_agent(analyst, message=message, model=model, store=store)
    analysis = parse_structured_response(raw, contracts.ClusterAnalysisOutput)
    return ClusterAssessment(
        cluster_id=cluster_id,
        name=analysis.name,
        hazard_statement=analysis.hazard_statement,
        risk=risk,
        member_acns=tuple(report.acn for report in reports),
        facets=cluster_facets(reports),
    )


class CoordinatorFailure(RuntimeError):
    """Raised when fewer than 2 of the 3 coordinator sub-agents succeed."""


def _call_or_none(fn: Callable[[], str]) -> str | None:
    try:
        return fn()
    except Exception:
        return None


def _precedent_candidates(
    assessment: ClusterAssessment, batch: Sequence[ASRSReport], *, limit: int
) -> list[ASRSReport]:
    """Cheap, deterministic RAG stand-in: other batch reports sharing a component.

    Scoped to the current batch/slice, not the full training corpus — matches
    the explicit 2026-08-29 scope decision against a full-corpus scale-up.
    """
    member_acns = set(assessment.member_acns)
    components = set(assessment.facets.get("component", ()))
    candidates = [
        report
        for report in batch
        if report.acn not in member_acns and report.component in components
    ]
    return candidates[:limit]


def live_draft_brief(
    assessment: ClusterAssessment,
    members: Sequence[ASRSReport],
    batch: Sequence[ASRSReport],
    *,
    precedent: object,
    risk: object,
    brief_writer: object,
    critic: object,
    model: str,
    brief_writer_model: str,
    store: TriageStore,
    max_evidence: int = 20,
    max_precedent_candidates: int = 30,
) -> str:
    """Draft a cited investigator brief for one escalated cluster.

    Precedent, Risk, and Brief Writer run concurrently (plain Python, per
    ARCHITECTURE.md's own "orchestration that can be plain code should be plain
    code") with independent failure isolation — if one raises, the other two
    still produce a brief and the result is marked DEGRADED (fewer than 2
    surviving raises ``CoordinatorFailure`` instead, matching "a bad report
    never kills a run" applied at cluster granularity). The Critic agent then
    reviews the assembled draft, and the existing deterministic
    ``strip_uncited_claims`` runs last, unconditionally — guardrail #4 has no
    exceptions, regardless of what the LLM critic did or whether it ran at all.
    """
    citations = " ".join(f"[ACN {acn}]" for acn in assessment.member_acns)
    candidates = _precedent_candidates(assessment, batch, limit=max_precedent_candidates)
    precedent_evidence = "\n".join(f"[ACN {r.acn}] {r.narrative}" for r in candidates)
    precedent_message = (
        f"Hazard: {assessment.hazard_statement}\n\n"
        f"Candidate historic reports from the same component category:\n"
        f"{precedent_evidence or '(none found in this batch)'}\n\n"
        "Return only ACN-cited observations relevant to this hazard."
    )
    risk_message = (
        "Deterministic risk components already computed by code for this cluster: "
        f"severity={assessment.risk.severity:.2f}, frequency={assessment.risk.frequency:.2f}, "
        f"trend={assessment.risk.trend:.2f}, total={assessment.risk.total:.2f}, "
        f"member count={len(assessment.member_acns)}. Explain what these mean in plain "
        "language. Do not change the numbers or recommend action."
    )
    evidence_sample = members[:max_evidence]
    evidence = "\n".join(f"[ACN {r.acn}] {r.narrative}" for r in evidence_sample)
    brief_writer_message = (
        f"Hazard: {assessment.hazard_statement}\n\nSupporting evidence:\n{evidence}\n\n"
        "Write a concise investigator draft. Every factual sentence must cite one or "
        "more ACNs in the form [ACN 1234567]."
    )

    with ThreadPoolExecutor(max_workers=3) as pool:
        precedent_future = pool.submit(
            _call_or_none,
            lambda: run_llm_agent(precedent, message=precedent_message, model=model, store=store),
        )
        risk_future = pool.submit(
            _call_or_none,
            lambda: run_llm_agent(risk, message=risk_message, model=model, store=store),
        )
        brief_future = pool.submit(
            _call_or_none,
            lambda: run_llm_agent(
                brief_writer, message=brief_writer_message, model=brief_writer_model, store=store
            ),
        )
        precedent_text = precedent_future.result()
        risk_text = risk_future.result()
        brief_text = brief_future.result()

    survived = sum(text is not None for text in (precedent_text, risk_text, brief_text))
    if survived < 2:
        raise CoordinatorFailure(
            f"cluster {assessment.cluster_id}: only {survived}/3 coordinator sub-agents succeeded"
        )

    sections = [f"# Draft: {assessment.name}"]
    if survived < 3:
        sections.append("DEGRADED")
    sections.append(f"## Hazard\n{assessment.hazard_statement} {citations}")
    sections.append(
        "## Precedent\n"
        + (precedent_text or f"Precedent analysis unavailable this run. {citations}")
    )
    sections.append(
        "## Risk Assessment\n"
        + (
            risk_text
            or (
                f"Deterministic risk score {assessment.risk.total:.2f} (severity "
                f"{assessment.risk.severity:.2f}, frequency {assessment.risk.frequency:.2f}, "
                f"trend {assessment.risk.trend:.2f}). {citations}"
            )
        )
    )
    sections.append(
        "## Recommended Brief\n"
        + (brief_text or f"Brief drafting unavailable this run. {citations}")
    )
    draft = "\n\n".join(sections)

    critic_text = _call_or_none(
        lambda: run_llm_agent(critic, message=draft, model=model, store=store)
    )
    return strip_uncited_claims(critic_text or draft).cleaned_brief
