# Hyperframes Composition Brief: VIGIL

## Objective

Create the **mandatory Devpost submission video** for VIGIL — All Things Agentic
Hackathon, Taskmaster category. This is a compliance-scored deliverable, not a
promo. Read `brag-plan.md` first; its header documents every deliberate deviation
from `/brag` defaults and the reason for each.

## Output

- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/vigil-demo.mp4`
- Format: landscape — **1920x1080**
- Duration: **232s (3:52)** against a **4:00 hard cap**. Not 4:01. The 8s of
  headroom is deliberate; do not spend it.

## Source Material

- Project root: `/Users/sush/Google All things Agent`
- Primary files read: `brag-output/narration/*.txt` (recording scripts),
  `docs/DEMO_SCRIPT.md` (factual basis + shot list — **the creative contract**),
  `docs/VIDEO_RUNBOOK.md` (capture procedure),
  `docs/BONUS_POSTS.md` (verified phrasings), `docs/architecture.png` (visual
  identity), `artifacts/demo_run.json` + `eval/runs/*.json` (every number)
- Product name: **VIGIL**
- Tagline: *Public ASRS safety-signal triage · drafts only · human approval is terminal*
- Strongest claim: *Every other demo shows what the agents can do; VIGIL's
  headline feature is what they're structurally forbidden from doing.*
- Key visual moments to recreate: the architecture graph assembling by stage; the
  gold `total ≥ 0.60?` threshold diamond; the red terminal `HUMAN APPROVAL` node
- Copy that must appear verbatim:
  - `A safety report that matters looks exactly like one that doesn't.`
  - `NASA ASRS — 100,000+ reports/yr · each screened by two human analysts within 3 working days`
  - `no LLM call reaches this code`
  - `config/frozen.yaml — thresholds loaded read-only`
  - `HUMAN APPROVAL — terminal`
  - `Google ADK Analyst`
  - `Gemini 3.7 Flash`
  - `https://vigil-ui-715230861973.us-central1.run.app`
  - `https://github.com/sushrutb17/vigil`

### Numbers — copy exactly, verify against the cited file, never round

| Value | Source |
|---|---|
| 5,000 reports triaged · 23 clusters · 4 escalated · 1,328 severe singletons | `artifacts/demo_run.json` |
| Critic gate: catch rate **1.000**, legitimate-claim retention **1.000** (400 seeded claims, 200 trials) | `eval/runs/20260829T192117Z-offline.json` |
| Clustering vs `Events_Anomaly` (4,998 reports): purity **0.301** (baseline 0.219), Adjusted Rand **0.0018**, noise fraction **0.837** vs declared **0.40** guard | same |
| Extractor: baseline **0.0515** dev · v1 **0.0056** dev / **0.0081** holdout · v2 **0.4099** dev / **0.4219** holdout | `eval/runs/20260829T185719Z-extractor.json` |
| Risk score: `0.5·severity + 0.3·frequency + 0.2·trend`, escalate at `≥ 0.60` | `config/frozen.yaml` |
| Corpus 47,723 reports — train 38,655 · val 4,295 · test LOCKED | `docs/DATA.md` |

**Do not put a brief-factual-coverage number on screen — it was never run.**
**Do not claim "we caught our own agent cheating"** — that never happened and
`eval/runs/` is committed, so a judge can check. `DEMO_SCRIPT.md` § 2:43–3:18
carries the honest substitute (the fabricated-ACN story) if a "we caught
ourselves" beat is wanted.

## Creative Direction

- **Tone preset:** `polished`
- **Creative direction:** an incident-review briefing that is unusually honest
  about its own instrumentation
- **Interpretation:** Confidence through restraint. Long settled holds, no hype
  verbs, no motion that outruns the reading floor. Pace comes from cuts between
  segments, never from flashing text.
- **Angle:** see `brag-plan.md` § The angle
- **Hook:** `A safety report that matters looks exactly like one that doesn't.` —
  held on near-black over dimmed scrolling ASRS narrative
- **Outro:** the thesis line, five prohibitions, stack, URLs, wordmark, silence
- **Avoid:**
  - Generic SaaS language
  - Abstract filler visuals
  - **Count-up number animations** — a ticking metric reads as a sales gesture in
    a safety context
  - **Any treatment that makes the failure numbers smaller, dimmer, or faster than
    the clean ones.** The video argues that publishing bad results is the feature;
    de-emphasising them on screen contradicts its own thesis.
  - Unrelated visual redesign

## Visual Identity

Semantic palette lifted from `docs/architecture.png` — colour encodes *what each
stage is permitted to do*, so it must be applied consistently, not decoratively.
(`ui/streamlit_app.py` has no custom CSS; stock Streamlit theming is the weaker
source and is not used.)

- Background: `#0d1117`
- Text: `#e6edf3`
- Deterministic / no-LLM: `#2ea043` on `#0b2a15`
- LLM agent: `#1f6feb` on `#0d1f3d`
- Decision gate: `#d4a017`
- Frozen config / human-terminal: `#f85149`
- Firestore: `#8957e5`
- Scheduler / unattended: `#00b4b4`
- Display font: grotesque, tight optical sizing at large scale (`-apple-system, Inter, sans-serif`)
- Body + **all numeric data**: monospace (`ui-monospace, SFMono-Regular, Menlo`).
  Every number, ACN, metric and threshold renders mono so figures read as evidence.
- Visual references: the architecture graph, the threshold diamond, the terminal
  approval node, the deployed Streamlit hazard queue

## Storyboard

`brag-plan.md`'s storyboard is the creative contract. Scene summary:

1. **The friction** — 28s — hook line + ASRS scale caption over dimmed scrolling narratives
2. **Architecture** — 30s — graph assembles in ~7 stage reveals, colour carries permission semantics
3. **Live execution + GCP** — 85s — **real capture, unbroken, uncut**
4. **Failure tolerance** — 20s — **real capture** + three sequential overlay callouts
5. **The numbers** — 35s — Critic gate 1.000/1.000, then the 0.837 tripwire failure at equal weight
6. **Close** — 34s — thesis, five prohibitions, stack, URLs, wordmark, silence

## Real footage — non-negotiable handling

Scenes 3 and 4 are **screen capture embedded as framework-owned media and played
untouched**, the same mechanism `embedded-captions` / `talking-head-recut` use.

This overrides `/brag`'s normal method (`step-1-inspect.md`: *"Reads the project
code directly — no live URL or screenshots needed"*, recreate UI in HTML). That
method is correct for a 20s teaser and **disqualifying here**: Stage One is
pass/fail on *unedited live execution*, so the pixels must be genuine.

Constraints on these two scenes:
- **No cuts, no speed ramps, no transitions inside scene 3.** Retakes are fine;
  edits within the take are not.
- **No SFX over either scene.**
- Scene 4 may carry overlay callouts; only one appears at a time in the reserved
  right-side lane, and none may obscure terminal text.
- Scene 3 must **visibly** contain all four Stage One proofs:
  - [ ] Gemini 3.7 Flash via the Gemini API (job output / `agent_log`)
  - [ ] Google ADK as the agent framework
  - [ ] Cloud Run **and** Firestore (service, job, documents appearing)
  - [ ] **~3s on the Cloud Scheduler trigger config** — the background-workflow
        evidence the Taskmaster category is scored on, and the easiest to forget
- Scene 2 must literally render `Google ADK Analyst` and `Gemini 3.7 Flash`; the
  live `agent_log` view in scene 3 then supplies the model execution receipt.

## Narration

The recording source is **the six `.txt` files in `brag-output/narration/`,
verbatim**. `docs/DEMO_SCRIPT.md` owns the factual basis and capture choreography.
Do not paraphrase, tighten, or "improve" while recording. In particular, scene 2
must not say ingest agents extract and dedupe, and must not say the analyst
scores risk.

The formerly underspecified live segment is now locked: scene 3 has a 173-word
script (~122 wpm) plus an 85-second continuous-take shot map, and scene 4 has a
41-word script (~123 wpm). These replace the old scene-3 bullet-only narration
and the rushed 63-word scene-4 take.

The bridge line in § 0:58–2:23 (job runs the 6-report fixture; dashboard serves the
committed 5,000-report snapshot) is **mandatory** — without it the segment reads as
incoherent to a judge watching 6 reports go in and 23 clusters come out.

### Decision: human voiceover, recorded by the entrant. No TTS.

**Settled 2026-08-30.** The hackathon Q&A advised against AI voiceover, which
outranks the determinism argument for TTS. Do not generate narration with
`npx hyperframes tts`, and do not add a synthetic track as a placeholder that
could survive into the render.

Production order — capture first, voice later:

1. **Screen capture is recorded silent.** Narration is laid over it in the
   composition, so a fluffed line is no longer a cause of re-shooting the
   unbroken 85s take. This is the main reason capture goes first.
2. **VO is recorded as six separate files**, one per segment, named
   `assets/vo/seg1.wav` … `seg6.wav`. Not one continuous take: a fluffed line
   then costs one segment, not four minutes. This also matches the existing
   "record six segments and stitch" guidance in `docs/VIDEO_RUNBOOK.md` § 3.

**The two halves flex in opposite directions — this drives the composition:**

- **Scenes 1, 2, 5, 6 (composed):** visuals flex to the VO. Do **not** hardcode
  scene lengths. Measure each `segN.wav` after recording and drive
  `data-duration` from it; the beat *proportions* in `brag-plan.md` hold, the
  absolute timings do not.
- **Scenes 3, 4 (real capture):** footage length is fixed and uncuttable, so the
  **VO must fit the footage**. Report each captured clip's exact duration back to
  the user before they record segments 3 and 4, so they can pace to it.

Total must still land at **≤4:00** once real audio lengths are known. The 8s of
headroom in the 3:52 target exists to absorb VO overrun — if segments come back
long, trim scene 5 per `DEMO_SCRIPT.md`'s stated cut order (extractor table
first), not the close.

## Audio

- **Audio role:** narration-led with **intentional silence** where music would sit
- **Audio arc:** narration throughout; sparse structural placement in scenes 2 and
  6 only; scenes 3, 4 and every metric left untouched
- **Music:** **none.** Bundled `/brag` tracks are 164s max against a 232s runtime
  and their cue presets only analyse the first 25s; a bed under four minutes of
  continuous technical narration also competes with numbers a judge must hear.
  This is `/brag`'s documented intentionally-silent path, not a missing asset.
- **Music cue guidance:** n/a — no music, therefore no beat-lock and no beat-grid.
- **Audio-reactive treatment:** none (nothing to react to).
- **Audio-coupled moments:**
  - Scene 2 — one soft low placement per stage reveal, ~5 of 7 (not every reveal),
    plus one distinct latch on the threshold diamond
  - Scene 6 — one soft placement per prohibition; nothing on the URLs
- **SFX selection guidance:** sparse and structural. Prefer low high-frequency-risk
  files per `sfx-analysis.md`. Nothing percussive, nothing triumphant.
- **Prohibited:** any cue over scenes 3–4; any cue on any metric in scene 5; risers,
  whooshes, impacts. If a cue would make a result feel like a win, cut it.

## Hyperframes Instructions

Load `hyperframes-core` (composition contract + `data-*` timing),
`hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats),
`hyperframes-keyframes` (seek-safe keyframes), `hyperframes-cli` (check/render).
`/brag` is its own workflow — do not enter the `hyperframes` entry-point intent
interview and do not route into its generic promo / launch-video workflow. Prefer
native Hyperframes conventions over anything in `/brag`.

Requirements:
- Total runtime **232s (3:52)**, hard-capped at 4:00.
- Scenes 3 and 4 play real captured footage untouched (see above).
- Every text element holds its reading floor: short label ~0.8s settled, sentence
  ~0.3s/word with a ~1.2s minimum. Sequential reveals hold each item to that floor.
- Keep all text readable in the final render; fix every `check` layout overflow.
- WCAG contrast gates as an error — apply the suggested compliant colour or adjust
  within the semantic palette family. Do not reach for `check --no-contrast`; it
  disables the entire WCAG pass, and this palette is dark-on-dark in places where
  that matters.
- Numbers never animate as count-ups.
- Run `npx hyperframes check` before render — the single gate.

## Blocking dependency

Scenes 3 and 4 need the screen capture, which does not exist yet. Compose and
validate scenes 1, 2, 5 and 6 first; leave scenes 3 and 4 as correctly-timed
placeholders that swap to real media on capture. Capture procedure and pre-flight
are in `docs/VIDEO_RUNBOOK.md`.
