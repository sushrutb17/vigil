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
