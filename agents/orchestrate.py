"""Live-agent replacements for pipeline/run_batch.py's deterministic stand-ins.

Only used when the batch is run with ``--live``; the deterministic stand-ins in
``pipeline/run_batch.py`` stay the default so the no-credentials demo path is
never affected by this module. Kept out of ``pipeline/`` since it depends on
``agents/live.py``'s ADK plumbing, not just plain Python.
"""

from __future__ import annotations

from collections.abc import Sequence

from agents import contracts
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
) -> ClusterAssessment:
    """Name a cluster and write its hazard statement with a live Analyst call.

    Risk stays fully deterministic — ``pipeline.risk.score_cluster`` already
    computed it before this is called. The Analyst only supplies the name and
    prose hazard statement, per ARCHITECTURE.md's stage 3.
    """
    evidence = "\n".join(f"[ACN {report.acn}] {report.narrative}" for report in reports)
    message = (
        f"Cluster of {len(reports)} public aviation safety reports:\n{evidence}\n\n"
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
