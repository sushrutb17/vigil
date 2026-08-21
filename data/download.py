"""Fetch ASRS Parquet exports and make the test split a locked holdout copy."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

DATASET_REPO = "elihoole/asrs-aviation-reports"
PARQUET_REVISION = "refs/convert/parquet"


def download_splits(destination: Path = Path("data/raw")) -> dict[str, Path]:
    """Download only Parquet artifacts from the approved Hugging Face revision."""
    from huggingface_hub import snapshot_download

    destination.mkdir(parents=True, exist_ok=True)
    snapshot_path = Path(
        snapshot_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            revision=PARQUET_REVISION,
            allow_patterns=["*.parquet"],
            local_dir=destination,
        )
    )
    splits = _find_splits(snapshot_path)
    if not {"train", "validation", "test"}.issubset(splits):
        raise RuntimeError("expected train, validation, and test Parquet splits")
    lock_holdout(splits["test"], Path("data/holdout/test.parquet"))
    return splits


def _find_splits(snapshot_path: Path) -> dict[str, Path]:
    """Find split files whether the conversion stores them by file or directory."""
    found: dict[str, Path] = {}
    for path in snapshot_path.rglob("*.parquet"):
        searchable = "/".join(part.lower() for part in path.relative_to(snapshot_path).parts)
        for split in ("train", "validation", "test"):
            if split in searchable and split not in found:
                found[split] = path
    return found


def lock_holdout(source: Path, destination: Path) -> None:
    """Copy the designated test split once; reject replacement to protect evaluation."""
    if destination.exists():
        raise FileExistsError("locked holdout already exists; it must not be replaced")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    destination.chmod(0o444)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download approved ASRS Parquet exports")
    parser.add_argument("--destination", type=Path, default=Path("data/raw"))
    args = parser.parse_args()
    splits = download_splits(args.destination)
    for split, path in sorted(splits.items()):
        print(f"{split}: {path}")


if __name__ == "__main__":
    main()
