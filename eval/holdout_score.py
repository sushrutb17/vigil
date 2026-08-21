"""The exclusive reader for data/holdout/.

This module is deliberately offline and should be called only at prompt-promotion
decisions or for final reporting. Do not import it in the live pipeline.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.ingest import normalize_rows

HOLDOUT_PATH = Path("data/holdout/test.parquet")


def load_locked_holdout(path: Path = HOLDOUT_PATH) -> int:
    """Read the locked Parquet split solely to report its validated record count."""
    import pandas as pd

    frame = pd.read_parquet(path)
    return len(normalize_rows(frame.to_dict(orient="records")))
