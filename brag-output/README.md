# VIGIL submission video — `/brag` × HyperFrames

The **mandatory Devpost video**, built by running `/brag`'s storytelling pipeline
at hackathon scale instead of its default 15–25s teaser scale, with HyperFrames
as the render engine.

```
brag-plan.md          creative contract  — angle, tone, storyboard, every deviation + why
composition-brief.md  build contract     — numbers, palette, prohibitions, swap procedure
composition/          the HyperFrames project
  index.html            MASTER: 6 scene slots, 2 capture videos, 6 VO tracks
  compositions/*.html   one sub-composition per scene — the actual content
  scene-hosts/*.html    thin per-scene render hosts (mount one scene each)
  assets/capture/       ← REAL SCREEN CAPTURE GOES HERE (placeholders now)
  assets/vo/            ← REAL VOICEOVER GOES HERE (silent placeholders now)
scenes/               per-scene MP4s — the editor-timeline deliverable
```

## Two ways to finish it — pick one

**A · Per-scene files, assembled in an editor** *(what you asked for)*. Each
composed scene renders as its own MP4 with **no audio**. Drop them on a timeline,
record voiceover over each, and slot your own capture and any extra scenes
between them. Most flexible; you own the final assembly.

**B · One master render.** `index.html` holds all six scenes and the VO tracks;
swap the placeholder assets and render once. No editor needed.

Both stay in sync automatically — the per-scene hosts in `scene-hosts/` only
*mount* the same sub-compositions the master uses, so a content edit in
`compositions/*.html` shows up in both. **Edit content only in `compositions/`.**

## Why it is not a 20-second brag video

`/brag`'s creative law is *"Short. 15–25 seconds."* The reason to override it is
external: this is a compliance-scored submission judged at **≤4:00**, and the
narration is already written and fact-checked in `docs/DEMO_SCRIPT.md`. The full
list of deviations and their justifications is the table at the top of
`brag-plan.md` — read it before changing anything.

The one place `/brag`'s method could not be stretched: it recreates product UI in
HTML ("no live URL or screenshots needed"). Stage One is pass/fail on **unedited
live execution**, so scenes 3 and 4 embed real screen capture, played untouched.

## Current state

`npx hyperframes check` **passes** — 0 lint, 0 runtime, 0 layout, 0 motion errors,
41/41 WCAG AA contrast. Scenes 1, 2, 5, 6 are finished. Scenes 3 and 4 are
correctly-timed placeholders waiting on footage.

| # | Scene | Window | Source | State |
|---|---|---|---|---|
| 1 | The friction | 0:00–0:28 | composed | ✅ done |
| 2 | Architecture | 0:28–0:58 | composed | ✅ done |
| 3 | Live execution + GCP | 0:58–2:23 | **real capture** | ⏳ needs footage |
| 4 | Failure tolerance | 2:23–2:43 | **real capture** | ⏳ needs footage |
| 5 | The numbers | 2:43–3:18 | composed | ✅ done |
| 6 | Close | 3:18–3:52 | composed | ✅ done |

**3:52 total — 8s under the 4:00 cap.** That headroom exists to absorb voiceover
overrun. If VO comes back long, trim scene 5 per `docs/DEMO_SCRIPT.md`'s stated
cut order (extractor table first), never the close.

## Finishing it — in order

### 1. Record the screen capture (silent)

Follow `docs/VIDEO_RUNBOOK.md` — pre-flight matters more than the take. In
particular: warm the hosted URL first (cold start puts ~10s of blank column on
camera), run `set -a; source .env; set +a` in the recording shell, and clear
tabs/desktop/notifications.

**Record silent.** Narration is laid over the footage in the composition, so a
fluffed line can no longer force a re-shoot of the unbroken 85s take. That is the
main reason capture goes first.

Segment 3 must **visibly** show all four Stage One proofs — Gemini via the API,
ADK, Cloud Run + Firestore, and ~3s on the Cloud Scheduler trigger config. Being
true in the repo does not count.

Then overwrite:

```
composition/assets/capture/seg3-live.mp4
composition/assets/capture/seg4-failure.mp4
```

Measure them and report the real durations — the VO for these two segments has to
fit the footage, not the other way round:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 composition/assets/capture/seg3-live.mp4
```

### 2. Record the voiceover — six files, your own voice

**No TTS.** The hackathon Q&A advised against AI voiceover.

Script is `docs/DEMO_SCRIPT.md`, **verbatim** — it has been corrected once already
for claims that had drifted false. Do not paraphrase or tighten it while
recording. The fixture-vs-snapshot bridge line in § 1:00–2:25 is mandatory.

Six separate files, so a fluffed line costs one segment rather than four minutes:

```
composition/assets/vo/seg1.wav … seg6.wav
```

### 3. Swap the placeholders out

1. Delete the `#s3-ph` block and its two timeline lines in `compositions/s3-live.html`.
2. Delete the `#s4-ph` block and its two timeline lines in `compositions/s4-failure.html`,
   and **retime the three callouts** to the moments they actually occur — the
   current times are guesses, not measurements.
3. Retime `index.html`: set each slot / `<video>` / `<audio>` `data-duration` to
   the real asset length, shift every later `data-start` by the delta, and update
   the root `data-duration`.
4. Scenes 1/2/5/6 flex their **visuals** to the VO length; scenes 3/4 have fixed
   footage, so the **VO** fits them instead.

### 4. Validate and render

```bash
cd composition
npx hyperframes check                                  # must pass, 0 errors
npx hyperframes snapshot --at 15,44,56,180,214,229     # eyeball — check cannot see overflow
```

**Route A — per-scene files** (already rendered into `scenes/`; re-run after edits):

```bash
npx hyperframes render -c scene-hosts/s1.html --quality high --output ../scenes/s1-friction.mp4
npx hyperframes render -c scene-hosts/s2.html --quality high --output ../scenes/s2-architecture.mp4
npx hyperframes render -c scene-hosts/s5.html --quality high --output ../scenes/s5-numbers.mp4
npx hyperframes render -c scene-hosts/s6.html --quality high --output ../scenes/s6-close.mp4
```

Scene 4's callouts render separately **with an alpha channel**, so they lay over
your terminal capture instead of being baked in — do this *after* recording, once
the placeholder is deleted and the callouts are retimed to the real footage
(`scene-hosts/s4-overlay.html` documents both steps):

```bash
npx hyperframes render -c scene-hosts/s4-overlay.html --format mov \
  --quality high --output ../scenes/s4-callouts.mov
```

Scene 3 needs nothing rendered — it is your capture, played untouched.

**Route B — one master render:**

```bash
npx hyperframes render --quality high --output ../vigil-demo.mp4
```

**Confirm the runtime is ≤4:00. Not 4:01.** Then upload per
`docs/VIDEO_RUNBOOK.md` § 4 — public, English, verified in an incognito window.

## Things that will bite

- **`check` cannot see text overflowing a box or the frame edge.** It passed clean
  on a version of scene 2 where `config/frozen.yaml` was sliced by the right edge
  and the Analyst node's text spilled out the bottom. Always snapshot after a copy
  change; the geometry grid is documented in that file's header comment.
- **Colour is semantic, not decorative.** Green = deterministic/no-LLM, blue = LLM
  agent, gold = decision gate, red = frozen/terminal. The narration leans on it.
  Recolouring a node changes what the diagram claims.
- **Do not add SFX or graphics over scene 3.** It is the unedited-execution proof.
- **Do not de-emphasise the failure numbers in scene 5.** Equal weight with the
  clean ones is a design requirement — the video argues that publishing bad results
  is the feature.
- **No music.** Deliberate, justified in `brag-plan.md` § Audio direction. Bundled
  `/brag` tracks max out at 164s against a 232s runtime.
