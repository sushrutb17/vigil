"""Storage interfaces with an in-memory implementation for the local demo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

from pipeline.models import HazardObservation, HazardRecord

#: Rejection reasons must be non-blank after trimming and no longer than this
#: (T1-03, docs/TIER1_ENHANCEMENTS_SPEC.md 8.1.7).
MAX_REJECTION_REASON_LENGTH = 2000

#: Strictly-greater-than boundary for hazard identity matching (T1-04, 9.1.3),
#: matching the existing escalation-ledger boundary in
#: previously_escalated/record_escalation below.
HAZARD_MATCH_THRESHOLD = 0.6


class RejectionReasonError(ValueError):
    """Raised by ``record_rejection`` when the reason fails validation."""


def _clean_rejection_reason(reason: str) -> str:
    """Shared by both store implementations so neither can drift from the
    other's notion of a valid reason (8.3)."""
    trimmed = reason.strip()
    if not trimmed:
        raise RejectionReasonError("Rejection reason cannot be blank.")
    if len(trimmed) > MAX_REJECTION_REASON_LENGTH:
        raise RejectionReasonError(
            f"Rejection reason must be {MAX_REJECTION_REASON_LENGTH} characters or fewer "
            f"(got {len(trimmed)})."
        )
    return trimmed


def match_hazard(
    member_acns: frozenset[str], candidates: Mapping[str, frozenset[str]]
) -> str | None:
    """Pick the existing hazard whose latest member set best overlaps
    ``member_acns``, or ``None`` if no candidate qualifies.

    Only similarity strictly greater than ``HAZARD_MATCH_THRESHOLD`` qualifies
    (9.1.3). Ties are broken by lexicographically smallest ``hazard_id`` so the
    choice is deterministic (9.1.4).
    """
    qualifying = [
        (hazard_id, _jaccard(member_acns, latest))
        for hazard_id, latest in candidates.items()
        if _jaccard(member_acns, latest) > HAZARD_MATCH_THRESHOLD
    ]
    if not qualifying:
        return None
    best_score = max(score for _, score in qualifying)
    return min(hazard_id for hazard_id, score in qualifying if score == best_score)


def _new_hazard_id(cluster_id: str, member_acns: frozenset[str]) -> str:
    """A fresh hazard's identity is derived from its first cluster ID plus a
    stable digest of its member set -- never a display name, which can change
    on a later re-observation (9.1.5)."""
    digest = sha256(",".join(sorted(member_acns)).encode()).hexdigest()[:10]
    return f"hazard-{cluster_id}-{digest}"


@dataclass(frozen=True, slots=True)
class AgentCallLog:
    agent: str
    model: str
    latency_ms: int
    tokens: int | None
    input_hash: str
    created_at: str

    @classmethod
    def create(
        cls, *, agent: str, model: str, input_text: str, latency_ms: int, tokens: int | None = None
    ) -> AgentCallLog:
        return cls(
            agent=agent,
            model=model,
            latency_ms=latency_ms,
            tokens=tokens,
            input_hash=sha256(input_text.encode()).hexdigest(),
            created_at=datetime.now(UTC).isoformat(),
        )


class TriageStore(Protocol):
    def put_report(self, acn: str, value: dict[str, Any]) -> None: ...

    def put_cluster(self, cluster_id: str, value: dict[str, Any]) -> None: ...

    def put_agent_log(self, value: AgentCallLog) -> None: ...

    def previously_escalated(self, member_acns: frozenset[str]) -> bool: ...

    def record_escalation(self, member_acns: frozenset[str]) -> None: ...

    def set_cluster_status(self, cluster_id: str, status: str) -> None: ...

    def put_cluster_brief(self, cluster_id: str, brief: str) -> None: ...

    def put_cluster_evidence(self, cluster_id: str, evidence_acns: list[str]) -> None: ...

    def put_rejection(self, cluster_id: str, value: dict[str, Any]) -> None: ...

    def record_approval(self, cluster_id: str, value: dict[str, Any]) -> None: ...

    def record_rejection(self, cluster_id: str, value: dict[str, Any]) -> None: ...

    def record_hazard_observation(
        self,
        *,
        cluster_id: str,
        display_name: str,
        member_acns: frozenset[str],
        risk_total: float,
        run_id: str,
        run_at: str,
    ) -> HazardRecord: ...


class MemoryStore:
    """Local-only store whose behavior mirrors the required Firestore collections."""

    def __init__(self) -> None:
        self.reports: dict[str, dict[str, Any]] = {}
        self.clusters: dict[str, dict[str, Any]] = {}
        self.agent_log: list[dict[str, Any]] = []
        self._escalations: list[frozenset[str]] = []
        self.rejections: dict[str, dict[str, Any]] = {}
        self.hazards: dict[str, dict[str, Any]] = {}
        self._hazard_observations: dict[str, dict[str, dict[str, Any]]] = {}

    def put_report(self, acn: str, value: dict[str, Any]) -> None:
        self.reports.setdefault(acn, value)

    def put_cluster(self, cluster_id: str, value: dict[str, Any]) -> None:
        self.clusters[cluster_id] = value

    def put_agent_log(self, value: AgentCallLog) -> None:
        self.agent_log.append(asdict(value))

    def previously_escalated(self, member_acns: frozenset[str]) -> bool:
        return any(_jaccard(member_acns, old) > 0.6 for old in self._escalations)

    def record_escalation(self, member_acns: frozenset[str]) -> None:
        if not self.previously_escalated(member_acns):
            self._escalations.append(member_acns)

    def set_cluster_status(self, cluster_id: str, status: str) -> None:
        """Update just the status field (human gate decision), preserving the rest
        of whatever the batch job already wrote for this cluster."""
        self.clusters.setdefault(cluster_id, {})["status"] = status

    def put_cluster_brief(self, cluster_id: str, brief: str) -> None:
        self.clusters.setdefault(cluster_id, {})["brief"] = brief

    def put_cluster_evidence(self, cluster_id: str, evidence_acns: list[str]) -> None:
        """Store which ACNs a cluster's final brief has evidence for (T1-02).

        Only the ACN list, not narrative text: full report documents already
        live once under ``reports/{acn}`` (docs/TIER1_ENHANCEMENTS_SPEC.md 5.2),
        so a cluster document must never duplicate narrative excerpts.
        """
        self.clusters.setdefault(cluster_id, {})["evidence_acns"] = evidence_acns

    def put_rejection(self, cluster_id: str, value: dict[str, Any]) -> None:
        self.rejections[cluster_id] = value

    def record_approval(self, cluster_id: str, value: dict[str, Any]) -> None:
        """Atomically (single dict mutation) persist an approval decision.

        Only the fields this decision owns are set, preserving whatever the
        batch job already wrote for this cluster (T1-03, 5.4, 8.1.5).
        """
        cluster = self.clusters.setdefault(cluster_id, {})
        cluster["status"] = "approved"
        cluster["brief_draft"] = value["brief_draft"]
        cluster["brief_approved"] = value["brief_approved"]
        cluster["decision_at"] = datetime.now(UTC).isoformat()

    def record_rejection(self, cluster_id: str, value: dict[str, Any]) -> None:
        """Atomically persist the cluster status flip and the rejection
        record as one logical decision (5.4). Raises ``RejectionReasonError``
        (blank or over 2,000 chars) and performs no writes at all -- neither
        the status nor the record -- on an invalid reason (8.1.9).
        """
        reason = _clean_rejection_reason(value["reason"])
        self.clusters.setdefault(cluster_id, {})["status"] = "rejected"
        self.rejections[cluster_id] = {
            "cluster_id": cluster_id,
            "reason": reason,
            "brief_draft": value["brief_draft"],
            "brief_at_rejection": value["brief_at_rejection"],
            "member_acns": list(value["member_acns"]),
            "decision_at": datetime.now(UTC).isoformat(),
        }

    def record_hazard_observation(
        self,
        *,
        cluster_id: str,
        display_name: str,
        member_acns: frozenset[str],
        risk_total: float,
        run_id: str,
        run_at: str,
    ) -> HazardRecord:
        """Match ``member_acns`` against existing hazards' latest member sets
        (T1-04 9.1), write one observation keyed by ``run_id`` (idempotent --
        replaying the same logical run adds no new point, 5.5), and return the
        hazard plus its history in ascending ``run_at`` order.
        """
        candidates = {
            hazard_id: frozenset(hazard["latest_member_acns"])
            for hazard_id, hazard in self.hazards.items()
        }
        hazard_id = match_hazard(member_acns, candidates)
        if hazard_id is None:
            hazard_id = _new_hazard_id(cluster_id, member_acns)
            self.hazards[hazard_id] = {
                "hazard_id": hazard_id,
                "display_name": display_name,
                "latest_member_acns": sorted(member_acns),
                "first_seen_at": run_at,
                "last_seen_at": run_at,
                "observation_count": 0,
            }
            self._hazard_observations[hazard_id] = {}

        observations = self._hazard_observations[hazard_id]
        if run_id not in observations:
            observations[run_id] = {
                "run_id": run_id,
                "run_at": run_at,
                "cluster_id": cluster_id,
                "member_count": len(member_acns),
                "risk_total": risk_total,
            }
            hazard = self.hazards[hazard_id]
            hazard["display_name"] = display_name
            hazard["latest_member_acns"] = sorted(member_acns)
            hazard["last_seen_at"] = run_at
            hazard["observation_count"] += 1

        return self._hazard_record(hazard_id)

    def _hazard_record(self, hazard_id: str) -> HazardRecord:
        hazard = self.hazards[hazard_id]
        observations = self._hazard_observations[hazard_id]
        history = tuple(
            HazardObservation(**observations[run_id])
            for run_id in sorted(observations, key=lambda rid: observations[rid]["run_at"])
        )
        return HazardRecord(
            hazard_id=hazard["hazard_id"],
            display_name=hazard["display_name"],
            latest_member_acns=tuple(hazard["latest_member_acns"]),
            first_seen_at=hazard["first_seen_at"],
            last_seen_at=hazard["last_seen_at"],
            observation_count=hazard["observation_count"],
            history=history,
        )


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


class FirestoreStore:
    """Firestore-backed store used by authenticated Cloud Run executions.

    The client is initialized lazily so no local import, test, or deterministic
    demo requires cloud credentials. Collections mirror the architecture doc.
    """

    def __init__(self, project: str | None = None) -> None:
        from google.cloud import firestore

        self._db = firestore.Client(project=project)
        # Kept for reuse by methods below (SERVER_TIMESTAMP, transactional) so
        # each one doesn't repeat the same lazy import.
        self._firestore = firestore

    def put_report(self, acn: str, value: dict[str, Any]) -> None:
        self._db.collection("reports").document(acn).set(value, merge=False)

    def put_cluster(self, cluster_id: str, value: dict[str, Any]) -> None:
        self._db.collection("clusters").document(cluster_id).set(value, merge=False)

    def put_agent_log(self, value: AgentCallLog) -> None:
        self._db.collection("agent_log").add(asdict(value))

    def previously_escalated(self, member_acns: frozenset[str]) -> bool:
        for document in self._db.collection("escalations").stream():
            existing = frozenset(document.to_dict().get("member_acns", []))
            if _jaccard(member_acns, existing) > 0.6:
                return True
        return False

    def record_escalation(self, member_acns: frozenset[str]) -> None:
        if not self.previously_escalated(member_acns):
            self._db.collection("escalations").add({"member_acns": sorted(member_acns)})

    def set_cluster_status(self, cluster_id: str, status: str) -> None:
        # merge=True: a status update from the human gate must not clobber the
        # analyst output/risk fields the batch job already wrote for this cluster.
        self._db.collection("clusters").document(cluster_id).set({"status": status}, merge=True)

    def put_cluster_brief(self, cluster_id: str, brief: str) -> None:
        # merge=True for the same reason as set_cluster_status: the brief is
        # written in a second pass, after triage_batch already populated this
        # document with the analyst output and risk score.
        #
        # Deliberately does NOT advance status to "briefed". The status field
        # carries the new/escalated distinction that drives the UI's
        # "NEW THIS RUN" badge and the escalation dedup ledger; overwriting it
        # here would make every briefed cluster indistinguishable from one that
        # was already escalated on a previous run.
        self._db.collection("clusters").document(cluster_id).set({"brief": brief}, merge=True)

    def put_cluster_evidence(self, cluster_id: str, evidence_acns: list[str]) -> None:
        # merge=True: written in the same second pass as put_cluster_brief, after
        # triage_batch already populated this cluster document. Only the ACN
        # list is stored -- full report documents already live once under
        # reports/{acn}, so this must never duplicate narrative text.
        self._db.collection("clusters").document(cluster_id).set(
            {"evidence_acns": evidence_acns}, merge=True
        )

    def put_rejection(self, cluster_id: str, value: dict[str, Any]) -> None:
        self._db.collection("rejections").document(cluster_id).set(value, merge=False)

    def record_approval(self, cluster_id: str, value: dict[str, Any]) -> None:
        # A single merge update -- approval only ever touches this one
        # document, so there is nothing that needs batching (8.2).
        self._db.collection("clusters").document(cluster_id).set(
            {
                "status": "approved",
                "brief_draft": value["brief_draft"],
                "brief_approved": value["brief_approved"],
                "decision_at": self._firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def record_rejection(self, cluster_id: str, value: dict[str, Any]) -> None:
        # Raise before touching Firestore at all: an invalid reason performs
        # no writes (8.1.9).
        reason = _clean_rejection_reason(value["reason"])
        # Atomic batched write: the cluster status flip and the rejection
        # record are one logical decision (5.4) and must never be observable
        # half-applied -- if commit() raises, neither write took effect.
        batch = self._db.batch()
        batch.set(
            self._db.collection("clusters").document(cluster_id),
            {"status": "rejected"},
            merge=True,
        )
        batch.set(
            self._db.collection("rejections").document(cluster_id),
            {
                "cluster_id": cluster_id,
                "reason": reason,
                "brief_draft": value["brief_draft"],
                "brief_at_rejection": value["brief_at_rejection"],
                "member_acns": list(value["member_acns"]),
                "decision_at": self._firestore.SERVER_TIMESTAMP,
            },
        )
        batch.commit()

    def record_hazard_observation(
        self,
        *,
        cluster_id: str,
        display_name: str,
        member_acns: frozenset[str],
        risk_total: float,
        run_id: str,
        run_at: str,
    ) -> HazardRecord:
        """Match, then write the chosen hazard and its observation atomically
        in one transaction (9.3). The transaction body only reads via the
        transaction snapshot and only mutates through ``transaction.set`` --
        never local/process state -- so a retry after a contention abort
        re-reads current data instead of replaying stale writes (9.4).
        """
        hazards_ref = self._db.collection("hazards")
        transaction = self._db.transaction()

        @self._firestore.transactional
        def _run(transaction: Any) -> dict[str, Any]:
            candidates = {
                doc.id: frozenset(doc.to_dict().get("latest_member_acns", []))
                for doc in hazards_ref.stream(transaction=transaction)
            }
            matched = match_hazard(member_acns, candidates)
            hazard_id = matched or _new_hazard_id(cluster_id, member_acns)
            hazard_doc = hazards_ref.document(hazard_id)
            existing_snapshot = hazard_doc.get(transaction=transaction)
            existing = existing_snapshot.to_dict() if existing_snapshot.exists else None

            obs_ref = hazard_doc.collection("observations").document(run_id)
            already_observed = obs_ref.get(transaction=transaction).exists
            if already_observed:
                # Idempotent replay of the same logical run: no new point,
                # no field changes -- return the hazard exactly as it stands.
                return existing or {
                    "hazard_id": hazard_id,
                    "display_name": display_name,
                    "latest_member_acns": sorted(member_acns),
                    "first_seen_at": run_at,
                    "last_seen_at": run_at,
                    "observation_count": 0,
                }

            hazard_data = {
                "hazard_id": hazard_id,
                "display_name": display_name,
                "latest_member_acns": sorted(member_acns),
                "first_seen_at": existing["first_seen_at"] if existing else run_at,
                "last_seen_at": run_at,
                "observation_count": (existing["observation_count"] if existing else 0) + 1,
            }
            transaction.set(hazard_doc, hazard_data)
            transaction.set(
                obs_ref,
                {
                    "run_id": run_id,
                    "run_at": run_at,
                    "cluster_id": cluster_id,
                    "member_count": len(member_acns),
                    "risk_total": risk_total,
                },
            )
            return hazard_data

        hazard_data = _run(transaction)
        hazard_id = hazard_data["hazard_id"]
        observations = [
            doc.to_dict()
            for doc in hazards_ref.document(hazard_id)
            .collection("observations")
            .order_by("run_at")
            .stream()
        ]
        return HazardRecord(
            hazard_id=hazard_data["hazard_id"],
            display_name=hazard_data["display_name"],
            latest_member_acns=tuple(hazard_data["latest_member_acns"]),
            first_seen_at=hazard_data["first_seen_at"],
            last_seen_at=hazard_data["last_seen_at"],
            observation_count=hazard_data["observation_count"],
            history=tuple(HazardObservation(**obs) for obs in observations),
        )
