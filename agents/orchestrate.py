"""Live-agent replacements for pipeline/run_batch.py's deterministic stand-ins.

Only used when the batch is run with ``--live``; the deterministic stand-ins in
``pipeline/run_batch.py`` stay the default so the no-credentials demo path is
never affected by this module. Kept out of ``pipeline/`` since it depends on
``agents/live.py``'s ADK plumbing, not just plain Python.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
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


def _backfill_empty_sections(brief: str, fallbacks: Mapping[str, str]) -> str:
    """Restore a cited placeholder for any section the citation gate emptied.

    ``strip_uncited_claims`` works line by line and always keeps headings, so a
    section whose every line lacked a citation survives as a bare heading with no
    body. That output is byte-identical to a section whose agent never ran, which
    is how the Precedent section shipped empty through three live Cloud Run
    executions without anything reporting an error — the agent succeeded, and the
    gate silently deleted all of it.

    The section-level fallbacks in ``live_draft_brief`` cannot cover this on their
    own: they are chosen before assembly and only fire when a sub-agent *raised*.
    This runs after the gate, so it is the only place that sees what the gate
    actually removed. Replacements carry the cluster's member ACNs by
    construction, so they pass the same gate they are repairing rather than
    smuggling an uncited claim in behind it.
    """
    lines = brief.splitlines()
    repaired: list[str] = []
    for index, line in enumerate(lines):
        repaired.append(line)
        if line.strip() not in fallbacks:
            continue
        # A section is empty when the next nonblank line is another heading (or
        # the document simply ends).
        following = next((later.strip() for later in lines[index + 1 :] if later.strip()), "")
        if not following or following.startswith("#"):
            repaired.append(fallbacks[line.strip()])
    return "\n".join(repaired)


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
        "language. Do not change the numbers or recommend action.\n\n"
        # RISK_INSTRUCTION tells this agent to cite "the ACNs supplied with the
        # cluster". They were never actually supplied, so the model invented the
        # obvious placeholder sequence [ACN 1000001]..[ACN 1000005] and the gate,
        # which only checked citation shape, kept all of it. Supply them.
        f"Cite only these ACNs, which are the reports in this cluster: {citations}"
    )
    evidence_sample = members[:max_evidence]
    evidence = "\n".join(f"[ACN {r.acn}] {r.narrative}" for r in evidence_sample)
    brief_writer_message = (
        f"Hazard: {assessment.hazard_statement}\n\nSupporting evidence:\n{evidence}\n\n"
        "Write a concise investigator draft. Every factual sentence must cite one or "
        "more ACNs in the form [ACN 1234567]."
    )

    with ThreadPoolExecutor(max_workers=3) as pool:
        # With no candidates there is no question to ask: the prompt would say
        # "(none found in this batch)" and the only honest answer is "no
        # comparable reports", which carries no ACN and the gate deletes in full.
        # Skipping the call states that deterministically and saves a live Flash
        # call per escalated cluster.
        precedent_future = (
            pool.submit(
                _call_or_none,
                lambda: run_llm_agent(
                    precedent, message=precedent_message, model=model, store=store
                ),
            )
            if candidates
            else None
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
        precedent_text = precedent_future.result() if precedent_future is not None else None
        risk_text = risk_future.result()
        brief_text = brief_future.result()

    # A deliberately skipped Precedent call is not a failure. Counting failures
    # rather than survivors keeps that distinction: an absent precedent must not
    # stamp DEGRADED on a run in which every agent that was asked succeeded.
    attempted = 3 if candidates else 2
    failures = sum(
        (
            bool(candidates) and precedent_text is None,
            risk_text is None,
            brief_text is None,
        )
    )
    if failures > 1:
        raise CoordinatorFailure(
            f"cluster {assessment.cluster_id}: only {attempted - failures}/{attempted} "
            "coordinator sub-agents succeeded"
        )

    # Keyed by heading so _backfill_empty_sections can reuse the same text after
    # the gate runs. Every value carries the member ACNs, so each one survives the
    # gate on its own.
    fallbacks = {
        "## Precedent": (
            f"No comparable reports outside this cluster appear in this batch. {citations}"
            if not candidates
            else f"Precedent analysis unavailable this run. {citations}"
        ),
        "## Risk Assessment": (
            f"Deterministic risk score {assessment.risk.total:.2f} (severity "
            f"{assessment.risk.severity:.2f}, frequency {assessment.risk.frequency:.2f}, "
            f"trend {assessment.risk.trend:.2f}). {citations}"
        ),
        "## Recommended Brief": f"Brief drafting unavailable this run. {citations}",
    }

    sections = [f"# Draft: {assessment.name}"]
    if failures:
        sections.append("DEGRADED")
    sections.append(f"## Hazard\n{assessment.hazard_statement} {citations}")
    sections.append("## Precedent\n" + (precedent_text or fallbacks["## Precedent"]))
    sections.append("## Risk Assessment\n" + (risk_text or fallbacks["## Risk Assessment"]))
    sections.append("## Recommended Brief\n" + (brief_text or fallbacks["## Recommended Brief"]))
    draft = "\n\n".join(sections)

    critic_text = _call_or_none(
        lambda: run_llm_agent(critic, message=draft, model=model, store=store)
    )
    # The Precedent agent legitimately cites reports outside the cluster, so the
    # allow-list is the cluster's members plus the candidates it was actually
    # given. Anything else in the draft was invented.
    allowed = {*assessment.member_acns, *(report.acn for report in candidates)}
    gated = strip_uncited_claims(critic_text or draft, allowed_acns=allowed).cleaned_brief
    return _backfill_empty_sections(gated, fallbacks)
