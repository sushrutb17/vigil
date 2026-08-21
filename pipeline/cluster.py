"""Deterministic, non-LLM clustering for emerging-hazard discovery."""

from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256

from pipeline.models import ASRSReport, Cluster


def cluster_reports(
    reports: Sequence[ASRSReport],
    *,
    min_cluster_size: int = 5,
    min_samples: int = 3,
) -> list[Cluster]:
    """Cluster text embeddings with seeded HDBSCAN and return stable member sets.

    This stage must stay free of generative-model calls. TF-IDF is a local,
    deterministic embedding fallback for the runnable demo; production may pass
    cached batch embeddings into ``cluster_embedding_matrix`` instead.
    """
    if not reports:
        return []
    if len(reports) < min_cluster_size:
        return [
            Cluster(
                cluster_id=f"noise-{report.acn}",
                member_acns=(report.acn,),
                label=-1,
                noise=True,
            )
            for report in reports
        ]
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1)
    embeddings = vectorizer.fit_transform([report.clustering_text() for report in reports])
    return cluster_embedding_matrix(
        reports,
        embeddings.toarray(),
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )


def cluster_embedding_matrix(
    reports: Sequence[ASRSReport],
    embeddings: object,
    *,
    min_cluster_size: int = 5,
    min_samples: int = 3,
) -> list[Cluster]:
    """Run HDBSCAN over precomputed batch embeddings without any LLM dependency."""
    if len(reports) == 0:
        return []
    if len(reports) < min_cluster_size:
        labels = [-1] * len(reports)
    else:
        import hdbscan

        model = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
            core_dist_n_jobs=1,
            approx_min_span_tree=False,
            prediction_data=False,
            allow_single_cluster=True,
        )
        labels = model.fit_predict(embeddings).tolist()
    grouped: dict[int, list[str]] = {}
    for report, label in zip(reports, labels, strict=True):
        grouped.setdefault(int(label), []).append(report.acn)
    clusters: list[Cluster] = []
    for label, acns in sorted(grouped.items()):
        members = tuple(sorted(acns))
        digest = sha256(",".join(members).encode()).hexdigest()[:12]
        clusters.append(
            Cluster(
                cluster_id=(f"noise-{digest}" if label == -1 else f"cluster-{digest}"),
                member_acns=members,
                label=label,
                noise=label == -1,
            )
        )
    return clusters
