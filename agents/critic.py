"""Deterministic final citation gate for investigator briefs."""

from __future__ import annotations

import re
from collections.abc import Collection
from dataclasses import dataclass

ACN_CITATION = re.compile(r"\[ACN\s+\d{4,}\]", re.IGNORECASE)
_ACN_DIGITS = re.compile(r"\d{4,}")


@dataclass(frozen=True, slots=True)
class CriticResult:
    cleaned_brief: str
    removed_claims: tuple[str, ...]
    fabricated_citations: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        return not self.removed_claims and not self.fabricated_citations


#: Citations shown inline before the list is summarized. A 629-member cluster is
#: real (it occurred on the 5,000-report slice), and spelling out every ACN twice
#: produced an 18,000-character brief that no human would read.
MAX_INLINE_CITATIONS = 12


def format_citations(acns: Collection[str], *, limit: int = MAX_INLINE_CITATIONS) -> str:
    """Render member ACNs as bracketed citations, capped for readability.

    Guardrail #4 requires every claim to cite *an* ACN, not every ACN that
    supports it, so truncating the list does not weaken the gate: the claim is
    still sourced, and the surviving citations still have to be real reports.
    The remainder is stated rather than silently dropped, and the UI shows the
    complete member list beside the brief.
    """
    ordered = list(acns)
    shown = " ".join(f"[ACN {acn}]" for acn in ordered[:limit])
    remaining = len(ordered) - limit
    return f"{shown} (+{remaining} more in this cluster)" if remaining > 0 else shown


def strip_uncited_claims(brief: str, allowed_acns: Collection[str] | None = None) -> CriticResult:
    """Strip claims that lack a bracketed ACN citation, and citations that are fabricated.

    This deterministic gate runs after the Critic agent so model output can never
    bypass the citation requirement. Headings and a literal ``DEGRADED`` banner
    are permitted because neither is a factual claim.

    ``allowed_acns`` is the set of report IDs the cluster actually contains. Pass
    it whenever it is known. Without it this function validates only the *shape*
    of a citation, and ``ACN_CITATION`` matches any 4+ digit number, so a
    hallucinated ID is indistinguishable from a real one. That gap is not
    theoretical: a Risk agent given no ACNs to work from invented the sequence
    [ACN 1000001]..[ACN 1000005] and every one of them passed the gate.

    A fabricated citation is worse than a missing one. An uncited claim is
    stripped and vanishes; a fabricated citation *survives and carries false
    authority*, and an investigator who pulls that ACN gets an unrelated report.
    So invalid citations are removed from the line surgically — a claim keeps its
    genuine sources and loses only the invented ones — and the claim itself is
    dropped when nothing valid is left to support it.
    """
    allowed = {str(acn).strip() for acn in allowed_acns} if allowed_acns is not None else None
    kept: list[str] = []
    removed: list[str] = []
    fabricated: list[str] = []

    for line in brief.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "DEGRADED":
            kept.append(line)
            continue

        citations = ACN_CITATION.findall(line)
        if not citations:
            removed.append(stripped)
            continue
        if allowed is None:
            kept.append(line)
            continue

        cleaned = line
        for citation in citations:
            digits = _ACN_DIGITS.search(citation)
            if digits and digits.group() not in allowed:
                fabricated.append(digits.group())
                cleaned = cleaned.replace(citation, "")
        if not ACN_CITATION.search(cleaned):
            # Every source it offered was invented, so nothing supports the claim.
            removed.append(stripped)
            continue
        kept.append(re.sub(r"[ \t]{2,}", " ", cleaned).rstrip())

    return CriticResult(
        cleaned_brief="\n".join(kept).strip(),
        removed_claims=tuple(removed),
        fabricated_citations=tuple(dict.fromkeys(fabricated)),
    )
