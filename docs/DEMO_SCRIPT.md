# VIGIL Demo Video — 4:00 max (first 4 min is all judges may watch)

Judging targets: problem + value prop stated, architecture explained, **unedited live execution**, **visible Google Cloud proof**. Talking head optional; screen + voiceover is fine.

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

## 2:45–3:25 — The numbers (our unfair advantage)

**Only say numbers that exist.** Everything below is in `eval/runs/*.json`, which
is committed, so a judge can check it. Cluster purity vs `Events_Anomaly`, brief
factual coverage vs expert synopses, and the Critic catch rate were **never run**
— they are still ⬜ in PHASES.md. Do not put them on screen.

Show the extractor improvement table (README → Measured results):

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
