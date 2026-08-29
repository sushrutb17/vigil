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

<!-- Add a new dated section above this line each time we make a decision, ship a
     feature, or change status. Keep entries short: what changed, what's verified,
     what's still open. -->
