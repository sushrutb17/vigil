"""Synchronous glue for running one ADK ``LlmAgent`` turn against a live model.

Kept separate from ``agents/definitions.py`` (which only builds agent objects and
must stay importable without credentials) and from ``agents/runtime.py`` (generic
retry/logging/JSON-repair, with no ADK dependency of its own).
"""

from __future__ import annotations

from dataclasses import dataclass

from agents.runtime import call_with_observability
from pipeline.store import TriageStore

_APP_NAME = "vigil"
_USER_ID = "vigil-batch"


@dataclass(frozen=True, slots=True)
class LiveCallResult:
    text: str
    tokens: int | None


def run_llm_agent(
    agent: object,
    *,
    message: str,
    model: str,
    store: TriageStore,
) -> str:
    """Run one ADK agent turn against a live model and log it to ``store``.

    Each call gets a fresh in-memory session — batch invocations are independent
    judgments (one report, one cluster), not turns in a shared conversation.
    Retries, backoff, and the ``agent_log`` entry are handled by
    ``call_with_observability``; this function only supplies the ADK-specific
    invoke step and pulls the token count out of the response for it to log.
    """
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    session_service = InMemorySessionService()
    session = session_service.create_session_sync(app_name=_APP_NAME, user_id=_USER_ID)
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)

    def invoke() -> LiveCallResult:
        content = types.Content(role="user", parts=[types.Part(text=message)])
        final_text: str | None = None
        tokens: int | None = None
        for event in runner.run(user_id=_USER_ID, session_id=session.id, new_message=content):
            if event.usage_metadata is not None:
                tokens = event.usage_metadata.total_token_count
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(part.text for part in event.content.parts if part.text)
        if final_text is None:
            raise RuntimeError(f"agent {agent.name!r} produced no final response")
        return LiveCallResult(text=final_text, tokens=tokens)

    result = call_with_observability(
        store=store,
        agent=agent.name,
        model=model,
        input_text=message,
        invoke=invoke,
        extract_tokens=lambda call: call.tokens,
    )
    return result.text
