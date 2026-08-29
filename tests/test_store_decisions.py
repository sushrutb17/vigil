"""Tests for the human-gate decision persistence added to TriageStore.

Covers the Approve/Reject -> store wiring: `set_cluster_status` must not
clobber fields a batch job already wrote for a cluster (a merge update, not
an overwrite), and `put_rejection` must record a negative example under its
own key, per ARCHITECTURE.md's `rejections/` collection.
"""

from pipeline.store import MemoryStore


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
