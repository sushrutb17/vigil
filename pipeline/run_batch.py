"""Resumable batch runner that keeps model-free orchestration in plain Python."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path

from agents.critic import strip_uncited_claims
from pipeline.cluster import cluster_reports
from pipeline.ingest import load_parquet
from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.risk import FrozenRiskPolicy, score_cluster
from pipeline.store import MemoryStore, TriageStore

AssessClusterFn = Callable[[str, Sequence[ASRSReport], RiskScore], ClusterAssessment]


def cluster_facets(reports: Sequence[ASRSReport]) -> dict[str, tuple[str, ...]]:
    """Shared facet summary used by both the deterministic and live assessors."""
    return {
        "component": tuple(sorted({report.component for report in reports if report.component})),
        "flight_phase": tuple(
            sorted({report.flight_phase for report in reports if report.flight_phase})
        ),
        "aircraft_type": tuple(
            sorted({report.aircraft_type for report in reports if report.aircraft_type})
        ),
    }


def _dominant(reports: Sequence[ASRSReport], attribute: str, *, fallback: str) -> str:
    values = [getattr(report, attribute) for report in reports if getattr(report, attribute)]
    return Counter(values).most_common(1)[0][0] if values else fallback


def _assess_cluster(
    cluster_id: str, reports: Sequence[ASRSReport], risk: RiskScore
) -> ClusterAssessment:
    component = _dominant(reports, "component", fallback="operational event")
    phase = _dominant(reports, "flight_phase", fallback="unknown phase")
    aircraft = _dominant(reports, "aircraft_type", fallback="mixed aircraft")
    return ClusterAssessment(
        cluster_id=cluster_id,
        name=f"{component} events during {phase}",
        hazard_statement=(
            f"Reports describe a recurring {component.lower()} pattern "
            f"on {aircraft} during {phase}."
        ),
        risk=risk,
        member_acns=tuple(report.acn for report in reports),
        facets=cluster_facets(reports),
    )


def run_batch(
    reports: Sequence[ASRSReport],
    *,
    policy: FrozenRiskPolicy,
    store: TriageStore,
    assess_cluster: AssessClusterFn = _assess_cluster,
) -> list[ClusterAssessment]:
    """Ingest, deterministically cluster, score, and persist a batch.

    ``assess_cluster`` defaults to a deterministic structured-field stand-in so
    the no-credentials demo path is unaffected. A live run passes
    ``agents.orchestrate.live_assess_cluster`` (bound to a real Analyst agent via
    ``functools.partial``) instead; the risk gate stays deterministic either way.
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
        assessment = assess_cluster(cluster.cluster_id, members, risk)
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
                # ARCHITECTURE.md's clusters/ spec calls for the analyst output,
                # which is the name AND the hazard statement. The statement is
                # the part a reviewer actually reads first.
                "hazard_statement": assessment.hazard_statement,
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
    return strip_uncited_claims(raw, allowed_acns=assessment.member_acns).cleaned_brief


def demo_reports() -> list[ASRSReport]:
    """Small public-data-shaped fixture; no external download or credentials required."""
    return [
        ASRSReport(
            acn=str(1000000 + index),
            narrative=(
                "During landing rollout the crew observed an uncommanded engine shutdown "
                "indication and completed the checklist."
            ),
            anomaly_labels=("Aircraft Equipment Problem Critical",),
            aircraft_type="Regional Jet",
            flight_phase="Landing Rollout",
            component="Engine Control",
            results=("Flight Crew Inflight Shutdown",),
            date_yyyymm=f"20220{index}",
        )
        for index in range(1, 7)
    ]


def load_dataset_slice(path: Path, *, slice_size: int | None, seed: int) -> list[ASRSReport]:
    """Load a real ASRS Parquet split and take a deterministic, seeded sample.

    Delegates to ``pipeline.ingest.load_parquet``, which already refuses to read
    the locked holdout copy — that guard is not duplicated here.
    """
    reports = load_parquet(path)
    if slice_size is None or slice_size >= len(reports):
        return reports
    return random.Random(seed).sample(reports, slice_size)


def _brief_for(
    assessment: ClusterAssessment,
    all_reports: Sequence[ASRSReport],
    by_acn: dict[str, ASRSReport],
    live_brief_kwargs: dict | None,
) -> str:
    """Live Coordinator+Critic for an escalated cluster in --live mode, else the
    deterministic template. Escalated clusters only get the live brief — that's
    where the architecture's threshold gate puts the expensive stage, and it's
    also what keeps a live run to a handful of calls instead of one per cluster.
    A coordinator failure (fewer than 2 of 3 sub-agents survived) falls back to
    the deterministic brief rather than dropping the cluster from the batch.
    """
    if live_brief_kwargs is not None and assessment.risk.escalated:
        from agents.orchestrate import CoordinatorFailure, live_draft_brief

        members = [by_acn[acn] for acn in assessment.member_acns]
        try:
            return live_draft_brief(assessment, members, all_reports, **live_brief_kwargs)
        except CoordinatorFailure:
            pass
    return draft_brief(assessment)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run VIGIL's batch triage pipeline")
    parser.add_argument("--demo", action="store_true", help="run the bundled six-report demo")
    parser.add_argument(
        "--dataset", type=Path, help="path to a real ASRS train/validation Parquet split"
    )
    parser.add_argument(
        "--slice",
        type=int,
        default=None,
        help="deterministic sample size drawn from --dataset (e.g. 5000)",
    )
    parser.add_argument("--seed", type=int, default=42, help="seed for --slice sampling")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    parser.add_argument(
        "--live",
        action="store_true",
        help="use a real Analyst LlmAgent call per cluster instead of the deterministic "
        "naming stand-in (needs live Gemini credentials)",
    )
    parser.add_argument(
        "--fail-agent",
        action="append",
        default=[],
        choices=["precedent", "risk", "brief_writer", "critic"],
        metavar="NAME",
        help="fault injection for the failure-tolerance demo: make this coordinator "
        "sub-agent raise instead of calling the model. Repeatable. Requires --live. "
        "Killing one leaves a DEGRADED brief; killing two of three falls back to the "
        "deterministic template. Never use for a run whose output will be published.",
    )
    parser.add_argument(
        "--firestore",
        action="store_true",
        help="persist reports/clusters/agent_log/escalations to Firestore instead of "
        "in-memory (needs GOOGLE_CLOUD_PROJECT and ADC)",
    )
    args = parser.parse_args()
    if bool(args.demo) == bool(args.dataset):
        parser.error("pass exactly one of --demo or --dataset PATH")
    if args.fail_agent and not args.live:
        parser.error("--fail-agent only affects the live coordinator; pass --live too")
    if args.fail_agent:
        # Loud and on stderr: an injected run must never be mistaken for a real
        # one when someone finds its output later. The DEGRADED banner in the
        # brief says a sub-agent failed; only this line says we caused it.
        print(
            f"!! FAULT INJECTION ACTIVE: {', '.join(sorted(args.fail_agent))} will raise. "
            "This run's briefs are a failure-tolerance demonstration, not real output.",
            file=sys.stderr,
        )
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    reports = (
        demo_reports()
        if args.demo
        else load_dataset_slice(args.dataset, slice_size=args.slice, seed=args.seed)
    )
    store: TriageStore
    if args.firestore:
        from pipeline.store import FirestoreStore

        store = FirestoreStore()
    else:
        store = MemoryStore()
    assess_cluster: AssessClusterFn = _assess_cluster
    live_brief_kwargs: dict | None = None
    if args.live:
        from functools import partial

        from agents.definitions import build_agent_graph, load_models
        from agents.orchestrate import live_assess_cluster

        graph = build_agent_graph()
        models = load_models()
        assess_cluster = partial(
            live_assess_cluster, analyst=graph["analyst"], model=models["flash"], store=store
        )
        live_brief_kwargs = {
            "precedent": graph["precedent"],
            "risk": graph["risk"],
            "brief_writer": graph["brief_writer"],
            "critic": graph["critic"],
            "model": models["flash"],
            "brief_writer_model": models["brief_writer"],
            "store": store,
            "fail_agents": frozenset(args.fail_agent),
        }
    assessments = run_batch(reports, policy=policy, store=store, assess_cluster=assess_cluster)
    by_acn = {report.acn: report for report in reports}
    payload = []
    for assessment in assessments:
        if assessment.cluster_id.startswith("noise-"):
            continue
        brief = _brief_for(assessment, reports, by_acn, live_brief_kwargs)
        # Briefs are drafted in this second pass, after triage_batch has written
        # the cluster documents, so they need their own write. Without it the
        # brief exists only in this process's stdout/--output JSON and never
        # reaches the store the UI and the audit trail read from.
        store.put_cluster_brief(assessment.cluster_id, brief)
        payload.append({**asdict(assessment), "brief": brief})
    output = json.dumps(payload, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
