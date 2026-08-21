"""Batch embedding adapter kept separate from deterministic clustering."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pipeline.models import ASRSReport


def embed_reports(reports: Sequence[ASRSReport], *, model: str) -> list[list[float]]:
    """Embed a report batch through Gemini and preserve input ordering.

    This is intentionally an upstream data-preparation step. ``cluster.py`` only
    receives numerical vectors and has no model client or model invocation.
    Credentials are resolved by the Google Gen AI SDK from the environment.
    """
    if not reports:
        return []
    from google import genai

    client = genai.Client()
    response = client.models.embed_content(
        model=model,
        contents=[report.clustering_text() for report in reports],
    )
    embeddings = response.embeddings or []
    values = [embedding.values for embedding in embeddings]
    if len(values) != len(reports) or any(vector is None for vector in values):
        raise RuntimeError("embedding response did not contain one vector per report")
    return [list(vector) for vector in values if vector is not None]


def cache_embeddings(
    reports: Sequence[ASRSReport], vectors: Sequence[Sequence[float]], path: Path
) -> None:
    """Persist batched embeddings to Parquet for reproducible no-call re-clustering."""
    if len(reports) != len(vectors):
        raise ValueError("reports and embedding vectors must have equal length")
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame({"acn": [report.acn for report in reports], "embedding": list(vectors)})
    frame.to_parquet(path, index=False)
