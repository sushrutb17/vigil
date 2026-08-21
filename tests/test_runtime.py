from agents.contracts import DedupOutput
from agents.runtime import call_with_observability, parse_structured_response
from pipeline.store import MemoryStore


def test_call_retries_then_logs_once() -> None:
    store = MemoryStore()
    attempts = 0

    def invoke() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary failure")
        return "ok"

    assert (
        call_with_observability(
            store=store,
            agent="extractor",
            model="gemini-3.7-flash",
            input_text="source input",
            invoke=invoke,
            backoff_seconds=0,
        )
        == "ok"
    )
    assert attempts == 2
    assert len(store.agent_log) == 1
    assert store.agent_log[0]["agent"] == "extractor"


def test_structured_parse_uses_one_repair_attempt() -> None:
    result = parse_structured_response(
        "not json",
        DedupOutput,
        repair=lambda _: '{"same_event": true, "confidence": 0.8, "reason": "shared details"}',
    )
    assert result.same_event
