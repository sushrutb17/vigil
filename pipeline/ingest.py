"""ASRS Parquet ingestion and schema normalization.

This module is the only place where source-column names are mapped into VIGIL's
internal record. It never reads the locked holdout directory.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from pipeline.models import ASRSReport


def _text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def split_multi(value: object | None) -> tuple[str, ...]:
    """Normalize ASRS semicolon-separated fields into stable tuples."""
    text = _text(value)
    return tuple(part.strip() for part in text.split(";") if part.strip()) if text else ()


def normalize_row(row: Mapping[str, object]) -> ASRSReport:
    """Map one ASRS source row into the stable record used by the pipeline."""
    acn = _text(row.get("acn_num_ACN"))
    narrative = _text(row.get("Report 1_Narrative"))
    if not acn or not narrative:
        raise ValueError("ASRS row requires both acn_num_ACN and Report 1_Narrative")
    return ASRSReport(
        acn=acn,
        narrative=narrative,
        anomaly_labels=split_multi(row.get("Events_Anomaly")),
        primary_problem=_text(row.get("Assessments.1_Primary Problem")),
        contributing_factors=split_multi(row.get("Assessments_Contributing Factors / Situations")),
        human_factors=split_multi(row.get("Person 1.7_Human Factors")),
        aircraft_type=_text(row.get("Aircraft 1.2_Make Model Name")),
        flight_phase=_text(row.get("Aircraft 1.9_Flight Phase")),
        component=_text(row.get("Component_Aircraft Component")),
        results=split_multi(row.get("Events.5_Result")),
        date_yyyymm=_text(row.get("Time_Date")),
        second_narrative=_text(row.get("Report 2_Narrative")),
    )


def normalize_rows(rows: Iterable[Mapping[str, object]]) -> list[ASRSReport]:
    """Normalize records and reject duplicate ACNs rather than silently overwriting."""
    reports = [normalize_row(row) for row in rows]
    acns = [report.acn for report in reports]
    if len(acns) != len(set(acns)):
        raise ValueError("duplicate ACN detected in source batch")
    return reports


def load_parquet(path: Path) -> list[ASRSReport]:
    """Load an approved train/validation Parquet file, never data/holdout/."""
    resolved = path.resolve()
    if "holdout" in resolved.parts:
        raise PermissionError("holdout data may only be read by eval/holdout_score.py")
    import pandas as pd

    frame = pd.read_parquet(resolved)
    return normalize_rows(frame.to_dict(orient="records"))
