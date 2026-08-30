# Devpost submission text — ready to paste

Category: **Taskmaster**. Solo entrant.

> **Honesty note for the submitter, not for pasting.** `SUBMISSION.md` planned a
> Twist line about "the guard that caught our own agent gaming ROUGE." **That
> never happened** — no revision ever gamed ROUGE, and the one guard that did
> fire turned out to be a bug in the guard itself. Claiming it would be a
> fabricated result in a submission whose entire thesis is verifiable restraint,
> and it is the kind of thing a judge who reads `eval/runs/` would catch. The
> three failures below are real, documented in `docs/PROGRESS.md`, and are
> better stories anyway.

---

## Inspiration

NASA's Aviation Safety Reporting System takes in over 100,000 confidential
incident reports a year. Every one is read by two expert analysts within a few
working days, and when a pattern is severe enough the output is an Alert Message
sent to the organizations in a position to act. It is one of the most successful
safety-learning institutions ever built, and it runs on human attention that does
not scale.

The friction is specific: the reports arrive faster than anyone can synthesize
them, and the value is not in any single report — it is in noticing that eleven
unrelated reports over five weeks describe the same emerging hazard. That is a
background, multi-step, judgment-heavy workflow. Nobody wants a chatbot for it.

## What it does

VIGIL ingests real NASA ASRS reports, clusters them into emerging hazard
patterns, scores each cluster against a frozen risk policy, and — only for
clusters that cross the severity threshold — fans out parallel agents to draft a
source-cited investigator brief. It runs unattended on a weekly Cloud Scheduler
trigger and remembers what it has already escalated, so it does not re-alert on a
pattern a human has already seen.

A human approves or rejects every brief. The system never sends, files, or
actions anything.

What the analyst actually gets, beyond the brief:

- **Nothing severe is silently dropped.** Clustering leaves most reports
  unclustered, and a report being statistically lonely says nothing about whether
  it is dangerous. Any report whose NASA-coded outcome matches the frozen severe
  vocabulary is surfaced in its own review queue even when it belongs to no
  pattern — **1,328 of them in the committed run**. It is deliberately given no
  name, no risk score and no brief, because one report is not a pattern and
  dressing it up as one would be the exact overreach this system avoids.
- **Every citation is one click from its source.** An ACN in a brief opens the
  underlying report: the narrative excerpt, flight phase, component, anomaly
  labels and outcome. Precedent citations — reports the agent pulled in from
  *outside* the cluster — are labelled as such, so a reviewer can see which
  evidence is the pattern and which is the argument for it.
- **The reviewer can edit before approving**, and the citation gate re-runs on
  the edited text. A human adding an uncited sentence is blocked exactly like the
  model would be. Rejection requires a written reason, which is stored as a
  negative example rather than discarded.
- **Hazards have an identity across runs.** Because the job runs weekly, the same
  hazard is matched between runs by member-set overlap and carries its own
  history — "seen in 3 runs · 12 → 19 → 31 reports". A pattern that is growing
  looks different from one that is stable, which is the entire reason to run this
  on a schedule instead of once.

## The Twist

**Every other demo shows what the agents can do. VIGIL's headline feature is what
they are structurally forbidden from doing.**

This is a safety-triage system, so the restraint is not a disclaimer in a README —
it is mechanical, and it is enforced by tests that fail if you remove it:

- **No LLM call can reach the clustering stage.** Pattern detection is embeddings
  plus seeded HDBSCAN, deterministic and reproducible. A test asserts that
  `pipeline/cluster.py` contains no model client at all.
- **The risk thresholds are frozen.** `config/frozen.yaml` is loaded read-only.
  No agent may retune the severity bar — including the self-improvement loop,
  which has no code path to that file. A safety system that quietly lowers its
  own alerting threshold to look calmer is an audit failure.
- **The citation gate is deterministic and runs last.** After the LLM Critic, a
  plain-Python pass removes every factual claim without a bracketed ACN. It runs
  even if the Critic call died, so the citation guarantee never depends on a
  model having cooperated. It validates *provenance*, not format: a
  correctly-formatted ACN that appears in no real report is stripped.
- **The holdout is locked.** `data/holdout/` is chmod 0444 and read by exactly
  one module. The self-improvement loop iterates on the validation split, and the
  holdout is consulted only at the promote/discard decision, after the candidate
  prompt text is already fixed — so nothing it returns can shape a revision. A
  guard failure short-circuits before it is read at all.
- **The gate has no exception for a human.** The reviewer can edit a draft before
  approving it — and the same deterministic citation gate runs against their
  edit. Add an uncited sentence and approval is refused, with the offending claim
  named. The privileged reviewer is the most plausible person to smuggle an
  unsourced claim into a safety document, so they are the last person who should
  get an exemption.
- **Evidence is checkable, not just cited.** A citation you cannot resolve is a
  claim of provenance rather than provenance. Every ACN in a brief opens the
  source report in one click, and artifact construction *fails* if a brief cites
  an ACN the run has no report for — so a citation the UI cannot resolve can
  never reach a reviewer in the first place.
- **The human gate is terminal.** There is no auto-approve flag, and adding one
  is listed as a prohibited change in the repo's own guardrails.

## How it mirrors the institution

VIGIL is deliberately shaped like the process it assists rather than like a
chatbot. ASRS screens every report through two independent expert analysts within
three working days, and escalates confirmed patterns as an Alert Message to
organizations in authority — it never takes operational action itself. VIGIL
mirrors that exact triage-then-alert workflow: independent parallel assessment,
a severity threshold that a human set and no agent can move, and a draft that
stops at a human's desk. (Sources: asrs.arc.nasa.gov; NTRS document
20210023200.)

## How we built it

- **Gemini 3.7 Flash** for every agent, via **Google ADK (Python)**. The Brief
  Writer is the only path allowed a larger model.
- **Cloud Run** for both the Streamlit UI service and the batch job, **Firestore**
  for state, **Cloud Scheduler** for the weekly unattended trigger, **Secret
  Manager** for the API key, with two least-privilege runtime service accounts.
- **Data:** NASA ASRS via the Hugging Face dataset `elihoole/asrs-aviation-reports`
  (47,723 reports, Apache-2.0 packaging; NASA ASRS as the underlying source).
- **The architecture diagram** attached to this submission is also published as an
  interactive version — https://vigil-architecture.vercel.app/diagram.html?theme=light —
  where the same live path can be panned, searched, and traced node by node.

Two architecture decisions worth naming, since the rubric asks about engineering
judgment rather than API calls:

**The expensive stage is behind the threshold gate.** The Analyst runs once per
*cluster*, not once per report — 23 calls on a 5,000-report slice, not 5,000. The
parallel Coordinator runs only for clusters that actually escalate. An early
design had a per-report extraction step; measuring it showed roughly 5,000 calls
to reproduce structured fields that NASA already codes in its own columns, so we
deleted it from the operational path and kept the Extractor as an offline
evaluation target instead.

**The parallel fan-out is plain Python, not a framework abstraction.** Precedent,
Risk, and Brief Writer run concurrently in a `ThreadPoolExecutor` with per-call
error isolation, because that makes 2-of-3 partial-failure tolerance
straightforward: one dead sub-agent yields a brief stamped `DEGRADED`, two dead
sub-agents fall back to a deterministic template, and the cluster is never
dropped. You can watch this rather than take our word for it:
`uv run python -m pipeline.run_batch --demo --live --fail-agent risk`.

## Self-improvement (offline, extractor only)

The loop scores the Extractor against NASA's own coded fields, hands an Evaluator
agent the ranked confusion list, and lets it rewrite the extractor instruction.
The revision is promoted only if it clears the reward-hacking guards *and*
improves on the locked holdout. Every outcome — promoted, discarded, or
guard-blocked — is written to `eval/runs/`, which is committed to the repo.

| Extractor prompt | dev macro-F1 | dev accuracy | holdout macro-F1 | holdout accuracy |
|---|---|---|---|---|
| majority-class + keyword baseline | 0.0515 | 0.395 | — | — |
| v1 (hand-written) | 0.0056 | 0.105 | 0.0081 | 0.080 |
| v2 (promoted by the loop) | **0.4099** | **0.600** | **0.4219** | **0.680** |

## What we measured, including what failed

Deterministic evals on the real 5,000-report slice (`make eval-offline`):

| Metric | Value | Reference |
|---|---|---|
| Critic catch rate (uncited + fabricated claims) | **1.000** | 400 seeded claims |
| Critic retention of correctly cited claims | **1.000** | control against a gate that just deletes everything |
| Cluster purity vs `Events_Anomaly` | 0.301 | majority-class baseline 0.219 |
| Adjusted Rand vs `Events_Anomaly` | 0.0018 | — |
| Noise fraction | 0.837 | exceeds our own declared 0.40 guard |

The citation gate is the component we most needed to be right, and it is: it
catches every planted uncited claim and every planted fabricated ACN, while
keeping every legitimate one.

**The clustering is the component we most wanted to be right, and it is not.**
Purity beats a single-blob baseline by only 0.08, the Adjusted Rand is
effectively zero, and 84% of reports end up unclustered — more than double the
`noise_fraction < 0.40` tripwire we ourselves predeclared. That guard was
implemented but only ever invoked on the extractor loop, so nothing had checked
it against the clustering stage it was written for until we ran this.

We did not tune the parameters to get under our own guard. Doing that hours
before a deadline, with no held-out check on the clustering stage, is the exact
behaviour the rest of this system exists to prevent, and we would rather submit a
measured failure than an unmeasured success.

What we did instead was change what happens to the reports the clustering fails
on. An 84% noise fraction is only a safety problem if noise means *discarded* —
so it no longer does. Every unclustered report is still checked against the
frozen severe-outcome vocabulary, and the 1,328 that match are routed to their
own analyst queue with their evidence attached. That does not make the clustering
better and we are not presenting it as though it does. It makes the clustering's
failure non-silent, which is a different and more honest claim: the metric stays
bad, and a report the algorithm could not place is now seen by a human instead of
falling through the floor.

## Challenges, findings and learnings

We are reporting the failures because they are the actual findings.

**1. Our hand-written extractor lost to a trivial baseline.** v1 scored macro-F1
0.0056 against majority-class-plus-keyword-rules at 0.0515 — roughly nine times
worse than a heuristic with no model in it. The cause was that v1 never told the
model the ASRS labels are a *closed vocabulary*, so it answered "Approach" where
the coded value is "Initial Approach". Without a baseline in the harness, v2's
0.41 would have read as an impressive result instead of what it was: the repair
of a regression. The holdout gain then came in slightly *larger* than the dev
gain (+0.414 vs +0.404), which is the opposite of overfitting.

**2. Our citation gate was checking the wrong thing.** It enforced that claims
*looked* cited — a regex for `[ACN 1234567]`. Reading a real brief showed the
Risk agent citing ACNs 1000001–1000005 for a cluster whose actual members were
1044401, 1461959, and others. Those IDs exist in none of the 38,655 reports; the
model had invented a plausible placeholder sequence and the gate kept it, because
a fabricated citation is *shaped* exactly like a real one. This is worse than an
uncited claim: an uncited claim gets stripped and disappears, while a fabricated
one survives carrying false authority to an investigator who might go pull that
report. The gate now validates against an allow-list of real ACNs and removes
invalid citations surgically.

**3. Two agents were spending tokens on output that was deleted every single
run.** `Precedent` and `Risk Assessment` came back empty in production while all
three sub-agents reported success. The gate required square-bracketed citations,
and only the Brief Writer's prompt actually specified that format — so 100% of
the Risk agent's output was being deleted by construction, silently, because
silent deletion is exactly what the gate is designed to do. Nothing errored. We
found it by reading the brief that landed in Firestore, not from any log.

**The through-line:** all three were failures of *verification*, not of model
capability, and none of them raised an exception. A system whose safety story is
"the agents are constrained" has to keep checking that the constraints are
measuring what they claim to measure. We also caught ourselves doing the
tempting version of this: a guard blocked a promotion, and on inspection the
guard's metric was wrong — it rewarded free-text sprawl and punished a correctly
constrained candidate. We fixed the metric so it is *stricter* against the hack
it was written for, and wrote the whole episode into `PROGRESS.md`, because
"changed a tripwire right after it blocked us" is precisely the move that needs
an audit trail rather than a quiet commit.

## What's next

Full-corpus precedent retrieval instead of same-batch matching; extending the
self-improvement loop beyond the extractor once its guard set has more history;
and a trend sparkline per cluster so an analyst can see a hazard accelerating
rather than inferring it from a score.

## Built with

Python 3.12 · Google ADK · google-genai · Gemini 3.7 Flash · Cloud Run ·
Firestore · Cloud Scheduler · Secret Manager · Streamlit · HDBSCAN ·
scikit-learn · pandas · pytest · ruff · uv

AI coding assistants were used during development (Claude Code and Codex), as
disclosed per the hackathon rules. Built entirely within the submission period.
