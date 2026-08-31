"""Tests for the offline extractor self-improvement loop (Phase 5)."""

from pathlib import Path

import pytest

from agents import prompts
from agents.contracts import ExtractionOutput, PromptRevision
from eval import improve
from eval.extractor_eval import ExtractorRun, collect_failures, score_run
from eval.guards import evaluate_extractor_guards
from pipeline.models import ASRSReport

ROOT = Path(__file__).parents[1]

BASE = {
    "primary_problem_accuracy": 0.40,
    "extractor_macro_f1": 0.30,
    "primary_problem_label_coverage": 0.80,
    "parse_coverage": 1.0,
    "sample_size": 10.0,
}


def _metrics(**overrides: float) -> dict[str, float]:
    return {**BASE, **overrides}


# --- guards ------------------------------------------------------------------


def test_guard_catches_accuracy_bought_with_macro_f1() -> None:
    """The known extractor hack: predict the majority label everywhere."""
    hacked = _metrics(primary_problem_accuracy=0.55, extractor_macro_f1=0.18)
    result = evaluate_extractor_guards(hacked, BASE)
    assert not result.passed
    assert "macro_f1_not_traded_for_accuracy" in result.failures


def test_guard_catches_label_collapse() -> None:
    collapsed = _metrics(extractor_macro_f1=0.35, primary_problem_label_coverage=0.05)
    result = evaluate_extractor_guards(collapsed, BASE)
    assert not result.passed
    assert "label_coverage_floor" in result.failures
    assert "label_coverage_not_collapsed" in result.failures


def test_guard_passes_a_genuine_improvement() -> None:
    better = _metrics(primary_problem_accuracy=0.52, extractor_macro_f1=0.44)
    assert evaluate_extractor_guards(better, BASE).passed


def test_guard_refuses_comparison_across_different_samples() -> None:
    other = _metrics(extractor_macro_f1=0.9, sample_size=25.0)
    assert "scored_on_same_sample" in evaluate_extractor_guards(other, BASE).failures


# --- loop --------------------------------------------------------------------

REPORTS = [
    ASRSReport(
        acn=str(1000 + index),
        narrative=f"Report {index} narrative text during cruise.",
        primary_problem="Aircraft" if index % 2 else "Human Factors",
        flight_phase="Cruise",
    )
    for index in range(10)
]


def _run_with(predictions: list[ExtractionOutput], version: str) -> ExtractorRun:
    run = ExtractorRun(instruction="x", version=version, predictions=predictions)
    run.failures = collect_failures(predictions, REPORTS)
    run.metrics = score_run(run, REPORTS)
    return run


def _perfect() -> list[ExtractionOutput]:
    return [
        ExtractionOutput(
            acn=report.acn,
            event_summary="s",
            primary_problem=report.primary_problem,
            flight_phase=report.flight_phase,
        )
        for report in REPORTS
    ]


def _swapped() -> list[ExtractionOutput]:
    """Wrong on every row but still inside the coded vocabulary.

    Distinct from ``_all_wrong``: label coverage stays 1.0, so the collapse
    guards pass and the loop has to reject this on the dev-gain check instead.
    """
    flip = {"Aircraft": "Human Factors", "Human Factors": "Aircraft"}
    return [
        ExtractionOutput(
            acn=report.acn,
            event_summary="s",
            primary_problem=flip[report.primary_problem],
            flight_phase=report.flight_phase,
        )
        for report in REPORTS
    ]


def _all_wrong() -> list[ExtractionOutput]:
    return [
        ExtractionOutput(
            acn=report.acn, event_summary="s", primary_problem="Weather", flight_phase="Taxi"
        )
        for report in REPORTS
    ]


@pytest.fixture
def loop_env(tmp_path, monkeypatch):
    """Wire the loop to fixed fake runs so no live model call is made."""
    prompt_root = tmp_path / "prompts"
    prompts.save_version("extractor", "v1", prompts.EXTRACTOR_INSTRUCTION, root=prompt_root)
    monkeypatch.setattr(improve, "dev_sample", lambda **_: REPORTS)
    monkeypatch.setattr(
        "agents.evaluator.propose_revision",
        lambda *args, **kwargs: PromptRevision(
            rationale="tell the agent the labels are a closed vocabulary",
            revised_instruction="Revised instruction text that is comfortably long enough.",
        ),
    )
    return prompt_root, tmp_path / "runs"


def _stub_runs(monkeypatch, incumbent, candidate) -> None:
    calls = iter([incumbent, candidate])

    def fake_run_extractor(reports, instruction, *, model, store, version="c", **kwargs):
        run = next(calls)
        run.version = version
        return run

    monkeypatch.setattr(improve, "run_extractor", fake_run_extractor)


def test_promotes_when_dev_and_holdout_both_improve(loop_env, monkeypatch) -> None:
    prompt_root, runs_dir = loop_env
    _stub_runs(monkeypatch, _run_with(_all_wrong(), "v1"), _run_with(_perfect(), "v2"))
    monkeypatch.setattr(
        "eval.holdout_score.score_prompt_on_holdout",
        lambda instruction, **kwargs: {
            "extractor_macro_f1": 0.9 if "Revised" in instruction else 0.2
        },
    )
    result = improve.improve_extractor(
        store=None, prompt_root=prompt_root, runs_dir=runs_dir, sample_size=10
    )
    assert result.promoted
    assert prompts.active_version("extractor", root=prompt_root) == "v2"
    assert list(runs_dir.glob("*-extractor.json"))


def test_discards_when_dev_improves_but_holdout_regresses(loop_env, monkeypatch) -> None:
    """A dev gain that does not survive the locked holdout is overfitting."""
    prompt_root, runs_dir = loop_env
    _stub_runs(monkeypatch, _run_with(_all_wrong(), "v1"), _run_with(_perfect(), "v2"))
    monkeypatch.setattr(
        "eval.holdout_score.score_prompt_on_holdout",
        lambda instruction, **kwargs: {
            "extractor_macro_f1": 0.1 if "Revised" in instruction else 0.5
        },
    )
    result = improve.improve_extractor(
        store=None, prompt_root=prompt_root, runs_dir=runs_dir, sample_size=10
    )
    assert not result.promoted
    assert "overfit" in result.reason
    assert prompts.active_version("extractor", root=prompt_root) == "v1"


def test_guard_failure_blocks_promotion_and_skips_the_holdout(loop_env, monkeypatch) -> None:
    prompt_root, runs_dir = loop_env
    _stub_runs(monkeypatch, _run_with(_perfect(), "v1"), _run_with(_all_wrong(), "v2"))

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("holdout must not be read for a rejected candidate")

    monkeypatch.setattr("eval.holdout_score.score_prompt_on_holdout", explode)
    result = improve.improve_extractor(
        store=None, prompt_root=prompt_root, runs_dir=runs_dir, sample_size=10
    )
    assert not result.promoted
    assert result.incumbent_holdout is None
    assert prompts.active_version("extractor", root=prompt_root) == "v1"


def test_every_outcome_is_recorded_in_the_ledger(loop_env, monkeypatch) -> None:
    """EVAL.md: the improvement curve is generated from eval/runs/, not drawn."""
    import json

    prompt_root, runs_dir = loop_env
    _stub_runs(monkeypatch, _run_with(_perfect(), "v1"), _run_with(_swapped(), "v2"))

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("holdout must not be read without a dev gain")

    monkeypatch.setattr("eval.holdout_score.score_prompt_on_holdout", explode)
    improve.improve_extractor(
        store=None, prompt_root=prompt_root, runs_dir=runs_dir, sample_size=10
    )
    entries = list(runs_dir.glob("*-extractor.json"))
    assert len(entries) == 1
    payload = json.loads(entries[0].read_text(encoding="utf-8"))
    assert payload["promoted"] is False
    # Guards pass here: the candidate got *worse*, so it traded nothing away.
    # It is the dev-gain check that rejects it, and the holdout stays unread.
    assert payload["guards"]["passed"] is True
    assert "no dev gain" in payload["reason"]
    assert payload["incumbent_holdout"] is None
    assert payload["baseline_metrics"]
    assert payload["candidate_version"] == "v2"
