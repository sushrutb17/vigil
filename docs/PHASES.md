# VIGIL Phases & Feature Status

**Read this file first, before touching anything else.** It's the live status board:
every feature the project needs, grouped into phases, each tagged with where it
actually stands. Update it — not just narrate progress in chat — whenever a feature's
status changes, so any agent (a fresh Claude session, a different tool, a human)
picking this project up mid-stream can find the exact edge of finished work in under
a minute, without replaying the conversation history.

## How to use this file (agent handoff protocol)

1. Read phases top to bottom. Phases are mostly sequential (later phases assume
   earlier ones), but within a phase, items can be done in any order — pick whatever's
   unblocked.
2. Find the first `⬜ Not Started` or `🔶 Partial` item you can act on. Check its
   **Blocked by** note before starting — don't start work whose prerequisite isn't
   `✅ Done` yet.
3. Do the work. Then, before ending your session: flip the status tag, add/update the
   **Note**, and if it's a real decision or a non-obvious discovery, add a dated entry
   to `docs/PROGRESS.md` explaining *why*, not just *what*.
4. Commit. Every session that touches code or docs ends with a git commit (repo is
   local-only for now — see Phase 0 — so this is just `git commit`, no push yet).
5. Never mark something `✅ Done` from reading the code alone — only from actually
   running it (tests, a real invocation, a deploy that responds). Code that exists but
   has never executed is `🔶 Partial`, tagged "written, unverified."

**Status legend:** ✅ Done (verified by running it) · 🔶 Partial (code/doc exists but
incomplete or unverified) · ⬜ Not Started · 🚫 Blocked (see note for what it's waiting on)

**Related docs:** `BUILD_PLAN.md` (original day-by-day time plan — calendar, not
feature status), `GATE_DECISION.md` (the Aug 28 scope decision), `PROGRESS.md`
(dated journal — the *why* behind changes), `ARCHITECTURE.md` (the design contract
every feature below has to satisfy), `DATA.md` / `EVAL.md` / `DEMO_SCRIPT.md` /
`SUBMISSION.md` (reference detail for Phases 2, 3, 5, 7).

---

## Phase 0 — Environment, Credits & Infra Bootstrap

| Feature | Status | Note |
|---|---|---|
| GCP $150 credit request submitted | ✅ Done | Via hackathon credit form |
| Devpost registration | ✅ Done | Username: sushrut17 |
| GCP project created | ✅ Done | |
| APIs enabled (Vertex AI, Cloud Run Admin, Firestore) | ✅ Done | |
| Budget alert ($50) | ✅ Done | Set in Billing → Budgets & alerts, scoped to `vigil-hackathon` project, threshold alerts on |
| Firestore database instance created | ✅ Done | `(default)` DB in `vigil-hackathon` project, Standard edition, Native mode, empty (collections created lazily on first write by `FirestoreStore`) — verified via Cloud Console, not yet exercised by a live write |
| Local git repo initialized, doc set committed | ✅ Done | Branch `main`, local commits only |
| Repo pushed to public GitHub | ⬜ Not Started | **Deliberately last** — see PROGRESS.md 2026-08-28 entry |

---

## Phase 1 — Local Deterministic Core *(no cloud credentials required)*

| Feature | Status | Note |
|---|---|---|
| Data models (`pipeline/models.py`) | ✅ Done | `ASRSReport`, `Cluster`, `RiskScore`, `ClusterAssessment` |
| Ingest/normalize (`pipeline/ingest.py`) | 🔶 Partial | Handles DATA.md quirks (multi-value split, empty→None); unverified against real rows — needs Phase 2 data |
| TF-IDF fallback + seeded HDBSCAN clustering (`pipeline/cluster.py`) | ✅ Done | No LLM calls, deterministic |
| Frozen risk policy + scoring (`config/frozen.yaml`, `pipeline/risk.py`) | ✅ Done | Escalation threshold 0.60, immutable at runtime |
| Deterministic cluster naming/hazard-statement stand-in (`run_batch._assess_cluster`) | ✅ Done | Explicit stand-in for the real Analyst agent (Phase 3) |
| Citation gate / critic (`agents/critic.py`) | ✅ Done | `strip_uncited_claims`, preserves `DEGRADED` banner |
| `MemoryStore` w/ idempotency (Jaccard overlap > 0.6 on escalations) | ✅ Done | |
| Test suite + lint | ✅ Done | 14/14 tests pass, ruff clean — verified 2026-08-28 |
| Streamlit UI: cluster browser, brief view (`ui/streamlit_app.py`) | ✅ Done | Demo-fixture mode only |
| UI Approve/Reject persists decisions to store as rejections/negative examples | ⬜ Not Started | Buttons currently only set local `st.session_state` — nothing written to `MemoryStore`/Firestore. Architecture doc requires `rejections/` collection feeding future Analyst prompts. |

---

## Phase 2 — Real Data Integration

| Feature | Status | Note |
|---|---|---|
| `data/download.py` (HF snapshot download, lock `data/holdout/`) | ✅ Done | Run 2026-08-29 in user's own terminal (real `.venv`, real network). `data/raw/default/{train,validation,test}/0000.parquet` present (49M/5.5M/6.1M). `data/holdout/test.parquet` locked (chmod 0o444) on this run — first run had downloaded raw splits but errored/stopped before the lock step; re-run completed it cleanly. |
| Real-data EDA vs DATA.md quirks (ZZZ rate, `;` splitting, Report 2 frequency) | ⬜ Not Started | 🚫 Blocked by: data download |
| `run_batch.py` support for a real dataset path | ⬜ Not Started | CLI currently only accepts `--demo`; no `--dataset` flag or loader wiring exists yet |
| Demo slice finalized (fixed seed, e.g. 5k train reports) | ⬜ Not Started | 🚫 Blocked by: EDA |

---

## Phase 3 — Live Agent Graph *(real Gemini calls via ADK)*

| Feature | Status | Note |
|---|---|---|
| `agents/definitions.py` — `build_agent_graph`: Extractor + Dedup (`SequentialAgent`), Analyst, Coordinator (`ParallelAgent`: Precedent ∥ Risk ∥ Brief Writer), Critic | 🔶 Partial | Written, imports delayed so it doesn't block local/test runs — **never executed against a live model** |
| `agents/contracts.py` (structured output schemas) | ✅ Done | `ExtractionOutput`, `DedupOutput`, `ClusterAnalysisOutput` |
| `agents/prompts.py` (agent instructions) | 🔶 Partial | Written, never evaluated for quality against real reports |
| `agents/runtime.py` (`call_with_observability`: retry+backoff, JSON repair, `agent_log`) | 🔶 Partial | Written, never exercised against a live model call |
| `pipeline/embeddings.py` real Gemini embedding call | 🔶 Partial | Written, never executed — needs live credentials |
| **Wire the live agent graph into `pipeline/run_batch.py`** | ⬜ Not Started | Right now `run_batch.py` only ever uses the deterministic stand-ins from Phase 1, even in an "authenticated" run — this wiring doesn't exist yet. This is the single biggest gap between what the architecture doc describes and what the code does. |
| Extractor eval vs coded fields (`eval/metrics.py`) | ⬜ Not Started | 🚫 Blocked by: real data + live extractor |
| Dedup eval vs Report-2 pairs | ⬜ Not Started | 🚫 Blocked by: real data + live dedup |
| Cluster purity/ARI vs `Events_Anomaly` on real data | ⬜ Not Started | Metric functions exist in `eval/metrics.py`; never run on real data |
| Critic eval — seeded uncited-claims catch rate | ⬜ Not Started | |

---

## Phase 4 — Persistence & Cloud Deployment

| Feature | Status | Note |
|---|---|---|
| `FirestoreStore` implementation (`pipeline/store.py`) | 🔶 Partial | Code mirrors `MemoryStore` behavior exactly (reports/clusters/agent_log/escalations); never run against a real Firestore instance |
| `infra/Dockerfile` | 🔶 Partial | Written, never built |
| `infra/deploy.sh` | 🔶 Partial | Written, never run |
| Cloud Run UI service deployed | ⬜ Not Started | 🚫 Blocked by: Firestore instance (Phase 0), live credentials (Phase 3) |
| Cloud Run batch job deployed | ⬜ Not Started | 🚫 Blocked by: same |
| End-to-end live run on Cloud Run against real data | ⬜ Not Started | This is the actual "deployed on Google Cloud" proof Devpost requires |

---

## Phase 5 — Self-Improvement Loop *(offline, extractor only)*

| Feature | Status | Note |
|---|---|---|
| Evaluator agent (reads failures, proposes prompt revision) | ⬜ Not Started | No code exists yet — not even a stub |
| Prompt versioning in `config/` + score history in `eval/runs/` | ⬜ Not Started | |
| Guard checks (`eval/guards.py`) wired into a promotion loop | 🔶 Partial | The guard *checks* exist (`evaluate_guards`: cluster count, noise fraction, extractor F1 ≥ 0.50, dedup precision ≥ 0.90, etc.) but nothing calls them as part of a loop yet |
| Final holdout scoring (`eval/holdout_score.py`) | 🔶 Partial | Currently only counts records in the locked holdout — does not compute or report any actual score |

---

## Phase 6 — Failure Tolerance & Polish

| Feature | Status | Note |
|---|---|---|
| `DEGRADED` banner recognized/preserved by critic | ✅ Done | `agents/critic.py` |
| Parallel fan-out partial-failure handling (2-of-3 sub-agents survive → `DEGRADED` brief) | ⬜ Not Started | Can't exist yet — the coordinator isn't wired into `run_batch.py` at all (Phase 3) |
| Resumable batch job (skip ACNs already processed) | 🔶 Partial | `put_report` uses `setdefault` so a re-run won't overwrite, but there's no skip-before-reprocessing logic, so a re-run still redoes clustering/scoring work |
| README: spin-up steps, architecture PNG, metrics table | 🔶 Partial | Spin-up steps exist; no PNG exported from `docs/asrs-agent-architecture.mermaid` yet; no metrics table (no real metrics yet — Phase 3/5) |

---

## Phase 7 — Video & Submission

| Feature | Status | Note |
|---|---|---|
| Demo script | ✅ Done | `docs/DEMO_SCRIPT.md` |
| Failure-tolerance demo path recorded | ⬜ Not Started | 🚫 Blocked by: Phase 6 fan-out handling |
| ≤4-min video (GCP console/Cloud Run proof + unedited live execution), uploaded public | ⬜ Not Started | 🚫 Blocked by: Phase 4 deploy |
| Devpost submission draft (description, track=Taskmaster, repo/hosted/video URLs, diagram) | ⬜ Not Started | |
| Bonus: dev.to/Medium writeup + LinkedIn post | ⬜ Not Started | Stretch, per BUILD_PLAN cut list |
| Final submission | ⬜ Not Started | Deadline: Aug 31, 5:00pm PDT / 8:00pm ET |

---

*Last full audit: 2026-08-28, by direct inspection of every file in `agents/`,
`pipeline/`, `eval/`, `ui/`, `infra/`, `config/` plus a clean-environment test run
(14/14 pass) and demo run. Update this file in place — it is a status board, not a
log; use `PROGRESS.md` for the append-only history.*
