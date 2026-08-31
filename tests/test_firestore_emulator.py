"""Live-emulator proof for FirestoreStore's atomic/idempotent T1-03 and T1-04
behavior (docs/TIER1_ENHANCEMENTS_SPEC.md section 12: "The Firestore emulator
run may be conditional in ordinary local tests, but it is mandatory before
marking T1-03 or T1-04 Done. A mocked Firestore client alone does not prove
cross-process persistence or atomic document behavior.").

Skipped entirely unless FIRESTORE_EMULATOR_HOST is set, so the rest of the
suite never needs Java or the emulator installed. Run with:

    export FIRESTORE_EMULATOR_HOST=localhost:8080
    uv run pytest tests/test_firestore_emulator.py -q
"""

from __future__ import annotations

import os
import uuid

import pytest

from pipeline.store import FirestoreStore, RejectionReasonError

pytestmark = pytest.mark.skipif(
    "FIRESTORE_EMULATOR_HOST" not in os.environ,
    reason="requires a running Firestore emulator (see module docstring)",
)


@pytest.fixture
def project() -> str:
    # A fresh project name per test run keeps collections isolated between
    # test functions in the same emulator instance.
    return f"vigil-test-{uuid.uuid4().hex[:8]}"


def test_record_rejection_writes_status_and_rejection_record_atomically(project: str) -> None:
    store = FirestoreStore(project=project)
    store.put_cluster("c1", {"name": "Fume events", "risk_score": 0.82, "status": "escalated"})

    store.record_rejection(
        "c1",
        {
            "reason": "  Overstates the cited evidence.  ",
            "brief_draft": "draft",
            "brief_at_rejection": "edited",
            "member_acns": ["1000001"],
        },
    )

    cluster_doc = store._db.collection("clusters").document("c1").get().to_dict()
    rejection_doc = store._db.collection("rejections").document("c1").get().to_dict()
    assert cluster_doc["status"] == "rejected"
    assert cluster_doc["name"] == "Fume events"  # merge, not overwrite
    assert rejection_doc["reason"] == "Overstates the cited evidence."  # trimmed
    assert rejection_doc["member_acns"] == ["1000001"]


def test_record_rejection_with_an_invalid_reason_writes_nothing(project: str) -> None:
    store = FirestoreStore(project=project)
    store.put_cluster("c1", {"name": "Fume events", "status": "escalated"})

    with pytest.raises(RejectionReasonError):
        store.record_rejection(
            "c1",
            {"reason": "   ", "brief_draft": "d", "brief_at_rejection": "d", "member_acns": []},
        )

    cluster_doc = store._db.collection("clusters").document("c1").get().to_dict()
    rejection_snapshot = store._db.collection("rejections").document("c1").get()
    assert cluster_doc["status"] == "escalated"
    assert not rejection_snapshot.exists


def test_record_approval_merges_into_the_existing_cluster_document(project: str) -> None:
    store = FirestoreStore(project=project)
    store.put_cluster("c1", {"name": "Fume events", "risk_score": 0.82, "status": "escalated"})

    store.record_approval("c1", {"brief_draft": "draft text", "brief_approved": "approved text"})

    doc = store._db.collection("clusters").document("c1").get().to_dict()
    assert doc["status"] == "approved"
    assert doc["name"] == "Fume events"
    assert doc["brief_draft"] == "draft text"
    assert doc["brief_approved"] == "approved text"
    assert doc["decision_at"] is not None


def test_hazard_observation_persists_and_is_visible_across_store_instances(project: str) -> None:
    """Cross-process persistence proof (9.6): two independent FirestoreStore
    instances pointed at the same project must see the same hazard state --
    a MemoryStore test cannot demonstrate this since its state never leaves
    the Python process.
    """
    writer = FirestoreStore(project=project)
    reader = FirestoreStore(project=project)
    members = frozenset({"1", "2", "3"})

    written = writer.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    hazard_doc = reader._db.collection("hazards").document(written.hazard_id).get().to_dict()
    assert hazard_doc["observation_count"] == 1
    assert set(hazard_doc["latest_member_acns"]) == members

    observations = list(
        reader._db.collection("hazards")
        .document(written.hazard_id)
        .collection("observations")
        .stream()
    )
    assert len(observations) == 1
    assert observations[0].id == "run-1"


def test_rerunning_the_same_run_id_from_a_second_store_instance_adds_no_duplicate(
    project: str,
) -> None:
    """The transactional retry/idempotency proof (9.5, 9.6): replaying the
    same logical run_id -- even from a completely separate FirestoreStore
    object, standing in for a retried process -- must not create a second
    observation document or double-count observation_count.
    """
    members = frozenset({"1", "2", "3"})
    first_store = FirestoreStore(project=project)
    first = first_store.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    second_store = FirestoreStore(project=project)
    second = second_store.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    assert second.hazard_id == first.hazard_id
    assert second.observation_count == 1
    observations = list(
        second_store._db.collection("hazards")
        .document(first.hazard_id)
        .collection("observations")
        .stream()
    )
    assert len(observations) == 1


def test_a_new_run_id_from_a_second_store_instance_appends_one_real_observation(
    project: str,
) -> None:
    members = frozenset({"1", "2", "3"})
    first_store = FirestoreStore(project=project)
    first = first_store.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    second_store = FirestoreStore(project=project)
    second = second_store.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.6,
        run_id="run-2",
        run_at="2026-01-08T00:00:00Z",
    )

    assert second.hazard_id == first.hazard_id
    assert second.observation_count == 2
    assert [observation.run_id for observation in second.history] == ["run-1", "run-2"]
