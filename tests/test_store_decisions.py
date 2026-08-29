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
