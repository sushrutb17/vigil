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
| GCP project created | ✅ Done | Project **ID** is `vigil-hackathon-506218` (display name is `vigil-hackathon`; GCP appended the suffix because the bare ID was globally taken). All `gcloud` commands need the ID — passing the name fails with a misleading "caller does not have permission" rather than "not found" |
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
| Frozen risk policy + scoring (`config/frozen.yaml`, `pipeline/risk.py`) | ✅ Done | Escalation threshold 0.60, immutable at runtime. `severe_results`/`severe_events` corrected 2026-08-29 to match real ASRS coded vocabulary — the original strings matched 0/5,000 real reports, which capped every cluster below the escalation threshold. Verified fixed: 4/23 real clusters now escalate. See PROGRESS.md. |
| Deterministic cluster naming/hazard-statement stand-in (`run_batch._assess_cluster`) | ✅ Done | Explicit stand-in for the real Analyst agent (Phase 3) |
| Citation gate / critic (`agents/critic.py`) | ✅ Done | `strip_uncited_claims`, preserves `DEGRADED` banner |
| `MemoryStore` w/ idempotency (Jaccard overlap > 0.6 on escalations) | ✅ Done | |
| Test suite + lint | ✅ Done | 14/14 tests pass, ruff clean — verified 2026-08-28 |
| Streamlit UI: cluster browser, brief view (`ui/streamlit_app.py`) | ✅ Done | Rewritten 2026-08-29 to serve **real data**: loads `artifacts/demo_run.json` (a committed snapshot of a real `--live` run over the real ASRS slice) and falls back to the bundled fixture if absent, so a fresh clone still works. Adds a triage summary header (23 clusters / 4 escalated / 816 reports), analyst queue ordering (escalated first, then descending risk, ⚠-marked), and collapsible ACN/facet panels. Verified locally against the real artifact. |
| UI Approve/Reject persists decisions to store as rejections/negative examples | ✅ Done | Implemented 2026-08-29: `TriageStore` gained `set_cluster_status` (merge update — does not clobber analyst output/risk already written by the batch job) and `put_rejection` (writes to `rejections/`, keyed by cluster id, per ARCHITECTURE.md). UI selects `FirestoreStore` when `GOOGLE_CLOUD_PROJECT` is set (mirrors `run_batch.py --firestore`), else `MemoryStore`, cached per session via `st.cache_resource` so decisions survive button-click reruns. Approve → `status=approved`. Reject → `status=rejected` + a rejection record (name/facets/member_acns/brief) for future Analyst prompt revisions. Verified via `tests/test_store_decisions.py` (3 new tests, 17/17 total pass) — not yet verified against a live Streamlit session or real Firestore. |

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
| `agents/definitions.py` — `build_agent_graph`: Extractor + Dedup (`SequentialAgent`), Analyst, Coordinator (`ParallelAgent`: Precedent ∥ Risk ∥ Brief Writer), Critic | ✅ Done | All five agents executed against a live model both locally and on Cloud Run; `agent_log` in Firestore is the receipt. |
| Coordinator sub-agent prompts specify the gate's citation format | ✅ Done | Fixed 2026-08-29 (commit `f2fe88a`) after reading the first live Cloud Run brief: `## Precedent` and `## Risk Assessment` came back **empty even though all 3 sub-agents succeeded**. `strip_uncited_claims` matches `\[ACN\s+\d{4,}\]` — square brackets required — and only `BRIEF_WRITER_INSTRUCTION` showed that form. Precedent asked for "ACN-cited observations" without a format; Risk mentioned citations not at all, so **100% of the Risk agent's output was deleted on every run, by construction**. Two of three parallel agents were spending tokens on text guaranteed to be discarded, and nothing errored — silent deletion is precisely what the gate is meant to do, which is what hid it. Tightens guardrail #4 rather than relaxing it: the gate is untouched; the agents are now told what compliance looks like. Same commit fixed `CRITIC_INSTRUCTION`, which asked for "the cleaned brief **and a list of removed claims**" while `live_draft_brief` uses the Critic's entire response verbatim as the brief — hence a stray `# Cleaned Brief` H1 in the reviewer-facing document. Both invariants locked by tests in `tests/test_safety_guards.py`. |
| No brief section can render as a bare heading | ✅ Done | Verified 2026-08-29 by reading the brief the post-`f2fe88a` Cloud Run execution actually wrote to Firestore over the REST API. `## Risk Assessment` came back fully populated and the stray `# Cleaned Brief` H1 was gone — the prompt fix landed. `## Precedent` was still empty, and the log showed the Precedent agent had **succeeded**, spending 596–1,108 tokens per execution. Two distinct causes, both now fixed in `agents/orchestrate.py`. **(1)** `_precedent_candidates` excludes cluster members and requires a matching component; in the 6-report `--demo` fixture all six reports share `component="Engine Control"` and all six are members, so the candidate list is *always* empty and the only honest answer ("none found in this batch") carries no ACN for the gate to keep. The call is now skipped when there are no candidates, replaced by a deterministic cited line — saves one live Flash call per escalated cluster and stops asking a question with no possible answer. Failure accounting switched from counting survivors to counting failures so a deliberately skipped Precedent does not spuriously stamp the brief `DEGRADED`. **(2)** The real defect, independent of the fixture: `strip_uncited_claims` is line-based and always keeps headings, so any section whose every line lacks a citation survives as a heading with an empty body — byte-identical to a section whose agent never ran. The existing per-section fallbacks could not cover this because they fire only when a sub-agent *raised*. New `_backfill_empty_sections` runs after the gate (the only point that can see what the gate removed) and restores a member-ACN-cited placeholder, so it passes the same gate it repairs. Guardrail #4 untouched. Both locked by tests that were confirmed to fail against the pre-fix source. |
| Citation gate validates provenance, not just format | ✅ Done | Found 2026-08-29 by reading the first real-data brief the regenerated artifact produced. `## Risk Assessment` cited `[ACN 1000001]`–`[ACN 1000005]` — the cluster's actual members were 1044401, 1461959, 1640441, 1748192, 1799467. Checked against the source parquet: those IDs appear in **none** of the 38,655 reports. Pure hallucination, and it passed the gate, because `ACN_CITATION` matches `\[ACN\s+\d{4,}\]` — any 4+ digit number — so the gate enforced *looks cited*, never *is sourced*. **Root cause was self-inflicted**: `f2fe88a` told the Risk agent to cite "the ACNs supplied with the cluster" while `risk_message` supplied only `member count=N` and no ACNs at all, so the model invented the obvious placeholder sequence. A fabricated citation is worse than a missing one: an uncited claim is stripped and vanishes, whereas a fabricated citation survives carrying false authority, and an investigator who pulls that ACN gets an unrelated report. Two fixes: `risk_message` now supplies the member ACNs, and `strip_uncited_claims` takes an `allowed_acns` allow-list, removing invalid citations surgically (a claim keeps its genuine sources, loses only invented ones) and dropping the claim when nothing valid remains. The allow-list is members **plus the precedent candidates actually supplied**, since Precedent legitimately cites outside the cluster — verified against the parquet that all such ACNs in the artifact are real reports. Tightens guardrail #4. |
| `agents/contracts.py` (structured output schemas) | ✅ Done | `ExtractionOutput`, `DedupOutput`, `ClusterAnalysisOutput` |
| `agents/prompts.py` (agent instructions) | 🔶 Partial | The **extractor** instruction is now measured against real reports and was replaced by the Phase 5 loop (v1 → v2, macro-F1 0.0056 → 0.4099 dev). The Analyst/Precedent/Risk/Brief Writer/Critic instructions are still unmeasured — they are judged by reading their output, not by a metric, and guardrail #7 keeps them out of the loop on purpose. |
| `agents/runtime.py` (`call_with_observability`: retry+backoff, JSON repair, `agent_log`) | ✅ Done | Extended with `extract_tokens` 2026-08-29 (live calls only know token count after the response); exercised live below |
| `agents/live.py` — synchronous ADK `Runner`/`InMemorySessionService` helper for one `LlmAgent` turn | ✅ Done | Added + verified live 2026-08-29: ran the real Extractor agent on one real report end to end (structured JSON out, parsed into `ExtractionOutput`, `agent_log` captured real latency (5,440ms) and token count (1,064)). Confirms the ADK Runner pattern works as inferred from the installed SDK source. |
| `pipeline/embeddings.py` real Gemini embedding call | ✅ Done | Live `embed_content` call against `gemini-embedding-2` verified 2026-08-29 (3072-dim vectors) — see smoke test below |
| Live credential smoke test — confirm `gemini-3.7-flash` / `gemini-embedding-2` still resolve via `google-genai` directly | ✅ Done | Verified 2026-08-29 in the user's terminal: `client.models.get()` resolved both IDs, one real `generate_content` call returned text, one real `embed_content` call returned a 3072-dim vector. This checked the raw model IDs via `google-genai`, not ADK's `LlmAgent`/`Runner` — that plumbing is exercised by the row above. |
| **Wire the live agent graph into `pipeline/run_batch.py`** | ✅ Done | Verified live end-to-end 2026-08-29 on the real 5k slice: 23 Analyst calls + Coordinator/Critic on all 4 escalated clusters, 4/4 got the full sectioned brief format, 0 DEGRADED. Scope corrected 2026-08-29: Extractor/Dedup are NOT per-report operational calls — ASRS pre-merges Report 1/Report 2 into one row per ACN (no cross-report dedup needed at runtime), and `pipeline/ingest.py` already gets structured fields free from NASA's own coded columns, so the live Extractor's job is a dev-sample eval, not a 5000-call batch step (that would be ~7hrs/~5M tokens — not viable). The real operational scope is smaller: Analyst runs once **per cluster** (23, not 5,000), Coordinator+Critic run once **per escalated cluster** (a handful, now that the risk-policy fix above makes real escalation possible). **Analyst wiring done and verified live** (`agents/orchestrate.live_assess_cluster`, injected into `run_batch()` via a new `assess_cluster` parameter, activated by `--live`/`make run-live`): ran clean on the real 5k slice after the evidence cap, all 23 clusters got real model-authored names/hazard statements (e.g. "Flight Control Trim System Malfunctions," "GPS signal loss and interference during flight operations"), and deterministic risk scores stayed byte-identical to the pre-live run — confirms the Analyst only touches naming/prose, never risk. **Coordinator+Critic wiring done and written** (`agents/orchestrate.live_draft_brief`): Precedent/Risk/Brief Writer run concurrently via plain-Python `ThreadPoolExecutor` (not ADK's `ParallelAgent` — a deliberate choice per ARCHITECTURE.md's own "orchestration that can be plain code should be plain code," and it makes 2-of-3 failure isolation straightforward with per-call try/except); fewer than 2 surviving raises `CoordinatorFailure`, caught by `run_batch.py._brief_for` which falls back to the deterministic brief template rather than dropping the cluster. Precedent's "RAG" is a same-batch, same-component filter (not a full-corpus vector search — matches the explicit no-full-corpus-scale-up scope decision). The Critic LLM reviews the assembled draft; the existing deterministic `strip_uncited_claims` always runs last regardless, per guardrail #4. Only escalated clusters get this treatment (a handful, per the scope note above). **Verified live:** the 4 escalated clusters on the real slice are all conflict/NMAC hazards ("Airborne Traffic Conflicts and Near Midair Collisions," "VFR Traffic Conflicts and Near Midair Collisions," "Low-altitude encounters and collision risk," "Cabin and Cockpit Fume and Odor Ingress") — i.e. the corrected `severe_events` categories are surfacing genuinely severe hazards, not arbitrary ones. |
| Extractor eval vs coded fields (`eval/metrics.py`) on a ~200-row dev sample | ✅ Done | Run live 2026-08-29 on a seeded 200-row validation sample (`eval/extractor_eval.py`). Headline finding is unflattering and worth keeping: the **v1 LLM extractor scored macro-F1 0.0056, *below* the majority-class + keyword baseline's 0.0515** — it emitted free-text paraphrases ("Approach", "Takeoff") against a closed ASRS coded vocabulary, so almost nothing matched. Only eligible rows (both scored coded fields present) are sampled, so a prompt cannot raise its score by staying silent. This harness is the objective function Phase 5 optimizes. |
| Dedup eval vs Report-2 pairs on a dev sample | ⬜ Not Started | 🚫 Blocked by: real data (unblocked) — separate from the live agent graph wiring above |
| Cluster purity/ARI vs `Events_Anomaly` on real data | ⬜ Not Started | Metric functions exist in `eval/metrics.py`; never run on real data |
| Critic eval — seeded uncited-claims catch rate | ⬜ Not Started | |

---

## Phase 4 — Persistence & Cloud Deployment

| Feature | Status | Note |
|---|---|---|
| `FirestoreStore` implementation (`pipeline/store.py`) | ✅ Done | **Verified against real Firestore 2026-08-29** by the first `vigil-batch` executions. All four collections created and populated: `reports` (6), `clusters` (1), `escalations` (1), `agent_log` (5 — one row per agent, with model/tokens/latency). Inspecting those writes caught a real gap the exit code hid: briefs were drafted in a second pass *after* `triage_batch` wrote the cluster docs, so they reached no store at all — only stdout/`--output`. Added `put_cluster_brief` (merge write, commit `cb1f248`), plus `hazard_statement`, which ARCHITECTURE.md's `clusters/` spec calls for and only `name` was satisfying. |
| `Dockerfile` (repo root, **not** `infra/`) | ✅ Done | Built successfully on Cloud Build 2026-08-29 for both the UI service and the batch job. **Moved to repo root 2026-08-29**: `gcloud run deploy --source .` only detects a root Dockerfile and silently falls back to buildpacks otherwise — it would not have errored, just built the wrong image. Deviates from the CLAUDE.md/ARCHITECTURE.md layout; rationale recorded in `infra/README.md`. Sets Streamlit headless/XSRF/`$PORT` flags needed behind Cloud Run's TLS-terminating proxy. |
| `.gcloudignore` + `.dockerignore` | ✅ Done | Added 2026-08-29. Neither existed; `--source .` would have uploaded `.venv` (594MB), `data/raw` (60MB), **and `data/holdout/`** — baking the locked holdout into a container image (guardrail #3 violation). Two files are required because they govern different tools: `.gcloudignore` for `gcloud run deploy`, `.dockerignore` for `docker build`. Both also exclude `.env` (live API key). Keep in sync. |
| `infra/deploy.sh` | ✅ Done | Rewritten 2026-08-29 and **run successfully end to end the same day**. One bug only the real run could surface: `--args -m,pipeline.run_batch,...` failed with "expected one argument" because the value's leading dash reads as a new flag — fixed to the `--args=` equals form (commit `d0b47f5`). The `describe`-before-`create` guards proved their worth here: the first attempt died after creating the service accounts, secret, and UI service, and the re-run skipped all of them cleanly. Creates two least-privilege runtime service accounts, stores the Gemini key in Secret Manager, deploys UI service + batch job, prints the hosted URL. Revised same day: UI service account now also gets `roles/datastore.user` and `GOOGLE_CLOUD_PROJECT` is passed to the UI service, so the deployed Approve/Reject buttons actually reach Firestore instead of silently falling back to a per-request `MemoryStore` that vanishes on the next Cloud Run instance. |
| Least-privilege deploy identities + Secret Manager | ✅ Done | Added 2026-08-29 after three automated security review findings (see PROGRESS.md); revised same day when Approve/Reject started writing to Firestore. `vigil-ui-run` holds `roles/datastore.user` only (no `secretAccessor` — the UI never calls the model); `vigil-batch-run` holds `secretmanager.secretAccessor` on the one secret plus `roles/datastore.user`. Neither uses the default compute SA, which carries primitive Editor project-wide — a public `--allow-unauthenticated` service running as project editor was the most serious issue found. |
| Cloud Run UI service deployed | ✅ Done | **Live: https://vigil-ui-715230861973.us-central1.run.app** (revision `vigil-ui-00003-rvl`, region `us-central1`, `--allow-unauthenticated`, 100% traffic). Redeployed 2026-08-29 as `vigil-ui-run` with the corrected committed artifact; public HTTP request returned 200 and the rendered page was verified in a real browser. |
| Regenerate `artifacts/demo_run.json` before recording | ✅ Done | Regenerated 2026-08-29 via `make artifact` alone (not chained with `run-live` — that target is a complete duplicate live run, not a prerequisite step; chaining them doubles the live-call count for one snapshot, see PROGRESS.md). This run carries all of today's fixes: the empty-section backfill, the skipped-Precedent-when-no-candidates change, and the citation-provenance gate. Verified by checking every cluster's cited ACNs against the full 38,655-report source parquet: zero fabricated citations, all 4 escalated briefs fully sectioned (Hazard/Precedent/Risk Assessment/Recommended Brief all non-empty), no DEGRADED banners, no stray headings. Committed in `4dedd8d` and deployed to `vigil-ui-00003-rvl`. |
| UI Approve/Reject verified against hosted Firestore | ✅ Done | Verified end to end on revision `vigil-ui-00003-rvl` on 2026-08-29. The hosted UI approved `cluster-3b7525506162` and rejected `cluster-09f38566aef2`; direct Firestore API reads confirmed the two `clusters/` status fields and a complete 10-report `rejections/cluster-09f38566aef2` negative-example document. This proves the public UI runs as `vigil-ui-run` with working `roles/datastore.user`, while the human gate remains terminal. |
| Cloud Run batch job deployed | ✅ Done | Job `vigil-batch` deployed 2026-08-29 in `us-central1` as `vigil-batch-run`, key mounted from Secret Manager. Runs `--demo --live --firestore`, so one execution exercises all three mandatory stack components (ADK/Gemini, Cloud Run, Firestore) and creates the Firestore collections. Redeployed from current `main` after the citation-provenance and empty-section fixes; scheduler-created execution `vigil-batch-pqm56` completed successfully on image `sha256:d33cb6d…` and persisted a complete four-section brief with only the six allowed fixture ACNs. Note for future sessions: `jobs execute` reruns the **already-built image**; a code change needs `jobs deploy` first. |
| Escalation dedup ledger verified live | ✅ Done | Unplanned but valuable: re-running the job left `escalations` at exactly **1** document and flipped the cluster's status from `escalated` to `new`, i.e. `previously_escalated()` matched the prior run by member-set Jaccard >0.6 and correctly declined to re-alert. That is the "runs repeatedly in the background without spamming" behavior demonstrated against real Firestore — worth ~5s of the video. **Naming wart, deliberately not changed:** a cluster seen on a *previous* run ends up with `status: "new"`, which reads backwards; the value really means "not escalated *this* run". The UI and badge depend on these strings, so renaming is a separate, tested change. |
| Cloud Scheduler weekly trigger for the batch job | ✅ Done | Live job `vigil-weekly-triage` is enabled in `us-central1`: Monday 09:00 `America/Toronto`, authenticated as dedicated `vigil-scheduler-run` with job-level `roles/run.invoker` only. Verified 2026-08-29 by a real scheduler attempt that created Cloud Run execution `vigil-batch-pqm56`; it completed successfully and wrote the cited brief to Firestore. `infra/deploy.sh` now creates or updates this setup idempotently. Human gate stays terminal. |
| End-to-end live run on Cloud Run against the demo fixture | ✅ Done | 2026-08-29. Gemini + ADK + Cloud Run + Firestore all exercised in one execution; `agent_log` shows all five agents (analyst 789 tok/2.5s, precedent 859/2.6s, risk 883/3.8s, brief_writer 1289/5.0s, critic 2289/14.4s) running in the cloud. Escalated cluster named "Uncommanded Engine Shutdown During Landing Rollout" at risk 0.69 — real model output, not the deterministic stand-in. |
| End-to-end live run on Cloud Run against **real** data | ⬜ Not Started | Still the stronger Devpost proof. The deployed job runs `--demo` (6-report fixture) because `data/raw` is correctly excluded from the image; the real-data run is currently the local path (`make run-live`). Options: mount the slice from GCS, or bake a larger fixture. Decide before recording. |

---

## Phase 5 — Self-Improvement Loop *(offline, extractor only)*

| Feature | Status | Note |
|---|---|---|
| Extractor dev-sample eval harness (`eval/extractor_eval.py`) | ✅ Done | Written 2026-08-29 with the majority-class + keyword baseline EVAL.md requires; scored end to end against fixtures by tests, **run against a live model 2026-08-29**. This is the loop's objective function, so it had to land before the Evaluator. Takes `reports`, never a path, so `eval/holdout_score.py` stays the only module that names the locked split. |
| Evaluator agent (reads failures, proposes prompt revision) | ✅ Done | Written 2026-08-29 (`agents/evaluator.py` + `EVALUATOR_INSTRUCTION`). Sees the current instruction, the dev-sample coded vocabulary, and a *frequency-ranked* confusion list — systematic error, not 200 anecdotes. Returns `PromptRevision` text only: it cannot write a file, cannot reach `config/frozen.yaml`, and never sees the holdout. **Run live 2026-08-29** — see the loop result below. |
| Prompt versioning in `config/` + score history in `eval/runs/` | ✅ Done | `config/prompts/extractor/v1.txt` + `active.yaml`, with load/save/promote/next_version in `agents/prompts.py`; `agents/definitions.py` now builds the Extractor from the *active* version, falling back to the in-source constant so a fresh clone with no `config/prompts/` still works. `REVISABLE` is `{"extractor"}` and the registry raises `KeyError` for any other agent — guardrail #7 enforced in code, not just prose. Ledger writing is implemented and tested; the first real entry is `eval/runs/20260829T185719Z-extractor.json`, now committed. |
| Guard checks (`eval/guards.py`) wired into a promotion loop | ✅ Done | `eval/improve.py` is the loop: dev sample → score incumbent → Evaluator → score candidate → guards → holdout → promote or discard, writing `eval/runs/` on **every** outcome. New `evaluate_extractor_guards` is deliberately **relative** (EVAL.md: "must not degrade these") rather than reusing `evaluate_guards`' absolute floors — those describe a finished system and would reject every first revision, making the loop theatre. Load-bearing check is `macro_f1_not_traded_for_accuracy`, which catches the exact hack EVAL.md names: predicting the majority label lifts plain accuracy on a field whose top class holds ~32% of rows while per-class F1 falls. **Run live 2026-08-29** — see the loop result below. |
| Final holdout scoring (`eval/holdout_score.py`) | ✅ Done | Extended 2026-08-29 with `load_holdout_sample` + `score_prompt_on_holdout`, so it now computes a real score instead of counting rows. Still the *only* reader of `data/holdout/`, now enforced by an AST-based guardrail test rather than a substring scan (the old scan could not tell a docstring promising isolation from a violation). Consulted only at the promotion decision, after the candidate text is already fixed, so nothing it returns can influence a revision. **Run live 2026-08-29** — see the loop result below. |

---

**First live loop result (2026-08-29, `make improve`, 200-row dev / 100-row holdout, 601 live Flash calls):**

| Prompt | dev macro-F1 | dev accuracy | holdout macro-F1 | holdout accuracy |
|---|---|---|---|---|
| majority-class + keyword baseline | 0.0515 | 0.395 | — | — |
| extractor **v1** (incumbent) | 0.0056 | 0.105 | 0.0081 | 0.080 |
| extractor **v2** (promoted) | **0.4099** | **0.600** | **0.4219** | **0.680** |

Guards passed; promoted (dev +0.4043, holdout +0.4139). Three things worth
carrying into the writeup and the video, all of them honest rather than
flattering:

1. **v1 was worse than a trivial baseline.** The LLM extractor lost to
   majority-class + keyword rules until the loop fixed it. Reporting the
   baseline is what makes the 0.41 meaningful instead of impressive-sounding.
2. **The holdout gain exceeded the dev gain** (+0.4139 vs +0.4043). That is the
   opposite of overfitting and is the strongest evidence the Evaluator fixed a
   real defect — v1 never told the model the ASRS labels are a *closed
   vocabulary*, so it answered "Approach" where the coded value is "Initial
   Approach" — rather than memorizing the dev sample. EVAL.md asks for both
   numbers side by side precisely so this gap is visible either way.
3. **The untargeted field still trails its baseline.** `flight_phase`
   (`field_macro_f1`) went 0.0844 → 0.1207 on dev, but the keyword baseline
   scores 0.1705. The loop optimizes `primary_problem`; the field it was not
   optimizing is still beaten by a deterministic heuristic. Say so.

**A guard fired on the first attempt and was found to be wrong.** The 8-row
smoke run blocked this same revision on `label_diversity_not_collapsed`.
Cause was a metric bug, not a caught cheat: diversity was
`distinct_predicted / distinct_expected`, which rewarded v1's free-text
sprawl (19 unique strings over 8 reports → 2.33) and punished a correctly
vocabulary-constrained candidate (1.00). Replaced with **in-vocabulary label
coverage**, bounded to [0,1], which *tightens* the guard against the hack
EVAL.md actually names: predicting one label everywhere on an 18-class field
now scores ~0.06, under the 0.15 floor. Recorded in PROGRESS.md because
"we changed a tripwire right after it blocked us" is exactly the thing that
needs an audit trail. **This is not the "caught our own agent cheating" demo
beat** — that beat still needs a real gamed revision, and claiming this one
would be dishonest.

---

## Phase 6 — Failure Tolerance & Polish

| Feature | Status | Note |
|---|---|---|
| `DEGRADED` banner recognized/preserved by critic | ✅ Done | `agents/critic.py` |
| Parallel fan-out partial-failure handling (2-of-3 sub-agents survive → `DEGRADED` brief) | 🔶 Partial | Written in `agents/orchestrate.live_draft_brief` (Phase 3) — per-call try/except around the 3 concurrent sub-agent calls, `DEGRADED` banner when survived<3, `CoordinatorFailure` when survived<2. Not yet demonstrated live (needs a real or forced sub-agent failure to observe) — that's the "kill one sub-agent → DEGRADED brief" demo beat from ARCHITECTURE.md. |
| Resumable batch job (skip ACNs already processed) | 🔶 Partial | `put_report` uses `setdefault` so a re-run won't overwrite, but there's no skip-before-reprocessing logic, so a re-run still redoes clustering/scoring work |
| UI: "NEW THIS RUN" badge on clusters | ⬜ Not Started | Added 2026-08-29: analysts care about *emerging* patterns; the escalation-idempotency ledger already computes member-set overlap vs prior runs — this surfaces existing state in the UI, no new pipeline logic |
| UI: Approve → download brief as Markdown (`st.download_button`) | ✅ Done | Implemented 2026-08-29. Downloads `vigil-brief-<cluster_id>.md`; help text states the human carries the draft onward and VIGIL never sends or files anything (guardrail #6 intact). |
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
