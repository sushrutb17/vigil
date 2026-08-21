from pathlib import Path

from pipeline.embeddings import cache_embeddings
from pipeline.run_batch import demo_reports


def test_embedding_cache_writes_parquet(tmp_path: Path) -> None:
    reports = demo_reports()[:2]
    path = tmp_path / "embeddings.parquet"
    cache_embeddings(reports, [[0.1, 0.2], [0.3, 0.4]], path)
    assert path.exists()
