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
class EvidenceRecord:
    """A drill-down view of one report's narrative and structured facets.

    Shared by the severe-singleton queue (T1-01) and, in a future pass, the
    per-cluster ACN evidence drill-down (T1-02) -- see
    docs/TIER1_ENHANCEMENTS_SPEC.md section 5.2.
    """

    acn: str
    narrative_excerpt: str
    narrative_truncated: bool
    date_yyyymm: str | None = None
    flight_phase: str | None = None
    component: str | None = None
    anomaly_labels: tuple[str, ...] = ()
    results: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SevereSingleton:
    """A noise (unclustered) report that matches the frozen severe vocabulary.

    This is a categorical triage rule, not a one-report risk score: no Analyst
    name, hazard statement, risk score, or investigator brief is generated for
    it. It is a source report surfaced for human review, not a fabricated
    one-report cluster (docs/TIER1_ENHANCEMENTS_SPEC.md, T1-01 section 6.1.8).
    """

    acn: str
    matched_severe_results: tuple[str, ...]
    matched_severe_events: tuple[str, ...]
    evidence: EvidenceRecord


@dataclass(frozen=True, slots=True)
class ClusterAssessment:
    cluster_id: str
    name: str
    hazard_statement: str
    risk: RiskScore
    member_acns: tuple[str, ...]
    facets: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: True when this cluster crossed the threshold on *this* run and the
    #: escalation ledger had no prior alert covering its members. Kept separate
    #: from the stored ``status`` string, whose "new" value confusingly means
    #: "not escalated this run" and which the UI and tests already depend on.
    newly_escalated: bool = False


JsonDict = dict[str, Any]
