"""Resumable batch runner that keeps model-free orchestration in plain Python."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from agents.critic import strip_uncited_claims
from pipeline.cluster import cluster_reports
from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.risk import FrozenRiskPolicy, score_cluster
from pipeline.store import MemoryStore, TriageStore


def run_batch(
    reports: Sequence[ASRSReport],
    *,
    policy: FrozenRiskPolicy,
    store: TriageStore,
) -> list[ClusterAssessment]:
    """Ingest, deterministically cluster, score, and persist a batch.

    This local implementation uses structured fields as an analyst stand-in only
    for the demo. Authenticated deployments replace the naming/brief text with
    the ADK agents defined in ``agents/definitions.py``; the risk gate remains
    deterministic in both modes.
    """
    for report in reports:
        store.put_report(report.acn, asdict(report))
    clusters = cluster_reports(
        reports,
        min_cluster_size=int(policy.clustering.get("min_cluster_size", 5)),
        min_samples=int(policy.clustering.get("min_samples", 3)),
    )
    by_acn = {report.acn: report for report in reports}
    assessments: list[ClusterAssessment] = []
    for cluster in clusters:
        members = [by_acn[acn] for acn in cluster.member_acns]
        risk = score_cluster(members, policy)
        assessment = _assess_cluster(cluster.cluster_id, members, risk)
        already_escalated = store.previously_escalated(frozenset(cluster.member_acns))
        status = "escalated" if risk.escalated and not already_escalated else "new"
        if risk.escalated and not already_escalated:
            store.record_escalation(frozenset(cluster.member_acns))
        store.put_cluster(
            cluster.cluster_id,
            {
                "member_acns": list(cluster.member_acns),
                "risk_score": risk.total,
                "status": status,
                "noise": cluster.noise,
                "name": assessment.name,
            },
        )
        assessments.append(assessment)
    return sorted(assessments, key=lambda assessment: assessment.risk.total, reverse=True)


def draft_brief(assessment: ClusterAssessment) -> str:
    """Create a local, source-cited draft suitable for UI and critic demos."""
    citations = " ".join(f"[ACN {acn}]" for acn in assessment.member_acns)
    raw = "\n".join(
        [
            f"# Draft: {assessment.name}",
            f"- {assessment.hazard_statement} {citations}",
            (
                "- Deterministic risk score: "
                f"{assessment.risk.total:.2f} (severity {assessment.risk.severity:.2f}, "
                f"frequency {assessment.risk.frequency:.2f}, "
                f"trend {assessment.risk.trend:.2f}). {citations}"
            ),
            "- This sentence is deliberately uncited and must be removed.",
        ]
    )
    return strip_uncited_claims(raw).cleaned_brief


def _assess_cluster(
    cluster_id: str, reports: Sequence[ASRSReport], risk: RiskScore
) -> ClusterAssessment:
    component = _dominant(reports, "component", fallback="operational event")
    phase = _dominant(reports, "flight_phase", fallback="unknown phase")
    aircraft = _dominant(reports, "aircraft_type", fallback="mixed aircraft")
    acns = tuple(report.acn for report in reports)
    return ClusterAssessment(
        cluster_id=cluster_id,
        name=f"{component} events during {phase}",
        hazard_statement=(
            f"Reports describe a recurring {component.lower()} pattern "
            f"on {aircraft} during {phase}."
        ),
        risk=risk,
        member_acns=acns,
        facets={
            "component": tuple(
                sorted({report.component for report in reports if report.component})
            ),
            "flight_phase": tuple(
                sorted({report.flight_phase for report in reports if report.flight_phase})
            ),
            "aircraft_type": tuple(
                sorted({report.aircraft_type for report in reports if report.aircraft_type})
            ),
        },
    )


def _dominant(reports: Sequence[ASRSReport], attribute: str, *, fallback: str) -> str:
    values = [getattr(report, attribute) for report in reports if getattr(report, attribute)]
    return Counter(values).most_common(1)[0][0] if values else fallback


def demo_reports() -> list[ASRSReport]:
    """Small public-data-shaped fixture; no external download or credentials required."""
    return [
        ASRSReport(
            acn=str(1000000 + index),
            narrative=(
                "During landing rollout the crew observed an uncommanded engine shutdown "
                "indication and completed the checklist."
            ),
            anomaly_labels=("Engine Shutdown",),
            aircraft_type="Regional Jet",
            flight_phase="Landing Rollout",
            component="Engine Control",
            results=("Engine Shutdown",),
            date_yyyymm=f"20220{index}",
        )
        for index in range(1, 7)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run VIGIL's deterministic local demo")
    parser.add_argument("--demo", action="store_true", help="run the bundled six-report demo")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    if not args.demo:
        parser.error("only --demo is available until a dataset path is supplied")
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    assessments = run_batch(demo_reports(), policy=policy, store=MemoryStore())
    payload = [
        {**asdict(assessment), "brief": draft_brief(assessment)}
        for assessment in assessments
        if not assessment.cluster_id.startswith("noise-")
    ]
    output = json.dumps(payload, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
