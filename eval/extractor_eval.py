"""Run and score the Extractor against ASRS coded fields on a dev sample.

This is the objective function the offline self-improvement loop optimizes. It
never names ``data/holdout/``: callers hand it already-loaded reports, so the
locked split stays readable only through ``eval/holdout_score.py`` (guardrail
#3). ``pipeline.ingest.load_parquet`` refuses a holdout path anyway, which makes
``dev_sample`` safe by construction as well.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from agents import contracts
from agents.runtime import parse_structured_response
from eval.metrics import macro_f1, score_extractions
from pipeline.models import ASRSReport
from pipeline.store import TriageStore

DEV_SPLIT = Path("data/raw/default/validation/0000.parquet")

#: Narrative excerpt length used both in the prompt and in failure reports.
NARRATIVE_CHARS = 1800


@dataclass(frozen=True, slots=True)
class Failure:
    """One scored field the Extractor got wrong, as shown to the Evaluator."""

    acn: str
    field_name: str
    predicted: str | None
    expected: str | None
    narrative_excerpt: str


@dataclass(slots=True)
class ExtractorRun:
    """Predictions plus everything the loop needs to judge and explain them."""

    instruction: str
    version: str
    predictions: list[contracts.ExtractionOutput] = field(default_factory=list)
    failures: list[Failure] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


def dev_sample(
    path: Path = DEV_SPLIT, *, size: int = 200, seed: int = 42
) -> list[ASRSReport]:
    """Draw a seeded, reproducible dev sample from the validation split.

    Only reports carrying both scored coded fields are eligible: a row with no
    ground truth cannot be right or wrong, and including it would let a prompt
    raise its score by staying silent.
    """
    from pipeline.ingest import load_parquet

    eligible = [
        report
        for report in load_parquet(path)
        if report.primary_problem and report.flight_phase
    ]
    rng = random.Random(seed)
    return rng.sample(eligible, min(size, len(eligible)))


def extractor_message(report: ASRSReport) -> str:
    """Render one report as the Extractor's input."""
    return (
        f"ACN: {report.acn}\n"
        f"Narrative:\n{report.narrative[:NARRATIVE_CHARS]}"
    )


def baseline_extractions(reports: Sequence[ASRSReport]) -> list[contracts.ExtractionOutput]:
    """Majority-class + keyword-rule baseline required by EVAL.md.

    The majority classes are fit on the same reports being scored, which makes
    this baseline *optimistic* — it cannot be beaten by luck, and any delta the
    live Extractor shows over it is therefore a conservative estimate.
    """
    problems = Counter(report.primary_problem for report in reports if report.primary_problem)
    majority_problem = problems.most_common(1)[0][0] if problems else None
    return [
        contracts.ExtractionOutput(
            acn=report.acn,
            event_summary=report.narrative[:200],
            flight_phase=_phase_by_keyword(report.narrative),
            primary_problem=majority_problem,
        )
        for report in reports
    ]


#: Ordered so that the more specific phrase wins when both appear.
_PHASE_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("rejected takeoff", "Other Rejected Takeoff"),
    ("initial climb", "Initial Climb"),
    ("final approach", "Final Approach"),
    ("initial approach", "Initial Approach"),
    ("takeoff", "Takeoff / Launch"),
    ("cruise", "Cruise"),
    ("descent", "Descent"),
    ("climb", "Climb"),
    ("landing", "Landing"),
    ("approach", "Initial Approach"),
    ("taxi", "Taxi"),
    ("gate", "Parked"),
    ("parked", "Parked"),
)


def _phase_by_keyword(narrative: str) -> str | None:
    lowered = narrative.lower()
    for keyword, phase in _PHASE_KEYWORDS:
        if keyword in lowered:
            return phase
    return None


def run_extractor(
    reports: Sequence[ASRSReport],
    instruction: str,
    *,
    model: str,
    store: TriageStore,
    version: str = "candidate",
    max_workers: int = 8,
) -> ExtractorRun:
    """Run a live Extractor turn per report and collect predictions + failures.

    A report whose response will not parse is recorded in ``unparsed`` rather
    than raised: one malformed response should cost the candidate prompt score,
    not abort a 200-call evaluation.
    """
    from google.adk.agents import LlmAgent

    from agents.live import run_llm_agent

    agent = LlmAgent(
        name="extractor",
        model=model,
        instruction=instruction,
        output_schema=contracts.ExtractionOutput,
    )

    def one(report: ASRSReport) -> contracts.ExtractionOutput | str:
        try:
            raw = run_llm_agent(
                agent, message=extractor_message(report), model=model, store=store
            )
            return parse_structured_response(raw, contracts.ExtractionOutput)
        except Exception:
            # Includes StructuredOutputError, ADK transport errors, and a model
            # that returned prose. All of them mean 'no usable prediction'.
            return report.acn

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        results = list(pool.map(one, reports))

    run = ExtractorRun(instruction=instruction, version=version)
    for report, result in zip(reports, results, strict=True):
        if isinstance(result, str):
            run.unparsed.append(result)
            continue
        # The model is told to echo the ACN; trusting it would silently misalign
        # predictions with ground truth, so the caller's ACN always wins.
        run.predictions.append(result.model_copy(update={"acn": report.acn}))
    run.failures = collect_failures(run.predictions, reports)
    run.metrics = score_run(run, reports)
    return run


def collect_failures(
    predictions: Sequence[contracts.ExtractionOutput], reports: Sequence[ASRSReport]
) -> list[Failure]:
    """List every scored field that disagrees with the ASRS coded value."""
    by_acn = {report.acn: report for report in reports}
    failures: list[Failure] = []
    for prediction in predictions:
        report = by_acn[prediction.acn]
        for field_name, predicted, expected in (
            ("primary_problem", prediction.primary_problem, report.primary_problem),
            ("flight_phase", prediction.flight_phase, report.flight_phase),
        ):
            if predicted != expected:
                failures.append(
                    Failure(
                        acn=report.acn,
                        field_name=field_name,
                        predicted=predicted,
                        expected=expected,
                        narrative_excerpt=report.narrative[:400],
                    )
                )
    return failures


def score_run(run: ExtractorRun, reports: Sequence[ASRSReport]) -> dict[str, float]:
    """Score a run and add the tripwire metrics the extractor guards read.

    ``score_extractions`` supplies the headline accuracy/F1. The extras exist to
    make the known reward hack — predicting the majority label everywhere —
    visible rather than profitable.
    """
    scored = score_extractions(run.predictions, reports)
    by_acn = {report.acn: report for report in reports}
    expected = [by_acn[p.acn].primary_problem or "<missing>" for p in run.predictions]
    predicted = [p.primary_problem or "<missing>" for p in run.predictions]
    distinct_expected = len(set(expected))
    return {
        **scored,
        "extractor_macro_f1": macro_f1(predicted, expected),
        "primary_problem_label_diversity": (
            len(set(predicted)) / distinct_expected if distinct_expected else 0.0
        ),
        "parse_coverage": len(run.predictions) / len(reports) if reports else 0.0,
        "sample_size": float(len(reports)),
    }


def failure_digest(failures: Sequence[Failure], *, limit: int = 40) -> str:
    """Render failures as the Evaluator's evidence, newest-first by frequency.

    Confusion pairs are counted so the Evaluator sees *systematic* error (a whole
    vocabulary mismatch) rather than 200 unrelated anecdotes.
    """
    pairs = Counter(
        (failure.field_name, failure.predicted, failure.expected) for failure in failures
    )
    lines = [
        f"{field_name}: predicted {predicted!r} -> coded {expected!r} ({count}x)"
        for (field_name, predicted, expected), count in pairs.most_common(limit)
    ]
    return "\n".join(lines)


def observed_vocabulary(reports: Sequence[ASRSReport]) -> dict[str, list[str]]:
    """Return the coded label sets present in the dev sample.

    Handed to the Evaluator so a proposed revision can be grounded in the real
    ASRS vocabulary. This reads the dev split only — never the holdout.
    """
    return {
        "primary_problem": sorted(
            {report.primary_problem for report in reports if report.primary_problem}
        ),
        "flight_phase": sorted(
            {report.flight_phase for report in reports if report.flight_phase}
        ),
    }


def run_to_json(run: ExtractorRun) -> str:
    return json.dumps(
        {
            "version": run.version,
            "metrics": run.metrics,
            "unparsed": run.unparsed,
            "failure_count": len(run.failures),
        },
        indent=2,
        sort_keys=True,
    )
