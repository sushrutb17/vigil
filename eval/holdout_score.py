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


def load_holdout_sample(
    path: Path = HOLDOUT_PATH, *, size: int = 100, seed: int = 42
) -> list:
    """Draw a seeded holdout sample. The only function that reads the locked split.

    Mirrors ``eval.extractor_eval.dev_sample``'s eligibility rule so dev and
    holdout numbers are comparable, per EVAL.md's "report both side by side".
    """
    import random

    import pandas as pd

    frame = pd.read_parquet(path)
    eligible = [
        report
        for report in normalize_rows(frame.to_dict(orient="records"))
        if report.primary_problem and report.flight_phase
    ]
    return random.Random(seed).sample(eligible, min(size, len(eligible)))


def score_prompt_on_holdout(
    instruction: str,
    *,
    model: str,
    store,
    size: int = 100,
    seed: int = 42,
    path: Path = HOLDOUT_PATH,
) -> dict[str, float]:
    """Score one instruction on the locked holdout, at a promotion decision only.

    Called by ``eval/improve.py`` *after* a candidate has already been written
    and judged on dev. The returned numbers may gate promotion; they must never
    be fed back into a revision, or the holdout stops being a holdout
    (guardrail #3).
    """
    from eval.extractor_eval import run_extractor

    reports = load_holdout_sample(path, size=size, seed=seed)
    run = run_extractor(
        reports, instruction, model=model, store=store, version="holdout"
    )
    return run.metrics
