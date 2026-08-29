# Session handoff log

Append-only. **Newest entry goes directly below this line**, so the top of the list
is always the most recent sign-off. Every harness session (Claude Code or Codex)
writes one entry before its usage window ends, and reads the newest entry when it
starts — this file is the baton between sessions, so the user never has to retype
project status into a new chat.

Entry format:

```
## <date time> — <account/lane, e.g. "Claude acct #1, critical path">
- Last commit: <hash> <subject>
- Finished: <what is now true that was not before>
- Next action: <the single most specific next step, as a command or file+change>
- Watch out: <surprises, dead ends, things the repo can't tell you>
```

---

## 2026-08-29 ~18:15 ET — Claude Code (verified the prompt fix in the cloud; fixed the empty-section class of bug)
- Last commit: `08adc32` Never let a brief section render as a bare heading
- Finished:
  - **Verified `f2fe88a` landed in production** by reading the brief execution
    `vigil-batch-dwpfp` wrote to Firestore (REST API, read-only). `## Risk
    Assessment` is now fully populated with cited bullets and the stray
    `# Cleaned Brief` H1 is gone.
  - **`## Precedent` was still empty — and the cause was not the prompt.** The
    `agent_log` showed Precedent *succeeding*, spending 596–1,108 tokens a run.
    Two separate causes, both fixed in `agents/orchestrate.py`:
    1. On the `--demo` fixture, `_precedent_candidates` can never return
       anything: all 6 reports share `component="Engine Control"` and all 6 are
       cluster members, and the function excludes members. The only honest
       answer carries no ACN, so the gate deleted it every time. The call is
       now skipped when there are no candidates (deterministic cited line
       instead) — one fewer live Flash call per escalated cluster.
    2. The general defect: `strip_uncited_claims` is line-based and always
       keeps headings, so **any** section whose lines all lack citations
       survives as a bare heading — byte-identical to a section whose agent
       never ran. The existing fallbacks only fire when a sub-agent *raised*,
       so they could not catch it. New `_backfill_empty_sections` runs after
       the gate and restores a member-ACN-cited placeholder.
  - Failure accounting now counts failures rather than survivors, so a skipped
    Precedent does not spuriously stamp the brief `DEGRADED`.
  - 23 tests pass (was 21), ruff clean. Both new tests were confirmed to fail
    against the pre-fix source via `git stash` — they are real guards.
- Next action, in priority order:
  1. **Regenerate `artifacts/demo_run.json`** (`make run-live` → `make artifact`
     → commit → redeploy `vigil-ui`). Still the highest value per minute: it is
     what a judge sees first. Doing it *now* captures both `f2fe88a` and this
     fix in one pass; doing it earlier would have wasted ~23 Analyst calls.
     The real 5k slice is also the first run that will produce genuine
     Precedent content, since it has non-member reports sharing a component.
  2. **Click Approve and Reject on the hosted URL**, confirm a `clusters/`
     status change and a `rejections/` doc land in Firestore.
  3. Then: Cloud Scheduler weekly trigger, DEGRADED demo path, Phase 5 loop
     (zero code exists — and per an explicit user directive it is NOT to be
     cut from scope).
- Watch out:
  - The batch job's image is one `jobs deploy` behind this fix. It needs a
    redeploy before its next execution shows the repaired Precedent section.
  - Don't "fix" the empty Precedent on the demo fixture by loosening
    `_precedent_candidates` to include members — a cluster is not its own
    precedent, and the emptiness there is semantically correct.
  - Reading what actually reached Firestore is what caught both of these. The
    job exit code was 0 and every agent reported success on all five
    executions. Trust the stored artifact, not the exit status.

## 2026-08-29 ~17:30 ET — Claude Code (Phase 4 deploy: DONE, live on GCP)
- Last commit: `f2fe88a` Make Precedent and Risk actually cite, so their output
  survives the gate
- Finished: **VIGIL is deployed and running on Google Cloud.**
  - UI: https://vigil-ui-715230861973.us-central1.run.app (public)
  - Batch job `vigil-batch`, project `vigil-hackathon-506218`, `us-central1`
  - One execution exercises Gemini+ADK, Cloud Run, and Firestore. All four
    collections populated; `agent_log` holds one row per agent with
    model/tokens/latency — that's the observability story, live.
  - Fixed three bugs the real run exposed: gcloud `--args` parsing (`d0b47f5`);
    briefs never reaching any store (`cb1f248`); and Precedent+Risk producing
    output the citation gate deleted 100% of the time (`f2fe88a`).
  - 21 tests pass, ruff clean, everything committed.
- Next action, in priority order:
  1. **Regenerate `artifacts/demo_run.json`** — the deployed UI serves this
     file and it predates `f2fe88a`, so the hosted briefs still show empty
     `## Precedent` / `## Risk Assessment` sections. `make run-live` then
     `make artifact` (needs credentials, ~23 Analyst calls on the real slice),
     commit, then redeploy `vigil-ui`. Highest value per minute: it's what a
     judge sees first.
  2. **Click Approve and Reject on the hosted URL** and confirm Firestore
     receives them (a `clusters/` status change and a `rejections/` doc). IAM
     and code are in place; only the live click is unverified.
  3. Then: Cloud Scheduler weekly trigger, DEGRADED demo path, Phase 5 loop
     (zero code exists — and per an explicit user directive it is NOT to be
     cut from scope).
- Watch out:
  - `gcloud run jobs execute` reruns the **already-built image**. A code change
    needs `gcloud run jobs deploy ... --source .` first. This cost two wasted
    executions and a "why didn't my fix work" detour.
  - When only app code changed, redeploy just the job — running the whole
    `deploy.sh` adds a new Secret Manager version every time.
  - The project ID is `vigil-hackathon-506218`; the bare name `vigil-hackathon`
    fails with a misleading *permission denied*, not *not found*.
  - The gcloud SDK is unpacked at the repo root (~250MB), excluded in all three
    ignore files. Don't commit it, don't delete the exclusions.
  - **Sush runs deploy/execute commands themselves** — hand over the command,
    don't run it for them. Read-only cloud inspection is welcome and has
    already caught one real bug (querying Firestore over REST, not the console).

## 2026-08-29 ~15:45 ET — Cowork session (relay pickup + Phase 1 close-out)
- Last commit: 1504d2a Restore executable bit on infra/deploy.sh (lost in previous edit)
- Finished: Picked up per Prompt B — tree was already green (14/14 tests, ruff
  clean; the code changes the ~10:30 handoff described as "uncommitted" had in
  fact already been committed by a session between then and now, commits
  8d4a032 through 62cbe86). Only two doc files were genuinely uncommitted
  (docs/HANDOFF.md, docs/KICKOFF_PROMPTS.md) — committed those, gitignored
  the local .agents/.claude/.vscode harness dirs. Then did the next unblocked
  Prompt A item (step 4): UI Approve/Reject now persists — TriageStore gained
  `set_cluster_status` (merge update) and `put_rejection`
  (rejections/, negative examples per ARCHITECTURE.md); UI picks
  FirestoreStore when GOOGLE_CLOUD_PROJECT is set. Caught and fixed a
  consequence before it could bite: infra/deploy.sh still deployed vigil-ui
  with zero IAM roles and no GOOGLE_CLOUD_PROJECT, which would have made
  Approve/Reject silently no-op in production — vigil-ui-run now gets
  roles/datastore.user and the env var. PHASES.md Phase 1's last open row is
  now Done. 17/17 tests pass, ruff clean, all committed.
- Next action: Phase 4 deploy is the only remaining unblocked critical-path
  item (Prompt A step 5) and it needs `gcloud`/network, which this session's
  device_bash does not have. Run in your own Mac terminal, repo root:
  ```
  gcloud auth login
  gcloud config set project vigil-hackathon-506218
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
      artifactregistry.googleapis.com secretmanager.googleapis.com
  export GOOGLE_CLOUD_PROJECT=vigil-hackathon-506218
  export GOOGLE_API_KEY=$(grep GOOGLE_API_KEY .env | cut -d'=' -f2-)
  make deploy
  ```
  Then `gcloud run jobs execute vigil-batch --project vigil-hackathon-506218 --region us-central1 --wait`
  (deploy.sh prints this exact command at the end too). After that: open the
  printed UI URL, click Approve/Reject once each to verify Firestore actually
  receives the writes (check the Firestore console for clusters/ status
  fields and a new rejections/ doc) — that live check is still unverified,
  only unit-tested so far. Once deploy is confirmed, PHASES.md's five Phase 4
  rows can flip to Done in the same commit as whatever session verifies them.
- Watch out: (1) `make deploy` runs `infra/deploy.sh`, which is idempotent on
  re-run (checks `describe` before `create` for service accounts/secrets) but
  NOT dry-run-safe — it will actually create billed Cloud Run
  services/secrets the first time. (2) The batch job (`vigil-batch`) runs
  `--demo --live --firestore` against the bundled 6-report fixture, not the
  real 5k slice (data/raw is gitignored and never in the image) — that's
  correct and intentional, not a bug to fix. (3) Deadline is Mon Aug 31, 8:00
  PM ET treat 6:00 PM as the real cutoff — deploy + E2E verify + video are
  still all ahead of the failure-tolerance demo and the Devpost draft
  (Phases 6/7), so don't let deploy prep expand past what's needed to get a
  URL.


## 2026-08-29 ~10:30 ET — Cowork session (planning, no code)
- Last commit: 6aab879 Mark real data download + holdout lock done (Phase 2)
- Finished: Multi-account working model decided (relay, not parallel lanes). Added
  the session boot protocol to CLAUDE.md + AGENTS.md, a Codex docs-lane restriction
  to AGENTS.md, `docs/KICKOFF_PROMPTS.md`, and this file. No code touched.
- Next action: Start a Claude Code session with Prompt B from
  `docs/KICKOFF_PROMPTS.md`. Its first job is the uncommitted work already in the
  tree (`--dataset` flag + seeded slicing in run_batch.py, TruncatedSVD densify in
  cluster.py, `make run-real`, new PHASES.md rows): get tests + lint green, then
  commit it along with these doc files.
- Watch out: (1) The uncommitted `cluster.py` change is a real performance fix — a
  5k-report run was burning 6+ min on a dense TF-IDF matrix; don't revert it
  without reading its docstring. (2) PHASES.md gained 5 rubric-alignment rows on
  Aug 29; the NEW-badge, brief-download and sparkline rows are explicitly forfeit
  if the critical path slips. (3) Deadline is Mon Aug 31 8:00 PM ET — treat 6:00 PM
  as the real cutoff.
