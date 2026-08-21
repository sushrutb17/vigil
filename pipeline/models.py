"""Typed records passed between deterministic stages of the triage pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ASRSReport:
    """A normalized public safety report keyed by its ACN citation identifier."""

    acn: str
    narrative: str
    anomaly_labels: tuple[str, ...] = ()
    primary_problem: str | None = None
    contributing_factors: tuple[str, ...] = ()
    human_factors: tuple[str, ...] = ()
    aircraft_type: str | None = None
    flight_phase: str | None = None
    component: str | None = None
    results: tuple[str, ...] = ()
    date_yyyymm: str | None = None
    second_narrative: str | None = None

    def clustering_text(self) -> str:
        """Return raw narrative plus safe structured facets for deterministic embedding."""
        facets = " ".join(
            item
            for item in (self.aircraft_type, self.flight_phase, self.component)
            if item and not item.upper().startswith("ZZZ")
        )
        return f"{self.narrative} {facets}".strip()


@dataclass(frozen=True, slots=True)
class Cluster:
    """A deterministic cluster and its input-member ACNs."""

    cluster_id: str
    member_acns: tuple[str, ...]
    label: int
    noise: bool = False


@dataclass(frozen=True, slots=True)
class RiskScore:
    severity: float
    frequency: float
    trend: float
    total: float
    escalated: bool


@dataclass(frozen=True, slots=True)
class ClusterAssessment:
    cluster_id: str
    name: str
    hazard_statement: str
    risk: RiskScore
    member_acns: tuple[str, ...]
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)


JsonDict = dict[str, Any]
