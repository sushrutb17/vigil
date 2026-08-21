"""Shared retry, JSON-repair, and observability behavior for ADK call paths."""

from __future__ import annotations

import json
import time
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

from pipeline.store import AgentCallLog, TriageStore


class StructuredOutputError(RuntimeError):
    """Raised after one JSON repair attempt cannot produce a valid schema result."""


def call_with_observability[Result](
    *,
    store: TriageStore,
    agent: str,
    model: str,
    input_text: str,
    invoke: Callable[[], Result],
    max_retries: int = 2,
    backoff_seconds: float = 0.25,
    tokens: int | None = None,
) -> Result:
    """Run an agent invocation with capped retries and one audit log entry.

    A failed report is raised to its batch-level caller, which records that report
    as failed and continues the batch. No retry policy is placed inside the
    deterministic clustering stage.
    """
    started = time.perf_counter()
    try:
        for attempt in range(max_retries + 1):
            try:
                result = invoke()
                break
            except Exception:
                if attempt == max_retries:
                    raise
                time.sleep(backoff_seconds * (2**attempt))
        else:  # pragma: no cover - loop either breaks or raises
            raise RuntimeError("agent invocation loop exited unexpectedly")
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        store.put_agent_log(
            AgentCallLog.create(
                agent=agent,
                model=model,
                input_text=input_text,
                latency_ms=elapsed_ms,
                tokens=tokens,
            )
        )
    return result


def parse_structured_response[Structured: BaseModel](
    raw: str,
    schema: type[Structured],
    *,
    repair: Callable[[str], str] | None = None,
) -> Structured:
    """Parse a model JSON response and use one supplied repair call at most once."""
    try:
        return schema.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as initial_error:
        if repair is None:
            raise StructuredOutputError(
                "model response did not match required JSON schema"
            ) from initial_error
    try:
        return schema.model_validate(json.loads(repair(raw)))
    except (json.JSONDecodeError, ValidationError) as repair_error:
        raise StructuredOutputError(
            "JSON repair attempt did not match required schema"
        ) from repair_error
