from pathlib import Path

import pytest

from agents.critic import strip_uncited_claims
from pipeline.ingest import load_parquet
from pipeline.risk import FrozenRiskPolicy


def test_critic_strips_uncited_claims() -> None:
    result = strip_uncited_claims("# Brief\nSupported [ACN 1234567]\nUnsupported conclusion")
    assert result.cleaned_brief == "# Brief\nSupported [ACN 1234567]"
    assert result.removed_claims == ("Unsupported conclusion",)


def test_frozen_policy_has_no_mutable_clustering_mapping() -> None:
    policy = FrozenRiskPolicy.from_path(Path("config/frozen.yaml"))
    with pytest.raises(TypeError):
        policy.clustering["min_cluster_size"] = 99  # type: ignore[index]


def test_live_ingest_refuses_holdout_reads() -> None:
    with pytest.raises(PermissionError):
        load_parquet(Path("data/holdout/test.parquet"))
