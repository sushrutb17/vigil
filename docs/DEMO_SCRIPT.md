# VIGIL Demo Video — 4:00 max (first 4 min is all judges may watch)

Judging targets: problem + value prop stated, architecture explained, **unedited live execution**, **visible Google Cloud proof**. Talking head optional; screen + voiceover is fine.

## 0:00–0:35 — The friction (BYOF)
"I manage operations for an airline flight-ops department. Safety reports arrive faster than analysts can read them. Each one looks minor and gets filed. The pattern across forty of them — same component, same aircraft type, same flight phase — surfaces months later in a quarterly review. That gap is a risk window. I built VIGIL to close it."
On screen: scrolling raw ASRS narratives (public NASA data).

## 0:35–1:05 — Architecture (30 seconds, diagram on screen)
Ingest agents extract and dedupe → deterministic clustering (deliberately not an LLM) → an analyst agent names hazards and scores risk → above a frozen threshold, a coordinator fans out parallel agents → a critic strips any claim that doesn't cite a source report → **a human approves. The system never actions anything itself.**

## 1:05–2:45 — Live execution (the unedited core — one continuous take)
1. Trigger Cloud Run batch job on "this quarter's intake" (terminal visible)
2. Logs stream: extraction counts, cluster formation, one cluster crosses threshold
3. **Cut to GCP console: Cloud Run dashboard + Firestore documents appearing** (mandatory proof)
4. Streamlit (the .run.app URL visible in the address bar): hazard cluster named, e.g. uncommanded-engine-shutdown pattern on a regional jet type during landing rollout
5. Open the draft brief: every claim carries an ACN citation; show the critic having stripped an uncited claim
6. Click **Approve** — and say the line: "approval is the only exit; drafts, never decisions"

## 2:45–3:25 — The numbers (our unfair advantage)
Metrics table + improvement curve from eval/runs:
- extraction accuracy vs NASA's coded fields (delta over baseline)
- cluster purity vs expert anomaly labels
- brief factual coverage vs expert-written synopses
- the self-improvement curve — **including the iteration where the agent gamed ROUGE and the guard metric caught it.** "We caught our own agent cheating; the guard rejected the change."

## 3:25–4:00 — Close
"Frozen risk thresholds — a safety system must not quietly retune its own severity bar. Human approval on every output. Built solo in 11 days on Gemini, ADK, Cloud Run, and Firestore. The pattern generalizes to every safety-critical intake queue: rail, medical devices, energy. VIGIL turns a report backlog into a ranked hazard list with an evidence-cited brief — hours, not months."

## Recording notes
- 1080p, terminal font ≥16pt, dark theme; phone-mounted or OBS screen capture; script the voiceover, don't improvise
- Do the live section as one take; retakes fine, edits within the take not fine
- English; public YouTube (not unlisted); link goes in Devpost form
