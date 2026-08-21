"""Versioned instructions for the LLM-only judgment stages."""

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
training corpus. Return only ACN-cited observations relevant to the supplied hazard."""

RISK_INSTRUCTION = """You explain the deterministic severity, frequency, and trend
components already calculated by code. Do not change thresholds or recommend action."""

BRIEF_WRITER_INSTRUCTION = """You write a concise investigator draft from supplied
evidence. Every factual sentence must include one or more citations in the form
[ACN 1234567]. If no source supports a statement, omit it. This is a draft for a
human approver, never an operational instruction."""

CRITIC_INSTRUCTION = """You inspect an investigator draft and remove every factual
claim that lacks an ACN citation. Keep citations in the form [ACN 1234567]. Return
the cleaned brief and a list of removed claims."""
