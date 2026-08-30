"""Tests for the human-gate decision persistence added to TriageStore.

Covers the Approve/Reject -> store wiring: `set_cluster_status` must not
clobber fields a batch job already wrote for a cluster (a merge update, not
an overwrite), and `put_rejection` must record a negative example under its
own key, per ARCHITECTURE.md's `rejections/` collection.

Also covers T1-03's `record_approval`/`record_rejection`
(docs/TIER1_ENHANCEMENTS_SPEC.md section 8.4): both must preserve fields a
batch job already wrote (same merge discipline as the pre-T1-03 methods
above), and `record_rejection`'s reason validation must block invalid input
before any write -- neither the status flip nor the rejection record.
"""

from unittest.mock import MagicMock

import pytest

from pipeline.store import (
    MAX_REJECTION_REASON_LENGTH,
    FirestoreStore,
    MemoryStore,
    RejectionReasonError,
)


def test_set_cluster_status_preserves_existing_fields() -> None:
    store = MemoryStore()
    store.put_cluster("c1", {"name": "Fume events", "risk": 0.82, "status": "escalated"})

    store.set_cluster_status("c1", "approved")

    assert store.clusters["c1"] == {
        "name": "Fume events",
        "risk": 0.82,
        "status": "approved",
    }


def test_set_cluster_status_on_unknown_cluster_creates_a_record() -> None:
    store = MemoryStore()

    store.set_cluster_status("c-new", "rejected")

    assert store.clusters["c-new"]["status"] == "rejected"


def test_put_cluster_brief_merges_into_the_existing_cluster_record() -> None:
    """Briefs are written in a second pass, after triage_batch has already
    created the cluster document. The write must merge, not overwrite, or the
    analyst output and risk score from the first pass are lost."""
    store = MemoryStore()
    store.put_cluster("c1", {"name": "Fume events", "risk_score": 0.82, "status": "escalated"})

    store.put_cluster_brief("c1", "## Draft\n[ACN 1000001] Crew reported fumes.")

    assert store.clusters["c1"] == {
        "name": "Fume events",
        "risk_score": 0.82,
        "status": "escalated",
        "brief": "## Draft\n[ACN 1000001] Crew reported fumes.",
    }


def test_put_cluster_brief_leaves_status_untouched() -> None:
    """status carries the new/escalated distinction behind the "NEW THIS RUN"
    badge and the escalation dedup ledger. Drafting a brief must not advance it."""
    store = MemoryStore()
    store.put_cluster("c1", {"status": "new"})

    store.put_cluster_brief("c1", "## Draft\n[ACN 1000001] ...")

    assert store.clusters["c1"]["status"] == "new"


def test_put_rejection_records_a_negative_example_keyed_by_cluster() -> None:
    store = MemoryStore()
    payload = {
        "cluster_id": "c1",
        "name": "Fume events",
        "member_acns": ["1000001", "1000002"],
        "brief": "## Draft brief\n[ACN 1000001] ...",
    }

    store.put_rejection("c1", payload)

    assert store.rejections["c1"] == payload
    assert "c2" not in store.clusters


def test_approving_unchanged_valid_text_stores_identical_draft_and_approved_fields() -> None:
    store = MemoryStore()
    store.put_cluster("c1", {"name": "Fume events", "risk_score": 0.82, "status": "escalated"})
    draft = "# Draft\n[ACN 1000001] Crew reported fumes."

    store.record_approval("c1", {"brief_draft": draft, "brief_approved": draft})

    assert store.clusters["c1"]["status"] == "approved"
    assert store.clusters["c1"]["brief_draft"] == draft
    assert store.clusters["c1"]["brief_approved"] == draft


def test_approving_a_valid_edit_stores_the_original_and_edited_versions_separately() -> None:
    store = MemoryStore()
    draft = "# Draft\n[ACN 1000001] Crew reported fumes."
    edited = "# Draft\n[ACN 1000001] Crew reported an odor in the cabin."

    store.record_approval("c1", {"brief_draft": draft, "brief_approved": edited})

    assert store.clusters["c1"]["brief_draft"] == draft
    assert store.clusters["c1"]["brief_approved"] == edited
    assert store.clusters["c1"]["brief_draft"] != store.clusters["c1"]["brief_approved"]


def test_record_approval_preserves_existing_cluster_fields() -> None:
    """Same merge discipline as set_cluster_status: an approval must not
    clobber the name/risk/member fields the batch job already wrote."""
    store = MemoryStore()
    store.put_cluster(
        "c1", {"name": "Fume events", "risk_score": 0.82, "member_acns": ["1000001"]}
    )

    store.record_approval("c1", {"brief_draft": "d", "brief_approved": "d"})

    assert store.clusters["c1"]["name"] == "Fume events"
    assert store.clusters["c1"]["risk_score"] == 0.82
    assert store.clusters["c1"]["member_acns"] == ["1000001"]


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
def test_blank_and_whitespace_only_rejection_reasons_are_rejected(reason: str) -> None:
    store = MemoryStore()
    store.put_cluster("c1", {"name": "Fume events", "status": "escalated"})

    with pytest.raises(RejectionReasonError):
        store.record_rejection(
            "c1",
            {"reason": reason, "brief_draft": "d", "brief_at_rejection": "d", "member_acns": []},
        )

    # No write at all -- neither the status flip nor the rejection record.
    assert store.clusters["c1"]["status"] == "escalated"
    assert "c1" not in store.rejections


def test_a_2001_character_reason_is_rejected_2000_characters_is_accepted() -> None:
    store = MemoryStore()
    value = {"brief_draft": "d", "brief_at_rejection": "d", "member_acns": []}

    with pytest.raises(RejectionReasonError):
        store.record_rejection("c1", {**value, "reason": "x" * (MAX_REJECTION_REASON_LENGTH + 1)})
    assert "c1" not in store.rejections

    store.record_rejection("c2", {**value, "reason": "x" * MAX_REJECTION_REASON_LENGTH})
    assert store.rejections["c2"]["reason"] == "x" * MAX_REJECTION_REASON_LENGTH


def test_rejection_reason_is_trimmed_before_persistence() -> None:
    store = MemoryStore()

    store.record_rejection(
        "c1",
        {
            "reason": "  Overstates the cited evidence.  ",
            "brief_draft": "d",
            "brief_at_rejection": "d",
            "member_acns": [],
        },
    )

    assert store.rejections["c1"]["reason"] == "Overstates the cited evidence."


def test_a_rejection_preserves_original_cluster_name_risk_members_and_draft() -> None:
    store = MemoryStore()
    store.put_cluster(
        "c1",
        {
            "name": "Fume events",
            "risk_score": 0.82,
            "member_acns": ["1000001", "1000002"],
            "brief": "# Draft\n[ACN 1000001] Crew reported fumes.",
        },
    )

    store.record_rejection(
        "c1",
        {
            "reason": "Overstates the cited evidence.",
            "brief_draft": "# Draft\n[ACN 1000001] Crew reported fumes.",
            "brief_at_rejection": "# Draft\n[ACN 1000001] Crew reported fumes.",
            "member_acns": ["1000001", "1000002"],
        },
    )

    cluster = store.clusters["c1"]
    assert cluster["name"] == "Fume events"
    assert cluster["risk_score"] == 0.82
    assert cluster["member_acns"] == ["1000001", "1000002"]
    assert cluster["brief"] == "# Draft\n[ACN 1000001] Crew reported fumes."
    assert cluster["status"] == "rejected"


def test_a_simulated_firestore_failure_cannot_leave_status_rejected_without_the_record() -> None:
    """record_rejection uses one Firestore batch for the status flip and the
    rejection record (8.2). A batch's set() calls only queue writes locally;
    nothing reaches Firestore until commit(). So if commit() raises, neither
    write took effect -- proven here by asserting commit() is the only call
    that can fail and is invoked exactly once, after both sets were already
    queued on the very same batch object.
    """
    store = FirestoreStore.__new__(FirestoreStore)  # skip __init__: no real client needed
    batch = MagicMock()
    batch.commit.side_effect = RuntimeError("simulated Firestore outage")
    db = MagicMock()
    db.batch.return_value = batch
    store._db = db
    store._firestore = MagicMock()

    with pytest.raises(RuntimeError, match="simulated Firestore outage"):
        store.record_rejection(
            "c1",
            {
                "reason": "Not enough evidence.",
                "brief_draft": "d",
                "brief_at_rejection": "d",
                "member_acns": ["1000001"],
            },
        )

    assert batch.set.call_count == 2
    batch.commit.assert_called_once()
