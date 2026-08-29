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
from pathlib import Path
from typing import Any

import streamlit as st

from pipeline.risk import FrozenRiskPolicy
from pipeline.run_batch import demo_reports, draft_brief, run_batch
from pipeline.store import MemoryStore

ARTIFACT_PATH = Path("artifacts/demo_run.json")


@st.cache_data(show_spinner=False)
def _load_clusters() -> tuple[list[dict[str, Any]], str]:
    """Return (clusters, source_label) from the real-run artifact or the fixture."""
    if ARTIFACT_PATH.exists():
        payload = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
        clusters = [
            {
                "id": entry["cluster_id"],
                "name": entry["name"],
                "risk": entry["risk"]["total"],
                "escalated": entry["risk"]["escalated"],
                "members": tuple(entry["member_acns"]),
                "facets": entry["facets"],
                "brief": entry["brief"],
            }
            for entry in payload
        ]
        return clusters, "real ASRS slice · live Gemini agents"

    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    assessments = run_batch(demo_reports(), policy=policy, store=MemoryStore())
    clusters = [
        {
            "id": assessment.cluster_id,
            "name": assessment.name,
            "risk": assessment.risk.total,
            "escalated": assessment.risk.escalated,
            "members": assessment.member_acns,
            "facets": assessment.facets,
            "brief": draft_brief(assessment),
        }
        for assessment in assessments
        if not assessment.cluster_id.startswith("noise-")
    ]
    return clusters, "bundled fixture · no credentials required"


def _sorted_choices(clusters: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Escalated clusters first, then by descending risk — an analyst's queue order."""
    ordered = sorted(clusters, key=lambda c: (not c["escalated"], -c["risk"]))
    return {
        f"{'⚠ ' if c['escalated'] else ''}{c['name']} · risk {c['risk']:.2f}": c for c in ordered
    }


def main() -> None:
    st.set_page_config(page_title="VIGIL", page_icon="◉", layout="wide")
    st.title("VIGIL")
    st.caption("Public ASRS safety-signal triage · drafts only · human approval is terminal")

    clusters, source_label = _load_clusters()
    if not clusters:
        st.info("No non-noise clusters in this batch.")
        return

    escalated_count = sum(1 for cluster in clusters if cluster["escalated"])
    summary = st.columns(3)
    summary[0].metric("Hazard clusters", len(clusters))
    summary[1].metric("Escalated for review", escalated_count)
    summary[2].metric("Reports triaged", sum(len(c["members"]) for c in clusters))
    st.caption(f"Source: {source_label}")

    choices = _sorted_choices(clusters)
    selected_label = st.sidebar.selectbox("Hazard clusters", list(choices))
    cluster = choices[selected_label]

    left, right = st.columns([1, 1])
    with left:
        st.subheader(str(cluster["name"]))
        st.metric("Deterministic risk", f"{cluster['risk']:.2f}")
        st.write(
            "**Status:**",
            "Escalation draft" if cluster["escalated"] else "Below threshold",
        )
        st.write("**Source reports:**", f"{len(cluster['members'])} ACNs")
        with st.expander("Source ACNs"):
            st.write(", ".join(cluster["members"]))
        st.json(cluster["facets"], expanded=False)
    with right:
        st.subheader("Investigator draft")
        st.code(str(cluster["brief"]), language="markdown")
        state_key = f"decision-{cluster['id']}"
        if state_key not in st.session_state:
            st.session_state[state_key] = "Pending human review"
        controls = st.columns(2)
        if controls[0].button("Approve draft", type="primary"):
            st.session_state[state_key] = "Approved by human"
        if controls[1].button("Reject draft"):
            st.session_state[state_key] = "Rejected by human; retain as negative example"
        st.info(st.session_state[state_key])
        st.download_button(
            "Download brief (Markdown)",
            data=str(cluster["brief"]),
            file_name=f"vigil-brief-{cluster['id']}.md",
            mime="text/markdown",
            help="The human carries the draft onward. VIGIL never sends or files anything.",
        )

    st.divider()
    st.caption(
        "Risk thresholds are loaded read-only from config/frozen.yaml and are never "
        "self-tuned. Every claim above cites an ACN; uncited claims are stripped "
        "deterministically before display."
    )


if __name__ == "__main__":
    main()
