from agents.contracts import ExtractionOutput
from eval.metrics import (
    accuracy,
    adjusted_rand,
    binary_precision_recall,
    cluster_purity,
    macro_f1,
    rouge_l,
    score_extractions,
)
from pipeline.models import ASRSReport


def test_metrics_cover_expected_basics() -> None:
    assert accuracy(["a", "b"], ["a", "c"]) == 0.5
    assert binary_precision_recall([True, True, False], [True, False, False]) == {
        "precision": 0.5,
        "recall": 1.0,
    }
    assert cluster_purity([0, 0, 1, -1], ["x", "x", "y", "z"]) == 1.0
    assert macro_f1(["x", "y"], ["x", "x"]) == 1 / 3
    assert adjusted_rand([0, 0, 1], ["x", "x", "y"]) == 1.0
    assert rouge_l("the quick fox", "the slow quick fox") == 6 / 7


def test_extraction_scoring_uses_source_acns() -> None:
    report = ASRSReport(
        acn="1234567",
        narrative="Narrative",
        primary_problem="Procedure",
        flight_phase="Cruise",
    )
    prediction = ExtractionOutput(
        acn="1234567",
        event_summary="Summary",
        primary_problem="Procedure",
        flight_phase="Cruise",
    )
    assert score_extractions([prediction], [report]) == {
        "primary_problem_accuracy": 1.0,
        "field_macro_f1": 1.0,
    }
