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
  gcloud config set project vigil-hackathon
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
      artifactregistry.googleapis.com secretmanager.googleapis.com
  export GOOGLE_CLOUD_PROJECT=vigil-hackathon
  export GOOGLE_API_KEY=$(grep GOOGLE_API_KEY .env | cut -d'=' -f2-)
  make deploy
  ```
  Then `gcloud run jobs execute vigil-batch --project vigil-hackathon --region us-central1 --wait`
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
