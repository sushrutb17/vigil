"""Streamlit UI for reviewing local/demo VIGIL cluster drafts.

Approval is intentionally a terminal human action. This app never sends or files
any report externally.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pipeline.risk import FrozenRiskPolicy
from pipeline.run_batch import demo_reports, draft_brief, run_batch
from pipeline.store import MemoryStore


@st.cache_data(show_spinner=False)
def _load_demo() -> list[dict[str, object]]:
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    assessments = run_batch(demo_reports(), policy=policy, store=MemoryStore())
    return [
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


def main() -> None:
    st.set_page_config(page_title="VIGIL", page_icon="◉", layout="wide")
    st.title("VIGIL")
    st.caption("Public ASRS safety-signal triage · drafts only · human approval is terminal")
    clusters = _load_demo()
    if not clusters:
        st.info("No non-noise clusters in this batch.")
        return
    choices = {f"{cluster['name']} · risk {cluster['risk']:.2f}": cluster for cluster in clusters}
    selected_label = st.sidebar.selectbox("Hazard clusters", list(choices))
    cluster = choices[selected_label]
    left, right = st.columns([1, 1])
    with left:
        st.subheader(str(cluster["name"]))
        st.metric("Deterministic risk", f"{cluster['risk']:.2f}")
        st.write("**Status:**", "Escalation draft" if cluster["escalated"] else "Below threshold")
        st.write("**Source ACNs:**", ", ".join(cluster["members"]))
        st.json(cluster["facets"])
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
    st.divider()
    st.caption(
        "Demo mode uses a local fixture. Firestore persistence and live ADK calls "
        "activate only with configured cloud credentials."
    )


if __name__ == "__main__":
    main()
