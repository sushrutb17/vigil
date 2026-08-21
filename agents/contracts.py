"""Structured outputs shared by the ADK judgment stages."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractionOutput(BaseModel):
    acn: str = Field(description="Source report identifier copied exactly from the input.")
    event_summary: str = Field(
        description="Factual, concise description grounded in the narrative."
    )
    aircraft_type: str | None = None
    flight_phase: str | None = None
    component: str | None = None
    primary_problem: str | None = None
    contributing_factors: list[str] = Field(default_factory=list)
    human_factors: list[str] = Field(default_factory=list)


class DedupOutput(BaseModel):
    same_event: bool
    confidence: float = Field(ge=0, le=1)
    reason: str


class ClusterAnalysisOutput(BaseModel):
    name: str
    hazard_statement: str
    supporting_acns: list[str] = Field(min_length=1)
