import sys
from pathlib import Path

import pytest

from pipeline.risk import FrozenRiskPolicy
from pipeline.run_batch import demo_reports, draft_brief, main, run_batch
from pipeline.store import MemoryStore


def test_demo_batch_escalates_a_cited_cluster() -> None:
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    store = MemoryStore()
    assessments = run_batch(demo_reports(), policy=policy, store=store)
    assert assessments
    assessment = assessments[0]
    assert not assessment.cluster_id.startswith("noise-")
    assert assessment.risk.escalated
    brief = draft_brief(assessment)
    assert "[ACN 1000001]" in brief
    assert "deliberately uncited" not in brief
    assert store.clusters[assessment.cluster_id]["status"] == "escalated"


def test_second_batch_does_not_re_escalate_same_members() -> None:
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    store = MemoryStore()
    run_batch(demo_reports(), policy=policy, store=store)
    assessments = run_batch(demo_reports(), policy=policy, store=store)
    assert store.clusters[assessments[0].cluster_id]["status"] == "new"


def test_newly_escalated_is_true_on_first_sight_and_false_on_repeat() -> None:
    """The NEW THIS RUN badge must not re-fire for a pattern already alerted."""
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    store = MemoryStore()
    reports = demo_reports()

    first = [a for a in run_batch(reports, policy=policy, store=store) if a.risk.escalated]
    assert first and all(a.newly_escalated for a in first)

    second = [a for a in run_batch(reports, policy=policy, store=store) if a.risk.escalated]
    assert second and not any(a.newly_escalated for a in second)


def test_live_without_an_api_key_exits_cleanly(monkeypatch, capsys) -> None:
    """--live must fail on a one-line message, not 700 lines of ADK traceback.

    The Makefile's require-key target only guards `make run-live`/`artifact`/
    `improve`. README's failure-tolerance section tells the reader to invoke the
    module directly, which skips make entirely -- so the guard has to live here.
    """
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr(
        sys, "argv", ["run_batch", "--demo", "--live", "--fail-agent", "risk"]
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert "GOOGLE_API_KEY" in capsys.readouterr().err
