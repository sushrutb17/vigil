"""Resumable batch runner that keeps model-free orchestration in plain Python."""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from agents.critic import extract_cited_acns, format_citations, strip_uncited_claims
from pipeline.cluster import cluster_reports
from pipeline.ingest import load_parquet
from pipeline.models import (
    ASRSReport,
    ClusterAssessment,
    EvidenceRecord,
    HazardRecord,
    JsonDict,
    RiskScore,
    SevereSingleton,
)
from pipeline.risk import FrozenRiskPolicy, score_cluster, severe_matches
from pipeline.store import MemoryStore, TriageStore

#: Cap applied to a normalized narrative before it is embedded in an artifact or
#: evidence record. Whitespace is normalized first so the cap counts meaningful
#: characters, not raw formatting (T1-01, docs/TIER1_ENHANCEMENTS_SPEC.md 5.2).
NARRATIVE_EXCERPT_LIMIT = 500

AssessClusterFn = Callable[[str, Sequence[ASRSReport], RiskScore], ClusterAssessment]


def new_run_context() -> tuple[str, str]:
    """Generate the (run_id, run_at) pair once per logical run.

    Hazard observations (T1-04) must key off the same ``run_id`` as the
    artifact they end up embedded in, so callers that need both generate this
    once and thread it through rather than letting each stage mint its own
    (T1-04, docs/TIER1_ENHANCEMENTS_SPEC.md 9.4).
    """
    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:6]}"
    run_at = datetime.now(UTC).isoformat()
    return run_id, run_at


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

    Thin wrapper over ``run_triage`` for callers that only need cluster
    assessments (the pre-T1-01 public contract; every existing caller and test
    keeps working unchanged). Use ``run_triage`` directly when the severe
    singleton queue or hazard history is also needed, to avoid clustering the
    batch twice.
    """
    assessments, _singletons, _hazards = run_triage(
        reports, policy=policy, store=store, assess_cluster=assess_cluster
    )
    return assessments


def run_triage(
    reports: Sequence[ASRSReport],
    *,
    policy: FrozenRiskPolicy,
    store: TriageStore,
    assess_cluster: AssessClusterFn = _assess_cluster,
    run_id: str | None = None,
    run_at: str | None = None,
) -> tuple[list[ClusterAssessment], list[SevereSingleton], dict[str, HazardRecord]]:
    """Ingest, deterministically cluster, score, and persist a batch; separately
    flag HDBSCAN noise reports against the frozen severe vocabulary and match
    every non-noise cluster to a persistent cross-run hazard identity.

    ``assess_cluster`` defaults to a deterministic structured-field stand-in so
    the no-credentials demo path is unaffected. A live run passes
    ``agents.orchestrate.live_assess_cluster`` (bound to a real Analyst agent via
    ``functools.partial``) instead; the risk gate stays deterministic either way.

    Noise reports never reach ``assess_cluster``: carrying ``Cluster.noise``
    explicitly (rather than relying on the ``noise-`` id prefix elsewhere in the
    codebase) means a live run never spends a real Analyst call naming a bucket
    of unrelated one-off reports that never surfaces in the UI as a cluster
    anyway (T1-01, docs/TIER1_ENHANCEMENTS_SPEC.md).

    ``run_id``/``run_at`` default to a freshly generated pair when omitted (the
    pre-T1-04 callers that don't care about hazard history), but a caller that
    also builds an artifact from the same run must generate them once via
    ``new_run_context()`` and pass the same pair to both, or the hazard
    observation would be keyed to a different run than the artifact it ends up
    embedded in (T1-04, 9.4).
    """
    if run_id is None or run_at is None:
        generated_id, generated_at = new_run_context()
        run_id = run_id or generated_id
        run_at = run_at or generated_at
    for report in reports:
        store.put_report(report.acn, asdict(report))
    clusters = cluster_reports(
        reports,
        min_cluster_size=int(policy.clustering.get("min_cluster_size", 5)),
        min_samples=int(policy.clustering.get("min_samples", 3)),
    )
    by_acn = {report.acn: report for report in reports}
    assessments: list[ClusterAssessment] = []
    noise_reports: list[ASRSReport] = []
    for cluster in clusters:
        if cluster.noise:
            noise_reports.extend(by_acn[acn] for acn in cluster.member_acns)
            continue
        members = [by_acn[acn] for acn in cluster.member_acns]
        risk = score_cluster(members, policy)
        assessment = assess_cluster(cluster.cluster_id, members, risk)
        already_escalated = store.previously_escalated(frozenset(cluster.member_acns))
        newly_escalated = risk.escalated and not already_escalated
        status = "escalated" if newly_escalated else "new"
        if newly_escalated:
            store.record_escalation(frozenset(cluster.member_acns))
        assessment = replace(assessment, newly_escalated=newly_escalated)
        store.put_cluster(
            cluster.cluster_id,
            {
                "member_acns": list(cluster.member_acns),
                "risk_score": risk.total,
                "status": status,
                "name": assessment.name,
                # ARCHITECTURE.md's clusters/ spec calls for the analyst output,
                # which is the name AND the hazard statement. The statement is
                # the part a reviewer actually reads first.
                "hazard_statement": assessment.hazard_statement,
            },
        )
        assessments.append(assessment)
    ranked = sorted(assessments, key=lambda assessment: assessment.risk.total, reverse=True)
    # Every non-noise cluster gets a hazard identity, escalated or not (9.2.1);
    # noise reports never reach this loop since `assessments` excludes them by
    # construction above. Purely descriptive bookkeeping -- it runs after
    # `risk` was already computed and never feeds back into it (9.2.7).
    hazards = {
        assessment.cluster_id: store.record_hazard_observation(
            cluster_id=assessment.cluster_id,
            display_name=assessment.name,
            member_acns=frozenset(assessment.member_acns),
            risk_total=assessment.risk.total,
            run_id=run_id,
            run_at=run_at,
        )
        for assessment in ranked
    }
    return ranked, find_severe_singletons(noise_reports, policy), hazards


def _build_evidence(report: ASRSReport) -> EvidenceRecord:
    """Normalize whitespace before applying the excerpt cap, so the cap counts
    meaningful characters rather than raw formatting (T1-01 5.2)."""
    normalized = " ".join(report.narrative.split())
    return EvidenceRecord(
        acn=report.acn,
        narrative_excerpt=normalized[:NARRATIVE_EXCERPT_LIMIT],
        narrative_truncated=len(normalized) > NARRATIVE_EXCERPT_LIMIT,
        date_yyyymm=report.date_yyyymm,
        flight_phase=report.flight_phase,
        component=report.component,
        anomaly_labels=report.anomaly_labels,
        results=report.results,
    )


def build_cluster_evidence(
    cluster_id: str,
    assessment: ClusterAssessment,
    brief: str,
    by_acn: Mapping[str, ASRSReport],
) -> list[JsonDict]:
    """Evidence for every cluster member plus any cited precedent ACN outside it.

    Deterministic order: member ACNs sorted, then cited non-members sorted
    (T1-02, docs/TIER1_ENHANCEMENTS_SPEC.md 5.2, 7.1). Each record carries a
    ``role`` of ``"member"`` or ``"precedent"`` so the UI can label precedent
    evidence distinctly rather than presenting it as cluster membership.

    Raises ``ValueError`` naming the cluster and ACN when the brief cites an
    ACN this run has no normalized report for -- the UI must never render a
    citation whose evidence is knowingly missing (5.1).
    """
    member_acns = set(assessment.member_acns)
    precedent_acns = sorted(acn for acn in extract_cited_acns(brief) if acn not in member_acns)
    records: list[JsonDict] = [
        {"role": "member", **asdict(_build_evidence(by_acn[acn]))} for acn in sorted(member_acns)
    ]
    for acn in precedent_acns:
        report = by_acn.get(acn)
        if report is None:
            raise ValueError(
                f"cluster {cluster_id} brief cites ACN {acn}, which does not resolve to a "
                "normalized report in this run -- cannot build its evidence record"
            )
        records.append({"role": "precedent", **asdict(_build_evidence(report))})
    return records


def find_severe_singletons(
    reports: Sequence[ASRSReport], policy: FrozenRiskPolicy
) -> list[SevereSingleton]:
    """Flag HDBSCAN noise reports against the frozen severe vocabulary.

    A categorical triage rule (``pipeline.risk.severe_matches``), not a
    one-report risk score -- see ``SevereSingleton``'s docstring. Sorted by
    report month descending, then ACN ascending, with missing months sorted
    last (T1-01 section 6.1.5).
    """
    by_acn = {report.acn: report for report in reports}
    singletons = []
    for report in reports:
        matched_results, matched_events = severe_matches(report, policy)
        if matched_results or matched_events:
            singletons.append(
                SevereSingleton(
                    acn=report.acn,
                    matched_severe_results=matched_results,
                    matched_severe_events=matched_events,
                    evidence=_build_evidence(report),
                )
            )

    def _sort_key(singleton: SevereSingleton) -> tuple[int, int, str]:
        month = by_acn[singleton.acn].date_yyyymm
        if month and month.isdigit():
            return (0, -int(month), singleton.acn)
        return (1, 0, singleton.acn)

    return sorted(singletons, key=_sort_key)


def build_artifact_payload(
    reports: Sequence[ASRSReport],
    assessments: Sequence[ClusterAssessment],
    briefs: Mapping[str, str],
    singletons: Sequence[SevereSingleton],
    hazards: Mapping[str, HazardRecord] | None = None,
    *,
    run_id: str | None = None,
    run_at: str | None = None,
) -> JsonDict:
    """Assemble the schema-v2 artifact object written by ``--output``/``make artifact``.

    ``run_id``/``run_at`` are generated once here by default; tests pass
    explicit values instead so output is reproducible (T1-01 5.1). ``hazards``
    is optional and keyed by ``cluster_id`` -- callers that don't pass one
    simply get no ``hazard_id``/``hazard_history`` on their cluster entries
    (T1-04, 9.4), which keeps every pre-T1-04 caller of this function working
    unchanged.
    """
    if run_id is None or run_at is None:
        generated_id, generated_at = new_run_context()
        run_id = run_id or generated_id
        run_at = run_at or generated_at
    by_acn = {report.acn: report for report in reports}
    hazards = hazards or {}
    return {
        "schema_version": 2,
        "run": {
            "run_id": run_id,
            "run_at": run_at,
            # Counts every normalized input report, including HDBSCAN noise --
            # not just the members visible in a cluster or singleton queue.
            "reports_triaged": len(reports),
        },
        "clusters": [
            {
                **asdict(assessment),
                "brief": briefs[assessment.cluster_id],
                "evidence": build_cluster_evidence(
                    assessment.cluster_id, assessment, briefs[assessment.cluster_id], by_acn
                ),
                **_hazard_payload(hazards.get(assessment.cluster_id)),
            }
            for assessment in assessments
        ],
        "severe_singletons": [asdict(singleton) for singleton in singletons],
    }


def _hazard_payload(record: HazardRecord | None) -> JsonDict:
    """``{}`` when no hazard record is available, so a cluster entry simply
    has no ``hazard_id``/``hazard_history`` keys rather than nulls."""
    if record is None:
        return {}
    return {
        "hazard_id": record.hazard_id,
        "hazard_history": [asdict(observation) for observation in record.history],
    }


def draft_brief(assessment: ClusterAssessment) -> str:
    """Create a local, source-cited draft suitable for UI and critic demos."""
    citations = format_citations(assessment.member_acns)
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
    if args.live and not os.environ.get("GOOGLE_API_KEY"):
        # The Makefile's require-key target guards `make run-live`/`artifact`/
        # `improve`, but not a direct `python -m pipeline.run_batch --live`,
        # which is exactly the form the README's failure-tolerance section tells
        # a reader to run. Without this, the key is missing until ADK builds its
        # client deep inside three worker threads, and the real cause arrives
        # buried in ~700 lines of traceback from a crashed thread.
        parser.error(
            "--live needs GOOGLE_API_KEY. Put it in .env (gitignored) and run "
            "`set -a; source .env; set +a`, or export it, then retry."
        )
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
    # Generated once and threaded through both calls below: the hazard
    # observation and the artifact it ends up embedded in must key off the
    # same run_id (T1-04, docs/TIER1_ENHANCEMENTS_SPEC.md 9.4).
    run_id, run_at = new_run_context()
    assessments, singletons, hazards = run_triage(
        reports,
        policy=policy,
        store=store,
        assess_cluster=assess_cluster,
        run_id=run_id,
        run_at=run_at,
    )
    by_acn = {report.acn: report for report in reports}
    briefs: dict[str, str] = {}
    for assessment in assessments:
        brief = _brief_for(assessment, reports, by_acn, live_brief_kwargs)
        # Briefs are drafted in this second pass, after triage_batch has written
        # the cluster documents, so they need their own write. Without it the
        # brief exists only in this process's stdout/--output JSON and never
        # reaches the store the UI and the audit trail read from.
        store.put_cluster_brief(assessment.cluster_id, brief)
        briefs[assessment.cluster_id] = brief
    artifact = build_artifact_payload(
        reports, assessments, briefs, singletons, hazards, run_id=run_id, run_at=run_at
    )
    for cluster_entry in artifact["clusters"]:
        # Only the ACN list goes to the store; narrative excerpts stay in the
        # artifact/reports/{acn} documents so a cluster document never
        # duplicates narrative text (T1-02, docs/TIER1_ENHANCEMENTS_SPEC.md 5.2).
        store.put_cluster_evidence(
            cluster_entry["cluster_id"], [item["acn"] for item in cluster_entry["evidence"]]
        )
    output = json.dumps(artifact, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
