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
| Ingest/normalize (`pipeline/ingest.py`) | ✅ Done | `normalize_rows` runs clean over all 38,655 real train rows + all 4,295 validation rows, zero errors — verified 2026-08-29 |
| TF-IDF fallback + seeded HDBSCAN clustering (`pipeline/cluster.py`) | ✅ Done | No LLM calls, deterministic. Verified at real 5k-report scale 2026-08-29 after fixing two scale bugs — see PROGRESS.md: (1) dense TF-IDF array before HDBSCAN made a 5k run take 6+ min and never finish, fixed with seeded TruncatedSVD; (2) `allow_single_cluster=True` collapsed 58% of the batch into one megacluster at scale, fixed to only apply when `len(reports) < 2*min_cluster_size` (the demo fixture's regime) |
| Frozen risk policy + scoring (`config/frozen.yaml`, `pipeline/risk.py`) | ✅ Done | Escalation threshold 0.60, immutable at runtime |
| Deterministic cluster naming/hazard-statement stand-in (`run_batch._assess_cluster`) | ✅ Done | Explicit stand-in for the real Analyst agent (Phase 3) |
| Citation gate / critic (`agents/critic.py`) | ✅ Done | `strip_uncited_claims`, preserves `DEGRADED` banner |
| `MemoryStore` w/ idempotency (Jaccard overlap > 0.6 on escalations) | ✅ Done | |
| Test suite + lint | ✅ Done | 14/14 tests pass, ruff clean — verified 2026-08-28 |
| Streamlit UI: cluster browser, brief view (`ui/streamlit_app.py`) | ✅ Done | Demo-fixture mode only |
| UI Approve/Reject persists decisions to store as rejections/negative examples | ⬜ Not Started | Buttons currently only set local `st.session_state` — nothing written to `MemoryStore`/Firestore. Architecture doc requires `rejections/` collection feeding future Analyst prompts. **Elevated 2026-08-29:** best story-per-hour item — one click on video evidences state management (30% rubric criterion) and learning-from-human-rejections (40% criterion). |

---

## Phase 2 — Real Data Integration

| Feature | Status | Note |
|---|---|---|
| `data/download.py` (HF snapshot download, lock `data/holdout/`) | ✅ Done | Run 2026-08-29 in user's own terminal (real `.venv`, real network). `data/raw/default/{train,validation,test}/0000.parquet` present (49M/5.5M/6.1M). `data/holdout/test.parquet` locked (chmod 0o444) on this run — first run had downloaded raw splits but errored/stopped before the lock step; re-run completed it cleanly. |
| Real-data EDA vs DATA.md quirks (ZZZ rate, `;` splitting, Report 2 frequency) | ✅ Done | 2026-08-29: ZZZ rate 52.1% (20,148/38,655 — confirms quirk #1, cluster on type×phase×component only); Report 2 present on 23.6% of rows (9,111/38,655 — the dedup label rate); `;`-splitting and empty-string→None both confirmed against real cells; 0 duplicate ACNs, 0 rows missing acn/narrative in the full train split |
| `run_batch.py` support for a real dataset path | ✅ Done | Added `--dataset`/`--slice`/`--seed` flags (mutually exclusive with `--demo`); reuses `pipeline.ingest.load_parquet`'s existing holdout-read guard rather than duplicating it. `make run-real` target added. |
| Demo slice finalized (fixed seed, e.g. 5k train reports) | ✅ Done | 5,000 train reports, seed 42 (`make run-real`). Exercising this slice caught and fixed two real clustering scale bugs — see PROGRESS.md 2026-08-29 |

---

## Phase 3 — Live Agent Graph *(real Gemini calls via ADK)*

| Feature | Status | Note |
|---|---|---|
| `agents/definitions.py` — `build_agent_graph`: Extractor + Dedup (`SequentialAgent`), Analyst, Coordinator (`ParallelAgent`: Precedent ∥ Risk ∥ Brief Writer), Critic | 🔶 Partial | Written, imports delayed so it doesn't block local/test runs — **never executed against a live model** |
| `agents/contracts.py` (structured output schemas) | ✅ Done | `ExtractionOutput`, `DedupOutput`, `ClusterAnalysisOutput` |
| `agents/prompts.py` (agent instructions) | 🔶 Partial | Written, never evaluated for quality against real reports |
| `agents/runtime.py` (`call_with_observability`: retry+backoff, JSON repair, `agent_log`) | 🔶 Partial | Written, never exercised against a live model call |
| `pipeline/embeddings.py` real Gemini embedding call | 🔶 Partial | Written, never executed — needs live credentials |
| Live credential smoke test — one real `LlmAgent` call + one embedding call; re-verify `gemini-3.7-flash` / `gemini-embedding-2` still resolve | ⬜ Not Started | Added 2026-08-29: IDs were doc-verified 2026-08-21 but never exercised. A dead model ID discovered on deploy day would be catastrophic — run this before any Cloud Run deploy. |
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
| Cloud Scheduler weekly trigger for the batch job | ⬜ Not Started | Added 2026-08-29 (rubric alignment): makes the hackathon's "agents that run in the background… asynchronously" tagline literal; Taskmaster judges assess whether the agent *intercepts* a background workflow. One `gcloud scheduler jobs create`; show the trigger config ~3s in the video's console segment. Human gate stays terminal. |
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
| UI: "NEW THIS RUN" badge on clusters | ⬜ Not Started | Added 2026-08-29: analysts care about *emerging* patterns; the escalation-idempotency ledger already computes member-set overlap vs prior runs — this surfaces existing state in the UI, no new pipeline logic |
| UI: Approve → download brief as Markdown (`st.download_button`) | ⬜ Not Started | Added 2026-08-29: lets the video end with the workflow *completing* (an artifact in hand) without violating guardrail #6 — nothing is auto-sent; the human carries it out |
| UI: per-cluster trend sparkline (stretch, last in line) | ⬜ Not Started | Added 2026-08-29: genuinely useful to analysts, but trend is already encoded in the risk score — build only after every other Phase 3–6 item is ✅ |
| README: spin-up steps, architecture PNG, metrics table | 🔶 Partial | Spin-up steps exist; no PNG exported from `docs/asrs-agent-architecture.mermaid` yet; no metrics table (no real metrics yet — Phase 3/5) |

---

## Phase 7 — Video & Submission

| Feature | Status | Note |
|---|---|---|
| Demo script | ✅ Done | `docs/DEMO_SCRIPT.md` |
| Failure-tolerance demo path recorded | ⬜ Not Started | 🚫 Blocked by: Phase 6 fan-out handling |
| ≤4-min video (GCP console/Cloud Run proof + unedited live execution), uploaded public | ⬜ Not Started | 🚫 Blocked by: Phase 4 deploy |
| Devpost submission draft (description, track=Taskmaster, repo/hosted/video URLs, diagram) | ⬜ Not Started | Description must include a literal **"The Twist"** section (restraint made mechanical: no-LLM clustering, frozen thresholds, locked holdout, citation critic, the caught reward-hack) + the ASRS institutional-mirror paragraph — see SUBMISSION.md |
| Bonus: dev.to/Medium writeup + LinkedIn post | ⬜ Not Started | Stretch, per BUILD_PLAN cut list |
| Final submission | ⬜ Not Started | Deadline: Aug 31, 5:00pm PDT / 8:00pm ET |

---

*Last full audit: 2026-08-28, by direct inspection of every file in `agents/`,
`pipeline/`, `eval/`, `ui/`, `infra/`, `config/` plus a clean-environment test run
(14/14 pass) and demo run. Update this file in place — it is a status board, not a
log; use `PROGRESS.md` for the append-only history.*

*Scope addendum 2026-08-29: rubric-alignment items added (live-credential smoke
test, Cloud Scheduler trigger, "NEW THIS RUN" badge, brief download, sparkline
stretch) after reviewing the plan against the published judging rubric and the
organizers' Q&A session — rationale in PROGRESS.md 2026-08-29 "(Sat, cont'd 2)".*
