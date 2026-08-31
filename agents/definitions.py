"""Google ADK agent graph.

Imports are intentionally delayed so deterministic stages and tests run without
credentials. ``build_agent_graph`` is called only by a live, authenticated run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agents import contracts, prompts


def load_models(path: Path = Path("config/models.yaml")) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as handle:
        values = yaml.safe_load(handle)
    if not isinstance(values, dict) or not all(isinstance(value, str) for value in values.values()):
        raise ValueError("models.yaml must map model roles to model IDs")
    return dict(values)


def build_agent_graph(models_path: Path = Path("config/models.yaml")) -> dict[str, Any]:
    """Create the ADK graph without putting any LLM call in clustering.

    The batch orchestrator invokes individual agents around plain-Python stages;
    this graph makes the Sequential and Parallel relationships explicit for live
    execution and observability.
    """
    from google.adk.agents import LlmAgent, ParallelAgent, SequentialAgent

    models = load_models(models_path)
    flash = models["flash"]
    extractor = LlmAgent(
        name="extractor",
        model=flash,
        # The one instruction the offline loop may replace; everything else
        # below is source-pinned. Falls back to the in-source constant when
        # config/prompts/ is absent, so a fresh clone still builds a graph.
        instruction=prompts.load_instruction("extractor"),
        output_schema=contracts.ExtractionOutput,
    )
    dedup = LlmAgent(
        name="dedup",
        model=flash,
        instruction=prompts.DEDUP_INSTRUCTION,
        output_schema=contracts.DedupOutput,
    )
    analyst = LlmAgent(
        name="analyst",
        model=flash,
        instruction=prompts.ANALYST_INSTRUCTION,
        output_schema=contracts.ClusterAnalysisOutput,
    )
    precedent = LlmAgent(name="precedent", model=flash, instruction=prompts.PRECEDENT_INSTRUCTION)
    risk = LlmAgent(name="risk", model=flash, instruction=prompts.RISK_INSTRUCTION)
    brief_writer = LlmAgent(
        name="brief_writer",
        model=models["brief_writer"],
        instruction=prompts.BRIEF_WRITER_INSTRUCTION,
    )
    critic = LlmAgent(name="critic", model=flash, instruction=prompts.CRITIC_INSTRUCTION)
    return {
        "intake": SequentialAgent(name="intake", sub_agents=[extractor, dedup]),
        "analyst": analyst,
        "coordinator": ParallelAgent(
            name="coordinator", sub_agents=[precedent, risk, brief_writer]
        ),
        # Also exposed individually: run_batch.py's live path fans these three
        # out with plain-Python concurrency (per-call try/except -> 2-of-3
        # failure tolerance) rather than through the ParallelAgent above, per
        # ARCHITECTURE.md's own "orchestration logic that can be plain Python
        # should be plain Python" guidance. The ParallelAgent object still
        # documents the real Sequential/Parallel shape of the graph.
        "precedent": precedent,
        "risk": risk,
        "brief_writer": brief_writer,
        "critic": critic,
    }
