from pathlib import Path

ROOT = Path(__file__).parents[1]


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
