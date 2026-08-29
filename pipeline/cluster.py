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
    max_svd_components: int = 100,
    seed: int = 42,
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

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=2)
    sparse_embeddings = vectorizer.fit_transform([report.clustering_text() for report in reports])
    embeddings = _densify(sparse_embeddings, max_components=max_svd_components, seed=seed)
    return cluster_embedding_matrix(
        reports,
        embeddings,
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
    )


def _densify(sparse_matrix: object, *, max_components: int, seed: int) -> object:
    """Densify a sparse TF-IDF matrix, reducing dimensionality first at scale.

    A raw TF-IDF matrix over thousands of aviation narratives with bigrams can
    reach tens of thousands of columns. Converting that directly to a dense
    array (the previous behavior) is what made a 5k-report run burn 6+ minutes
    of CPU and multiple GB of RAM without finishing: HDBSCAN's exact-mode
    pairwise distance computation degrades badly at that width, on top of the
    memory cost of the dense array itself. TruncatedSVD (seeded, deterministic,
    no LLM call — compliant with the no-LLM-in-clustering guardrail) projects
    down first; this is also the standard LSA fix for HDBSCAN's known
    curse-of-dimensionality behavior on sparse TF-IDF space, not just a speed
    hack. Small inputs (below max_components) just densify directly, so the
    tiny demo fixture's behavior is unchanged.
    """
    n_samples, n_features = sparse_matrix.shape
    n_components = min(max_components, n_features - 1, n_samples - 1)
    if n_components < 2:
        return sparse_matrix.toarray()
    from sklearn.decomposition import TruncatedSVD

    reducer = TruncatedSVD(n_components=n_components, random_state=seed)
    return reducer.fit_transform(sparse_matrix)


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

        # A batch smaller than 2x min_cluster_size cannot physically split into
        # more than one qualifying cluster, so allow_single_cluster=True is the
        # only way to surface a pattern at all (this is what makes the 6-report
        # demo fixture escalate). At real scale, the same setting collapses a
        # diverse corpus into one dominant megacluster — verified on a 5k-report
        # real slice: allow_single_cluster=True gave 1 cluster covering 58% of
        # the batch, versus 23 distinct clusters with it off. So it only turns
        # on in the regime where it's load-bearing, not generally.
        model = hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            min_samples=min_samples,
            metric="euclidean",
            core_dist_n_jobs=1,
            approx_min_span_tree=False,
            prediction_data=False,
            allow_single_cluster=len(reports) < 2 * min_cluster_size,
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
