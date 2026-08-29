"""Tests for T1-01 -- the severe-but-unclustered queue.

Covers docs/TIER1_ENHANCEMENTS_SPEC.md section 6.3's required list: reports
matching severe_results and/or severe_events qualify as singletons, non-severe
noise and severe non-noise reports do not, ordering is deterministic, no live
Analyst call is ever spent on noise, and the frozen policy is left untouched.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.risk import FrozenRiskPolicy, severe_matches
from pipeline.run_batch import (
    build_artifact_payload,
    demo_reports,
    find_severe_singletons,
    run_triage,
)
from pipeline.store import MemoryStore

POLICY = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))


def _report(
    acn: str,
    *,
    results: tuple[str, ...] = (),
    anomaly_labels: tuple[str, ...] = (),
    date_yyyymm: str | None = None,
) -> ASRSReport:
    return ASRSReport(
        acn=acn,
        narrative=f"Narrative for {acn}.",
        results=results,
        anomaly_labels=anomaly_labels,
        date_yyyymm=date_yyyymm,
    )


def test_a_noise_report_matching_severe_results_qualifies() -> None:
    report = _report("1", results=("Flight Crew Inflight Shutdown",))

    singletons = find_severe_singletons([report], POLICY)

    assert [s.acn for s in singletons] == ["1"]
    assert singletons[0].matched_severe_results == ("Flight Crew Inflight Shutdown",)
    assert singletons[0].matched_severe_events == ()


def test_a_noise_report_matching_severe_events_qualifies() -> None:
    report = _report("2", anomaly_labels=("Conflict NMAC",))

    singletons = find_severe_singletons([report], POLICY)

    assert [s.acn for s in singletons] == ["2"]
    assert singletons[0].matched_severe_events == ("Conflict NMAC",)
    assert singletons[0].matched_severe_results == ()


def test_a_report_matching_both_appears_once_with_both_reason_lists() -> None:
    report = _report(
        "3",
        results=("Flight Crew Inflight Shutdown",),
        anomaly_labels=("Conflict NMAC",),
    )

    singletons = find_severe_singletons([report], POLICY)

    assert len(singletons) == 1
    assert singletons[0].matched_severe_results == ("Flight Crew Inflight Shutdown",)
    assert singletons[0].matched_severe_events == ("Conflict NMAC",)


def test_a_non_severe_noise_report_does_not_qualify() -> None:
    report = _report("4", results=("Some Unrelated Result",))

    assert find_severe_singletons([report], POLICY) == []


def test_a_severe_non_noise_report_does_not_enter_the_singleton_queue() -> None:
    """demo_reports() is a 6-report fixture that clusters (not noise) and whose
    results already match severe_results -- it must show up as an assessment,
    never as a singleton."""
    reports = demo_reports()
    store = MemoryStore()

    assessments, singletons = run_triage(reports, policy=POLICY, store=store)

    assert assessments
    assert singletons == []


def test_missing_or_empty_result_anomaly_tuples_do_not_raise() -> None:
    report = _report("5")  # results=(), anomaly_labels=() by default

    assert find_severe_singletons([report], POLICY) == []


def test_output_ordering_is_deterministic() -> None:
    """Report month descending, then ACN ascending; missing months sort last."""
    reports = [
        _report("300", results=("Flight Crew Inflight Shutdown",), date_yyyymm="202401"),
        _report("100", results=("Flight Crew Inflight Shutdown",), date_yyyymm="202403"),
        _report("200", results=("Flight Crew Inflight Shutdown",), date_yyyymm="202403"),
        _report("050", results=("Flight Crew Inflight Shutdown",), date_yyyymm=None),
    ]

    singletons = find_severe_singletons(reports, POLICY)

    assert [s.acn for s in singletons] == ["100", "200", "300", "050"]

    # Shuffled input must not change the result.
    shuffled = find_severe_singletons(list(reversed(reports)), POLICY)
    assert [s.acn for s in shuffled] == ["100", "200", "300", "050"]


def test_a_fake_live_assessor_that_raises_if_called_is_not_called_for_noise() -> None:
    """A live run must never spend a real Analyst call naming a bucket of
    unrelated noise reports that never surfaces in the UI as a cluster."""

    def _raising_assessor(
        cluster_id: str, reports: list[ASRSReport], risk: RiskScore
    ) -> ClusterAssessment:
        raise AssertionError("assess_cluster must never be called for a noise cluster")

    # Fewer reports than min_cluster_size (5): every report is noise.
    reports = [
        _report(str(index), results=("Flight Crew Inflight Shutdown",)) for index in range(3)
    ]
    store = MemoryStore()

    assessments, singletons = run_triage(
        reports, policy=POLICY, store=store, assess_cluster=_raising_assessor
    )

    assert assessments == []
    assert len(singletons) == 3


def test_risk_weights_escalation_threshold_and_policy_bytes_are_unchanged_by_a_run() -> None:
    policy_path = Path("config/frozen.yaml")
    before = policy_path.read_bytes()
    weights_before = (POLICY.severity_weight, POLICY.frequency_weight, POLICY.trend_weight)
    threshold_before = POLICY.escalation_score

    run_triage(demo_reports(), policy=POLICY, store=MemoryStore())

    after = policy_path.read_bytes()
    assert before == after
    assert weights_before == (POLICY.severity_weight, POLICY.frequency_weight, POLICY.trend_weight)
    assert threshold_before == POLICY.escalation_score


def test_artifact_reports_triaged_equals_input_count_not_visible_queue_count() -> None:
    """reports_triaged must count every normalized input report, including any
    that end up in neither the cluster nor singleton queue -- proving it can't
    be computed by summing what's visible in either queue.

    Uses build_artifact_payload directly (rather than routing an extra report
    through real HDBSCAN clustering) so the test doesn't depend on which side
    of a clustering decision an adversarial input happens to land on.
    """
    reports = demo_reports() + [_report("999999", results=("Some Unrelated Result",))]
    assessment = ClusterAssessment(
        cluster_id="cluster-1",
        name="Uncommanded Engine Shutdown",
        hazard_statement="Crews saw shutdown indications on rollout.",
        risk=RiskScore(severity=1.0, frequency=0.3, trend=0.5, total=0.69, escalated=True),
        member_acns=("1000001", "1000002"),
    )

    artifact = build_artifact_payload(
        reports,
        [assessment],
        {"cluster-1": "brief text"},
        [],
        run_id="test-run",
        run_at="2026-01-01T00:00:00Z",
    )

    visible_count = sum(len(c["member_acns"]) for c in artifact["clusters"]) + len(
        artifact["severe_singletons"]
    )
    assert artifact["run"]["reports_triaged"] == len(reports) == 7
    assert visible_count < len(reports)


def test_severe_matches_is_a_pure_categorical_check() -> None:
    report = _report(
        "1",
        results=("Flight Crew Inflight Shutdown", "Unrelated"),
        anomaly_labels=("Conflict NMAC",),
    )

    matched_results, matched_events = severe_matches(report, POLICY)

    assert matched_results == ("Flight Crew Inflight Shutdown",)
    assert matched_events == ("Conflict NMAC",)


def test_evidence_excerpt_normalizes_whitespace_before_capping() -> None:
    report = ASRSReport(
        acn="1",
        narrative="line one\n\n  line   two  ",
        results=("Flight Crew Inflight Shutdown",),
    )

    singletons = find_severe_singletons([report], POLICY)

    assert singletons[0].evidence.narrative_excerpt == "line one line two"
    assert singletons[0].evidence.narrative_truncated is False


def test_a_deterministic_fixture_with_a_cluster_and_two_noise_reports_shows_one_singleton() -> None:
    """Acceptance criterion (T1-01 6.4): a fixture with clustered reports, a
    severe noise report, and a non-severe noise report shows exactly one
    severe singleton."""
    severe_noise = ASRSReport(
        acn="9000001",
        narrative=(
            "While taxiing to the gate the tower issued a traffic alert for another "
            "aircraft crossing the active runway without clearance."
        ),
        anomaly_labels=("Conflict NMAC",),
        aircraft_type="Widebody",
        flight_phase="Taxi",
        component="Ground Navigation",
        date_yyyymm="202312",
    )
    non_severe_noise = ASRSReport(
        acn="9000002",
        narrative=(
            "Cabin crew noted a minor galley cart latch was loose and secured it "
            "before beverage service began."
        ),
        anomaly_labels=("Aircraft Equipment Problem Less Severe",),
        aircraft_type="Widebody",
        flight_phase="Cruise",
        component="Galley Equipment",
        date_yyyymm="202312",
    )
    reports = [*demo_reports(), severe_noise, non_severe_noise]
    store = MemoryStore()

    assessments, singletons = run_triage(reports, policy=POLICY, store=store)

    assert assessments, "the demo fixture's cluster must still form"
    assert [s.acn for s in singletons] == ["9000001"]
