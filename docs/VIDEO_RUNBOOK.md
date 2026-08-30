# Video production runbook

**Pick this up when you're ready to record.** This file is the *operational*
side — setup, commands, mechanics, upload, verification. What to actually say and
show is in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md), which holds the narration, the shot
list and the time budget. Read this one first, then record against that one.

Status when this was written (2026-08-30): everything upstream of recording is
done. Cloud Run is deployed and verified, the repo is public, the failure
tolerance clip is verified, and the script is corrected. **Nothing blocks
recording except recording.**

- Hard deadline: **Aug 31 2026, 5:00pm PDT / 8:00pm EDT.** Target submit 12pm ET.
- Hosted URL: `https://vigil-ui-715230861973.us-central1.run.app`
- Repo: `https://github.com/sushrutb17/vigil`
- Requirement: **≤4:00**, public, English, on YouTube or Vimeo.

---

## 1. Pre-flight — all five, before the first take

| # | Do | Why it's on the list |
|---|---|---|
| 1 | **Warm the hosted URL** — open it, let it fully render | `--min-instances 0` means a cold start leaves the right-hand draft column blank for ~10s. On camera that reads as a broken app, not a cost decision. Warm, the page completes in 3.8s. |
| 2 | **Export the key in the recording shell**: `set -a; source .env; set +a` | A fresh terminal silently drops `GOOGLE_API_KEY`; `--live` then fails. This caused two false starts on 2026-08-30. |
| 3 | **Clear the screen** — unrelated tabs, bookmarks bar, desktop icons, Do Not Disturb on | No third-party logos or trademarks anywhere on screen. This is a **compliance item** in `SUBMISSION.md`, not tidiness, and a notification sliding in mid-take is a re-shoot. |
| 4 | **Terminal**: ≥16pt font, dark theme, cleared scrollback | Legibility at 1080p. |
| 5 | **Dry-run both live commands once** (§2) | So you know their duration and nothing surprises you mid-take. |

---

## 2. The two live commands

Both are safe to dry-run before recording.

### Cloud Run batch job — segment 3, the Stage One proof

```bash
gcloud run jobs execute vigil-batch --project vigil-hackathon-506218 \
  --region us-central1 --wait
```

Exercises Gemini + ADK + Cloud Run + Firestore in one execution. **Safe to
re-run**: the escalation ledger dedups by member-set overlap, and the UI's 🆕
badge is read from the committed artifact (`ui/streamlit_app.py:131`), not from
Firestore — so a dry run cannot spoil the badge you show later.

### Failure tolerance — segment 4

```bash
set -a; source .env; set +a
uv run python -m pipeline.run_batch --demo --live --fail-agent risk
```

**~11s, exit 0, and it prints nothing between the banner and the final JSON.
Silent, not hung — do not interrupt it.** Verified 2026-08-30. Costs ~4 live
Flash calls, so it is cheap to re-shoot.

Expected output, and the three things to point at on screen:

1. stderr banner: `!! FAULT INJECTION ACTIVE: risk will raise…`
2. `DEGRADED` in the brief
3. `## Risk Assessment` carrying its **cited deterministic fallback**, while
   `## Recommended Brief` is still model-authored

> If `## Risk Assessment` comes back as a bare heading with nothing under it,
> stop — that is the exact defect `_backfill_empty_sections` exists to prevent,
> and it would mean a regression worth fixing before recording.

---

## 3. Recording mechanics

**Record six segments and stitch them.** Only **segment 3 must be one unbroken
take** — the "unedited" requirement applies to the live execution, not to the
whole video. Chasing a single flawless 4-minute take is wasted effort.

- macOS: `Cmd+Shift+5`, select microphone under **Options**. Or OBS if you want
  scene-switching between browser and terminal.
- 1080p. Script the voiceover; don't improvise.
- Stitch in iMovie (installed) or your preferred editor.

Segment order and timings are in [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Summary:

| # | Segment | Window |
|---|---|---|
| 1 | The friction (BYOF) | 0:00–0:30 |
| 2 | Architecture | 0:30–1:00 |
| 3 | **Live execution + GCP console** | 1:00–2:25 — unbroken |
| 4 | Failure tolerance | 2:25–2:45 |
| 5 | The numbers | 2:45–3:20 |
| 6 | Close | 3:20–4:00 |

### Segment 3 is the pass/fail segment

Stage One is pass/fail and eliminates on a miss regardless of how good everything
else is. Segment 3 must **visibly** show all three mandatory technologies:

- [ ] Gemini 3.5+ via the Gemini API (the job's `agent_log` / console output)
- [ ] Google ADK as the agent framework
- [ ] Cloud Run **and** Firestore (console: service, job, Firestore documents)
- [ ] **~3s on the Cloud Scheduler trigger config** — this is the
      *background-workflow* evidence the Taskmaster category is scored on, and
      it is the easiest of the four to forget

Also say the bridge line in `DEMO_SCRIPT.md` between the job and the dashboard:
the job runs the 6-report fixture, the UI serves the 5,000-report snapshot, and a
judge watching 6 go in and 23 clusters come out will notice if you don't explain.

---

## 4. Upload and verify

1. Upload to **YouTube** (or Vimeo). **Unlisted is fine; private is not** — a
   judge must be able to open it.
2. Set language to **English**.
3. **Verify playback in an incognito window**, logged out. Same reasoning as the
   hosted-URL check: your own signed-in session proves less than a clean one.
4. Confirm the runtime is **≤4:00**. Not 4:01.
5. Put the URL into `SUBMISSION.md`'s "Ready to paste" table.

---

## 5. Then submit

Everything the Devpost form needs is pre-filled in
[`SUBMISSION.md`](SUBMISSION.md) → "Ready to paste", except the video URL.

Do not forget, in order of how easy they are to skip:

- **The architecture diagram must be uploaded to the form.** `docs/architecture.png`
  — the README embed does not carry over, and neither does the interactive diagram
  at <https://vigil-architecture.vercel.app/diagram.html?theme=light>.
  That page is a nice thing to pan across on screen during the architecture beat,
  but the form wants the file.
- **The three URLs are form fields, not body text.** `DEVPOST_DRAFT.md` has no
  placeholder markers for them, which makes them easy to miss under time pressure.
- **AI-assistant disclosure** (Claude Code / Codex) and the built-within-the-
  submission-period attestation.
- Tick the three mandatory-tech boxes in `SUBMISSION.md` **only after** you have
  seen all three on screen in your own footage.

---

## Known gotchas — all of these actually happened on 2026-08-30

| Symptom | Cause | Fix |
|---|---|---|
| Draft column blank, Streamlit "Stop" button visible | Cloud Run cold start | Warm the URL first. Not a bug. |
| `--live` dies with a wall of ADK traceback | `GOOGLE_API_KEY` not in this shell | `set -a; source .env; set +a`. Now caught by a 4-line argparse error instead. |
| `zsh: command not found: python` | No bare `python` on PATH | `uv run python …` |
| Command appears hung for ~11s | It is silent by design | Wait. Do not Ctrl+C. |
| `./infra/deploy.sh` looks stuck for minutes | Cloud Build step is quiet | Wait. The script is re-runnable if you do interrupt it. |
