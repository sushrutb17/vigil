"""Tests for T1-04 -- cross-run hazard identity and history.

Covers docs/TIER1_ENHANCEMENTS_SPEC.md section 9.5's required list: identity
matching and its threshold/tie-break rules, idempotent observations keyed by
run_id, chronological history ordering, noise/below-threshold hazard-ID
behavior, risk isolation, per-instance state isolation, and a Streamlit
AppTest smoke test for first- and multi-observation views. The Firestore
transactional path's cross-instance idempotency is proven for real against a
live emulator in tests/test_firestore_emulator.py, not mocked here.
"""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pipeline.models import ASRSReport
from pipeline.risk import FrozenRiskPolicy, score_cluster
from pipeline.run_batch import demo_reports, run_triage
from pipeline.store import MemoryStore, match_hazard

POLICY = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))


def _report(acn: str, *, results: tuple[str, ...] = ()) -> ASRSReport:
    return ASRSReport(acn=acn, narrative=f"Narrative for {acn}.", results=results)


def _non_severe_reports(count: int = 6) -> list[ASRSReport]:
    """Clusters together (same narrative/facets as demo_reports()'s pattern)
    but carries no severe result/label, so severity stays 0 and the total
    risk score is well under the 0.60 escalation threshold regardless of
    trend -- used to prove a non-escalating cluster still gets a hazard ID."""
    return [
        ASRSReport(
            acn=str(2000000 + index),
            narrative=(
                "During cruise the crew noted a minor cabin temperature fluctuation "
                "and adjusted the environmental control system."
            ),
            aircraft_type="Regional Jet",
            flight_phase="Cruise",
            component="Environmental Control",
            date_yyyymm=f"20220{index}",
        )
        for index in range(1, count + 1)
    ]


def test_an_unmatched_cluster_creates_one_hazard_and_one_observation() -> None:
    store = MemoryStore()

    record = store.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=frozenset({"1", "2", "3"}),
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    assert len(store.hazards) == 1
    assert record.observation_count == 1
    assert len(record.history) == 1


def test_exact_repeat_members_match_the_existing_hazard() -> None:
    store = MemoryStore()
    members = frozenset({"1", "2", "3"})

    first = store.record_hazard_observation(
        cluster_id="c1",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )
    second = store.record_hazard_observation(
        cluster_id="c2",
        display_name="Fume events",
        member_acns=members,
        risk_total=0.6,
        run_id="run-2",
        run_at="2026-01-08T00:00:00Z",
    )

    assert second.hazard_id == first.hazard_id
    assert len(store.hazards) == 1
    assert second.observation_count == 2


def test_similarity_of_exactly_0_6_does_not_match_and_above_it_does() -> None:
    at_threshold = frozenset({"1", "2", "3"})  # vs {1..5}: 3/5 = 0.6 exactly
    candidates = {"hazard-x": frozenset({"1", "2", "3", "4", "5"})}
    assert match_hazard(at_threshold, candidates) is None

    just_above = frozenset({"1", "2"})  # vs {1,2,3}: 2/3 = 0.667 > 0.6
    candidates2 = {"hazard-x": frozenset({"1", "2", "3"})}
    assert match_hazard(just_above, candidates2) == "hazard-x"


def test_the_highest_overlap_hazard_wins() -> None:
    member_acns = frozenset({"1", "2", "3", "4"})
    candidates = {
        "hazard-a": frozenset({"1", "2", "3", "4", "5", "6"}),  # 4/6 = 0.667
        "hazard-b": frozenset({"1", "2", "3", "4", "5"}),  # 4/5 = 0.8, highest
    }

    assert match_hazard(member_acns, candidates) == "hazard-b"


def test_tie_breaking_is_deterministic_by_lexicographically_smallest_hazard_id() -> None:
    member_acns = frozenset({"1", "2", "3", "4"})
    candidates = {
        "hazard-z": frozenset({"1", "2", "3", "4", "5"}),  # 0.8
        "hazard-a": frozenset({"1", "2", "3", "4", "6"}),  # 0.8, tied
    }

    assert match_hazard(member_acns, candidates) == "hazard-a"


def test_latest_member_acns_becomes_the_newest_set_not_a_cumulative_union() -> None:
    store = MemoryStore()
    first_members = frozenset({"1", "2", "3", "4", "5"})
    second_members = frozenset({"2", "3", "4", "5", "6"})  # jaccard 4/6 = 0.667

    store.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=first_members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )
    record = store.record_hazard_observation(
        cluster_id="c2",
        display_name="x",
        member_acns=second_members,
        risk_total=0.5,
        run_id="run-2",
        run_at="2026-01-08T00:00:00Z",
    )

    assert set(record.latest_member_acns) == second_members
    assert set(record.latest_member_acns) != first_members | second_members


def test_rerunning_the_same_run_id_does_not_increment_count_or_add_a_point() -> None:
    store = MemoryStore()
    members = frozenset({"1", "2", "3"})
    kwargs = {
        "cluster_id": "c1",
        "display_name": "x",
        "member_acns": members,
        "risk_total": 0.5,
        "run_id": "run-1",
        "run_at": "2026-01-01T00:00:00Z",
    }

    first = store.record_hazard_observation(**kwargs)
    second = store.record_hazard_observation(**kwargs)

    assert first.observation_count == second.observation_count == 1
    assert len(second.history) == 1


def test_a_new_run_id_appends_exactly_one_point() -> None:
    store = MemoryStore()
    members = frozenset({"1", "2", "3"})
    store.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    second = store.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=members,
        risk_total=0.6,
        run_id="run-2",
        run_at="2026-01-08T00:00:00Z",
    )

    assert second.observation_count == 2
    assert len(second.history) == 2


def test_history_returns_in_chronological_order_even_when_inserted_out_of_order() -> None:
    store = MemoryStore()
    members = frozenset({"1", "2", "3", "4", "5"})

    store.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=members,
        risk_total=0.5,
        run_id="run-3",
        run_at="2026-01-15T00:00:00Z",
    )
    store.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=members,
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )
    record = store.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=members,
        risk_total=0.5,
        run_id="run-2",
        run_at="2026-01-08T00:00:00Z",
    )

    assert [observation.run_id for observation in record.history] == ["run-1", "run-2", "run-3"]


def test_noise_creates_no_hazard() -> None:
    # Fewer reports than min_cluster_size (5): every report is HDBSCAN noise.
    reports = [
        _report(str(index), results=("Flight Crew Inflight Shutdown",)) for index in range(3)
    ]
    store = MemoryStore()

    assessments, singletons, hazards = run_triage(reports, policy=POLICY, store=store)

    assert assessments == []
    assert hazards == {}
    assert store.hazards == {}


def test_below_threshold_non_noise_clusters_still_receive_a_hazard_id() -> None:
    reports = _non_severe_reports()
    store = MemoryStore()

    assessments, _singletons, hazards = run_triage(reports, policy=POLICY, store=store)

    assert assessments, "fixture must actually cluster, not fall to noise"
    assert not assessments[0].risk.escalated
    assert assessments[0].cluster_id in hazards
    assert hazards[assessments[0].cluster_id].observation_count == 1


def test_risk_components_and_total_are_unchanged_by_history_recording() -> None:
    reports = demo_reports()
    store = MemoryStore()

    assessments, _singletons, hazards = run_triage(reports, policy=POLICY, store=store)
    # An independent recomputation of the same batch's risk, entirely outside
    # run_triage/the hazard store -- score_cluster never receives or reads
    # hazard state, so this must match byte-for-byte.
    risk_alone = score_cluster(reports, POLICY)

    assert assessments[0].risk == risk_alone
    assert hazards, "history recording did happen for this run"


def test_two_isolated_memorystore_instances_do_not_leak_history() -> None:
    store_a = MemoryStore()
    store_b = MemoryStore()

    store_a.record_hazard_observation(
        cluster_id="c1",
        display_name="x",
        member_acns=frozenset({"1", "2", "3"}),
        risk_total=0.5,
        run_id="run-1",
        run_at="2026-01-01T00:00:00Z",
    )

    assert store_b.hazards == {}


_ARTIFACT_WITH_HAZARD_HISTORY = {
    "schema_version": 2,
    "run": {"run_id": "test-run-2", "run_at": "2026-01-08T00:00:00Z", "reports_triaged": 12},
    "clusters": [
        {
            "cluster_id": "cluster-first",
            "name": "First-observation cluster",
            "hazard_statement": "x",
            "risk": {
                "total": 0.69,
                "escalated": True,
                "severity": 1.0,
                "frequency": 0.3,
                "trend": 0.5,
            },
            "member_acns": ["1000001"],
            "facets": {},
            "newly_escalated": True,
            "brief": "# Draft\n[ACN 1000001] x",
            "evidence": [],
            "hazard_history": [
                {
                    "run_id": "run-1",
                    "run_at": "2026-01-01T00:00:00Z",
                    "cluster_id": "cluster-first",
                    "member_count": 12,
                    "risk_total": 0.69,
                }
            ],
        },
        {
            "cluster_id": "cluster-repeat",
            "name": "Multi-observation cluster",
            "hazard_statement": "x",
            "risk": {
                "total": 0.40,
                "escalated": False,
                "severity": 0.2,
                "frequency": 0.3,
                "trend": 0.5,
            },
            "member_acns": ["2000001"],
            "facets": {},
            "newly_escalated": False,
            "brief": "# Draft\n[ACN 2000001] y",
            "evidence": [],
            "hazard_history": [
                {
                    "run_id": "run-1",
                    "run_at": "2026-01-01T00:00:00Z",
                    "cluster_id": "cluster-repeat",
                    "member_count": 12,
                    "risk_total": 0.35,
                },
                {
                    "run_id": "run-2",
                    "run_at": "2026-01-08T00:00:00Z",
                    "cluster_id": "cluster-repeat",
                    "member_count": 19,
                    "risk_total": 0.40,
                },
            ],
        },
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


def _rendered_text(at: AppTest) -> str:
    return " ".join(
        element.value
        for kind in ("markdown", "caption", "subheader")
        for element in at.main.get(kind)
    )


def test_first_observation_view_shows_first_observed_run(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT_WITH_HAZARD_HISTORY)
    selectbox = at.sidebar.selectbox[0]
    first_option = next(o for o in selectbox.options if "First-observation" in o)

    selectbox.set_value(first_option).run()

    assert not at.exception, at.exception
    assert "First observed run" in _rendered_text(at)


def test_multi_observation_view_shows_the_seen_in_n_runs_summary(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT_WITH_HAZARD_HISTORY)
    selectbox = at.sidebar.selectbox[0]
    repeat_option = next(o for o in selectbox.options if "Multi-observation" in o)

    selectbox.set_value(repeat_option).run()

    assert not at.exception, at.exception
    rendered = _rendered_text(at)
    assert "Seen in 2 runs" in rendered
    assert "12 → 19" in rendered
