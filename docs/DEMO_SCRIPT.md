# VIGIL Demo Video — 4:00 max (first 4 min is all judges may watch)

Judging targets: problem + value prop stated, architecture explained, **unedited live execution**, **visible Google Cloud proof**. Talking head optional; screen + voiceover is fine.

## Pre-flight — do all five before the first take

1. **Warm the hosted URL.** Open `https://vigil-ui-715230861973.us-central1.run.app`
   once and let it finish. At `--min-instances 0` a cold start leaves the
   right-hand draft column blank for ~10s, which reads on camera as a broken app.
2. **Export the key in the recording shell**: `set -a; source .env; set +a`.
   A fresh terminal drops it and `--live` then fails.
3. **Clear the screen**: close unrelated tabs, hide the bookmarks bar, clear the
   desktop, turn on Do Not Disturb. No third-party logos/trademarks anywhere —
   this is a compliance item, not tidiness.
4. **Terminal**: ≥16pt font, dark theme, cleared scrollback.
5. **Dry-run the two live commands once** (below) so you know their duration and
   nothing surprises you mid-take.

## Time budget (4:00 hard cap — judges may watch nothing past it)

| Segment | Window | Length |
|---|---|---|
| 1 · The friction (BYOF) | 0:00–0:30 | 30s |
| 2 · Architecture | 0:30–1:00 | 30s |
| 3 · Live execution + GCP proof | 1:00–2:25 | **85s — one unbroken take** |
| 4 · Failure tolerance | 2:25–2:45 | 20s |
| 5 · The numbers | 2:45–3:20 | 35s |
| 6 · Close | 3:20–4:00 | 40s |

**Record as six segments and stitch**, keeping segment 3 unbroken. A single
flawless 4-minute take is not worth chasing; the "unedited" requirement applies
to the live execution, not to the whole video.

**The two live commands, ready to paste:**

```bash
# Segment 3 — the Cloud Run job (exercises Gemini + ADK + Cloud Run + Firestore)
gcloud run jobs execute vigil-batch --project vigil-hackathon-506218 \
  --region us-central1 --wait

# Segment 4 — failure tolerance (~11s, silent until it finishes; not hung)
set -a; source .env; set +a
uv run python -m pipeline.run_batch --demo --live --fail-agent risk
```

## 0:00–0:35 — The friction (BYOF)
"I manage operations for an airline flight-ops department. Safety reports arrive faster than analysts can read them. Each one looks minor and gets filed. The pattern across forty of them — same component, same aircraft type, same flight phase — surfaces months later in a quarterly review. That gap is a risk window. I built VIGIL to close it."
On screen: scrolling raw ASRS narratives (public NASA data) + caption: "NASA ASRS: 100,000+ reports/yr — each screened by two human analysts within 3 working days." Optional half-sentence of VO: "NASA's own program pays two analysts to read every single one."

## 0:35–1:05 — Architecture (30 seconds, diagram on screen)
Deterministic ingest reads NASA's own coded fields → deterministic clustering, **no LLM in that stage at all** → an analyst agent names the hazard and writes the statement, while *code* — not the agent — computes the risk score → above a frozen threshold, a coordinator fans out three agents in parallel → a critic strips uncited claims, and then a deterministic gate runs again regardless → **a human approves. The system never actions anything itself.**

*(Accuracy note for the VO: do not say "ingest agents extract and dedupe" — those stages were cut, ingest is plain code. Do not say the analyst scores risk; it doesn't. Both were in the old script and both contradict the diagram on screen.)*

## 1:05–2:45 — Live execution (the unedited core — one continuous take)
1. Trigger Cloud Run batch job on "this quarter's intake" (terminal visible) — mention it normally fires weekly via Cloud Scheduler; today we trigger it by hand for the camera
2. Logs stream: extraction counts, cluster formation, one cluster crosses threshold
3. **Cut to GCP console: Cloud Run dashboard + Firestore documents appearing** (mandatory proof) + ~3s on the Cloud Scheduler trigger config (background-workflow proof)
4. Streamlit (the .run.app URL visible in the address bar): hazard cluster named, e.g. uncommanded-engine-shutdown pattern on a regional jet type during landing rollout, wearing its **NEW THIS RUN** badge
5. Open the draft brief: every claim carries an ACN citation; show the critic having stripped an uncited claim
6. Click **Approve** — the brief downloads as a Markdown packet — and say the line: "approval is the only exit; drafts, never decisions"

**Say this bridge line between steps 3 and 4, or the segment looks incoherent.**
The job you just triggered processes the 6-report demo fixture; the UI you are
about to open serves a committed snapshot of a real 5,000-report run. A judge
watching 6 reports go in and 23 clusters come out will notice. The reason is
good, so say it:

> "That job just ran the full agent graph in the cloud on a small fixture —
> that's the live proof. The dashboard serves a committed snapshot of a real
> five-thousand-report run, so it loads instantly for you without a model call
> per page view, and without depending on my API quota surviving the judging
> window. Same pipeline, same code, bigger slice."

## 2:25–2:45 — Failure tolerance (20s)

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

> "I killed one of the three parallel agents on purpose. Its section fell back
> to a cited deterministic line, the other two were untouched, and the brief is
> stamped DEGRADED so nobody mistakes it for a clean run. The failure is
> injected at the real call site, so it travels the same path a genuine API
> outage would."

## 2:45–3:20 — The numbers (35s — more content than time; cut in this order)

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

## 3:25–4:00 — Close
"The twist isn't what these agents can do — it's what they're structurally forbidden from doing. Frozen risk thresholds — a safety system must not quietly retune its own severity bar. Human approval on every output. Built solo in 11 days on Gemini, ADK, Cloud Run, and Firestore. The pattern generalizes to every safety-critical intake queue: rail, medical devices, energy. VIGIL turns a report backlog into a ranked hazard list with an evidence-cited brief — hours, not months."

## Recording notes
- 1080p, terminal font ≥16pt, dark theme; phone-mounted or OBS screen capture; script the voiceover, don't improvise
- Do the live section as one take; retakes fine, edits within the take not fine
- English; public YouTube (not unlisted); link goes in Devpost form
