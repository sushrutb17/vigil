from pathlib import Path

import pytest

from agents.critic import strip_uncited_claims
from pipeline.ingest import load_parquet
from pipeline.risk import FrozenRiskPolicy


def test_critic_strips_uncited_claims() -> None:
    result = strip_uncited_claims("# Brief\nSupported [ACN 1234567]\nUnsupported conclusion")
    assert result.cleaned_brief == "# Brief\nSupported [ACN 1234567]"
    assert result.removed_claims == ("Unsupported conclusion",)


def test_brief_contributing_prompts_demand_the_bracketed_citation_form() -> None:
    """Every agent whose prose flows into a brief must be told the exact bracketed
    citation format the deterministic gate matches.

    strip_uncited_claims keys on ACN_CITATION (``[ACN 1234567]``, square brackets
    required). An agent told only to "cite ACNs" writes bare "ACN 1234567", and the
    gate then deletes 100% of its output — the agent burns tokens on every run and
    contributes nothing, with no error to show for it. That is exactly how the
    Precedent and Risk sections shipped empty in the first live Cloud Run execution.
    """
    from agents import prompts

    for name in ("PRECEDENT_INSTRUCTION", "RISK_INSTRUCTION", "BRIEF_WRITER_INSTRUCTION"):
        instruction = getattr(prompts, name)
        assert "[ACN " in instruction, f"{name} must show the bracketed [ACN ...] form"
        # A sentence the prompt itself models must survive the real gate.
        sample = "Component driven by two reports [ACN 1000001] [ACN 1000002]."
        assert strip_uncited_claims(sample).cleaned_brief == sample


def test_critic_prompt_forbids_adding_its_own_wrapper() -> None:
    """live_draft_brief uses the Critic's entire response verbatim as the brief, so
    any title or commentary it adds lands in front of a human reviewer."""
    from agents import prompts

    assert "ONLY the cleaned brief" in prompts.CRITIC_INSTRUCTION


def test_frozen_policy_has_no_mutable_clustering_mapping() -> None:
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    with pytest.raises(TypeError):
        policy.clustering["min_cluster_size"] = 99  # type: ignore[index]


def test_live_ingest_refuses_holdout_reads() -> None:
    with pytest.raises(PermissionError):
        load_parquet(Path("data/holdout/test.parquet"))
