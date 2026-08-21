"""Deterministic final citation gate for investigator briefs."""

from __future__ import annotations

import re
from dataclasses import dataclass

ACN_CITATION = re.compile(r"\[ACN\s+\d{4,}\]", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class CriticResult:
    cleaned_brief: str
    removed_claims: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.removed_claims


def strip_uncited_claims(brief: str) -> CriticResult:
    """Strip nonblank bullet/paragraph claims that lack a bracketed ACN citation.

    This deterministic gate runs after the Critic agent so model output can never
    bypass the citation requirement. Headings and a literal ``DEGRADED`` banner
    are permitted because neither is a factual claim.
    """
    kept: list[str] = []
    removed: list[str] = []
    for line in brief.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "DEGRADED":
            kept.append(line)
        elif ACN_CITATION.search(line):
            kept.append(line)
        else:
            removed.append(stripped)
    return CriticResult(cleaned_brief="\n".join(kept).strip(), removed_claims=tuple(removed))
