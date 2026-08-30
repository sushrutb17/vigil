# Devpost Submission Checklist — All Things Agentic Hackathon

Deadline: **Aug 31 2026, 5:00pm PDT (8:00pm ET).** Target submit: **Aug 31, 12pm ET.**
Category: **Taskmaster.** Entrant: solo individual (also eligible for the Individual/Hobbyist prize pool and the Best Architectural Design side prize).

## Ready to paste (filled in 2026-08-30 — verified, not assumed)

| Form field | Value |
|---|---|
| Category | **Taskmaster** |
| Hosted project URL | `https://vigil-ui-715230861973.us-central1.run.app` |
| Repo URL (public) | `https://github.com/sushrutb17/vigil` |
| Architecture diagram | `docs/architecture.png` — **upload the file**; the README embed does not carry over to the form |
| Description body | `docs/DEVPOST_DRAFT.md`, paste-ready (~1,600 words, includes the literal "The Twist" section and the ASRS institutional-mirror paragraph) |
| Data credit | NASA ASRS, packaged as HF `elihoole/asrs-aviation-reports` (Apache-2.0 packaging) |
| AI-assistant disclosure | Claude Code / Codex |
| Video URL | ⬜ *not yet recorded* — see [`VIDEO_RUNBOOK.md`](VIDEO_RUNBOOK.md) |

> Cloud Run answers on two URL forms — the project-number one above and
> `https://vigil-ui-6bbjbbpdca-uc.a.run.app`. Both return 200. **Use the
> project-number form everywhere** so README, Devpost and the video agree.
>
> `DEVPOST_DRAFT.md` contains no placeholder markers for the three URLs — they
> are form fields, not body text, which makes them easy to skip under time
> pressure. Check them off deliberately.

---

## Judging rubric (verified 2026-08-29 against the published rules page)
- **Stage One is pass/fail:** all mandatory requirements present and properly applied. No live GCP proof = eliminated, regardless of architecture. This is why the live path (Phases 3–4) outranks every polish item.
- **Stage Two, scored 1–5 per criterion:**
  - **Innovation & Operational Utility — 40%:** "Does the system eliminate real-world friction? Is the 'Twist' present?" — "high-value, autonomous execution over simple chat queries"
  - **Architectural Discipline & Tech Stack — 30%:** "We are evaluating your engineering decisions, not just your ability to call an API" — decoupling, state management, robust agentic design
  - **Demo & Production Readiness — 30%:** "undeniable proof of execution" + clean, reproducible documentation
- **Taskmaster lens:** does the agent "intercept and complete a multi-step background workflow"? Plus BYOF ("Bring Your Own Friction") — a unique, personal friction story.
- **Stage Three bonus:** +0.2 content post, +0.2 social post, +0.2 per additional Google model (Gemma/Veo/Lyria) up to 0.6. **Decision: Gemma only, stretch only.** Do not chase Veo/Lyria or the Multimodal UX side prize — forcing them into a safety-triage tool costs 30%-criterion points to gain bonus decimals.

## Mandatory tech (verify all three are visibly true in repo + video)
- [ ] Gemini 3.5+ via Gemini API or Vertex AI *(true in repo; tick only after you see it in your own footage — [`VIDEO_RUNBOOK.md`](VIDEO_RUNBOOK.md) §3)*
- [ ] Google Agent Framework: **ADK (Python)**
- [ ] GCP infra service: **Cloud Run + Firestore**

## Submission form items
- [x] Category selected: Taskmaster *(value known; tick again on the form itself)*
- [ ] Text description: features, functionality, tech used, data sources (NASA ASRS via HF `elihoole/asrs-aviation-reports`), findings & learnings (they explicitly ask for learnings — include the caught-reward-hack story)
  - [ ] Literal **"The Twist"** section: restraint made mechanical — no-LLM clustering, frozen thresholds the agents cannot touch, locked holdout, citation-stripping critic, and the citation gate we caught validating *shape* instead of *provenance* (a model invented ACNs 1000001–1000005 and the gate kept them). **Corrected 2026-08-29: the originally planned "agent gamed ROUGE and a guard caught it" story never happened** — do not claim it; `eval/runs/` is committed and a judge can check. See `docs/DEVPOST_DRAFT.md` for the paste-ready text. Framing line: "Every other demo shows what the agents can do; VIGIL's headline feature is what they're structurally forbidden from doing."
  - [ ] ASRS institutional-mirror paragraph: NASA ASRS takes 100,000+ reports/yr; every report is screened by two expert analysts within 3 working days; the real-world output is an Alert Message to organizations in authority — VIGIL mirrors that exact triage→alert workflow (cite asrs.arc.nasa.gov + NTRS doc 20210023200)
- [x] Hosted project URL (Cloud Run .run.app — "highly encouraged" and keeps the live-proof story tight)
- [x] Repo URL (public; if private instead, grant testing@devpost.com and cloudhackathons@google.com)
- [x] README spin-up instructions (reproducibility is an explicit judging line item)
- [x] Architecture diagram (export the mermaid to PNG; also embed in README) — **PNG exists and is embedded; still must be uploaded to the form**
- [ ] Video ≤4 min, public YouTube/Vimeo, English: problem + value prop + live demo + **GCP console proof on screen**; console segment includes ~3s of the Cloud Scheduler trigger config (background-workflow proof) — **step-by-step: [`VIDEO_RUNBOOK.md`](VIDEO_RUNBOOK.md)**
- [ ] Project built entirely within the Submission Period (started Aug 20 — compliant); disclose AI coding assistants used (Claude Code / Codex) and any third-party libs

## Compliance checks
- [ ] No third-party logos/trademarks in video or screenshots (mind browser tabs and desktop)
- [x] Dataset licensing credited: Apache-2.0 (HF packaging) + NASA ASRS as source — in README; **still to be entered on the form**
- [x] No employer data or references anywhere — scanned every tracked file **and** every historical blob 2026-08-30, zero hits; screen recordings still to check at record time
- [x] Judges' testing access works from a clean machine/incognito — verified 2026-08-30 from a clean unauthenticated browser context: HTTP 200 and the full page renders

## Bonus points (Stage Three, up to +1.0)
- [ ] +0.2 — public build-story post (dev.to / Medium / YouTube) including the required line that it was created for entering this hackathon — **draft ready: [`BONUS_POSTS.md`](BONUS_POSTS.md) Post 1.** Verify the exact required wording against the live rules page before posting; +0.2 rides on one sentence.
- [ ] +0.2 — social post on LinkedIn or X with **#AllThingsAgentic** hashtag — **draft ready: [`BONUS_POSTS.md`](BONUS_POSTS.md) Post 2** (LinkedIn version + X thread variant).
- [ ] +0.2 (stretch) — integrate one more Google model (Gemma) for a real sub-task (rules allow +0.2 per extra model up to 0.6 — deliberate decision to stop at Gemma; see rubric section above)

## After submitting
- [ ] Confirmation email received; submission visible in gallery
- [ ] Scale Cloud Run to zero / disable services; check billing
- [ ] Keep the deployment resurrectable: judging runs Sep 1 – Oct 1 and judges may test the hosted URL during that window — min-instances 0 costs ~nothing, so leave the service up rather than deleting it
- [ ] Winners on/around Oct 8
