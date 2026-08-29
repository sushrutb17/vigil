"""Streamlit smoke tests for the Severe singletons queue (T1-01).

Uses Streamlit's native AppTest API (bare-mode script execution, no browser)
to prove the queue actually renders and is selectable, not just that the
loader function returns the right Python values.
"""

from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

_ARTIFACT_WITH_SINGLETON = {
    "schema_version": 2,
    "run": {"run_id": "test-run", "run_at": "2026-01-01T00:00:00Z", "reports_triaged": 8},
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
            "member_acns": ["1000001", "1000002"],
            "facets": {"component": ["Engine Control"]},
            "newly_escalated": True,
            "brief": "# Draft\n[ACN 1000001] Crew reported shutdown.",
        }
    ],
    "severe_singletons": [
        {
            "acn": "9000001",
            "matched_severe_results": [],
            "matched_severe_events": ["Conflict NMAC"],
            "evidence": {
                "acn": "9000001",
                "narrative_excerpt": "Traffic alert during taxi.",
                "narrative_truncated": False,
                "date_yyyymm": "202312",
                "flight_phase": "Taxi",
                "component": "Ground Navigation",
                "anomaly_labels": ["Conflict NMAC"],
                "results": [],
            },
        }
    ],
}

_APP_SCRIPT = """
from pathlib import Path
import ui.streamlit_app as app
app.ARTIFACT_PATH = Path({artifact_path!r})
# Streamlit's cache_data keys on the decorated function's arguments, and
# _load_artifact takes none -- it reads the ARTIFACT_PATH module global
# instead. Different tests point that global at different files within the
# same process, so the cache must be cleared per run or a later test would
# silently see an earlier test'''s artifact.
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


def test_summary_metrics_include_severe_singleton_count_and_reports_triaged(
    tmp_path: Path,
) -> None:
    at = _run_app(tmp_path, _ARTIFACT_WITH_SINGLETON)

    values = [metric.value for metric in at.main.get("metric")]
    # Hazard clusters, Escalated for review, Severe singletons, Reports triaged.
    assert values[:4] == ["1", "1", "1", "8"]


def test_severe_singletons_queue_is_selectable_and_shows_its_evidence(tmp_path: Path) -> None:
    at = _run_app(tmp_path, _ARTIFACT_WITH_SINGLETON)

    radio = at.sidebar.radio[0]
    assert radio.options[0] == "Hazard clusters"
    singleton_option = next(o for o in radio.options if o.startswith("Severe singletons"))

    radio.set_value(singleton_option).run()

    assert not at.exception, at.exception
    rendered = " ".join(
        element.value
        for kind in ("markdown", "subheader", "caption")
        for element in at.main.get(kind)
    )
    assert "9000001" in rendered
    assert "Conflict NMAC" in rendered
    assert "Traffic alert during taxi." in rendered


def test_no_singletons_means_no_queue_selector_at_all(tmp_path: Path) -> None:
    """A run with zero severe singletons must not show an empty/dead queue toggle."""
    artifact = {**_ARTIFACT_WITH_SINGLETON, "severe_singletons": []}

    at = _run_app(tmp_path, artifact)

    assert at.sidebar.radio == []
    values = [metric.value for metric in at.main.get("metric")]
    assert values[:4] == ["1", "1", "0", "8"]
