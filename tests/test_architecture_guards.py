import ast
from pathlib import Path

ROOT = Path(__file__).parents[1]


def code_only(relative_path: str) -> str:
    """Return a module's executable source with docstrings and comments removed.

    A plain substring scan cannot tell "writes config/frozen.yaml" from a
    docstring promising it never does, and these modules document their own
    guardrails at length. ``ast.unparse`` drops comments for free; docstrings
    are stripped explicitly.
    """
    tree = ast.parse((ROOT / relative_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_cluster_stage_has_no_google_model_client() -> None:
    source = (ROOT / "pipeline/cluster.py").read_text(encoding="utf-8")
    assert "from google" not in source
    assert "genai.Client" not in source


def test_holdout_reader_is_isolated_from_live_pipeline() -> None:
    live_pipeline = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "pipeline").glob("*.py")
        if path.name != "ingest.py"
    )
    assert "data/holdout" not in live_pipeline


def test_self_improvement_loop_is_not_reachable_from_the_live_pipeline() -> None:
    """Guardrail #7: the loop is offline. Nothing in pipeline/ may import it."""
    pipeline_source = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "pipeline").glob("*.py")
    )
    for offline_module in ("eval.improve", "eval.extractor_eval", "agents.evaluator"):
        assert offline_module not in pipeline_source


def test_loop_never_writes_the_frozen_risk_policy() -> None:
    """Guardrail #2: a promotion writes config/prompts/, never config/frozen.yaml."""
    loop_source = "\n".join(
        code_only(name)
        for name in ("eval/improve.py", "agents/evaluator.py", "eval/extractor_eval.py")
    )
    assert "frozen.yaml" not in loop_source


def test_holdout_is_read_only_through_the_holdout_scorer() -> None:
    """Guardrail #3: extend the isolation check to the whole offline loop."""
    for name in ("eval/improve.py", "eval/extractor_eval.py", "agents/evaluator.py"):
        assert "data/holdout" not in code_only(name)


def test_only_the_extractor_prompt_is_revisable() -> None:
    from agents.prompts import REVISABLE

    assert set(REVISABLE) == {"extractor"}
