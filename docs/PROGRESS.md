# VIGIL Progress Log

Running status doc, updated as we go. See `BUILD_PLAN.md` for the original day-by-day
plan and `GATE_DECISION.md` for the scope decision. This file is the source of truth
for "what's actually verified working" vs. "what's built but untested."

---

## 2026-08-28 (Fri evening) — Status check + gate decision

**Context:** Original plan called for a Day-7 gate on Aug 27. That didn't happen as a
discrete step — most of the pipeline was built in one session on Aug 21 (single commit
`dd645fc Build VIGIL local triage foundation`) and then untouched until tonight. With
3 days left to the Aug 31 5pm PDT / 8pm ET deadline, tonight *is* the gate, done late.

**Verified working tonight** (fresh `uv sync` + `pytest` + `ruff` + demo run, in a clean
environment, not the possibly-stale local `.venv`):
- All 14 tests pass, `ruff check` clean.
- `make demo` (`pipeline.run_batch --demo`) runs end-to-end on the bundled fixture:
  ingest → embed (TF-IDF fallback) → HDBSCAN cluster → frozen-config risk scoring →
  citation-stamped brief. Deterministic, no credentials needed, no GCP calls.
- Code exists for the fuller design: `agents/critic.py` (citation gate),
  `agents/definitions.py` (ADK graph, `gemini-3.7-flash` for agents, `gemini-embedding-2`
  for batch), `pipeline/store.py` (Firestore), `ui/streamlit_app.py`, `eval/guards.py`,
  `eval/holdout_score.py`.

**Not yet verified — these are the real risk items, not feature gaps:**
1. Repo is a local commit only. **No GitHub remote — not public.** Devpost requires a
   public repo URL. Highest-priority blocker.
2. `data/download.py` has never been run. No real ASRS data, no `data/holdout/` lock.
   Everything above was tested against the tiny bundled fixture only.
3. No live Gemini/Vertex call has ever been made. Model IDs (`gemini-3.7-flash`,
   `gemini-embedding-2`) were verified against docs on 2026-08-21 but never exercised.
4. Firestore: code exists (`pipeline/store.py`) but no Firestore **database instance**
   has been created in the GCP project yet (API enabled ≠ database created).
5. No GCP budget alert set (plan says $50).
6. Nothing has been deployed to Cloud Run (`infra/deploy.sh` unrun).
7. No `docs/GATE_DECISION.md` existed before tonight — see that file for the decision
   made now.
8. No video, no Devpost draft.

**Gate decision:** ship the full build, not the cut-down floor. Rationale: the floor
(ingest → cluster → analyst → brief → critic → human gate) and the fuller design
(coordinator fan-out, Firestore idempotency, UI) both already exist as code and pass
their local tests — cutting scope now would mean deleting working code, not saving
time. The actual remaining work is entirely in categories 1–6 above: make it public,
make it real (real data), make it live (real GCP), not "build more." See
`GATE_DECISION.md`.

**Immediate next actions, in order:**
1. Push repo to a public GitHub repo (blocks: needs `git remote add` + push with your
   credentials — I can prep the commands, you run the push, or tell me you've done it).
2. GCP console: create the Firestore database (Native mode) and set the $50 budget
   alert — both still open from earlier tonight.
3. Run `data/download.py` for real data + do the 30-min EDA pass.
4. Set up live credentials (API key or Vertex) and make one real `LlmAgent` call to
   confirm the model IDs still resolve.
5. `infra/deploy.sh` to Cloud Run (batch job + UI service).
6. Re-run the pipeline against real data, live, and capture the evidence (console
   screenshots, logs) needed for the video.

---

## 2026-08-28 (Fri evening, cont'd) — Priority order + a real constraint found

**Operating constraint discovered tonight:** the Claude session's `device_bash` access
to this Mac runs in a sandboxed Linux VM with **no network access** and a **broken
`.venv`** (it's a macOS-native venv; the Linux VM can't resolve the python symlink
inside it). Practical effect: anything needing the internet (HF dataset download, a
live Gemini API call, `gcloud`/GitHub auth) has to be run **by you, in your own
terminal on the Mac** — Claude can prep the exact command and review the output/files
afterward, but can't execute network calls against this repo's real `.venv` directly.
(Claude *can* run code with network access in its own separate cloud workspace, but
that's not this repo's environment, and large files — the ~51MB train split — exceed
what can be handed back automatically.)

**Agreed priority order for the remaining 3 days** (repo-public push deliberately
last):

1. GCP budget alert ($50) — console, quick.
2. Firestore database instance (Native mode) — console, quick.
3. Real data download — run `make download` (`uv run python -m data.download`) in
   your own terminal; needs network + the real `.venv`.
4. Live Gemini credentials — get an API key from Google AI Studio, put it in a local
   `.env` (already gitignored), run one real `LlmAgent` call to confirm
   `gemini-3.7-flash` / `gemini-embedding-2` still resolve.
5. `infra/deploy.sh` → Cloud Run (batch job + UI service).
6. Re-run the pipeline against real data, live; capture video evidence.
7. Push the repo to a public GitHub remote — **last**, per explicit instruction, so
   nothing half-broken sits in public view while steps 1–6 are still moving.

---

## 2026-08-29 (Sat) — Firestore database created (step 2 of priority order)

Created the Firestore `(default)` database in the `vigil-hackathon` GCP project via
Google Cloud Console (Standard edition, Native mode — not the newer Enterprise/MongoDB
-compatible option, which `pipeline/store.py`'s `google-cloud-firestore` client can't
talk to). Currently empty — no collections yet, which is expected: `FirestoreStore`
creates `reports`, `clusters`, `agent_log`, and `escalations` lazily on first write.

Update (same day): $50 budget alert also confirmed set (Billing → Budgets & alerts,
scoped to `vigil-hackathon`). Both Phase 0 console tasks (budget alert + Firestore) are
now done. Next up per the priority order: step 3, real data download (`make download`
in your own Mac terminal — needs network), then steps 4-7 (live Gemini credentials,
Cloud Run deploy, real-data run, public repo push).

## 2026-08-29 (Sat, cont'd) — Real data downloaded, holdout locked

Ran `uv run python -m data.download` in the user's own terminal (real `.venv`, real
network — this needed the Mac shell, not the Claude device session, which has no
network access). Two attempts:

1. First attempt: raw splits landed at `data/raw/default/{train,validation,test}/0000.parquet`
   (49M/5.5M/6.1M) but `data/holdout/test.parquet` was missing afterward — the run
   evidently stopped or errored somewhere after the HF snapshot download completed but
   before (or during) the `lock_holdout()` copy+chmod step. Root cause not diagnosed
   (no traceback captured from that run).
2. Second attempt (re-run of the same command): completed cleanly, printed the
   `test:`/`train:`/`validation:` path lines from `main()`, and this time
   `data/holdout/test.parquet` exists (6.3M, matches the test split size) and is
   chmod'd read-only. Confirmed via the device bridge's view of the mounted folder.

This is a meaningful guardrail checkpoint (see CLAUDE.md guardrail #3 — "data/holdout/
is sacred"): the holdout file is now actually locked, not just planned. `lock_holdout()`
refuses to run again if the file already exists (`FileExistsError`), so this is a
one-way step — don't delete `data/holdout/` to "fix" something without recognizing
you'd be re-opening a file the eval design assumes is fixed forever.

Next per the priority order: live Gemini credentials (Google AI Studio API key → local
`.env`, confirm `gemini-3.7-flash` / `gemini-embedding-2` still resolve), then the EDA
pass against the real data (Phase 2, blocked on nothing else now), then Cloud Run
deploy, then the public GitHub push (deliberately last).

## 2026-08-29 (Sat, cont'd 2) — Judging-rubric review adopted into scope

Reviewed the whole plan against the published judging rubric (Devpost rules page +
the organizers' "How to Win the All Things Agentic Hackathon: Judging Criteria Live
Q&A" session). Rubric facts, verified against the rules page today: **Stage One is
pass/fail** (no live GCP proof = eliminated); Stage Two is Innovation & Operational
Utility **40%** ("Is the 'Twist' present?"), Architectural Discipline **30%** ("your
engineering decisions, not just your ability to call an API"), Demo & Production
Readiness **30%** ("undeniable proof of execution"); Taskmaster judges assess
whether the agent "intercepts and completes a multi-step background workflow";
bonus stage allows +0.2 per extra Google model up to 0.6.

**User directive:** incorporate all review recommendations — value wins over the
time budget. The BUILD_PLAN cut list still exists but is now last-resort only.

**Adopted (each is now a PHASES.md item or a doc edit):**
1. Live path (Phases 3–4) stays top priority — everything else is worthless if
   Stage One fails. New explicit live-credential smoke-test item (model IDs were
   doc-verified 2026-08-21 but never exercised).
2. Approve/Reject persistence elevated: best story-per-hour item (state management
   for the 30% criterion + learning-from-human-rejections for the 40% one).
3. "The Twist" named explicitly in the Devpost description and the video close —
   the twist is inverted: restraint made mechanical (no-LLM clustering, frozen
   thresholds, locked holdout, citation critic, the caught reward-hack).
4. Cloud Scheduler weekly trigger on the batch job (new Phase 4 item) — makes the
   hackathon's "runs in the background, asynchronously" tagline literal.
5. Analyst-value UI touches (new Phase 6 items): "NEW THIS RUN" badge (surfaces
   the existing escalation-ledger diff) and Approve → Markdown brief download
   (workflow completes with an artifact in hand; guardrail #6 intact — nothing
   auto-sent). Trend sparkline recorded as an explicit last-in-line stretch.
6. ASRS institutional-mirror framing in video + description: ASRS takes 100k+
   reports/yr, two expert analysts screen each within 3 working days, and the real
   output is an Alert Message to organizations in authority — VIGIL mirrors that
   exact triage→alert workflow (asrs.arc.nasa.gov + NTRS doc 20210023200).

**Explicitly rejected, on purpose:** chasing Veo/Lyria model bonuses or the
Multimodal UX side prize (forcing them into a safety-triage tool costs
30%-criterion points to gain bonus decimals); full-corpus scale-up; any new agent
types. Gemma stays a stretch-only bonus.

Docs touched: PHASES.md (new/annotated items + footer addendum), SUBMISSION.md
(rubric section + description/video sub-items), DEMO_SCRIPT.md (ASRS caption,
scheduler shot, badge, download ending, twist line in the close), ARCHITECTURE.md
(scheduler, badge, brief export). No code changed in this session-segment.

## 2026-08-29 (Sat) — Real-data EDA, `--dataset` wiring, and two clustering scale bugs

Ran the EDA pass (Phase 2, unblocked once data landed) and wired `run_batch.py` to
accept a real dataset instead of only the 6-report demo fixture.

**EDA findings** (full 38,655-row train split unless noted): ZZZ rate in
`Place_Locale Reference` is 52.1% (20,148 rows) — confirms DATA.md quirk #1;
airport-level trends really are unusable, type×phase×component is the only viable
cluster facet. Report 2 present on 23.6% of rows (9,111/38,655) — that's the dedup
label base rate to eval against later. `;`-splitting and empty-string→None both
behave as `pipeline/ingest.py` assumes. 0 duplicate ACNs, 0 rows missing
acn/narrative in the full train split. `normalize_rows` ran clean over all 38,655
train + all 4,295 validation rows — first time `pipeline/ingest.py` has touched real
data; moves it from "written, unverified" to actually verified.

**`run_batch.py`:** added `--dataset PATH --slice N --seed N` (mutually exclusive
with `--demo`), backed by `pipeline.ingest.load_parquet` — its existing holdout-read
guard is reused, not duplicated, so an accidental `--dataset data/holdout/test.parquet`
still fails hard. `make run-real` runs a 5,000-report seed-42 slice of train, which
is now the finalized demo slice size (Phase 2's open decision).

**Two real bugs found by actually running the 5k slice** (not found any other way —
the 6-report fixture is too small to expose either):
1. `cluster_reports` converted the full TF-IDF sparse matrix to a dense array before
   HDBSCAN. At 5k documents with bigrams that matrix has ~84k columns; the dense
   version is large enough that a run took 6+ minutes of CPU and never finished
   (killed manually, never printed output). Fixed by adding seeded `TruncatedSVD`
   (100 components, `random_state=42` — deterministic, no LLM call, so guardrail #1
   still holds) between the vectorizer and HDBSCAN; small inputs below the
   component count still densify directly, so the demo fixture's behavior is
   unchanged. Full 5k run is now ~5 seconds.
2. Once it ran, the result was one 2,879-member cluster (58% of the batch) and
   nothing else — not what "surfaces emerging hazard patterns" is supposed to look
   like. Root cause: `allow_single_cluster=True` was hardcoded in
   `cluster_embedding_matrix`. That setting is *load-bearing* for the 6-report demo
   fixture (verified directly: with it off, the fixture produces zero clusters, all
   noise — HDBSCAN can't split 6 points into sub-clusters below the root), but at
   real scale it lets HDBSCAN pick the whole-dataset root as "the" cluster instead
   of splitting it. Fixed with a size-aware rule instead of a flat setting:
   `allow_single_cluster = len(reports) < 2 * min_cluster_size` — below that count a
   second qualifying cluster can't physically exist anyway, so allowing the
   single-cluster root is the only way to detect a pattern at all; above it, real
   sub-cluster splitting is what we want. Re-ran the 5k slice after the fix: 23
   distinct clusters (e.g. "Horizontal Stabilizer Trim events during Climb",
   "Hydraulic Main System events during Cruise", "GPS & Other Satellite Navigation
   events during Cruise"), largest cluster 629 members, still ~5 seconds. All 14
   tests still pass, ruff clean.

**Scope call made this session:** Phase 5 (self-improvement loop) has zero code —
not even a stub — and is offline/extractor-only, isolated from everything else that
still needs to happen (live agent wiring, Cloud Run deploy, video, submission). With
~2.5 days left, recommending it be the one exception to the "incorporate all rubric
recommendations" directive above: cut it for this submission rather than build a
loop that can only run 0-1 iterations in the time left. This is a recommendation,
not something already acted on — flagged for the user to confirm or override.

Next: live Gemini credential smoke test (Phase 3, needs the user's terminal —
network), then wire the live agent graph into `run_batch.py` (the single biggest
gap between the architecture doc and the code), then Cloud Run deploy.

**User directive, same session:** do not drop Phase 5. Keep it in scope; the
cut-list recommendation above stands as a flagged option only, not acted on.

## 2026-08-29 (Sat, cont'd 3) — Live Gemini credentials confirmed working

Ran the live-credential smoke test in the user's terminal (API key from Google AI
Studio → local `.env`, gitignored). Checked both model IDs from `config/models.yaml`
directly via `google-genai` (not through ADK's `LlmAgent`/`Runner` — that's the next
item): `client.models.get()` resolved both `gemini-3.7-flash` and
`gemini-embedding-2`, one real `generate_content` call against `gemini-3.7-flash`
returned text, and one real `embed_content` call against `gemini-embedding-2`
returned a 3072-dimension vector. Both model IDs are alive as of today, six weeks
after being doc-verified on 2026-08-21 — the highest-risk unknown (a dead model ID
discovered on deploy day) is now closed. `pipeline/embeddings.py`'s `embed_reports`
is exercised by this same call path, so its PHASES.md row moves to done too.

Next: wire the live ADK agent graph (`agents/definitions.py`) into
`pipeline/run_batch.py` — the single biggest gap between the architecture doc and
the running code. This needs the ADK `Runner`/session-service plumbing, which
`build_agent_graph` alone doesn't exercise (constructing an `LlmAgent` doesn't call
the API — only running it through a `Runner` does).

## 2026-08-29 (Sat, cont'd 4) — ADK Runner validated live; scope correction; risk-policy bug found and fixed

Added `agents/live.py` (a synchronous `Runner`/`InMemorySessionService` helper for
one ADK `LlmAgent` turn, built from reading the installed `google-adk==2.7.1`
source directly rather than guessing the API — CLAUDE.md's instruction to verify
SDK surfaces before writing code) and a small `extract_tokens` addition to
`agents/runtime.call_with_observability` (live calls only know their token count
after the response comes back, unlike the existing static `tokens=` param).

**Validated live in the user's terminal:** built a standalone Extractor `LlmAgent`
(real prompt, real `ExtractionOutput` schema) and ran it on one real report through
`agents/live.py`. Structured JSON came back correctly, parsed clean into
`ExtractionOutput`, and the `agent_log` entry captured real latency (5,440ms) and
token count (1,064) — proving the Runner/session pattern inferred from source
actually works, before building the other four agent stages on top of it unverified.

**Scope correction, found while planning the wiring:** Extractor and Dedup are NOT
per-report operational calls in the live batch path. ASRS pre-merges "Report 1" and
"Report 2" (a second reporter's account of the *same* event) into one row under one
ACN before publishing — there is no cross-report duplicate to find at runtime.
`pipeline/ingest.py` already gets structured fields free from NASA's own coded
columns, so the LLM Extractor's actual job is proving it can derive the same fields
from raw narrative text, scored against those coded fields as ground truth on a
~200-row dev sample (exactly what BUILD_PLAN.md's Day-2 plan says) — not a call per
report in the operational batch. That distinction matters for cost: my one
Extractor call took 5.4s/1,064 tokens; at 5,000 reports that's 7+ hours and ~5M
tokens, not viable and not what the architecture calls for. The real operational
live scope is: Analyst once **per cluster** (23, not 5,000), Coordinator+Critic once
**per escalated cluster** (a handful). Extractor/Dedup live exercise moves to a
separate eval-script task, not `run_batch.py --live` wiring.

**Bug found while checking whether that operational scope was even reachable:**
zero of the real 5k slice's 23 clusters crossed the 0.60 escalation threshold — max
observed was 0.40. Root cause: `config/frozen.yaml`'s `severe_results`/
`severe_events` listed plausible-sounding labels (`"Aircraft Damage"`, `"Injury"`,
`"Loss of Control"`, `"Engine Shutdown"`, `"Near Midair Collision"`,
`"Loss of Separation"`) that **do not exist anywhere in the real ASRS coded
vocabulary** — checked directly: 0 of 5,000 real reports matched any of them. Since
`severity_weight` is 0.50 of the total score, `severity=0` caps every cluster's
total at ≤0.50, structurally below the 0.60 threshold regardless of cluster size or
trend — no real-data cluster could ever have escalated under the old config.

Flagged this to the user explicitly before touching it, since `config/frozen.yaml`
is the guardrail #2 "immutable risk policy" file — its own header permits "a
reviewed code/configuration change," but changing what counts as severe is a
substantive correction, not a mechanical bugfix, so it went through
`AskUserQuestion` rather than being silently committed. **User confirmed: fix now,
verify, commit.**

Corrected `severe_results`/`severe_events` to the real matching ASRS values (found
by dumping the full 38-value `Events.5_Result` and 92-value `Events_Anomaly`
vocabularies and searching for the intended concepts): `Aircraft Aircraft Damaged`,
`General Physical Injury / Incapacitation`, `Flight Crew Inflight Shutdown` (all
Result-column values, → `severe_results`); `Conflict NMAC`, `Conflict Airborne
Conflict`, `Conflict Ground Conflict`, `Ground Event / Encounter Loss Of Aircraft
Control`, `Inflight Event / Encounter Loss Of Aircraft Control`, `Flight Deck /
Cabin / Aircraft Event Illness / Injury` (all Anomaly-column values, → `severe_events`).

This also broke `test_demo_batch_escalates_a_cited_cluster` — the synthetic demo
fixture used the same fictional `"Engine Shutdown"` placeholder in both its
`results` and `anomaly_labels` fields, which (by design, before this fix) happened
to match the old fictional policy string. Fixed the fixture to use real values too
(`results=("Flight Crew Inflight Shutdown",)`, `anomaly_labels=("Aircraft Equipment
Problem Critical",)`) — both real ASRS strings, so the demo fixture is now
factually grounded rather than coincidentally matching a made-up label. All 14
tests pass again.

**Verified on the real 5k slice after the fix:** 4 of 23 clusters now escalate
(risk 0.71, 0.70, 0.66, 0.66), with sensible gradation — small tight clusters (5-8
members) escalate on real severity signal, while the large 629-member "Engine
events during Parked" cluster stays at 0.50 (low proportional severity-hit rate).
The core "surfaces emerging hazard patterns, escalates the severe ones" story now
actually works against real data, not just the synthetic fixture.

Next: wire live Analyst (per cluster) and Coordinator+Critic (per escalated
cluster) into `run_batch.py` behind a `--live` flag, now that escalated clusters
exist on real data to test against.

## 2026-08-29 (Sat, cont'd 5) — Analyst wired into run_batch.py behind --live

Wired the live Analyst call into the operational batch path. `run_batch()` now
takes an injectable `assess_cluster` parameter (default: the existing
deterministic stand-in, so the no-credentials demo path is byte-for-byte
unaffected); `main()` builds a real Analyst `LlmAgent` via
`agents.definitions.build_agent_graph()` and binds it in with `functools.partial`
when `--live` is passed. New `agents/orchestrate.py` holds `live_assess_cluster`,
which calls the Analyst through the validated `agents/live.py` Runner helper and
parses its structured `ClusterAnalysisOutput` — risk itself stays fully
deterministic (`pipeline.risk.score_cluster` runs before this, unchanged).
`make run-live` runs the real 5k slice with this turned on. Refactored
`_assess_cluster`'s inline facets dict into a shared `cluster_facets()` so the
live and deterministic paths don't duplicate that logic. All 14 tests pass
(default behavior unchanged), ruff clean.

Not yet run against real data — that needs the user's terminal/credentials. Once
confirmed, next is Coordinator (Precedent ∥ Risk ∥ Brief Writer) with 2-of-3
failure tolerance, then Critic (LLM pass + the existing deterministic
`strip_uncited_claims` backstop, which stays mandatory regardless of what the LLM
critic does — guardrail #4 has no exceptions).

<!-- Add a new dated section above this line each time we make a decision, ship a
     feature, or change status. Keep entries short: what changed, what's verified,
     what's still open. -->
