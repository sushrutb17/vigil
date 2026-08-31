# VIGIL Demo Video — 4:00 max (first 4 min is all judges may watch)

Judging targets: problem + value prop stated, architecture explained, **unedited live execution**, **visible Google Cloud proof**. Talking head optional; screen + voiceover is fine.

> **Before recording, read [`VIDEO_RUNBOOK.md`](VIDEO_RUNBOOK.md)** — pre-flight,
> the exact commands, recording mechanics, upload and verification live there.
> This file is what you *say and show*; that one is how you *operate*.

## Time budget (4:00 hard cap — judges may watch nothing past it)

| Segment | Window | Length |
|---|---|---|
| 1 · The friction | 0:00–0:28 | 28s |
| 2 · Architecture | 0:28–0:58 | 30s |
| 3 · Live execution + GCP proof | 0:58–2:23 | **85s — one unbroken take** |
| 4 · Failure tolerance | 2:23–2:43 | 20s |
| 5 · The numbers | 2:43–3:18 | 35s |
| 6 · Close | 3:18–3:52 | 34s |

**Record as six segments and stitch**, keeping segment 3 unbroken. A single
flawless 4-minute take is not worth chasing; the "unedited" requirement applies
to the live execution, not to the whole video.

Commands to paste are in [`VIDEO_RUNBOOK.md`](VIDEO_RUNBOOK.md) §2.

## Recording source of truth

Record the six plain-text files in
[`brag-output/narration/`](../brag-output/narration/README.md). They are split by
scene, paced to the rendered picture, and map directly to `seg1.wav` through
`seg6.wav`. This document owns the factual basis, capture choreography, and
supporting detail; do not combine its optional reference lines with the final
recording scripts.

## 0:00–0:28 — The friction

Final narration: [`scene-01-friction.txt`](../brag-output/narration/scene-01-friction.txt).

On screen: scrolling raw ASRS narratives (public NASA data) + caption: "NASA ASRS: 100,000+ reports/yr — each screened by two human analysts within 3 working days."

## 0:28–0:58 — Architecture (30 seconds, diagram on screen)

Final narration: [`scene-02-architecture.txt`](../brag-output/narration/scene-02-architecture.txt).

The spoken sequence follows the diagram exactly: deterministic ingest and
clustering → Google ADK analyst on Gemini 3.7 Flash → code-computed risk against
frozen thresholds → three-agent parallel fan-out → critic → deterministic
citation backstop → terminal human approval.

*(Accuracy note for the VO: do not say "ingest agents extract and dedupe" — those stages were cut, ingest is plain code. Do not say the analyst scores risk; it doesn't. Both were in the old script and both contradict the diagram on screen.)*

## 0:58–2:23 — Live execution (the unedited core — one continuous take)

This mirrors `brag-output/narration/scene-03-live.txt`. At 173 words it lands around 122 words
per minute, leaving room to switch views and let the proof sit on screen:

> "This job normally starts from a weekly Cloud Scheduler trigger. For the demo,
> I'm starting the same Cloud Run batch job by hand.
>
> The live run uses Gemini 3.7 Flash through Google ADK. Each agent call records
> its agent name, model, token count, and latency in Firestore.
>
> Here is the Cloud Run execution, and here are the Firestore agent-log documents
> written by that run. This is the weekly Scheduler configuration that normally
> starts it unattended.
>
> That job just ran the full agent graph in the cloud on a small fixture — that's
> the live proof. The dashboard serves a committed snapshot of a real
> five-thousand-report run, so it loads instantly for you without a model call per
> page view, and without depending on my API quota surviving the judging window.
> Same pipeline, same code, bigger slice.
>
> Now the deployed dashboard. This cluster is new this run. Every brief claim
> carries a source ACN, and an uncited edit is blocked. Approval is the only exit:
> drafts, never decisions. The approved Markdown packet downloads here."

Keep this as one uninterrupted screen recording. Switching terminal/browser tabs
inside the take is fine; an editorial cut is not.

| Target window | What must remain visibly legible |
|---|---|
| 0:00–0:10 | Full `gcloud run jobs execute vigil-batch ... --wait` command, project, and region |
| 0:10–0:24 | Cloud Run execution/log stream; successful agent activity and model name where available |
| 0:24–0:36 | Firestore `agent_log` document showing `agent`, `model`, `tokens`, and `latency_ms` |
| 0:36–0:47 | Cloud Run job/service console with the correct project visible |
| 0:47–0:55 | Firestore collections/documents written by the run |
| 0:55–1:00 | Cloud Scheduler trigger configuration, held for at least three settled seconds |
| 1:00–1:16 | Hosted `.run.app` URL, 5,000-report summary, and `NEW THIS RUN` cluster |
| 1:16–1:25 | ACN-cited brief, blocked uncited edit, Approve, and Markdown download |

The video must literally show **Google ADK** and **Gemini 3.7 Flash**, not only
generic "agent" or "model" labels. Scene 2 establishes both visibly; this live
segment supplies the execution receipts.

## 2:23–2:43 — Failure tolerance (20s)

Terminal, one command, ~11s of runtime:

```bash
uv run python -m pipeline.run_batch --demo --live --fail-agent risk
```

It prints nothing between the fault-injection banner and the final JSON —
**silent, not hung.** On screen, point at three things in the output:

- the stderr banner: `!! FAULT INJECTION ACTIVE: risk will raise…`
- `DEGRADED` in the brief
- `## Risk Assessment` carrying its **cited deterministic fallback**, while
  `## Recommended Brief` is still model-authored

This mirrors `brag-output/narration/scene-04-failure.txt`. The shortened narration is 41 words (about 123 words per minute), leaving
the output readable instead of forcing the old 63-word take to roughly 189 words
per minute:

> "I make the Risk agent fail on purpose. The agents keep working, so VIGIL
> produces a brief. It marks the result DEGRADED and fills the Risk section with
> a cited backup based on fixed rules. An API failure follows this path."

## 2:43–3:18 — The numbers (35s)

Final narration: [`scene-05-results.txt`](../brag-output/narration/scene-05-results.txt).
It covers the citation gate and the failed clustering guard—the two results that
the rendered scene actually shows. The material below is supporting evidence and
cut rationale, not additional narration to record.

**This section holds three results and room for roughly two.** Priority, highest
value first: (1) the Critic gate, (2) the noise-fraction failure, (3) the
extractor improvement table. **Cut (3) first** — it is the longest to explain and
it is already in the README and the Devpost description, where a judge will read
it without a clock running. Cut (2) only if you are badly over; it is the
credibility beat and the cheapest way to earn trust on every other number.

**Only say numbers that exist.** Everything below is in `eval/runs/*.json`, which
is committed, so a judge can check it.

**Updated 2026-08-30 — cluster purity and the Critic catch rate have since been
run** (`make eval-offline` → `eval/runs/20260829T192117Z-offline.json`), so the
old instruction to keep them off screen no longer applies. One is the strongest
number in the project and one is the weakest; show both, in that order.

**Brief factual coverage vs expert synopses was still never run.** Do not put a
coverage number on screen.

Show the Critic gate result first — it is the one predeclared metric that came
back clean, and it is the numeric proof of the Twist:

| Critic gate (400 seeded claims, 200 trials) | Result |
|---|---|
| Uncited / fabricated-ACN catch rate | **1.000** |
| Legitimate-claim retention | **1.000** |

Retention is the load-bearing half of that pair — a gate that simply deleted
every claim would also score a perfect catch rate. Say so out loud; it is the
difference between a measurement and a number.

Then the clustering result, which is bad and is being shown anyway:

| Clustering vs `Events_Anomaly` (4,998 reports) | Result |
|---|---|
| Purity | 0.301 (majority-class baseline 0.219) |
| Adjusted Rand | 0.0018 |
| Noise fraction | **0.837 — exceeds our own declared 0.40 guard** |

> "We predeclared a tripwire at 0.40 noise. We hit 0.837 and we are showing you
> the failure instead of retuning the parameters until it passed. The guard is
> in `eval/guards.py` and the number is in a committed JSON file — you can check
> both."

Then show the extractor improvement table (README → Measured results):

| prompt | dev macro-F1 | holdout macro-F1 |
|---|---|---|
| majority-class + keyword baseline | 0.0515 | — |
| v1 hand-written | 0.0056 | 0.0081 |
| v2 promoted by the loop | 0.4099 | 0.4219 |

The line to say, which is both true and better than the one it replaces:

> "Our hand-written extractor was losing to a majority-class baseline — nine
> times worse than a heuristic with no model in it. The loop found out why: we'd
> never told the model the labels were a closed vocabulary. And the gain held on
> a holdout the loop is not allowed to read."

**Do NOT say "we caught our own agent cheating."** The earlier plan assumed a
revision would game ROUGE and get caught by a guard. It never happened. The one
guard that did fire was itself buggy — it rewarded free-text sprawl — and we
fixed the metric. Claiming the reward-hack story on camera would be a fabricated
result in a submission whose whole thesis is verifiable restraint.

**The honest substitute, if you want a "we caught ourselves" beat** — and it is a
stronger one, because it is about the safety mechanism rather than the model:

> "Our citation gate was checking that claims *looked* cited. It wasn't checking
> they were *sourced*. A model invented ACN 1000001 through 1000005 — reports
> that exist in none of the 38,655 — and the gate kept them, because a fabricated
> citation is shaped exactly like a real one. An uncited claim gets stripped and
> disappears. A fabricated one survives carrying false authority. We found it by
> reading the brief, not from any log. The gate now validates provenance."

## 3:18–3:52 — Close

Final narration: [`scene-06-close.txt`](../brag-output/narration/scene-06-close.txt).
Finish the voice by roughly 3:49 so the VIGIL end card holds in silence.

## Recording notes
- 1080p, terminal font ≥16pt, dark theme; phone-mounted or OBS screen capture; script the voiceover, don't improvise
- Do the live section as one take; retakes fine, edits within the take not fine
- English; public YouTube (not unlisted); link goes in Devpost form
