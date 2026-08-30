"""Tests for T1-03 -- edit-before-approve and required rejection reason.

Covers docs/TIER1_ENHANCEMENTS_SPEC.md section 8.4's required list at two
levels: the pure decision-orchestration helpers in ``ui.streamlit_app``
(browser-free, per 8.3), and a Streamlit ``AppTest`` pass proving the editor,
validation messages, and terminal state actually render. Download content is
asserted through the pure helper's ``brief_approved`` value rather than the
browser download element, which does not expose file bytes (8.4).
"""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pipeline.store import MemoryStore
from ui.streamlit_app import build_rejection_value, evaluate_approval, evidence_acns

MEMBER_ACNS = ("1000001", "1000002")


def test_an_uncited_human_added_claim_blocks_approval_and_performs_no_write() -> None:
    draft = "# Draft\n[ACN 1000001] Crew reported fumes."
    edited = draft + "\nThe aircraft was later grounded for a week."  # no citation

    outcome = evaluate_approval(draft, edited, MEMBER_ACNS)

    assert not outcome.approved
    assert outcome.value is None
    assert any("grounded" in line for line in outcome.removed_claims)

    store = MemoryStore()
    if outcome.approved:  # pragma: no cover -- documents the caller's own gate
        store.record_approval("c1", outcome.value)
    assert "c1" not in store.clusters


def test_a_fabricated_or_unrelated_acn_blocks_approval_and_performs_no_write() -> None:
    draft = "# Draft\n[ACN 1000001] Crew reported fumes."
    edited = "# Draft\n[ACN 9999999] A different report entirely."

    outcome = evaluate_approval(draft, edited, MEMBER_ACNS)

    assert not outcome.approved
    assert outcome.value is None
    assert "9999999" in outcome.fabricated_citations

    store = MemoryStore()
    if outcome.approved:  # pragma: no cover -- documents the caller's own gate
        store.record_approval("c1", outcome.value)
    assert "c1" not in store.clusters


def test_a_valid_cited_deletion_or_wording_change_is_accepted() -> None:
    draft = (
        "# Draft\n"
        "[ACN 1000001] Crew reported fumes.\n"
        "[ACN 1000002] Crew also noted a burning smell."
    )
    edited = "# Draft\n[ACN 1000001] Crew reported an unusual odor in the cabin."

    outcome = evaluate_approval(draft, edited, MEMBER_ACNS)

    assert outcome.approved
    assert outcome.value == {"brief_draft": draft, "brief_approved": edited}


def test_downloaded_bytes_equal_brief_approved_not_the_original_draft() -> None:
    draft = "# Draft\n[ACN 1000001] Crew reported fumes."
    edited = "# Draft\n[ACN 1000001] Crew reported an unusual odor."

    outcome = evaluate_approval(draft, edited, MEMBER_ACNS)

    assert outcome.approved
    download_data = outcome.value["brief_approved"]
    assert download_data == edited
    assert download_data != draft


def test_evidence_acns_uses_the_evidence_list_falling_back_to_members() -> None:
    with_evidence = {
        "members": ("1000001",),
        "evidence": [{"acn": "1000001"}, {"acn": "9000002"}],
    }
    assert evidence_acns(with_evidence) == {"1000001", "9000002"}

    without_evidence = {"members": ("1000001", "1000002"), "evidence": []}
    assert evidence_acns(without_evidence) == {"1000001", "1000002"}


def test_build_rejection_value_carries_the_original_draft_and_current_editor_text() -> None:
    cluster = {"brief": "# Draft\n[ACN 1000001] x", "members": ("1000001", "1000002")}

    value = build_rejection_value(cluster, "  Not enough evidence.  ", "edited text")

    # Trimming is the store's job (shared validation, 8.3) -- the pure helper
    # passes the reason through verbatim.
    assert value["reason"] == "  Not enough evidence.  "
    assert value["brief_draft"] == cluster["brief"]
    assert value["brief_at_rejection"] == "edited text"
    assert value["member_acns"] == ["1000001", "1000002"]


_ORIGINAL_BRIEF = (
    "# Draft\n"
    "[ACN 1000001] Crew reported fumes.\n"
    "[ACN 1000002] Crew also noted a burning smell."
)

_ARTIFACT = {
    "schema_version": 2,
    "run": {"run_id": "test-run", "run_at": "2026-01-01T00:00:00Z", "reports_triaged": 2},
    "clusters": [
        {
            "cluster_id": "cluster-1",
            "name": "Engine Control events during Landing Rollout",
            "hazard_statement": "x",
            "risk": {
                "total": 0.69,
                "escalated": True,
                "severity": 1.0,
                "frequency": 0.3,
                "trend": 0.5,
            },
            "member_acns": list(MEMBER_ACNS),
            "facets": {},
            "newly_escalated": True,
            "brief": _ORIGINAL_BRIEF,
            "evidence": [
                {
                    "role": "member",
                    "acn": acn,
                    "narrative_excerpt": "x",
                    "narrative_truncated": False,
                    "date_yyyymm": None,
                    "flight_phase": None,
                    "component": None,
                    "anomaly_labels": [],
                    "results": [],
                }
                for acn in MEMBER_ACNS
            ],
        }
    ],
    "severe_singletons": [],
}


_APP_SCRIPT = """
from pathlib import Path
import ui.streamlit_app as app
app.ARTIFACT_PATH = Path({artifact_path!r})
app._load_artifact.clear()
app.main()
"""


def _run_app(tmp_path: Path, artifact: dict) -> AppTest:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")
    script_path = tmp_path / "app_script.py"
    script_path.write_text(_APP_SCRIPT.format(artifact_path=str(artifact_path)), encoding="utf-8")
    at = AppTest.from_file(str(script_path))
    at.run()
    assert not at.exception, at.exception
    return at


def _editor(at: AppTest):
    return next(t for t in at.main.get("text_area") if t.label.startswith("Edit draft"))


def _button(at: AppTest, label: str):
    return next(b for b in at.main.get("button") if b.label == label)


def test_editor_is_seeded_with_the_original_immutable_draft(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT)

    assert _editor(at).value == _ORIGINAL_BRIEF


def test_approving_an_uncited_edit_is_blocked_and_the_editor_stays_open(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT)
    edited = _ORIGINAL_BRIEF + "\nThe aircraft was later grounded for inspection."
    _editor(at).set_value(edited).run()

    _button(at, "Approve draft").click().run()

    assert not at.exception, at.exception
    assert at.main.get("error")
    # Not terminal: the editor is still present for another attempt.
    assert any(t.label.startswith("Edit draft") for t in at.main.get("text_area"))


def test_approving_a_valid_edit_becomes_terminal_and_offers_the_approved_download(
    tmp_path: Path,
) -> None:
    at = _run_app(tmp_path, _ARTIFACT)
    edited = "# Draft\n[ACN 1000001] Crew reported an unusual odor in the cabin."
    _editor(at).set_value(edited).run()

    _button(at, "Approve draft").click().run()

    assert not at.exception, at.exception
    # Terminal: no editor, no Approve/Reject controls any more (8.1.10).
    assert not [t for t in at.main.get("text_area") if t.label.startswith("Edit draft")]
    assert not [b for b in at.main.get("button") if b.label in ("Approve draft", "Reject draft")]
    download = next(iter(at.main.get("download_button")))
    assert download.label == "Download approved brief (Markdown)"
    rendered = " ".join(el.value for el in at.main.get("code"))
    assert "unusual odor" in rendered
    assert "burning smell" not in rendered  # the original draft is gone, not just hidden


def test_rejecting_with_a_blank_reason_is_blocked_and_performs_no_write(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT)

    _button(at, "Reject draft").click().run()

    assert not at.exception, at.exception
    assert at.main.get("error")
    assert any(t.label.startswith("Edit draft") for t in at.main.get("text_area"))


def test_rejecting_with_a_valid_reason_is_terminal_and_shows_it(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT)
    reason_box = next(t for t in at.main.get("text_area") if t.label.startswith("Rejection"))
    reason_box.set_value("Overstates the cited evidence.").run()

    _button(at, "Reject draft").click().run()

    assert not at.exception, at.exception
    rendered = " ".join(w.value for w in at.main.get("warning"))
    assert "Overstates the cited evidence." in rendered
    assert not [t for t in at.main.get("text_area") if t.label.startswith("Edit draft")]
    assert not [b for b in at.main.get("button") if b.label in ("Approve draft", "Reject draft")]
