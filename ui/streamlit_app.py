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
from dataclasses import asdict
from pathlib import Path
from typing import Any

import streamlit as st

from agents.critic import extract_cited_acns
from pipeline.risk import FrozenRiskPolicy
from pipeline.run_batch import build_cluster_evidence, demo_reports, draft_brief, run_triage
from pipeline.store import MemoryStore, TriageStore

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


def _cluster_payload(cluster: dict[str, Any]) -> dict[str, Any]:
    return {
        "cluster_id": cluster["id"],
        "name": cluster["name"],
        "risk": cluster["risk"],
        "escalated": cluster["escalated"],
        "new_this_run": cluster["new_this_run"],
        "member_acns": list(cluster["members"]),
        "facets": cluster["facets"],
        "brief": str(cluster["brief"]),
    }


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
    assessments, severe = run_triage(reports, policy=policy, store=MemoryStore())
    clusters = []
    for assessment in assessments:
        brief = draft_brief(assessment)
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
    with right:
        st.subheader("Investigator draft")
        st.code(str(cluster["brief"]), language="markdown")
        store = _get_store()
        state_key = f"decision-{cluster['id']}"
        if state_key not in st.session_state:
            st.session_state[state_key] = "Pending human review"
        controls = st.columns(2)
        if controls[0].button("Approve draft", type="primary"):
            store.set_cluster_status(cluster["id"], "approved")
            st.session_state[state_key] = "Approved by human — persisted to store"
        if controls[1].button("Reject draft"):
            store.set_cluster_status(cluster["id"], "rejected")
            # Written to rejections/ as a negative few-shot example (ARCHITECTURE.md
            # "State & memory") so a future Analyst prompt-revision pass can be
            # told what a human already rejected, not just what got escalated.
            store.put_rejection(cluster["id"], _cluster_payload(cluster))
            st.session_state[state_key] = (
                "Rejected by human — persisted as a negative example for future Analyst prompts"
            )
        st.info(st.session_state[state_key])
        st.download_button(
            "Download brief (Markdown)",
            data=str(cluster["brief"]),
            file_name=f"vigil-brief-{cluster['id']}.md",
            mime="text/markdown",
            help="The human carries the draft onward. VIGIL never sends or files anything.",
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
