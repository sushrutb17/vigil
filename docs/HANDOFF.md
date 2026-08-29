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

## 2026-08-30 ~00:30 ET — Claude Code (submission deliverables; measured the core stage and it failed)
- Last commit: `af4d8d0` Put the clustering failure in the README and Devpost draft
- Finished:
  - **Architecture diagram rewritten and rendered.** The mermaid source was from
    Aug 20 and had drifted into three *false* claims, each making the agents look
    more autonomous than they are: risk shown as `severity × freq × trend` (it is
    a deterministic weighted sum, and the Analyst does not compute it), Extractor
    and Dedup shown in the operational batch path (scoped out Aug 29 — that
    implied 5,000 model calls that do not happen), and the locked holdout shown
    running *before* the guards (the real order short-circuits so it is never
    read). Split into `docs/architecture.png` + `docs/self-improvement-loop.png`,
    both embedded in the README. **Last README gap closed.**
  - **Megacluster brief fixed.** `format_citations` caps the inline list at 12
    and states the remainder. The 629-member cluster's brief went **18,068 → 636
    characters**; largest brief in the whole artifact is now 4,095. Artifact
    regenerated and re-verified: 23 clusters, 4 escalated, **zero fabricated
    citations** against all 38,655 source ACNs, no DEGRADED, all four escalated
    briefs fully sectioned.
  - **`make eval-offline`** (`eval/offline_report.py`) — deterministic, no model
    calls. Closed both remaining cheap Phase 3 eval rows.
  - **NEW THIS RUN badge** shipped, driven off the existing escalation ledger.
  - **`docs/DEVPOST_DRAFT.md`** — ~1,600 words, paste-ready.
  - 52 tests pass, ruff clean, tree clean.
- **Two honesty problems found and fixed — read these before recording:**
  1. **`DEMO_SCRIPT.md` told the recorder to say on camera "We caught our own
     agent cheating; the guard rejected the change."** That never happened. No
     revision ever gamed ROUGE. Following the script would have put a fabricated
     result in the submission video. Rewritten with an honest substitute (the
     citation gate that validated *shape* not *provenance* and kept five
     invented ACNs) — a better beat anyway, because it is about the safety
     mechanism rather than the model. Same claim corrected in `SUBMISSION.md`
     and flagged at the top of the Devpost draft.
  2. The same script section listed cluster purity, factual coverage and Critic
     catch rate as numbers to show. Two of the three did not exist yet.
- **The significant new finding — clustering fails its own guard:**
  - Purity **0.301** vs a majority-class baseline of **0.219** (+0.08, modest).
    Adjusted Rand **0.0018** — essentially no recovery of NASA's anomaly
    partition. Noise fraction **0.837**: 23 clusters covering 816 of 4,998
    labelled reports.
  - **0.837 breaches EVAL.md's own predeclared `noise_fraction < 0.40`
    tripwire.** `evaluate_guards` implements that check but is only ever invoked
    on the extractor promotion loop, so **nothing had ever run it against the
    clustering stage it was written for.**
  - **Deliberately not fixed, and the next session should think hard before
    "fixing" it.** Tuning `min_cluster_size` until the number drops under its own
    guard, hours from a deadline, with no held-out check on clustering, is the
    exact reward-hack this project claims to have engineered against. The honest
    options are (a) raise the parameter and re-measure properly, or (b) argue the
    0.40 threshold is wrong for hazard detection where most reports genuinely are
    one-offs — but (b) has to be argued *before* seeing whether it helps.
  - The Critic eval, by contrast, came back **1.000** catch rate with **1.000**
    retention of legitimate claims (the retention control matters — a gate that
    deleted everything would score 1.000 on catch rate alone).
- Next action — **everything left is yours, not code**, deadline Aug 31 5pm PDT:
  1. **Redeploy `vigil-ui`** so the hosted service serves the regenerated
     artifact. The deployed revision still has the 18,068-character brief.
     `./infra/deploy.sh` (you run deploys, not the harness).
  2. **Push to public GitHub.** Pre-push audit is done and clean: no secrets in
     files or history, `.env` never committed, no raw/holdout data tracked, no
     guardrail-#5 violations anywhere including history. 72 tracked files, 4.3MB.
  3. **Record the video** using the corrected `DEMO_SCRIPT.md`.
  4. **Submit Devpost** from `docs/DEVPOST_DRAFT.md` + the three URLs.
- Watch out:
  - `make improve` = **601 live Flash calls**. `make artifact` = a **complete**
    live run (~39 calls); never chain it after `run-live`.
  - Still ⬜ and fine to cut: dedup eval, real-data Cloud Run job, trend
    sparkline, bonus posts.
  - The "caught our own agent cheating" reward-hack beat remains **unearned**.
    Do not let it back into any artifact.

---

## 2026-08-29 ~22:00 ET — Claude Code (Phase 5 built and run live; DEGRADED demo landed)
- Last commit: `9be1743` Put the real measured numbers in the README
- **Note for whoever reads this next:** the previous handoff entry was stale on
  arrival — its three "next actions" (regenerate artifact, verify Approve/Reject
  against hosted Firestore, Cloud Scheduler) had all been *done and committed*
  without a sign-off. Tree was clean, 26 tests green. Trust `docs/PHASES.md`
  over the newest handoff entry when they disagree; PHASES.md was accurate.
- Finished:
  - **Phase 5 is done, end to end, verified on live models.** It had zero code.
    The loop is `make improve`: seeded dev sample from the validation split →
    score incumbent → Evaluator reads the *frequency-ranked confusion list* →
    candidate prompt → score candidate → guards → locked holdout → promote or
    discard, writing `eval/runs/*.json` on **every** outcome (now committed via
    a deliberate `.gitignore` exception; EVAL.md makes the ledger the source of
    the improvement curve).
  - **First real run promoted extractor v1 → v2.** 200-row dev / 100-row
    holdout, 601 live Flash calls. dev macro-F1 0.0056 → 0.4099, holdout
    0.0081 → 0.4219. Guards passed.
  - **The headline result is unflattering and should stay that way.** v1 scored
    *below* the majority-class + keyword baseline (0.0515). v1 never told the
    model the ASRS labels are a closed vocabulary, so it answered "Approach"
    where the coded value is "Initial Approach", and omitted `primary_problem`
    from its field list entirely. The Evaluator diagnosed exactly that from the
    confusion list alone. Holdout gain (+0.4139) *exceeded* dev gain (+0.4043)
    — the opposite of overfitting. `flight_phase`, which the loop does not
    optimize, still trails its keyword baseline (0.121 vs 0.171). All three
    numbers are in the README and PROGRESS.md. Do not quietly drop the third.
  - **A guard fired and the guard turned out to be wrong — read PROGRESS.md on
    this before touching `eval/guards.py`.** The 8-row smoke run blocked this
    revision on label diversity. It was a metric bug: diversity was
    `distinct_predicted / distinct_expected`, which rewarded v1's free-text
    sprawl (2.33) and punished a correctly vocabulary-constrained candidate
    (1.00). Replaced with in-vocabulary label *coverage*, bounded [0,1], which
    **tightens** the guard (majority-label hack now scores ~0.06 vs a 0.15
    floor). Documented at length precisely because "changed a tripwire right
    after it blocked us" is the most self-serving-looking move in this repo.
  - **Phase 6 fan-out failure tolerance is now demonstrated live**, not just
    written. `--fail-agent {precedent,risk,brief_writer,critic}` (repeatable,
    requires `--live`, loud stderr banner) raises a real `InjectedFailure` at
    the call site, so the demo travels the genuine failure path. Verified:
    `--demo --live --fail-agent risk` → `DEGRADED` brief, Risk section fell
    back to its cited deterministic line, everything still ACN-cited.
  - **Found and fixed a real bug while testing that:** the `DEGRADED` banner
    survived only if the LLM Critic echoed it (its response is used verbatim as
    the brief, and `CRITIC_INSTRUCTION` asks it to preserve *headings* — which
    `DEGRADED` is not). A reviewer could not tell a partial-failure brief from
    a clean one. `_reassert_degraded` now derives the banner from what the
    orchestrator knows for certain. Locked by a test whose fake critic strips it.
  - README now has the measured-results table, `make improve`, the
    failure-tolerance command, and the loop's guardrails.
  - 49 tests pass, ruff clean, tree clean.
- Next action, in priority order — **the deadline is Aug 31 5:00pm PDT and every
  remaining blocker is a submission deliverable, not code**:
  1. **Export the architecture PNG** from `docs/asrs-agent-architecture.mermaid`.
     It is the last README gap and an explicit definition-of-done item.
  2. **Push the repo to public GitHub** (Phase 0, deliberately deferred, still
     ⬜). Nothing else can be judged until this happens.
  3. **Record the video** (≤4 min). The failure-tolerance beat is now unblocked
     and cheap to shoot: `python -m pipeline.run_batch --demo --live
     --fail-agent risk`, ~4 calls, ~20s.
  4. **Devpost form** — needs the literal "The Twist" section per SUBMISSION.md.
     The Phase 5 numbers above are the strongest material it has; lead with v1
     losing to the baseline, since honesty about that is the whole thesis.
  5. Only if time remains: Phase 4's real-data Cloud Run job (⬜), the
     "NEW THIS RUN" UI badge (⬜), resumable batch (🔶).
- Watch out:
  - **No redeploy or artifact regeneration is needed from this session's work.**
    `extractor` appears nowhere in `pipeline/`, so promoting v2 cannot change
    the batch pipeline, `artifacts/demo_run.json`, or the live Cloud Run
    services. Verified, don't re-spend the ~39 live calls checking.
  - `make improve` costs **601 live Flash calls** per full iteration. The
    holdout half is only paid once a candidate has cleared the guards *and*
    shown a dev gain. Use `--sample-size 8 --no-holdout` (~17 calls) to smoke
    test plumbing changes.
  - The 629-member megacluster's 18,000-character deterministic brief is
    **still unfixed** and still in the deployed UI. A judge will see it. This
    remains the most visible cosmetic problem in the demo.
  - The "caught our own agent cheating" demo beat from EVAL.md is **still
    unearned**. The guard event above was a metric bug, not a gamed revision.
    Do not dress it up as the reward-hack beat in the video or on Devpost.
  - Prompt versions live in `config/prompts/`; `config/frozen.yaml` is still
    never written by anything. `REVISABLE == {"extractor"}` raises for any
    other agent. Both are enforced by tests, not convention.

---

## 2026-08-29 ~19:00 ET — Claude Code (artifact regenerated; found fabricated citations)
- Last commit: see `git log -1`
- Finished:
  - `make run-live && make artifact` ran clean on the real 5k slice: 23 clusters,
    4 escalated, all 4 with fully populated `## Hazard` / `## Precedent` /
    `## Risk Assessment` / `## Recommended Brief`, no DEGRADED, no stray H1.
    Precedent produces genuine content on real data, as expected.
  - **Then found a worse bug by reading the brief.** `## Risk Assessment` cited
    `[ACN 1000001]`-`[ACN 1000005]`; the cluster's members were 1044401,
    1461959, 1640441, 1748192, 1799467. Those IDs are in NONE of the 38,655
    reports (checked against the parquet). The model fabricated them and the
    gate kept them, because `ACN_CITATION` matches any 4+ digit number — it
    validated *shape*, never *provenance*.
  - Root cause was self-inflicted: `f2fe88a` told Risk to cite "the ACNs
    supplied with the cluster" while `risk_message` supplied only
    `member count=N` and no ACNs, so the model invented placeholders.
  - Fixed both halves: `risk_message` now supplies the member ACNs, and
    `strip_uncited_claims` takes an `allowed_acns` allow-list. Invalid
    citations are cut surgically (a claim keeps genuine sources, loses only
    invented ones); a claim whose every source was invented is dropped.
    Allow-list = cluster members + the precedent candidates actually supplied,
    because Precedent legitimately cites outside the cluster. Verified against
    the parquet that every such out-of-cluster ACN in the artifact is real.
  - `make run-live` also could not find the API key: the Makefile never loaded
    `.env`, so it died inside ADK's first Analyst call, once per cluster, after
    already clustering 5,000 reports. Makefile now loads `.env` and has a
    `require-key` guard.
  - 26 tests pass, ruff clean.
- Next action:
  1. **Regenerate the artifact again** — `artifacts/demo_run.json` on disk is
     the pre-fix run and 3 of its 4 escalated briefs contain fabricated ACNs.
     Do NOT deploy it. Run **`make artifact` on its own** (now works without
     sourcing .env), then re-verify with the snippet in PROGRESS.md before
     committing and redeploying `vigil-ui`. Do not chain
     `make run-live && make artifact`: the two targets are the same complete
     live run differing only in output destination, so chaining them burns
     ~78 live Gemini calls instead of 39 for one snapshot.
  2. Click Approve/Reject on the hosted URL, confirm Firestore receives them.
  3. Then: Cloud Scheduler trigger, DEGRADED demo path, Phase 5 loop (zero
     code, and per explicit user directive NOT to be cut).
- Watch out:
  - The 5k slice has one 629-member megacluster ("Aircraft Maintenance
    Installation Errors"), whose deterministic brief is an 18,000-character
    wall of ~630 ACN citations. Not wrong, but it looks terrible in the UI and
    a judge will see it. Consider capping the citation list in
    `run_batch.draft_brief`, or excluding that cluster from the demo view.
  - Unbracketed ACNs inside the Analyst's `hazard_statement` prose (e.g.
    "(ACN 1121783, ...)") are NOT validated by the gate — only bracketed
    citations are. They duplicate the bracketed list, so low risk, but know it.
  - The batch job image is behind: it predates both today's orchestrate fixes.

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
