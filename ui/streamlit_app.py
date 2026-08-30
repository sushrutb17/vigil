"""Streamlit UI for reviewing VIGIL cluster drafts.

Approval is intentionally a terminal human action. This app never sends or files
any report externally.

Data source, in priority order:
1. ``artifacts/demo_run.json`` — a committed snapshot of a real ``--live`` run
   over the real ASRS slice. This is what the deployed Cloud Run service serves:
   reviewers get genuine model-written briefs over real data instantly, with no
   per-pageview model cost, no cold-start latency, and no dependence on API
   quota holding up across a month-long judging window.
2. The bundled six-report fixture, if that artifact is absent (a fresh clone
   that has not run the pipeline yet still gets a working UI).

Regenerate the artifact with ``make artifact``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Collection
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import streamlit as st

from agents.critic import extract_cited_acns, strip_uncited_claims
from pipeline.risk import FrozenRiskPolicy
from pipeline.run_batch import build_cluster_evidence, demo_reports, draft_brief, run_triage
from pipeline.store import (
    MAX_REJECTION_REASON_LENGTH,
    MemoryStore,
    RejectionReasonError,
    TriageStore,
)

ARTIFACT_PATH = Path("artifacts/demo_run.json")


@st.cache_resource(show_spinner=False)
def _get_store() -> TriageStore:
    """One store instance per Streamlit session, shared across button-click reruns.

    Mirrors the ``--firestore`` selection in ``pipeline/run_batch.py``: when this
    app runs on Cloud Run against real data, ``GOOGLE_CLOUD_PROJECT`` is set and
    Approve/Reject decisions land in the same Firestore project the batch job
    wrote clusters/escalations to. Locally (no env var, no credentials needed),
    decisions still persist for the lifetime of the running UI process.
    """
    if os.environ.get("GOOGLE_CLOUD_PROJECT"):
        from pipeline.store import FirestoreStore

        return FirestoreStore()
    return MemoryStore()


@dataclass(frozen=True, slots=True)
class ApprovalOutcome:
    """Result of re-running the citation gate against a human-edited brief.

    A pure, browser-free decision so approval logic is testable without
    Streamlit (T1-03, docs/TIER1_ENHANCEMENTS_SPEC.md 8.3).
    """

    approved: bool
    value: dict[str, Any] | None
    removed_claims: tuple[str, ...] = ()
    fabricated_citations: tuple[str, ...] = ()


def evaluate_approval(
    original_draft: str, edited_brief: str, allowed_acns: Collection[str]
) -> ApprovalOutcome:
    """Re-run the deterministic citation gate against human-edited text before
    any approval is persisted. Guardrail #4 makes no exception for a human
    edit: an uncited line or an ACN outside the allow-list blocks approval
    outright, rather than silently storing a gate-stripped version the human
    never saw (8.1.3-4).
    """
    result = strip_uncited_claims(edited_brief, allowed_acns=allowed_acns)
    if not result.passed:
        return ApprovalOutcome(
            approved=False,
            value=None,
            removed_claims=result.removed_claims,
            fabricated_citations=result.fabricated_citations,
        )
    return ApprovalOutcome(
        approved=True,
        value={"brief_draft": original_draft, "brief_approved": result.cleaned_brief},
    )


def build_rejection_value(
    cluster: dict[str, Any], reason: str, edited_brief: str
) -> dict[str, Any]:
    """Pure construction of a ``record_rejection`` payload (5.4) -- testable
    without a browser. Reason validation itself lives in ``pipeline.store``,
    shared by both store implementations rather than duplicated here.
    """
    return {
        "reason": reason,
        "brief_draft": str(cluster["brief"]),
        "brief_at_rejection": edited_brief,
        "member_acns": list(cluster["members"]),
    }


def evidence_acns(cluster: dict[str, Any]) -> set[str]:
    """The citation-gate allow-list for an edited brief: every ACN this
    cluster has evidence for -- members plus any precedent already cited in
    the original draft (8.1.3). Falls back to plain membership for an
    artifact with no evidence field (legacy or pre-T1-02).
    """
    acns = {item["acn"] for item in cluster.get("evidence", [])}
    return acns or set(cluster["members"])


def _clusters_from_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": entry["cluster_id"],
            "name": entry["name"],
            "risk": entry["risk"]["total"],
            "escalated": entry["risk"]["escalated"],
            # Artifacts written before this field existed are single fresh
            # runs against an empty ledger, so every escalation in them is
            # by construction new.
            "new_this_run": entry.get("newly_escalated", entry["risk"]["escalated"]),
            "members": tuple(entry["member_acns"]),
            "facets": entry["facets"],
            "brief": entry["brief"],
            # Absent on artifacts written before T1-02 (legacy v1 lists and
            # pre-evidence v2 objects alike) -- the evidence selector simply
            # has nothing to show for those, rather than failing to load.
            "evidence": entry.get("evidence", []),
            # Absent on artifacts written before T1-04 -- the history panel
            # renders "First observed run" in that case, same as a cluster
            # with exactly one observation.
            "hazard_history": entry.get("hazard_history", []),
        }
        for entry in entries
    ]


def _singletons_from_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "acn": entry["acn"],
            "matched_severe_results": tuple(entry["matched_severe_results"]),
            "matched_severe_events": tuple(entry["matched_severe_events"]),
            "evidence": entry["evidence"],
        }
        for entry in entries
    ]


@st.cache_data(show_spinner=False)
def _load_artifact() -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, str]:
    """Return (clusters, severe_singletons, reports_triaged, source_label).

    Accepts the current artifact schema (a ``schema_version: 2`` object with
    ``run``/``clusters``/``severe_singletons``) and the legacy top-level list a
    pre-T1-01 artifact used. A legacy artifact produces an empty singleton
    queue and derives ``reports_triaged`` from visible cluster members (its own
    run predates the noise-vs-cluster split), rather than failing to load
    (T1-01, docs/TIER1_ENHANCEMENTS_SPEC.md 5.1).
    """
    if ARTIFACT_PATH.exists():
        payload = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            clusters = _clusters_from_entries(payload)
            singletons: list[dict[str, Any]] = []
            reports_triaged = sum(len(c["members"]) for c in clusters)
        elif isinstance(payload, dict):
            version = payload.get("schema_version")
            if version != 2:
                raise ValueError(f"unsupported artifact schema_version: {version!r}")
            clusters = _clusters_from_entries(payload["clusters"])
            singletons = _singletons_from_entries(payload.get("severe_singletons", []))
            reports_triaged = payload["run"]["reports_triaged"]
        else:
            raise ValueError("artifact must be a JSON object (schema v2) or list (legacy)")
        return clusters, singletons, reports_triaged, "real ASRS slice · live Gemini agents"

    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    reports = demo_reports()
    by_acn = {report.acn: report for report in reports}
    assessments, severe, hazards = run_triage(reports, policy=policy, store=MemoryStore())
    clusters = []
    for assessment in assessments:
        brief = draft_brief(assessment)
        hazard = hazards.get(assessment.cluster_id)
        clusters.append(
            {
                "id": assessment.cluster_id,
                "name": assessment.name,
                "risk": assessment.risk.total,
                "escalated": assessment.risk.escalated,
                "new_this_run": assessment.newly_escalated,
                "members": assessment.member_acns,
                "facets": assessment.facets,
                "brief": brief,
                "evidence": build_cluster_evidence(
                    assessment.cluster_id, assessment, brief, by_acn
                ),
                "hazard_history": (
                    [asdict(observation) for observation in hazard.history] if hazard else []
                ),
            }
        )
    singletons = [
        {
            "acn": singleton.acn,
            "matched_severe_results": singleton.matched_severe_results,
            "matched_severe_events": singleton.matched_severe_events,
            "evidence": asdict(singleton.evidence),
        }
        for singleton in severe
    ]
    return clusters, singletons, len(reports), "bundled fixture · no credentials required"


def _sorted_choices(clusters: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Escalated clusters first, then by descending risk — an analyst's queue order."""
    ordered = sorted(clusters, key=lambda c: (not c["escalated"], -c["risk"]))
    return {
        f"{'⚠ ' if c['escalated'] else ''}{'🆕 ' if c['new_this_run'] else ''}"
        f"{c['name']} · risk {c['risk']:.2f}": c
        for c in ordered
    }


def _render_evidence_panel(evidence: dict[str, Any]) -> None:
    """One evidence record's detail view -- narrative excerpt, date, flight
    phase, component, anomaly labels, and result labels. Shared by the T1-02
    cluster evidence drill-down and the T1-01 severe-singleton queue.

    Missing optional metadata renders as "Not recorded" rather than a blank
    panel (T1-02, docs/TIER1_ENHANCEMENTS_SPEC.md section 7.1.6). A missing
    narrative is not handled here: build_cluster_evidence/find_severe_singletons
    fail artifact generation instead of ever reaching a blank panel for that.
    """
    left, right = st.columns([1, 1])
    with left:
        st.write("**Flight phase:**", evidence.get("flight_phase") or "Not recorded")
        st.write("**Component:**", evidence.get("component") or "Not recorded")
        st.write("**Report month:**", evidence.get("date_yyyymm") or "Not recorded")
    with right:
        anomaly_labels = evidence.get("anomaly_labels") or []
        results = evidence.get("results") or []
        st.write("**Anomaly labels:**", ", ".join(anomaly_labels) or "Not recorded")
        st.write("**Results:**", ", ".join(results) or "Not recorded")

    st.markdown("**Narrative excerpt**")
    excerpt = evidence.get("narrative_excerpt", "")
    st.write(excerpt + ("…" if evidence.get("narrative_truncated") else ""))


def _render_cluster_evidence(cluster: dict[str, Any]) -> None:
    """T1-02 ACN evidence drill-down: replaces the old comma-separated
    member-ACN list with a selector covering every cluster member plus any
    precedent ACN the brief cites from outside the cluster.

    ACNs cited in the current brief are listed first (member or precedent
    alike); precedent entries are labeled distinctly from cluster membership
    (docs/TIER1_ENHANCEMENTS_SPEC.md section 7.1).
    """
    evidence_list = cluster.get("evidence", [])
    if not evidence_list:
        return
    cited = set(extract_cited_acns(str(cluster["brief"])))
    # A stable sort preserves each group's existing deterministic order
    # (member ACNs sorted, then precedent ACNs sorted) while moving cited
    # entries to the front.
    ordered = sorted(evidence_list, key=lambda item: item["acn"] not in cited)
    choices = {
        f"{'📌 ' if item['acn'] in cited else ''}ACN {item['acn']} · "
        f"{'Precedent evidence' if item['role'] == 'precedent' else 'Cluster member'}": item
        for item in ordered
    }
    selected_label = st.selectbox("Evidence", list(choices), key=f"evidence-{cluster['id']}")
    _render_evidence_panel(choices[selected_label])


def _render_hazard_history(cluster: dict[str, Any]) -> None:
    """T1-04 cross-run hazard identity: observation date, member count, and
    frozen risk total across runs. Purely descriptive -- it renders whatever
    ``run_batch`` already recorded and never recomputes or alters the risk
    score shown elsewhere on this cluster (docs/TIER1_ENHANCEMENTS_SPEC.md
    9.2.3, 9.2.7). The "NEW THIS RUN" badge stays driven by the escalation
    ledger alone; hazard identity does not touch it (9.2.6).
    """
    history = sorted(cluster.get("hazard_history", []), key=lambda obs: obs["run_at"])
    if not history:
        return
    if len(history) < 2:
        st.caption("First observed run")
        return
    counts = " → ".join(str(observation["member_count"]) for observation in history)
    st.write(f"**Seen in {len(history)} runs** · {counts} reports")
    st.line_chart([observation["member_count"] for observation in history], height=100)
    with st.expander("Observation history"):
        st.table(
            [
                {
                    "Run": observation["run_at"],
                    "Members": observation["member_count"],
                    "Risk total": observation["risk_total"],
                }
                for observation in history
            ]
        )


def _render_cluster_queue(clusters: list[dict[str, Any]]) -> None:
    choices = _sorted_choices(clusters)
    selected_label = st.sidebar.selectbox("Hazard clusters", list(choices))
    cluster = choices[selected_label]

    left, right = st.columns([1, 1])
    with left:
        st.subheader(str(cluster["name"]))
        if cluster["new_this_run"]:
            # The signal an analyst actually wants: not "is this severe" (the
            # risk score says that) but "is this severe AND something I have not
            # already been alerted about". It comes from the escalation ledger's
            # member-set overlap check, so a pattern that merely persists across
            # weeks stays quiet instead of re-alerting every Monday.
            st.success("🆕 NEW THIS RUN — not covered by any previous escalation")
        st.metric("Deterministic risk", f"{cluster['risk']:.2f}")
        st.write(
            "**Status:**",
            "Escalation draft" if cluster["escalated"] else "Below threshold",
        )
        st.write("**Source reports:**", f"{len(cluster['members'])} ACNs")
        st.json(cluster["facets"], expanded=False)
        _render_cluster_evidence(cluster)
        _render_hazard_history(cluster)
    with right:
        st.subheader("Investigator draft")
        store = _get_store()
        state_key = f"decision-{cluster['id']}"
        editor_key = f"editor-{cluster['id']}"
        reason_key = f"reason-{cluster['id']}"
        decision = st.session_state.get(state_key)

        if decision is None:
            # key=editor_key (not tied to the evidence selection above) is what
            # preserves the human's in-progress edit across reruns triggered by
            # switching the evidence ACN or any other widget on this page
            # (8.1.2).
            edited = st.text_area(
                "Edit draft (Markdown)",
                value=str(cluster["brief"]),
                key=editor_key,
                height=280,
            )
            reason = st.text_area(
                "Rejection reason (required to reject)",
                key=reason_key,
                max_chars=MAX_REJECTION_REASON_LENGTH,
                help=(
                    "Trimmed before persisting. Blank or over "
                    f"{MAX_REJECTION_REASON_LENGTH} characters cannot be submitted (8.1.7)."
                ),
            )
            controls = st.columns(2)
            if controls[0].button("Approve draft", type="primary"):
                outcome = evaluate_approval(str(cluster["brief"]), edited, evidence_acns(cluster))
                if outcome.approved:
                    store.record_approval(cluster["id"], outcome.value)
                    st.session_state[state_key] = {
                        "status": "approved",
                        "brief_approved": outcome.value["brief_approved"],
                    }
                    st.rerun()
                else:
                    if outcome.removed_claims:
                        st.error(
                            "Blocked: every factual line must cite an ACN. Uncited line(s):\n"
                            + "\n".join(f"- {line}" for line in outcome.removed_claims)
                        )
                    if outcome.fabricated_citations:
                        st.error(
                            "Blocked: cites an ACN outside this cluster's evidence: "
                            + ", ".join(outcome.fabricated_citations)
                        )
            if controls[1].button("Reject draft"):
                try:
                    store.record_rejection(
                        cluster["id"], build_rejection_value(cluster, reason, edited)
                    )
                except RejectionReasonError as exc:
                    st.error(str(exc))
                else:
                    # Written to rejections/ as a negative few-shot example
                    # (ARCHITECTURE.md "State & memory") so a future Analyst
                    # prompt-revision pass can be told what a human already
                    # rejected, not just what got escalated.
                    st.session_state[state_key] = {"status": "rejected", "reason": reason.strip()}
                    st.rerun()
        elif decision["status"] == "approved":
            # Terminal: the editor is gone, replaced by the immutable
            # approved text (8.1.6, 8.1.10).
            st.code(decision["brief_approved"], language="markdown")
            st.success("Approved by human — persisted to store. The editor is now locked.")
            st.download_button(
                "Download approved brief (Markdown)",
                data=decision["brief_approved"],
                file_name=f"vigil-brief-{cluster['id']}.md",
                mime="text/markdown",
                help=(
                    "The human carries the approved text onward. "
                    "VIGIL never sends or files anything."
                ),
            )
        else:
            st.code(str(cluster["brief"]), language="markdown")
            st.warning(
                "Rejected by human — persisted as a negative example for future Analyst "
                f"prompts. Reason: {decision['reason']}"
            )


def _render_singleton_queue(singletons: list[dict[str, Any]]) -> None:
    """T1-01: HDBSCAN noise that matches the frozen severe vocabulary directly.

    Deliberately no Analyst name, hazard statement, risk score, or brief here —
    this is a source report surfaced for human review, not a fabricated
    one-report cluster (docs/TIER1_ENHANCEMENTS_SPEC.md, T1-01 section 6.1.8).
    """
    choices = {
        f"ACN {s['acn']} · {len(s['matched_severe_results']) + len(s['matched_severe_events'])} "
        f"matched term(s)": s
        for s in singletons
    }
    selected_label = st.sidebar.selectbox("Severe singletons", list(choices))
    singleton = choices[selected_label]
    evidence = singleton["evidence"]

    st.subheader(f"Severe singleton · ACN {singleton['acn']}")
    st.caption(
        "Did not join any hazard cluster this run (HDBSCAN noise). Surfaced because it "
        "matches the frozen severe-result/severe-event vocabulary directly — a categorical "
        "check, not a cluster risk score."
    )
    if singleton["matched_severe_results"]:
        st.write("**Matched severe results:**", ", ".join(singleton["matched_severe_results"]))
    if singleton["matched_severe_events"]:
        st.write("**Matched severe events:**", ", ".join(singleton["matched_severe_events"]))

    _render_evidence_panel(evidence)


def main() -> None:
    st.set_page_config(page_title="VIGIL", page_icon="◉", layout="wide")
    st.title("VIGIL")
    st.caption("Public ASRS safety-signal triage · drafts only · human approval is terminal")

    clusters, singletons, reports_triaged, source_label = _load_artifact()
    if not clusters and not singletons:
        st.info("No hazard clusters or severe singletons in this batch.")
        return

    escalated_count = sum(1 for cluster in clusters if cluster["escalated"])
    summary = st.columns(4)
    summary[0].metric("Hazard clusters", len(clusters))
    summary[1].metric("Escalated for review", escalated_count)
    summary[2].metric("Severe singletons", len(singletons))
    summary[3].metric("Reports triaged", reports_triaged)
    st.caption(f"Source: {source_label}")

    queue_options = ["Hazard clusters"]
    if singletons:
        queue_options.append(f"Severe singletons ({len(singletons)})")
    queue = st.sidebar.radio("Queue", queue_options) if len(queue_options) > 1 else queue_options[0]

    if queue == "Hazard clusters":
        if clusters:
            _render_cluster_queue(clusters)
        else:
            st.info("No hazard clusters in this batch — check Severe singletons.")
    else:
        _render_singleton_queue(singletons)

    st.divider()
    st.caption(
        "Risk thresholds are loaded read-only from config/frozen.yaml and are never "
        "self-tuned. Every claim above cites an ACN; uncited claims are stripped "
        "deterministically before display."
    )


if __name__ == "__main__":
    main()
