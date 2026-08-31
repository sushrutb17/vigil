"""Read-only risk policy loading and deterministic score calculation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import yaml

from pipeline.models import ASRSReport, RiskScore


@dataclass(frozen=True, slots=True)
class FrozenRiskPolicy:
    policy_version: str
    escalation_score: float
    severity_weight: float
    frequency_weight: float
    trend_weight: float
    severe_results: frozenset[str]
    severe_events: frozenset[str]
    clustering: Mapping[str, int]

    @classmethod
    def from_path(cls, path: Path) -> FrozenRiskPolicy:
        """Load and validate the policy without offering any write capability."""
        with path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
        if not isinstance(raw, dict) or not isinstance(raw.get("risk"), dict):
            raise ValueError("invalid frozen risk policy")
        risk = raw["risk"]
        weights = [
            risk.get("severity_weight"),
            risk.get("frequency_weight"),
            risk.get("trend_weight"),
        ]
        if any(not isinstance(weight, (int, float)) for weight in weights):
            raise ValueError("risk weights must be numeric")
        if abs(sum(float(weight) for weight in weights) - 1.0) > 1e-9:
            raise ValueError("risk weights must sum to 1.0")
        return cls(
            policy_version=str(raw.get("policy_version", "unknown")),
            escalation_score=float(risk["escalation_score"]),
            severity_weight=float(risk["severity_weight"]),
            frequency_weight=float(risk["frequency_weight"]),
            trend_weight=float(risk["trend_weight"]),
            severe_results=frozenset(map(str, risk.get("severe_results", []))),
            severe_events=frozenset(map(str, risk.get("severe_events", []))),
            clustering=MappingProxyType(dict(raw.get("clustering", {}))),
        )


def score_cluster(reports: Sequence[ASRSReport], policy: FrozenRiskPolicy) -> RiskScore:
    """Score a cluster from observed severity, frequency, and month-over-month trend."""
    if not reports:
        raise ValueError("cannot score an empty cluster")
    severity_hits = sum(
        bool(set(report.results) & policy.severe_results)
        or bool(set(report.anomaly_labels) & policy.severe_events)
        for report in reports
    )
    severity = severity_hits / len(reports)
    frequency = min(1.0, len(reports) / 20.0)
    trend = _trend_score(reports)
    total = (
        severity * policy.severity_weight
        + frequency * policy.frequency_weight
        + trend * policy.trend_weight
    )
    return RiskScore(
        severity=round(severity, 3),
        frequency=round(frequency, 3),
        trend=round(trend, 3),
        total=round(total, 3),
        escalated=total >= policy.escalation_score,
    )


def severe_matches(
    report: ASRSReport, policy: FrozenRiskPolicy
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Pure categorical check: which frozen severe-result/severe-event terms a
    single report matches, sorted for deterministic output.

    Used for severe-but-unclustered triage (T1-01,
    docs/TIER1_ENHANCEMENTS_SPEC.md) -- never for cluster risk scoring.
    ``score_cluster``'s frequency/trend terms describe a group of reports and
    would obscure the actual single-report qualification rule.
    """
    matched_results = tuple(sorted(set(report.results) & policy.severe_results))
    matched_events = tuple(sorted(set(report.anomaly_labels) & policy.severe_events))
    return matched_results, matched_events


def _trend_score(reports: Sequence[ASRSReport]) -> float:
    months = sorted(
        report.date_yyyymm
        for report in reports
        if report.date_yyyymm and report.date_yyyymm.isdigit()
    )
    if len(months) < 2:
        return 0.0
    midpoint = len(months) // 2
    earlier = max(1, midpoint)
    later = len(months) - midpoint
    slope = (later - earlier) / len(months)
    return min(1.0, max(0.0, 0.5 + slope))
