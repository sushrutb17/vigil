"""Storage interfaces with an in-memory implementation for the local demo."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol


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


class MemoryStore:
    """Local-only store whose behavior mirrors the required Firestore collections."""

    def __init__(self) -> None:
        self.reports: dict[str, dict[str, Any]] = {}
        self.clusters: dict[str, dict[str, Any]] = {}
        self.agent_log: list[dict[str, Any]] = []
        self._escalations: list[frozenset[str]] = []

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
