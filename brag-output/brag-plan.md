# Brag Plan: VIGIL

> **Deliberate deviation from `/brag` defaults — read this before "fixing" anything below.**
>
> `/brag`'s creative law is *"Short. 15–25 seconds. Not one second more without a
> reason."* We have a reason, and it is external: this composition is the
> **mandatory Devpost submission video** for the All Things Agentic Hackathon,
> which is judged at **≤4:00** against a fixed rubric. The narrative script is
> already written, fact-checked and corrected (`docs/DEMO_SCRIPT.md`), and one
> prior session had to remove claims from it that had drifted false — so the
> angle is **not** to be re-derived from a cold repo scan.
>
> What we keep from `/brag`: the inspect→plan→brief→Hyperframes→deliver pipeline,
> the 9-question rubric, the tone system, the Hook→Reveal→Highlights→Punchline
> shape, the reading-time floors, and the delivery/poster discipline.
>
> What we override, and why:
>
> | `/brag` default | Here | Why |
> |---|---|---|
> | 15–25s total | **232s (3:52)** | Hackathon rubric; 8s of headroom under the 4:00 cap |
> | 3–4 scenes (`polished`) | **6 scenes** | Fixed segment map in `docs/DEMO_SCRIPT.md` |
> | Recreate UI in HTML, "no live URL or screenshots needed" | **Scenes 3 & 4 are real screen capture, embedded untouched** | Stage One is pass/fail on *unedited live execution*. A recreation would be disqualifying, not merely weaker. |
> | Music bed on by default | **No music** | Bundled tracks max out at 164s (need 232s) and their cue analysis only covers the first 25s. Continuous narration also makes a bed a liability. `/brag` permits intentional silence. |
> | Auto-inferred angle from repo scan | **Angle fixed by `docs/DEMO_SCRIPT.md` + `docs/BONUS_POSTS.md`** | Those are fact-checked against committed JSON; a fresh inference risks reintroducing a corrected-false claim |
>
> Everything else follows `/brag` as written.

## What is this app?

VIGIL is a multi-agent system that triages NASA ASRS aviation safety reports —
clustering them into emerging hazard patterns, scoring each against a frozen risk
policy, and fanning out parallel agents to draft a source-cited investigator brief
for the severe ones. A human approves everything; it never sends, files, or actions.

## The angle

**Every other demo shows what the agents can do. VIGIL's headline feature is what
they are structurally forbidden from doing.**

Restraint as a mechanism, not a disclaimer: no LLM call can reach the clustering
stage, the risk thresholds live in a file no agent can write to, the holdout is
chmod 0444, the citation gate has no exception even for the human reviewer, and
the human gate is terminal with no auto-approve flag.

The corollary the video commits to on screen: **we publish the numbers where it
underperforms.** A safety tool that only shows its good metrics is not one you
should trust — so a failed tripwire (0.837 noise fraction against our own declared
0.40) goes on camera next to the clean one.

## Hook (first 3 seconds)

Not a logo, not a product name. The problem stated as a fact the viewer can feel:

> **A safety report that matters looks exactly like one that doesn't.**

Held on a near-black frame in large light type while raw ASRS narrative text
scrolls behind it, dimmed. This is the strongest line from `BONUS_POSTS.md` Post 2
and it earns the next 30 seconds without claiming anything about the product yet.

## Key moments (the middle)

1. **The architecture diagram assembling by stage**, colour-coded by *what is
   allowed to think* — green deterministic, blue LLM, gold decision gate, red
   frozen/terminal. The restraint thesis told in colour before it is told in words.
2. **The real Cloud Run job executing** — unedited terminal, logs streaming,
   a cluster crossing threshold, then the GCP console showing Cloud Run, Firestore
   documents appearing, and the Cloud Scheduler trigger config.
3. **A named agent killed on purpose**, its section falling back to a cited
   deterministic line while the brief stamps itself `DEGRADED`.
4. **The two numbers side by side** — the gate that scored 1.000/1.000, and the
   tripwire we blew through at 0.837 and published anyway.

## Outro / punchline

> "The twist isn't what these agents can do — it's what they're structurally
> forbidden from doing."

Then the five prohibitions as a settling list, the stack line, and the two URLs.
`polished` outro discipline: product name, tagline, silence.

## User flow worth showing

Entry → key action → result, and **all three are captured live rather than
recreated** (this is the Stage One proof, so it cannot be animated):

1. **Entry** — `gcloud run jobs execute vigil-batch` in a real terminal; mention it
   normally fires weekly via Cloud Scheduler, triggered by hand for the camera.
2. **Key action** — logs stream: extraction counts, cluster formation, one cluster
   crossing the frozen threshold. Cut to GCP console: Cloud Run dashboard,
   Firestore documents appearing, ~3s on the Cloud Scheduler config.
3. **Result** — the deployed Streamlit dashboard: the named hazard cluster wearing
   its **NEW THIS RUN** badge, the draft brief with every claim carrying an ACN
   citation, the critic having stripped an uncited claim, and **Approve** clicked —
   the brief downloads as a Markdown packet.

## Tone

- **Preset:** `polished`
- **Creative direction:** *an incident-review briefing that is unusually honest
  about its own instrumentation*
- **Interpretation:** Confidence through restraint. No hype verbs, no exclamation,
  no motion that outruns the reading floor. Long settled holds; the pace comes
  from cuts between segments, never from flashing text. The failure numbers get
  the *same* visual weight as the clean ones — designing them as smaller or dimmer
  would contradict the thesis the video is arguing. `polished`'s "the product
  speaks for itself" voice, applied to a product whose claim is that it restrains
  itself.

## Format: landscape — 1920x1080
## Duration: 232s (3:52), against a 4:00 hard cap

## Visual identity (from the project)

Extracted from `docs/architecture.png`, which is the project's de-facto design
system — the colours are **semantic**, encoding what each stage is permitted to do.
(`ui/streamlit_app.py` carries no custom CSS; it runs stock Streamlit theming, so
the diagram is the stronger and more specific source.)

- **Background:** `#0d1117` (near-black)
- **Text:** `#e6edf3` (off-white)
- **Deterministic / no-LLM:** `#2ea043` green on `#0b2a15` fill
- **LLM agent:** `#1f6feb` blue on `#0d1f3d` fill
- **Decision gate:** `#d4a017` gold
- **Frozen config / human-terminal:** `#f85149` red
- **Firestore:** `#8957e5` purple
- **Scheduler / unattended:** `#00b4b4` teal
- **Display font:** a grotesque with tight optical sizing at large scale
  (Inter Tight / Söhne family feel; system fallback `-apple-system, Inter, sans-serif`)
- **Body + all data:** monospace (`ui-monospace, SFMono-Regular, Menlo`) — every
  number, ACN, metric and threshold renders mono so figures read as *evidence*
  rather than as marketing copy. This is the single strongest typographic decision
  in the piece.
- **Strongest visual element:** the frozen-threshold diamond (`total ≥ 0.60?`) and
  the red `HUMAN APPROVAL — terminal` node. Those two shapes *are* the thesis.

## Share copy (draft)

> VIGIL triages 5,000 NASA aviation safety reports into 23 named hazard patterns,
> 4 escalated with source-cited investigator briefs, and 1,328 severe reports that
> matched nothing and are surfaced rather than dropped. Every claim cites the
> report it came from. It cannot act — a human approves everything. Built solo in
> 11 days on Gemini, ADK, Cloud Run and Firestore, with the metrics where it
> underperforms published alongside the ones where it doesn't.

## Audio direction

- **Role:** narration-led, **intentional silence** where music would normally sit.
- **Music:** none. Justified above — bundled tracks are 164s max against a 232s
  runtime, cue presets only analyse the first 25s, and a bed under four minutes of
  continuous technical narration competes with the numbers a judge must hear.
  This is `/brag`'s documented "intentionally silent" path, not a missing asset.
- **Narration:** the voiceover script is `docs/DEMO_SCRIPT.md` verbatim — it is
  fact-checked and must not be paraphrased during composition. **Human voice,
  recorded by the entrant — no TTS** (settled 2026-08-30; the hackathon Q&A
  advised against AI voiceover). Six files, one per segment. Screen capture is
  recorded silent and narration is laid over it, so a fluffed line never costs a
  re-shoot of the unbroken 85s take. Scenes 1/2/5/6 flex their visuals to the VO;
  scenes 3/4 have fixed footage length, so their VO must fit the footage instead.
  See `composition-brief.md` § Narration.
- **Audio-reactive treatment:** none. With no music there is nothing to react to,
  and reactive motion would read as decoration in a safety context.
- **SFX posture:** sparse, and **only in scenes 1, 2, 5, 6**. Scenes 3 and 4 carry
  their captured audio (or clean silence) untouched — laying effects over the
  unedited proof segment is exactly the kind of embellishment the segment exists
  to disprove.
- **Audio-coupled moments:** the architecture diagram's stage-by-stage assembly
  (one soft low-frequency placement per stage, ~5 total); the threshold diamond
  latching; the five prohibitions settling in the close. Nothing on the numbers —
  a metric that arrives with a sound effect reads as a sales figure.
- **Restraint rule:** no whooshes, no risers, no impacts over any real footage, no
  sound on any failure number. If a cue would make a result feel triumphant, cut it.

## Storyboard

Six scenes, timings fixed by `docs/DEMO_SCRIPT.md`. Scenes **3 and 4 are embedded
real capture** — Hyperframes plays them as framework-owned media, uncut.

### Scene 1 — The friction — 28s — `0:00–0:28`
Near-black. Raw ASRS narrative text scrolls slowly behind at ~12% opacity, real
public report text. The hook line holds centre for its full reading floor, then
gives way to the ASRS scale caption in mono: `NASA ASRS — 100,000+ reports/yr ·
each screened by two human analysts within 3 working days`. VO is
`DEMO_SCRIPT.md` § 0:00–0:30.
Sequential/interaction: none — one line, one caption, one long hold. `deadpan`-adjacent restraint on purpose.
Audio intent: near-silence. The scroll is visual, not audible.
Audio-coupled idea: none.
Music: none.
Transition mood: clean, slow → Scene 2

### Scene 2 — Architecture — 30s — `0:28–0:58`
`docs/architecture.png`'s graph, rebuilt as vector and **assembled stage by
stage** rather than shown whole: corpus → deterministic ingest+clustering (green,
with `no LLM call reaches this code` surfacing as its own beat) → **Google ADK
Analyst · Gemini 3.7 Flash** (blue) with risk scoring held deliberately *outside*
it in green → the gold
`total ≥ 0.60?` diamond → the three-agent fan-out → Critic + the deterministic
strip that always runs last → the red terminal `HUMAN APPROVAL`. `config/frozen.yaml`
enters in red with its read-only arrow. VO is `DEMO_SCRIPT.md` § 0:30–1:00, whose
accuracy note must be honoured: **do not** say ingest agents extract and dedupe,
**do not** say the analyst scores risk.
Sequential/interaction: yes — ~7 stage reveals, each held ≥1.2s settled, colour carrying the permission semantics before the VO names them.
Audio intent: structural. Each stage lands with weight, none with excitement.
Audio-coupled idea: one soft low placement per stage reveal (~5 of 7, not all — every-beat placement reads as a machine gun); one distinct latch on the threshold diamond.
Music: none.
Transition mood: hard cut → Scene 3 (the cut into real footage should be felt)

### Scene 3 — Live execution + GCP proof — 85s — `0:58–2:23` — **REAL CAPTURE, UNBROKEN**
Embedded screen recording, played untouched. Terminal executes the Cloud Run job;
logs stream; a cluster crosses threshold; cut to GCP console for Cloud Run,
Firestore documents appearing, and ~3s on the Cloud Scheduler trigger config;
then the deployed Streamlit URL visible in the address bar, the hazard cluster
with its **NEW THIS RUN** badge, the draft brief's ACN citations, the stripped
uncited claim, and **Approve** → Markdown packet downloads.
The bridge line from `DEMO_SCRIPT.md` (job runs the 6-report fixture, dashboard
serves the committed 5,000-report snapshot) **must** be spoken between the console
and the dashboard or the segment reads as incoherent.
The final 173-word narration and continuous-take shot windows are locked in
`docs/DEMO_SCRIPT.md`; do not improvise this segment.
Sequential/interaction: real, not simulated. This is the whole point of the segment.
Audio intent: captured audio or clean silence. Narration over the top.
Audio-coupled idea: **none — prohibited.** No SFX may touch this scene.
Music: none.
Transition mood: hard cut → Scene 4

### Scene 4 — Failure tolerance — 20s — `2:23–2:43` — **REAL CAPTURE**
Embedded capture of `uv run python -m pipeline.run_batch --demo --live
--fail-agent risk` (~11s, silent by design between the banner and the JSON — it is
not hung). A restrained overlay marks the three things to look at without
obscuring the terminal: the fault-injection banner, `DEGRADED`, and
`## Risk Assessment` on its cited deterministic fallback while
`## Recommended Brief` stays model-authored.
Use the final shortened 41-word narration in `docs/DEMO_SCRIPT.md`; the previous
63-word version outran a readable 20-second technical demonstration.
Sequential/interaction: real execution; overlay callouts are the only added layer.
Audio intent: unchanged from capture.
Audio-coupled idea: none over the footage. Overlay callouts appear silently.
Music: none.
Transition mood: clean → Scene 5

### Scene 5 — The numbers — 35s — `2:43–3:18`
Two result blocks in mono, given **equal** visual weight. First the Critic gate
(400 seeded claims, 200 trials): catch rate `1.000`, legitimate-claim retention
`1.000` — with the retention row explicitly called out, because a gate that
deleted everything would also score a perfect catch rate. Then clustering vs
`Events_Anomaly` (4,998 reports): purity `0.301` against a `0.219` majority-class
baseline, Adjusted Rand `0.0018`, and noise fraction `0.837` set against our own
declared `0.40` guard — the failed row rendered in the frozen-red, not hidden.
`DEMO_SCRIPT.md` flags this section as over-budget by design: **cut the extractor
table first** if the take runs long; it is already in the README and Devpost where
a judge reads it without a clock.
Sequential/interaction: yes — rows arrive one at a time, each holding its full reading floor. Numbers are mono and never animate as count-ups; a ticking number is a sales gesture.
Audio intent: silence. Let the failed number sit.
Audio-coupled idea: **none.** Explicitly no cue on any metric.
Music: none.
Transition mood: slow crossfade → Scene 6

### Scene 6 — Close — 34s — `3:18–3:52`
The thesis line, held. Then the five prohibitions settling as a list in the
diagram's own colours — no LLM near clustering (green), frozen thresholds (red),
locked holdout (red), citation gate with no human exception (red), terminal human
approval (red). Then the stack line — Gemini · Google ADK · Cloud Run · Firestore,
solo, 11 days — the generalisation beat (rail, medical devices, energy), and the
two URLs in mono. Ends on the VIGIL wordmark and silence.
Sequential/interaction: yes — five prohibitions, each ≥1.2s settled; snap to every other beat equivalent, never one per beat.
Audio intent: the close should feel like a document being set down, not a launch.
Audio-coupled idea: one soft placement per prohibition; nothing on the URLs.
Music: none.
Transition mood: hold to black.

**Music mood for this video:** none — intentional silence (justified in Audio direction).
**Audio summary:** Narration carries the entire runtime. Sparse structural placement marks the architecture assembly and the closing prohibitions; the two real-capture segments and every metric are left deliberately untouched, so the proof and the failures arrive without any production gloss arguing on their behalf.

## Runtime budget

| # | Scene | Window | Length | Source |
|---|---|---|---|---|
| 1 | The friction | 0:00–0:28 | 28s | Composed |
| 2 | Architecture | 0:28–0:58 | 30s | Composed |
| 3 | Live execution + GCP | 0:58–2:23 | **85s** | **Real capture, unbroken** |
| 4 | Failure tolerance | 2:23–2:43 | 20s | **Real capture** + overlay |
| 5 | The numbers | 2:43–3:18 | 35s | Composed |
| 6 | Close | 3:18–3:52 | 34s | Composed |
| | **Total** | | **3:52** | 8s under the 4:00 cap |

## Blocking dependency

Scenes 3 and 4 cannot be composed until the screen capture exists. Everything
else can be built and validated first. Capture procedure, pre-flight checklist and
the exact commands are in `docs/VIDEO_RUNBOOK.md` — including the two gotchas that
cost false starts on 2026-08-30 (warm the hosted URL first; `set -a; source .env;
set +a` in the recording shell).
