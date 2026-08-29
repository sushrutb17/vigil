# VIGIL Tier 1 Enhancements — Technical Specification

**Document status:** Ready for implementation

**Scope:** Tier 1 items 1–4 from `docs/FUTURE_ENHANCEMENTS.md` only

**Implementation baseline:** `main` at `e40d86c`

**Status last audited:** 2026-08-29

**Intended readers:** Developers implementing, reviewing, testing, or accepting the work

## 1. Purpose

This document turns the Tier 1 roadmap into an implementation contract. It states
what must be built, where it belongs, how data moves through it, which safety
properties must remain true, and which automated and manual checks prove completion.

This is not a replacement for `docs/FUTURE_ENHANCEMENTS.md`. That document explains
why each enhancement matters. This document defines the buildable behavior and the
evidence required before its status can be changed to Done.

## 2. Scope and current status

| ID | Enhancement | Current status | Existing foundation |
|---|---|---|---|
| T1-01 | Severe-but-unclustered queue | ✅ Done | Implemented 2026-08-30 on `main` (commit `a2d719f`): `pipeline.risk.severe_matches`, `pipeline.run_batch.find_severe_singletons`/`run_triage`/`build_artifact_payload`, artifact schema v2 with a legacy-list-compatible loader, and a Severe singletons UI queue. All section 6.3 tests plus a literal section-6.4 acceptance fixture pass (`tests/test_severe_singletons.py`, `tests/test_streamlit_app.py`); full suite 68/68, ruff clean. Not yet re-verified against a live `--live` run or a redeployed Cloud Run UI (needs network/credentials). See `docs/PHASES.md` Phase 8 for the mirrored status row and full note. |
| T1-02 | ACN evidence drill-down | ⬜ Not Started | Normalized reports and full narratives already exist in memory and in Firestore `reports/`; briefs already carry bracketed ACN citations |
| T1-03 | Edit-before-approve and required rejection reason | 🔶 Partial | Approve/Reject update status, rejections persist, and Markdown download exists; editing, reasons, atomic decision records, and post-edit citation validation do not |
| T1-04 | Cross-run hazard identity and history | 🔶 Partial | Escalation-member Jaccard matching and the NEW THIS RUN flag exist; persistent hazard records, run observations, and history UI do not |

### Status legend

- ⬜ **Not Started** — no user-visible implementation exists.
- 🔶 **Partial** — some required behavior exists, but the acceptance criteria are not met.
- ✅ **Done** — all required automated tests pass and the feature has completed its
  manual or real-service proof listed in this document.
- 🚫 **Blocked** — implementation cannot continue without the dependency stated beside it.

Status changes must be made in this file and `docs/PHASES.md` in the same commit as
the behavior change. Code existing without executed proof is at most Partial.

## 3. Non-negotiable constraints

Every Tier 1 implementation must preserve these properties:

1. Severe-singleton classification and hazard matching are deterministic. They make
   no generative-model calls.
2. Clustering remains embeddings plus seeded HDBSCAN. Tier 1 work must not add an LLM
   call to clustering or tune clustering parameters to make a metric pass.
3. `config/frozen.yaml` remains read-only at runtime. These enhancements reuse its
   severity vocabulary and risk output; none may edit its weights or thresholds.
4. Every factual brief claim must still pass the deterministic ACN citation and
   provenance gate.
5. The human gate remains terminal. VIGIL may persist, display, and export a
   human-approved brief; it must not send, file, or action one.
6. The locked holdout remains inaccessible to the operational pipeline and UI.
7. Public ASRS data is the only report data in scope.
8. A static artifact remains a supported UI data source. Reviewers must be able to
   exercise Tier 1 behavior without live model calls.

## 4. Target user flow

```text
Batch run
  -> deterministic clustering
  -> non-noise clusters -> deterministic risk -> agent-authored/cited draft
  -> noise reports -> deterministic severe-vocabulary check
  -> versioned artifact + Firestore state

Analyst opens VIGIL
  -> chooses Hazard clusters or Severe singletons
  -> inspects an ACN's evidence without leaving the app
  -> edits a draft or records a rejection reason
  -> citation gate validates the human-edited text
  -> human approves and downloads, or rejects with a reason

Next batch run
  -> non-noise cluster is matched to a persistent hazard identity
  -> one idempotent observation is appended for the run
  -> UI shows member-count and risk history without altering frozen risk
```

## 5. Shared data contracts

### 5.1 Artifact schema version 2

The current artifact is a top-level JSON list. Tier 1 requires run metadata and a
second queue, so new artifacts must use a versioned object:

```json
{
  "schema_version": 2,
  "run": {
    "run_id": "2026-08-29T210000Z-7f2c4a",
    "run_at": "2026-08-29T21:00:00Z",
    "reports_triaged": 5000
  },
  "clusters": [],
  "severe_singletons": []
}
```

Requirements:

- `run_id` is generated once at the CLI boundary and passed inward. Tests must be able
  to inject it.
- `run_at` is an RFC 3339 UTC timestamp generated once per run, not once per record.
- `reports_triaged` counts all normalized input reports, including HDBSCAN noise.
- `_load_clusters` is replaced by an artifact loader that accepts both schema v2 and
  the legacy top-level list. Legacy artifacts produce an empty singleton queue and
  unknown run metadata rather than failing.
- Unknown future schema versions fail with a clear error. They must not be silently
  interpreted as version 2.
- Artifact generation fails if a brief cites an ACN that cannot be resolved to a
  normalized report. The UI must never render a citation whose evidence is knowingly
  missing.

### 5.2 Evidence record

Each cluster embeds evidence for every member ACN plus any cited precedent ACN outside
the cluster. Each singleton embeds its own evidence record.

```json
{
  "acn": "1044401",
  "narrative_excerpt": "First 500 normalized characters…",
  "narrative_truncated": true,
  "date_yyyymm": "202601",
  "flight_phase": "Initial Approach",
  "component": "Flight Management System",
  "anomaly_labels": ["Aircraft Equipment Problem Less Severe"],
  "results": []
}
```

Requirements:

- Normalize repeated whitespace before applying the 500-character cap.
- Set `narrative_truncated` from the normalized full narrative, not from the raw text.
- Preserve complete ACN membership separately from excerpts; never cap the ACN list.
- Do not duplicate narrative excerpts into Firestore `clusters/` documents. Firestore
  already stores full report documents under `reports/{acn}`. Cluster documents store
  `evidence_acns`; the static artifact embeds excerpts because it has no report read path.
- Evidence order is deterministic: member ACNs in sorted order, followed by sorted
  cited non-members.

### 5.3 Severe singleton record

```json
{
  "acn": "1234567",
  "matched_severe_results": ["Flight Crew Inflight Shutdown"],
  "matched_severe_events": [],
  "evidence": {}
}
```

A report qualifies when it is HDBSCAN noise and either intersection is non-empty:

```text
report.results ∩ policy.severe_results
OR
report.anomaly_labels ∩ policy.severe_events
```

This is a categorical triage rule, not a one-report risk score. Do not call
`score_cluster([report])`, because its frequency and trend terms describe clusters and
would obscure the actual qualification rule.

### 5.4 Decision records

Approved cluster fields:

```json
{
  "status": "approved",
  "brief_draft": "Original gate-cleaned draft",
  "brief_approved": "Human-edited and revalidated brief",
  "decision_at": "2026-08-29T21:14:00Z"
}
```

Rejected record under `rejections/{cluster_id}`:

```json
{
  "cluster_id": "cluster-abc123",
  "reason": "Risk language overstates the cited evidence.",
  "brief_draft": "Original draft",
  "brief_at_rejection": "Current editor contents",
  "member_acns": ["1234567"],
  "decision_at": "2026-08-29T21:15:00Z"
}
```

The cluster status update and rejection-record write form one logical decision and
must be atomic in the Firestore implementation.

### 5.5 Hazard and observation records

`hazards/{hazard_id}`:

```json
{
  "hazard_id": "hazard-abc123",
  "display_name": "Flight Control Trim System Malfunctions",
  "latest_member_acns": ["1234567", "1234568"],
  "first_seen_at": "2026-08-15T09:00:00Z",
  "last_seen_at": "2026-08-29T09:00:00Z",
  "observation_count": 3
}
```

`hazards/{hazard_id}/observations/{run_id}`:

```json
{
  "run_id": "2026-08-29T090000Z-7f2c4a",
  "run_at": "2026-08-29T09:00:00Z",
  "cluster_id": "cluster-def456",
  "member_count": 31,
  "risk_total": 0.71
}
```

Requirements:

- Observation document IDs use `run_id`; rerunning the same logical run cannot append
  a duplicate history point.
- `latest_member_acns` is replaced with the newest matching member set. It is not an
  ever-growing union, which would progressively distort Jaccard matching.
- History is displayed in ascending `run_at` order.
- Hazard history is descriptive only. It must not feed `score_cluster` or modify the
  frozen risk score.

## 6. T1-01 — Severe-but-unclustered queue

### 6.1 Required behavior

1. Inspect every report assigned to HDBSCAN noise.
2. Select reports matching the frozen policy's severe result or severe event vocabulary.
3. Persist selected records in artifact schema v2 under `severe_singletons`.
4. Render a distinct sidebar queue named **Severe singletons** with a visible count.
5. Sort the queue by report month descending, then ACN ascending. Missing months sort last.
6. Display the exact matched policy terms so the analyst can see why the report surfaced.
7. Display the evidence record in the main pane.
8. Do not generate an Analyst name, hazard statement, risk score, or investigator brief
   for a singleton. It is a source report for human review, not a fabricated one-report
   cluster.
9. A severe clustered report appears only in its cluster, never in the singleton queue.

### 6.2 Implementation map

- `pipeline/models.py`
  - Add immutable typed records for `EvidenceRecord` and `SevereSingleton`.
- `pipeline/risk.py`
  - Add a pure `severe_matches(report, policy)` helper returning the two sorted match sets.
- `pipeline/run_batch.py`
  - Carry the `Cluster.noise` flag explicitly rather than relying only on an ID prefix.
  - Do not invoke the live `assess_cluster` callback for noise.
  - Build singleton records from noise members after clustering.
  - Write artifact schema v2.
- `ui/streamlit_app.py`
  - Add the queue selector and singleton detail view.
  - Report the artifact's `reports_triaged` value instead of summing only visible clusters.

### 6.3 Required automated tests

Create `tests/test_severe_singletons.py` with at least:

- a noise report matching `severe_results` qualifies;
- a noise report matching `severe_events` qualifies;
- a report matching both appears once with both reason lists;
- a non-severe noise report does not qualify;
- a severe non-noise report does not enter the singleton queue;
- missing or empty result/anomaly tuples do not raise;
- output ordering is deterministic;
- a fake live assessor that raises if called is not called for noise;
- risk weights, escalation threshold, and policy file bytes are unchanged by a run;
- artifact `reports_triaged` equals the input count, not the visible queue count.

### 6.4 Acceptance criteria

- All tests above pass without credentials or network access.
- A deterministic fixture containing clustered reports, a severe noise report, and a
  non-severe noise report shows exactly one severe singleton.
- On the seeded real slice, the UI no longer silently represents all HDBSCAN noise as
  absent: qualifying severe reports are visible and the total triaged count remains 5,000.
- No additional model call appears in `agent_log` because of singleton processing.

## 7. T1-02 — ACN evidence drill-down

### 7.1 Required behavior

1. Replace the comma-separated ACN-only experience with an evidence selector.
2. Selecting an ACN displays narrative excerpt, date, flight phase, component, anomaly
   labels, and result labels.
3. Mark ACNs cited in the current brief and list them first in the evidence selector.
4. Include cited precedent ACNs even when they are not cluster members; label them
   **Precedent evidence** rather than cluster members.
5. Preserve the complete member-ACN list for audit and membership counts.
6. Missing optional metadata renders as **Not recorded**. Missing narrative or unresolved
   cited ACNs are artifact-generation errors, not blank UI panels.

### 7.2 Implementation map

- `agents/critic.py`
  - Add a public `extract_cited_acns(brief)` helper using the same citation grammar as
    the final gate. Preserve first occurrence and remove duplicates.
- `pipeline/run_batch.py`
  - Build evidence from cluster members plus cited non-members after the brief is final.
  - Fail artifact generation with cluster ID and ACN in the error message when resolution
    fails.
- `pipeline/store.py`
  - Store `evidence_acns` on cluster documents; continue storing full reports only once.
- `ui/streamlit_app.py`
  - Render the evidence selector and detail panel.
  - Visually distinguish member evidence from precedent evidence.

### 7.3 Required automated tests

Create `tests/test_evidence.py` with at least:

- citation extraction is case-insensitive, ordered, and deduplicated;
- all cluster members receive evidence records;
- a cited non-member precedent receives evidence and the correct role;
- an uncited non-member is not embedded;
- a cited unknown ACN fails artifact construction;
- whitespace normalization occurs before the 500-character cap;
- exactly 500 normalized characters is not marked truncated; 501 is;
- deterministic evidence ordering survives shuffled input;
- artifact v2 round-trips through the UI loader;
- a legacy list artifact still loads with an empty singleton queue.

Add a Streamlit `AppTest` smoke test that selects a second ACN and asserts that its
narrative and metadata, rather than the first ACN's, are rendered. Streamlit's native
test API is documented at <https://docs.streamlit.io/develop/api-reference/app-testing>.

### 7.4 Acceptance criteria

- Every bracketed ACN visible in a brief can be selected and inspected in the same app.
- At least one real cluster with precedent evidence demonstrates a cited non-member ACN.
- No cluster Firestore document duplicates narrative text.
- The committed artifact remains practical to load; record its byte size before and after
  in the implementing commit or handoff.

## 8. T1-03 — Edit-before-approve and required rejection reason

### 8.1 Required behavior

1. Seed an editable Markdown text area with the immutable original draft.
2. Preserve editor state across Streamlit reruns and when switching ACN evidence.
3. On Approve, run the deterministic citation gate against the edited text using all
   evidence ACNs as the allow-list.
4. Block approval if the edited text contains an uncited factual line or an ACN outside
   the allow-list. Show actionable validation feedback; do not silently approve a
   rewritten or stripped version the human did not see.
5. Atomically persist `status`, `brief_draft`, `brief_approved`, and `decision_at`.
6. After successful approval, lock the editor and expose a Markdown download containing
   byte-for-byte `brief_approved`.
7. Require a non-blank rejection reason after trimming whitespace. Enforce a 2,000
   character maximum in UI and persistence validation.
8. Atomically update cluster status and write the rejection record.
9. A blank or overlong reason performs no writes.
10. Approval and rejection are terminal for the current UI session. Reopening a decision
    is a separate, out-of-scope workflow.

### 8.2 Store API

Replace multi-call UI decisions with intention-revealing protocol methods:

```python
record_approval(cluster_id: str, value: dict[str, Any]) -> None
record_rejection(cluster_id: str, value: dict[str, Any]) -> None
```

`MemoryStore` must mirror Firestore semantics. `FirestoreStore` must use an atomic
batched write for rejection and a single merge update for approval. Firestore documents
atomic write behavior here:
<https://cloud.google.com/firestore/docs/manage-data/transactions>.

Keep the existing lower-level methods only while callers or tests still require them;
remove them in a later cleanup rather than mixing a compatibility removal into Tier 1.

### 8.3 Implementation map

- `pipeline/store.py`
  - Add the two decision methods, server-side UTC timestamps where available, and
    validation shared by both store implementations.
- `ui/streamlit_app.py`
  - Add the editor, rejection-reason input, validation messages, terminal decision state,
    and approved-content download.
  - Move decision orchestration into pure helper functions so behavior is testable without
    a browser.
- `agents/critic.py`
  - Reuse the existing deterministic gate; do not create a weaker UI-only validator.

### 8.4 Required automated tests

Extend `tests/test_store_decisions.py` and add `tests/test_ui_decisions.py` with at least:

- approving unchanged valid text stores identical draft and approved fields;
- approving a valid edit stores the original and edited versions separately;
- an uncited human-added claim blocks approval and performs no write;
- a fabricated or unrelated ACN blocks approval and performs no write;
- a valid cited deletion or wording change is accepted;
- blank and whitespace-only rejection reasons are rejected;
- a 2,001-character reason is rejected; 2,000 characters is accepted;
- rejection reason is trimmed before persistence;
- a rejection preserves original cluster name, risk, members, and draft;
- a simulated Firestore failure cannot leave status rejected without the rejection record;
- downloaded bytes equal `brief_approved`, not the original draft;
- controls become terminal after a successful decision.

Use Streamlit `AppTest` for editor input, button behavior, and displayed validation.
Test download content through the pure download-data helper because not every Streamlit
test element exposes browser download handling.

### 8.5 Acceptance criteria

- A reviewer can edit, approve, reload, and observe both original and approved text.
- A reviewer cannot approve or export an edited brief that fails the existing citation
  gate.
- Reject is impossible without a reason, and the reason is visible in the stored negative
  example.
- VIGIL still sends or files nothing; the only outward action is human-triggered download.

## 9. T1-04 — Cross-run hazard identity and history

### 9.1 Identity algorithm

Apply identity matching to non-noise clusters only:

1. Load candidate hazards and their `latest_member_acns`.
2. Compute Jaccard similarity between the current cluster members and each candidate.
3. Keep candidates with similarity strictly greater than `0.6`, preserving the existing
   escalation-ledger boundary.
4. Choose the highest similarity. Break an exact tie by lexicographically smallest
   `hazard_id` so results are deterministic.
5. If no candidate qualifies, create a new hazard ID derived from the first cluster ID
   plus a stable digest; do not use a display name as identity.
6. Write one observation keyed by `run_id`, update latest members and timestamps, and
   return `hazard_id` plus sorted history.

This first version is honest about its limitation: member-set matching works for repeated
or overlapping rolling-window batches. Disjoint weekly batches with entirely new ACNs
cannot be linked by Jaccard alone. Semantic identity across disjoint batches requires a
separately specified and evaluated matching method; do not claim Tier 1 solves it.

### 9.2 Required behavior

1. Every non-noise cluster receives a `hazard_id`, whether or not it escalates.
2. Store one observation per hazard per logical run.
3. Add a history panel showing observation date, member count, and frozen risk total.
4. Display a compact summary such as **Seen in 3 runs · 12 → 19 → 31 reports**.
5. Render a member-count sparkline when at least two observations exist; otherwise render
   **First observed run**.
6. Keep the NEW THIS RUN badge driven by the escalation ledger. Hazard identity must not
   silently redefine alert deduplication.
7. Keep risk totals byte-identical with and without hazard history enabled.

### 9.3 Store API

Add to `TriageStore`:

```python
record_hazard_observation(
    *,
    cluster_id: str,
    display_name: str,
    member_acns: frozenset[str],
    risk_total: float,
    run_id: str,
    run_at: str,
) -> HazardRecord
```

`MemoryStore` gains `hazards` and observation maps. `FirestoreStore` writes the chosen
hazard and its observation atomically. Transaction functions must be safe to retry and
must not mutate Streamlit or process state.

### 9.4 Implementation map

- `pipeline/models.py`
  - Add `HazardObservation` and `HazardRecord`.
- `pipeline/store.py`
  - Extract the existing Jaccard helper into tested matching logic.
  - Implement deterministic selection, idempotent observations, and Firestore persistence.
- `pipeline/run_batch.py`
  - Generate/inject run context once.
  - Record an observation after each non-noise assessment and add `hazard_id` and history
    to the artifact payload.
- `ui/streamlit_app.py`
  - Render history summary, table, and sparkline.

### 9.5 Required automated tests

Create `tests/test_hazard_history.py` with at least:

- an unmatched cluster creates one hazard and one observation;
- exact repeat members match the existing hazard;
- similarity `0.6` does not match and `> 0.6` does;
- the highest-overlap hazard wins;
- tie-breaking is deterministic;
- `latest_member_acns` becomes the newest set rather than a cumulative union;
- rerunning the same `run_id` does not increment count or add a point;
- a new `run_id` appends exactly one point;
- history returns in chronological order even when inserted out of order;
- noise creates no hazard;
- below-threshold non-noise clusters still receive a hazard ID;
- risk components and total are unchanged by history recording;
- two isolated `MemoryStore` instances do not leak history;
- Firestore transaction retry produces one observation, not duplicates.

Add a Streamlit `AppTest` smoke test for first-observation and multi-observation views.

### 9.6 Acceptance criteria

- Running an overlapping fixture twice with different run IDs produces one hazard with
  two ordered observations.
- Repeating either run ID leaves the stored document set unchanged.
- The UI shows the same risk score as the original assessment and a separate history
  visualization.
- A real Firestore or emulator smoke test verifies persistence across process instances.

## 10. File-level delivery map

| File | Required Tier 1 responsibility |
|---|---|
| `pipeline/models.py` | Evidence, singleton, hazard, observation typed records |
| `pipeline/risk.py` | Pure severe-vocabulary matching |
| `agents/critic.py` | Shared ACN extraction and unchanged final citation gate |
| `pipeline/run_batch.py` | Run context, singleton extraction, evidence assembly, hazard observation, artifact v2 |
| `pipeline/store.py` | Atomic decisions, hazard persistence, history queries, MemoryStore parity |
| `ui/streamlit_app.py` | Two queues, evidence pane, editor/reason controls, history display |
| `tests/test_severe_singletons.py` | T1-01 behavior and deterministic guard proofs |
| `tests/test_evidence.py` | T1-02 evidence and artifact compatibility |
| `tests/test_store_decisions.py` | Store-level T1-03 decisions |
| `tests/test_ui_decisions.py` | UI-level T1-03 validation and terminal state |
| `tests/test_hazard_history.py` | T1-04 matching, idempotency, ordering, and risk isolation |
| `tests/test_tier1_app.py` | Headless Streamlit Tier 1 smoke path |
| `docs/TIER1_ENHANCEMENTS_SPEC.md` | Status and acceptance source of truth for this work |

Do not create a new framework around these features. Keep domain behavior in plain,
typed Python functions and keep Streamlit code focused on rendering and user events.

## 11. Build order and green checkpoints

### Checkpoint A — Shared schema and compatibility

- Add typed records and artifact v2 loader/writer.
- Preserve legacy artifact loading.
- Add fixture builders shared by the new tests.
- Proof: new schema tests plus the entire existing suite and lint pass.

### Checkpoint B — T1-01 severe singletons

- Add pure classification, artifact output, and queue UI.
- Mark T1-01 Done only after deterministic fixture and seeded-slice proof.
- Commit status updates with implementation.

### Checkpoint C — T1-02 evidence

- Add evidence assembly and UI drill-down.
- Verify cluster-member and precedent citations.
- Record artifact size impact.

### Checkpoint D — T1-03 decisions

- Add editor, validator, atomic store methods, reason requirement, and approved download.
- Exercise both MemoryStore and Firestore/emulator paths.

### Checkpoint E — T1-04 history

- Add run context, hazard matching, observations, and UI history.
- Demonstrate idempotency across process instances.
- Do not broaden the matcher beyond the member-overlap contract in this checkpoint.

Each checkpoint must leave `make demo` runnable. Avoid one commit containing all four
features; each enhancement must be independently reviewable and revertible.

## 12. Verification matrix

| Proof level | Command or action | Required result |
|---|---|---|
| Focused unit tests | `uv run pytest tests/test_severe_singletons.py tests/test_evidence.py tests/test_store_decisions.py tests/test_ui_decisions.py tests/test_hazard_history.py` | All pass without credentials |
| Full regression | `uv run pytest` | Entire suite passes |
| Static quality | `uv run ruff check .` | No findings |
| Deterministic demo | `make demo` | Existing cited, escalated fixture still runs |
| Headless UI | `uv run pytest tests/test_tier1_app.py` | Both queues, evidence selection, decisions, and history render without exception |
| Store integration | Run the Tier 1 store tests with `FIRESTORE_EMULATOR_HOST` set | Decision atomicity, hazard idempotency, and cross-instance persistence pass |
| Seeded real slice | Generate artifact v2 from the existing seeded 5k input | 5,000 reports recorded as triaged; qualifying severe noise is visible; all brief citations resolve |
| Manual human-gate smoke | Edit a cited line, try an uncited line, approve valid content, reject another cluster with a reason | Invalid approval is blocked; approved download matches persisted text; rejection reason persists |

The Firestore emulator run may be conditional in ordinary local tests, but it is mandatory
before marking T1-03 or T1-04 Done. A mocked Firestore client alone does not prove
cross-process persistence or atomic document behavior.

## 13. Global definition of done

Tier 1 is complete only when all of the following are true:

- [ ] T1-01 through T1-04 each show ✅ Done in section 2.
- [ ] All required tests in sections 6–9 exist and have been executed.
- [ ] The complete pre-Tier-1 test suite remains green.
- [ ] Ruff is clean.
- [ ] The deterministic demo remains runnable.
- [ ] Artifact v2 and legacy artifact loading both work.
- [ ] Every visible brief citation resolves to in-app evidence.
- [ ] Human edits cannot bypass the citation gate.
- [ ] Blank rejection reasons cannot persist.
- [ ] Hazard observation writes are idempotent by `run_id`.
- [ ] Hazard history does not alter deterministic risk.
- [ ] No new LLM call occurs for singleton detection, evidence display, decisions, or
  hazard matching.
- [ ] `config/frozen.yaml` is unchanged unless a separate, explicitly reviewed policy
  change was requested outside this scope.
- [ ] Firestore/emulator proof and the manual human-gate smoke are recorded in
  `docs/PROGRESS.md` or the current handoff.

## 14. Explicit non-goals

The following are not part of this Tier 1 specification:

- retuning HDBSCAN or changing the declared clustering guard;
- semantic hazard matching across disjoint member sets;
- full-corpus vector retrieval for Precedent;
- extending the self-improvement loop beyond its existing permitted agent;
- running the full real dataset on a weekly Cloud Run job;
- notification delivery;
- automated approval, submission, filing, or sending;
- changing risk weights, escalation thresholds, or severe vocabularies;
- adapting VIGIL to a different reporting domain.

If one of these becomes necessary, write and approve a separate specification rather
than expanding Tier 1 during implementation.
