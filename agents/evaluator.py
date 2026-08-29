"""The Evaluator: reads extractor failures and proposes a prompt revision.

Offline only. Guardrail #7 scopes self-improvement to the extractor, so nothing
here may be imported by ``pipeline/run_batch.py`` — ``eval/improve.py`` is the
only caller. The Evaluator returns *text*; it never writes a file, never sees
``data/holdout/``, and has no path to ``config/frozen.yaml``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from agents import contracts, prompts
from agents.runtime import parse_structured_response
from eval.extractor_eval import Failure, failure_digest
from pipeline.store import TriageStore


def revision_message(
    current_instruction: str,
    failures: Sequence[Failure],
    vocabulary: Mapping[str, Sequence[str]],
    metrics: Mapping[str, float],
) -> str:
    """Assemble the Evaluator's evidence packet.

    Vocabulary is truncated per field: the point is to show the agent that the
    labels are a closed set, not to paste 101 rarely-used phase combinations
    into every revision.
    """
    vocabulary_lines = "\n".join(
        f"{field_name}: " + ", ".join(sorted(values)[:25])
        for field_name, values in vocabulary.items()
    )
    scored = {
        key: round(value, 4)
        for key, value in metrics.items()
        if key
        in {"primary_problem_accuracy", "extractor_macro_f1", "field_macro_f1", "parse_coverage"}
    }
    return (
        "CURRENT INSTRUCTION:\n"
        f"{current_instruction}\n\n"
        "SCORES ON THE DEV SAMPLE:\n"
        f"{json.dumps(scored, sort_keys=True)}\n\n"
        "CODED VOCABULARY OBSERVED IN THE DEV SAMPLE:\n"
        f"{vocabulary_lines}\n\n"
        "MOST FREQUENT MISTAKES:\n"
        f"{failure_digest(failures)}\n"
    )


def propose_revision(
    current_instruction: str,
    failures: Sequence[Failure],
    vocabulary: Mapping[str, Sequence[str]],
    metrics: Mapping[str, float],
    *,
    model: str,
    store: TriageStore,
) -> contracts.PromptRevision:
    """Ask the Evaluator for a replacement instruction for the extractor."""
    from google.adk.agents import LlmAgent

    from agents.live import run_llm_agent

    agent = LlmAgent(
        name="evaluator",
        model=model,
        instruction=prompts.EVALUATOR_INSTRUCTION,
        output_schema=contracts.PromptRevision,
    )
    message = revision_message(current_instruction, failures, vocabulary, metrics)
    raw = run_llm_agent(agent, message=message, model=model, store=store)
    return parse_structured_response(raw, contracts.PromptRevision)
