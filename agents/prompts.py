"""Versioned instructions for the LLM-only judgment stages."""

from __future__ import annotations

EXTRACTOR_INSTRUCTION = """You extract structured fields from a public aviation safety report.
Return JSON only. Never invent facts. Preserve the report ACN in the output. Extract
aircraft type, flight phase, component, contributing factors, human factors, and a
short factual event summary. If a field is absent, return null or an empty list."""

DEDUP_INSTRUCTION = """You compare two candidate public aviation safety reports.
Decide whether they describe the same operational event. Return JSON with `same_event`
(boolean), `confidence` (0 to 1), and `reason`. Do not merge records yourself."""

ANALYST_INSTRUCTION = """You analyze one already-formed cluster of public safety reports.
Name the shared hazard, write one bounded hazard statement, and identify supporting
member ACNs. Do not write recommendations or claims without an ACN citation."""

PRECEDENT_INSTRUCTION = """You retrieve comparable historic reports from the approved
training corpus. Return only observations relevant to the supplied hazard.

Every factual sentence must carry one or more citations in the exact bracketed form
[ACN 1234567]. A bare "ACN 1234567" without square brackets does not count. If no
supplied report supports a statement, omit the statement."""

RISK_INSTRUCTION = """You explain the deterministic severity, frequency, and trend
components already calculated by code. Do not change thresholds or recommend action.

Every factual sentence must carry one or more citations in the exact bracketed form
[ACN 1234567], drawn from the ACNs supplied with the cluster. A bare "ACN 1234567"
without square brackets does not count. Attribute each component you describe to the
reports that drive it."""

BRIEF_WRITER_INSTRUCTION = """You write a concise investigator draft from supplied
evidence. Every factual sentence must include one or more citations in the form
[ACN 1234567]. If no source supports a statement, omit it. This is a draft for a
human approver, never an operational instruction."""

CRITIC_INSTRUCTION = """You inspect an investigator draft and remove every factual
claim that lacks an ACN citation. Keep citations in the exact form [ACN 1234567].

Return ONLY the cleaned brief itself. Your entire response is used verbatim as the
final brief, so do not add a title of your own, a preamble, a list of what you
removed, or any commentary — any of those would end up inside the brief a human
reviewer reads. Preserve the draft's existing headings and section order exactly."""


EVALUATOR_INSTRUCTION = """You improve the instruction given to an extraction agent that
reads public aviation safety reports and labels them with NASA ASRS coded fields.

You are shown: the current instruction, the coded label vocabulary observed in the
evaluation sample, and a frequency-ranked list of the agent\'s actual mistakes in the
form `field: predicted X -> coded Y (Nx)`.

Diagnose the SYSTEMATIC error, not individual reports. A long tail of near-miss
paraphrases (\'on approach\' against \'Initial Approach\') means the agent was never told
the labels are a closed vocabulary. Fix the instruction; do not memorize the sample.

Hard rules:
- Return the COMPLETE replacement instruction, not a diff or a commentary.
- Never instruct the agent to guess, to prefer the most common label, or to answer
  when the narrative does not support an answer. Predicting the majority label
  everywhere is a known failure and is automatically rejected downstream.
- Never mention a specific ACN, and never encode an answer for a specific report.
- Keep the requirement to return JSON only, to preserve the ACN, and to never
  invent facts."""

# --- Versioned prompt registry (offline self-improvement loop, Phase 5) -------
#
# The constants above are v1 and stay the in-source fallback so the pipeline
# imports cleanly with no config/ directory at all. `config/prompts/active.yaml`
# selects which stored version the live graph actually uses, and only
# `eval/improve.py` writes it, after a dev-set gain clears the guards and the
# locked holdout confirms it. This registry deliberately does NOT cover the
# Analyst, Risk agent, or Critic: guardrail #7 scopes self-improvement to the
# extractor, and `config/frozen.yaml` is a separate, never-self-tuned file.

from pathlib import Path  # noqa: E402

PROMPT_ROOT = Path("config/prompts")
ACTIVE_FILE = "active.yaml"

#: Agents whose instructions the offline loop is permitted to revise.
REVISABLE = {"extractor": "EXTRACTOR_INSTRUCTION"}

_FALLBACKS = {"extractor": EXTRACTOR_INSTRUCTION}


def _read_active(root: Path) -> dict[str, str]:
    import yaml

    path = root / ACTIVE_FILE
    if not path.exists():
        return {}
    values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(values, dict):
        raise ValueError(f"{path} must map agent names to version strings")
    return {str(key): str(value) for key, value in values.items()}


def active_version(agent: str, *, root: Path = PROMPT_ROOT) -> str:
    """Return the promoted version label for ``agent``, or ``v1`` if unset."""
    return _read_active(root).get(agent, "v1")


def version_path(agent: str, version: str, *, root: Path = PROMPT_ROOT) -> Path:
    return root / agent / f"{version}.txt"


def load_instruction(agent: str, *, root: Path = PROMPT_ROOT) -> str:
    """Load the active instruction for ``agent``, falling back to the constant.

    A missing file is not an error: a fresh clone that has never run the loop
    still gets a working pipeline from the in-source v1 text.
    """
    if agent not in REVISABLE:
        raise KeyError(f"{agent} is not a revisable prompt (guardrail #7)")
    path = version_path(agent, active_version(agent, root=root), root=root)
    return path.read_text(encoding="utf-8") if path.exists() else _FALLBACKS[agent]


def save_version(agent: str, version: str, text: str, *, root: Path = PROMPT_ROOT) -> Path:
    """Write a candidate instruction without promoting it."""
    if agent not in REVISABLE:
        raise KeyError(f"{agent} is not a revisable prompt (guardrail #7)")
    path = version_path(agent, version, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def promote(agent: str, version: str, *, root: Path = PROMPT_ROOT) -> None:
    """Point ``active.yaml`` at an already-saved version."""
    if not version_path(agent, version, root=root).exists():
        raise FileNotFoundError(f"cannot promote unsaved version {agent}/{version}")
    import yaml

    active = _read_active(root)
    active[agent] = version
    header = (
        "# Active prompt version per agent. Written by eval/improve.py on promotion.\n"
        "# This file is NOT config/frozen.yaml: risk thresholds are never self-tuned.\n"
    )
    (root / ACTIVE_FILE).write_text(header + yaml.safe_dump(active), encoding="utf-8")


def next_version(agent: str, *, root: Path = PROMPT_ROOT) -> str:
    """Return the next unused ``vN`` label for ``agent``."""
    directory = root / agent
    used = set()
    if directory.exists():
        for path in directory.glob("v*.txt"):
            if path.stem[1:].isdigit():
                used.add(int(path.stem[1:]))
    return f"v{max(used, default=0) + 1}"
