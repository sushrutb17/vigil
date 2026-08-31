# Kickoff prompts — copy-paste one of these to start each harness session

**How the relay works.** Two Claude Code accounts alternate on the CRITICAL PATH in
the main checkout — only one runs at a time. When one hits its 5-hour usage limit:
it commits (including a fresh entry in `docs/HANDOFF.md`) and you start the *other*
Claude account with **Prompt B**. You do not retype status — the new session reads
`docs/HANDOFF.md` itself. Codex runs docs-only in a separate worktree and may run at
the same time as a Claude session.

**One-time setup for the Codex worktree** (run yourself in a Mac terminal, repo root):

    git worktree add ../vigil-docs -b docs-collateral

**Merging Codex's work later** (only when `git status` in the main checkout is clean):

    git merge docs-collateral

---

## Prompt A — Claude Code, critical path (fresh start, clean tree)

> You are the critical-path session for VIGIL. Read CLAUDE.md fully, then
> docs/PHASES.md fully, and follow the boot protocol in CLAUDE.md (git status
> first).
>
> Your lane, in strict order — do not reorder, and do not build anything that is
> not a row in PHASES.md:
> 1. Verify the real-data path end to end: `make run-real` completes and produces
>    sane clusters (Phase 2).
> 2. Live credential smoke test: one real LlmAgent call + one embedding call;
>    confirm the exact current Gemini model IDs resolve (there is a PHASES.md row
>    for this). Check official Google docs for IDs — never guess.
> 3. Wire the live agent graph into pipeline/run_batch.py behind an explicit flag,
>    keeping `make demo` deterministic and all tests green (Phase 3).
> 4. UI Approve/Reject persists decisions to the store (Phase 1's last open row —
>    elevated priority for the video).
> 5. Docker build, deploy.sh, Cloud Run deploy, live E2E run (Phase 4).
>
> Rules of engagement: the guardrails in CLAUDE.md are absolute. Commit at every
> green checkpoint and flip the PHASES.md tag in the same commit. If tests or lint
> break, fix before proceeding. When your usage window nears its end, stop at a
> committable state, add a HANDOFF entry to docs/HANDOFF.md, and commit.
>
> Begin with step 0: report in 5 lines what git status and PHASES.md say the
> current edge of finished work is, then start.

## Prompt B — Claude Code, relay pickup (previous session hit its limit)

> You are picking up VIGIL mid-relay; the previous session ran out of usage.
> Read CLAUDE.md fully, then docs/PHASES.md, then run `git status` and
> `git log --oneline -5`.
>
> The previous session's sign-off is the newest entry in `docs/HANDOFF.md` — read
> it first. If it is missing or stale, the uncommitted diff IS the handoff: read it
> file by file before touching anything.
>
> First job: get the working tree committed at a green checkpoint — understand the
> uncommitted diff, run `make test` and `make lint`, finish any half-done edit
> needed to get green, update PHASES.md tags to match reality, and commit. Then
> continue the critical-path lane exactly as defined in Prompt A of
> docs/KICKOFF_PROMPTS.md, from wherever the previous session stopped. Same rules
> of engagement.

## Prompt C — Codex, docs lane (runs in ../vigil-docs worktree)

> You are the docs-only session for VIGIL. Work ONLY in this worktree
> (../vigil-docs, branch docs-collateral). Read AGENTS.md fully — especially the
> Codex lane restriction — then docs/PHASES.md for project context. Never edit
> code directories.
>
> Your tasks, in order:
> 1. docs/SUBMISSION.md: draft the full Devpost description. It must include a
>    literal "The Twist" section (restraint made mechanical: no-LLM clustering,
>    frozen thresholds, locked holdout, citation critic) and the ASRS
>    institutional-mirror paragraph, per the notes already in SUBMISSION.md.
>    Track: Taskmaster. Leave clearly marked TODO placeholders for the repo URL,
>    hosted URL, video URL, and all metrics numbers — do not invent any of them.
> 2. Export docs/asrs-agent-architecture.mermaid to docs/architecture.png
>    (installing mermaid-cli locally is fine).
> 3. README.md: embed docs/architecture.png and add a metrics-table scaffold with
>    TODO placeholders. Do not invent numbers.
>
> Commit each finished task on this branch. Do not merge — the user merges. Before
> you finish, add a HANDOFF entry to docs/HANDOFF.md listing your commits and
> anything the code lane needs to know.
