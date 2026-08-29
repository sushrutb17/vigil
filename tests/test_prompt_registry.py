from pathlib import Path

import pytest

from agents import prompts

ROOT = Path(__file__).parents[1]


def test_stored_v1_matches_the_in_source_constant() -> None:
    """The fallback and the file must not drift; the loop diffs against v1."""
    stored = (ROOT / "config/prompts/extractor/v1.txt").read_text(encoding="utf-8")
    assert stored == prompts.EXTRACTOR_INSTRUCTION


def test_load_falls_back_when_no_config_directory(tmp_path: Path) -> None:
    assert prompts.load_instruction("extractor", root=tmp_path) == prompts.EXTRACTOR_INSTRUCTION
    assert prompts.active_version("extractor", root=tmp_path) == "v1"


def test_save_then_promote_changes_the_active_instruction(tmp_path: Path) -> None:
    prompts.save_version("extractor", "v2", "revised text for the extractor", root=tmp_path)
    assert prompts.load_instruction("extractor", root=tmp_path) == prompts.EXTRACTOR_INSTRUCTION
    prompts.promote("extractor", "v2", root=tmp_path)
    assert prompts.active_version("extractor", root=tmp_path) == "v2"
    assert prompts.load_instruction("extractor", root=tmp_path) == "revised text for the extractor"


def test_cannot_promote_a_version_that_was_never_saved(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        prompts.promote("extractor", "v9", root=tmp_path)


def test_registry_refuses_non_revisable_agents() -> None:
    """Guardrail #7: the loop is extractor-only, enforced at the registry."""
    for agent in ("analyst", "risk", "critic", "brief_writer"):
        with pytest.raises(KeyError):
            prompts.load_instruction(agent)
        with pytest.raises(KeyError):
            prompts.save_version(agent, "v2", "text")


def test_next_version_skips_used_labels(tmp_path: Path) -> None:
    prompts.save_version("extractor", "v1", "a", root=tmp_path)
    prompts.save_version("extractor", "v7", "b", root=tmp_path)
    assert prompts.next_version("extractor", root=tmp_path) == "v8"
