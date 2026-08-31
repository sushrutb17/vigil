"""Tests for T1-02 -- the ACN evidence drill-down.

Covers docs/TIER1_ENHANCEMENTS_SPEC.md section 7.3's required list: citation
extraction, member/precedent evidence assembly and roles, the unresolved-ACN
artifact-construction failure, narrative excerpt normalization/truncation
boundaries, deterministic ordering, and artifact v2/legacy round-trips through
the UI loader. ``ACN_CITATION`` only recognizes 4+ digit numbers, so every ACN
used here has at least four digits.
"""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

import ui.streamlit_app as app
from agents.critic import extract_cited_acns
from pipeline.models import ASRSReport, ClusterAssessment, RiskScore
from pipeline.run_batch import build_artifact_payload, build_cluster_evidence, demo_reports
from ui.streamlit_app import _clusters_from_entries


def _report(acn: str, *, narrative: str = "Narrative text.") -> ASRSReport:
    return ASRSReport(acn=acn, narrative=narrative)


def _assessment(cluster_id: str, member_acns: tuple[str, ...]) -> ClusterAssessment:
    return ClusterAssessment(
        cluster_id=cluster_id,
        name="Test Hazard",
        hazard_statement="Test statement.",
        risk=RiskScore(severity=1.0, frequency=0.3, trend=0.5, total=0.69, escalated=True),
        member_acns=member_acns,
    )


def test_citation_extraction_is_case_insensitive_ordered_and_deduplicated() -> None:
    brief = "See [acn 1002] and [ACN 1001] again [ACN 1002]."

    assert extract_cited_acns(brief) == ("1002", "1001")


def test_all_cluster_members_receive_evidence_records() -> None:
    reports = [_report("1001"), _report("1002"), _report("1003")]
    by_acn = {r.acn: r for r in reports}
    assessment = _assessment("c1", ("1001", "1002", "1003"))

    evidence = build_cluster_evidence("c1", assessment, "# Draft\nNo citations here.", by_acn)

    assert {item["acn"] for item in evidence} == {"1001", "1002", "1003"}
    assert all(item["role"] == "member" for item in evidence)


def test_a_cited_non_member_precedent_receives_evidence_and_the_correct_role() -> None:
    reports = [_report("1001"), _report("1002"), _report("9999")]
    by_acn = {r.acn: r for r in reports}
    assessment = _assessment("c1", ("1001", "1002"))
    brief = "# Draft\nSimilar pattern seen before [ACN 9999]."

    evidence = build_cluster_evidence("c1", assessment, brief, by_acn)

    precedent = [item for item in evidence if item["role"] == "precedent"]
    assert [item["acn"] for item in precedent] == ["9999"]
    assert {item["acn"] for item in evidence if item["role"] == "member"} == {"1001", "1002"}


def test_an_uncited_non_member_is_not_embedded() -> None:
    reports = [_report("1001"), _report("1002"), _report("9999")]
    by_acn = {r.acn: r for r in reports}
    assessment = _assessment("c1", ("1001", "1002"))
    brief = "# Draft\nNothing cites that other report here."

    evidence = build_cluster_evidence("c1", assessment, brief, by_acn)

    assert {item["acn"] for item in evidence} == {"1001", "1002"}


def test_a_cited_unknown_acn_fails_artifact_construction() -> None:
    reports = demo_reports()
    assessment = _assessment("c1", tuple(r.acn for r in reports[:3]))
    brief = "# Draft\nCites a report outside this run [ACN 9999999]."

    try:
        build_artifact_payload(
            reports, [assessment], {"c1": brief}, [], run_id="r", run_at="2026-01-01T00:00:00Z"
        )
    except ValueError as exc:
        assert "c1" in str(exc)
        assert "9999999" in str(exc)
    else:
        raise AssertionError("expected a ValueError for an unresolved cited ACN")


def test_whitespace_normalization_occurs_before_the_500_character_cap() -> None:
    report = _report("1001", narrative="word   " * 100)
    assessment = _assessment("c1", ("1001",))

    evidence = build_cluster_evidence("c1", assessment, "# Draft", {"1001": report})

    normalized = " ".join(report.narrative.split())
    assert evidence[0]["narrative_excerpt"] == normalized[:500]


def test_exactly_500_normalized_characters_is_not_marked_truncated_501_is() -> None:
    at_limit = _report("1001", narrative="a" * 500)
    over_limit = _report("1002", narrative="a" * 501)

    evidence_a = build_cluster_evidence(
        "ca", _assessment("ca", ("1001",)), "# Draft", {"1001": at_limit}
    )
    evidence_b = build_cluster_evidence(
        "cb", _assessment("cb", ("1002",)), "# Draft", {"1002": over_limit}
    )

    assert evidence_a[0]["narrative_truncated"] is False
    assert evidence_b[0]["narrative_truncated"] is True


def test_deterministic_evidence_ordering_survives_shuffled_input() -> None:
    reports = {acn: _report(acn) for acn in ["1003", "1001", "1002", "9050", "9010"]}
    assessment = _assessment("c1", ("1003", "1001", "1002"))
    brief = "# Draft\nSee [ACN 9050] and [ACN 9010]."

    evidence = build_cluster_evidence("c1", assessment, brief, reports)

    assert [item["acn"] for item in evidence] == ["1001", "1002", "1003", "9010", "9050"]

    # Same inputs, shuffled dict insertion order -- output must be identical.
    reversed_reports = dict(reversed(list(reports.items())))
    reshuffled = build_cluster_evidence("c1", assessment, brief, reversed_reports)
    assert [item["acn"] for item in reshuffled] == ["1001", "1002", "1003", "9010", "9050"]


def test_artifact_v2_round_trips_through_the_ui_loader() -> None:
    reports = demo_reports() + [_report("9000001")]
    member_acns = tuple(r.acn for r in reports if r.acn != "9000001")
    assessment = _assessment("c1", member_acns)
    brief = f"# Draft\nHazard seen. [ACN {member_acns[0]}] precedent [ACN 9000001]."

    artifact = build_artifact_payload(
        reports, [assessment], {"c1": brief}, [], run_id="r", run_at="2026-01-01T00:00:00Z"
    )
    loaded = _clusters_from_entries(artifact["clusters"])

    assert loaded[0]["evidence"]
    roles = {item["acn"]: item["role"] for item in loaded[0]["evidence"]}
    assert roles["9000001"] == "precedent"
    assert roles[member_acns[0]] == "member"


def test_a_legacy_list_artifact_still_loads_with_an_empty_singleton_queue(tmp_path: Path) -> None:
    """A pre-T1-01 top-level-list artifact predates both the singleton queue
    and the evidence field -- neither should break the load."""
    legacy_payload = [
        {
            "cluster_id": "c1",
            "name": "Legacy Cluster",
            "hazard_statement": "x",
            "risk": {"total": 0.5, "escalated": False},
            "member_acns": ["1001", "1002"],
            "facets": {},
            "brief": "# Draft\nx [ACN 1001]",
        }
    ]
    artifact_path = tmp_path / "legacy.json"
    artifact_path.write_text(json.dumps(legacy_payload), encoding="utf-8")
    app.ARTIFACT_PATH = artifact_path
    app._load_artifact.clear()

    clusters, singletons, _reports_triaged, _source = app._load_artifact()

    assert singletons == []
    assert clusters[0]["evidence"] == []


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


_ARTIFACT_WITH_PRECEDENT_EVIDENCE = {
    "schema_version": 2,
    "run": {"run_id": "test-run", "run_at": "2026-01-01T00:00:00Z", "reports_triaged": 3},
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
            "member_acns": ["1000001", "1000003"],
            "facets": {},
            "newly_escalated": True,
            "brief": (
                "# Draft\n[ACN 1000001] Crew reported shutdown. "
                "Similar past event [ACN 9000002]."
            ),
            # Deliberately not member-then-precedent order, and with an
            # uncited member first, so the AppTest below actually exercises
            # cited-first reordering rather than an already-sorted list.
            "evidence": [
                {
                    "role": "member",
                    "acn": "1000003",
                    "narrative_excerpt": "An unrelated cluster member never cited in the brief.",
                    "narrative_truncated": False,
                    "date_yyyymm": "202203",
                    "flight_phase": "Taxi",
                    "component": "Engine Control",
                    "anomaly_labels": [],
                    "results": [],
                },
                {
                    "role": "member",
                    "acn": "1000001",
                    "narrative_excerpt": "Crew reported an uncommanded shutdown on rollout.",
                    "narrative_truncated": False,
                    "date_yyyymm": "202201",
                    "flight_phase": "Landing Rollout",
                    "component": "Engine Control",
                    "anomaly_labels": [],
                    "results": [],
                },
                {
                    "role": "precedent",
                    "acn": "9000002",
                    "narrative_excerpt": "A prior report describing a comparable shutdown pattern.",
                    "narrative_truncated": False,
                    "date_yyyymm": "202112",
                    "flight_phase": "Cruise",
                    "component": "Engine Control",
                    "anomaly_labels": [],
                    "results": [],
                },
            ],
        }
    ],
    "severe_singletons": [],
}


def test_evidence_selector_lists_cited_acns_first(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT_WITH_PRECEDENT_EVIDENCE)

    selectbox = next(sb for sb in at.main.get("selectbox") if sb.label == "Evidence")

    assert "1000001" in selectbox.options[0]
    assert "9000002" in selectbox.options[1]
    assert "1000003" in selectbox.options[2]
    assert "Precedent evidence" in selectbox.options[1]
    assert "Cluster member" in selectbox.options[0]


def test_selecting_a_second_acn_renders_its_narrative_and_metadata_not_the_first(
    tmp_path: Path,
) -> None:
    at = _run_app(tmp_path, _ARTIFACT_WITH_PRECEDENT_EVIDENCE)
    selectbox = next(sb for sb in at.main.get("selectbox") if sb.label == "Evidence")

    second_option = next(o for o in selectbox.options if "9000002" in o)
    selectbox.set_value(second_option).run()

    assert not at.exception, at.exception
    rendered = " ".join(
        element.value
        for kind in ("markdown", "subheader", "caption")
        for element in at.main.get(kind)
    )
    assert "prior report describing a comparable shutdown" in rendered
    assert "Cruise" in rendered
    assert "an uncommanded shutdown on rollout" not in rendered
