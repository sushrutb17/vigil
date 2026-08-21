"""Offline metrics over ASRS-coded fields and deterministic cluster labels."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence

from sklearn.metrics import adjusted_rand_score, f1_score

from agents.contracts import ExtractionOutput
from pipeline.models import ASRSReport


def accuracy(predicted: Iterable[str | None], expected: Iterable[str | None]) -> float:
    pairs = list(zip(predicted, expected, strict=True))
    return sum(left == right for left, right in pairs) / len(pairs) if pairs else 0.0


def binary_precision_recall(
    predicted: Iterable[bool], expected: Iterable[bool]
) -> dict[str, float]:
    pairs = list(zip(predicted, expected, strict=True))
    true_positive = sum(left and right for left, right in pairs)
    false_positive = sum(left and not right for left, right in pairs)
    false_negative = sum(not left and right for left, right in pairs)
    return {
        "precision": true_positive / (true_positive + false_positive)
        if true_positive + false_positive
        else 0.0,
        "recall": true_positive / (true_positive + false_negative)
        if true_positive + false_negative
        else 0.0,
    }


def cluster_purity(cluster_labels: Sequence[int], reference_labels: Sequence[str]) -> float:
    """Calculate majority-label purity, excluding HDBSCAN's -1 noise label."""
    buckets: dict[int, list[str]] = {}
    for cluster, reference in zip(cluster_labels, reference_labels, strict=True):
        if cluster != -1:
            buckets.setdefault(cluster, []).append(reference)
    assigned = sum(len(labels) for labels in buckets.values())
    if not assigned:
        return 0.0
    correct = sum(Counter(labels).most_common(1)[0][1] for labels in buckets.values())
    return correct / assigned


def macro_f1(predicted: Sequence[str], expected: Sequence[str]) -> float:
    """Return macro F1 so majority-label extraction cannot masquerade as quality."""
    if not expected:
        return 0.0
    return float(f1_score(expected, predicted, average="macro", zero_division=0))


def adjusted_rand(cluster_labels: Sequence[int], reference_labels: Sequence[str]) -> float:
    """Return adjusted Rand index against ASRS anomaly labels."""
    if len(cluster_labels) != len(reference_labels):
        raise ValueError("cluster and reference labels must have equal length")
    return float(adjusted_rand_score(reference_labels, cluster_labels)) if cluster_labels else 0.0


def rouge_l(candidate: str, reference: str) -> float:
    """Calculate a compact ROUGE-L F1 score without downloading metric assets."""
    candidate_tokens = candidate.lower().split()
    reference_tokens = reference.lower().split()
    if not candidate_tokens or not reference_tokens:
        return 0.0
    lcs = _lcs_length(candidate_tokens, reference_tokens)
    precision = lcs / len(candidate_tokens)
    recall = lcs / len(reference_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _lcs_length(left: Sequence[str], right: Sequence[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_token in left:
        current = [0]
        for right_index, right_token in enumerate(right, start=1):
            current.append(
                previous[right_index - 1] + 1
                if left_token == right_token
                else max(previous[right_index], current[-1])
            )
        previous = current
    return previous[-1]


def score_extractions(
    predictions: Sequence[ExtractionOutput], reports: Sequence[ASRSReport]
) -> dict[str, float]:
    """Score extractor fields against ASRS-coded values on a non-holdout split."""
    by_acn = {report.acn: report for report in reports}
    if {prediction.acn for prediction in predictions} - by_acn.keys():
        raise ValueError("extraction prediction contains an ACN outside the scored split")
    pairs = [(prediction, by_acn[prediction.acn]) for prediction in predictions]
    if not pairs:
        return {"primary_problem_accuracy": 0.0, "field_macro_f1": 0.0}
    primary_accuracy = accuracy(
        [prediction.primary_problem for prediction, _ in pairs],
        [report.primary_problem for _, report in pairs],
    )
    expected = [report.flight_phase or "<missing>" for _, report in pairs]
    predicted = [prediction.flight_phase or "<missing>" for prediction, _ in pairs]
    return {
        "primary_problem_accuracy": primary_accuracy,
        "field_macro_f1": macro_f1(predicted, expected),
    }
