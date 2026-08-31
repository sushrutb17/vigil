"""Reward-hacking tripwires for offline extractor prompt promotion."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuardResult:
    passed: bool
    failures: tuple[str, ...]


def evaluate_guards(metrics: Mapping[str, float]) -> GuardResult:
    """Reject metric gains that violate predeclared safety/evaluation floors."""
    checks = {
        "cluster_count": 1 <= metrics.get("cluster_count", 0) <= 200,
        "median_cluster_size": metrics.get("median_cluster_size", 0) >= 5,
        "noise_fraction": metrics.get("noise_fraction", 1) < 0.40,
        "factual_coverage": metrics.get("factual_coverage", 0) >= 0.0,
        "length_ratio": 0.60 <= metrics.get("length_ratio", 0) <= 1.40,
        "extractor_macro_f1": metrics.get("extractor_macro_f1", 0) >= 0.50,
        "dedup_precision": metrics.get("dedup_precision", 0) >= 0.90,
    }
    failures = tuple(name for name, passed in checks.items() if not passed)
    return GuardResult(passed=not failures, failures=failures)


#: A candidate may lose this much parse coverage before it counts as degradation.
COVERAGE_TOLERANCE = 0.05
#: Floor below which predictions have collapsed toward a single label. On an
#: 18-class field, predicting one label everywhere scores ~0.06.
MIN_LABEL_COVERAGE = 0.15


def evaluate_extractor_guards(
    candidate: Mapping[str, float], incumbent: Mapping[str, float]
) -> GuardResult:
    """Refuse an extractor prompt revision that games its own metric.

    Deliberately *relative*, per EVAL.md ("must not degrade these"): the absolute
    floors in ``evaluate_guards`` describe a finished system, and applying them
    to a first revision would reject every candidate and make the loop theatre.

    The load-bearing check is ``macro_f1_not_traded_for_accuracy``. The known
    extractor hack is to predict the majority label everywhere: on a field where
    one class holds ~32% of the rows that lifts plain accuracy while per-class
    F1 falls. A revision that buys accuracy with macro-F1 is refused even when
    the headline number improved.
    """
    accuracy_gain = candidate.get("primary_problem_accuracy", 0.0) - incumbent.get(
        "primary_problem_accuracy", 0.0
    )
    macro_f1_gain = candidate.get("extractor_macro_f1", 0.0) - incumbent.get(
        "extractor_macro_f1", 0.0
    )
    incumbent_coverage = incumbent.get("primary_problem_label_coverage", 0.0)
    candidate_coverage = candidate.get("primary_problem_label_coverage", 0.0)
    checks = {
        "macro_f1_not_traded_for_accuracy": not (accuracy_gain > 0 and macro_f1_gain < 0),
        "label_coverage_floor": candidate_coverage >= MIN_LABEL_COVERAGE,
        "label_coverage_not_collapsed": candidate_coverage >= 0.5 * incumbent_coverage,
        "parse_coverage_not_degraded": candidate.get("parse_coverage", 0.0)
        >= incumbent.get("parse_coverage", 0.0) - COVERAGE_TOLERANCE,
        "scored_on_same_sample": candidate.get("sample_size") == incumbent.get("sample_size"),
    }
    failures = tuple(name for name, passed in checks.items() if not passed)
    return GuardResult(passed=not failures, failures=failures)
