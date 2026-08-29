"""Offline self-improvement loop for the Extractor prompt (Phase 5).

    dev sample -> score incumbent -> Evaluator reads failures -> candidate prompt
    -> score candidate on dev -> guards -> locked holdout -> promote or discard

Never imported by the live pipeline (guardrail #7) and never touches
``config/frozen.yaml`` (guardrail #2): a promotion writes only
``config/prompts/``. The holdout is read exclusively through
``eval.holdout_score`` and only at the promotion decision, after the candidate
text is already fixed — nothing it returns can influence a revision
(guardrail #3).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agents import prompts
from agents.definitions import load_models
from eval.extractor_eval import (
    ExtractorRun,
    baseline_extractions,
    collect_failures,
    dev_sample,
    observed_vocabulary,
    run_extractor,
    score_run,
)
from eval.guards import GuardResult, evaluate_extractor_guards
from pipeline.store import MemoryStore, TriageStore

RUNS_DIR = Path("eval/runs")


@dataclass(frozen=True, slots=True)
class LoopResult:
    promoted: bool
    reason: str
    incumbent_version: str
    candidate_version: str
    rationale: str
    baseline_metrics: dict[str, float]
    incumbent_dev: dict[str, float]
    candidate_dev: dict[str, float]
    guards: GuardResult
    incumbent_holdout: dict[str, float] | None
    candidate_holdout: dict[str, float] | None


def _baseline_run(reports) -> ExtractorRun:
    """Score the majority-class + keyword baseline EVAL.md requires."""
    run = ExtractorRun(instruction="<majority-class + keyword rules>", version="baseline")
    run.predictions = baseline_extractions(reports)
    run.failures = collect_failures(run.predictions, reports)
    run.metrics = score_run(run, reports)
    return run


def improve_extractor(
    *,
    sample_size: int = 200,
    holdout_size: int = 100,
    seed: int = 42,
    store: TriageStore | None = None,
    models_path: Path = Path("config/models.yaml"),
    prompt_root: Path = prompts.PROMPT_ROOT,
    runs_dir: Path = RUNS_DIR,
    use_holdout: bool = True,
) -> LoopResult:
    """Run one full improvement iteration and write a ledger entry either way."""
    store = store or MemoryStore()
    model = load_models(models_path)["flash"]
    reports = dev_sample(size=sample_size, seed=seed)

    incumbent_version = prompts.active_version("extractor", root=prompt_root)
    incumbent_text = prompts.load_instruction("extractor", root=prompt_root)

    baseline = _baseline_run(reports)
    incumbent = run_extractor(
        reports, incumbent_text, model=model, store=store, version=incumbent_version
    )

    from agents.evaluator import propose_revision

    revision = propose_revision(
        incumbent_text,
        incumbent.failures,
        observed_vocabulary(reports),
        incumbent.metrics,
        model=model,
        store=store,
    )
    candidate_version = prompts.next_version("extractor", root=prompt_root)
    # Saved before it is judged: a discarded candidate is still evidence, and the
    # ledger entry below points at a file that must exist.
    prompts.save_version(
        "extractor", candidate_version, revision.revised_instruction, root=prompt_root
    )
    candidate = run_extractor(
        reports,
        revision.revised_instruction,
        model=model,
        store=store,
        version=candidate_version,
    )

    guards = evaluate_extractor_guards(candidate.metrics, incumbent.metrics)
    dev_gain = candidate.metrics["extractor_macro_f1"] - incumbent.metrics["extractor_macro_f1"]

    incumbent_holdout: dict[str, float] | None = None
    candidate_holdout: dict[str, float] | None = None
    promoted = False
    if not guards.passed:
        reason = f"guard failure: {', '.join(guards.failures)}"
    elif dev_gain <= 0:
        reason = f"no dev gain (macro-F1 {dev_gain:+.4f}); holdout not consulted"
    elif not use_holdout:
        reason = f"dev gain {dev_gain:+.4f}, holdout skipped (--no-holdout); not promoted"
    else:
        from eval.holdout_score import score_prompt_on_holdout

        incumbent_holdout = score_prompt_on_holdout(
            incumbent_text, model=model, store=store, size=holdout_size, seed=seed
        )
        candidate_holdout = score_prompt_on_holdout(
            revision.revised_instruction,
            model=model,
            store=store,
            size=holdout_size,
            seed=seed,
        )
        holdout_gain = (
            candidate_holdout["extractor_macro_f1"] - incumbent_holdout["extractor_macro_f1"]
        )
        if holdout_gain > 0:
            prompts.promote("extractor", candidate_version, root=prompt_root)
            promoted = True
            reason = f"promoted: dev {dev_gain:+.4f}, holdout {holdout_gain:+.4f}"
        else:
            reason = (
                f"discarded: dev gained {dev_gain:+.4f} but holdout {holdout_gain:+.4f} "
                "— dev overfit"
            )

    result = LoopResult(
        promoted=promoted,
        reason=reason,
        incumbent_version=incumbent_version,
        candidate_version=candidate_version,
        rationale=revision.rationale,
        baseline_metrics=baseline.metrics,
        incumbent_dev=incumbent.metrics,
        candidate_dev=candidate.metrics,
        guards=guards,
        incumbent_holdout=incumbent_holdout,
        candidate_holdout=candidate_holdout,
    )
    write_ledger_entry(result, runs_dir=runs_dir)
    return result


def write_ledger_entry(result: LoopResult, *, runs_dir: Path = RUNS_DIR) -> Path:
    """Append one immutable run record to eval/runs/.

    EVAL.md: the improvement curve in the video is generated from this ledger,
    never hand-drawn — so a discarded or guard-blocked candidate is recorded
    exactly as carefully as a promoted one.
    """
    runs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = runs_dir / f"{stamp}-extractor.json"
    payload: dict[str, Any] = asdict(result)
    payload["guards"] = {
        "passed": result.guards.passed,
        "failures": list(result.guards.failures),
    }
    payload["recorded_at"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _format(result: LoopResult) -> str:
    def row(label: str, metrics: dict[str, float] | None) -> str:
        if not metrics:
            return f"  {label:<26} (not run)"
        return (
            f"  {label:<26} macro-F1 {metrics['extractor_macro_f1']:.4f}  "
            f"acc {metrics['primary_problem_accuracy']:.4f}  "
            f"diversity {metrics['primary_problem_label_diversity']:.2f}"
        )

    guard_line = (
        "PASS" if result.guards.passed else "FAIL " + ", ".join(result.guards.failures)
    )
    lines = [
        "Extractor self-improvement loop",
        row("baseline (majority+rules)", result.baseline_metrics),
        row(f"incumbent {result.incumbent_version} (dev)", result.incumbent_dev),
        row(f"candidate {result.candidate_version} (dev)", result.candidate_dev),
        row("incumbent (holdout)", result.incumbent_holdout),
        row("candidate (holdout)", result.candidate_holdout),
        f"  guards: {guard_line}",
        f"  rationale: {result.rationale}",
        f"  decision: {result.reason}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--holdout-size", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-holdout",
        action="store_true",
        help="Score and guard on dev only; never promote. Use while iterating.",
    )
    args = parser.parse_args(argv)
    result = improve_extractor(
        sample_size=args.sample_size,
        holdout_size=args.holdout_size,
        seed=args.seed,
        use_holdout=not args.no_holdout,
    )
    print(_format(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
