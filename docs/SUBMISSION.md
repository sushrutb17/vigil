# Devpost Submission Checklist — All Things Agentic Hackathon

Deadline: **Aug 31 2026, 5:00pm PDT (8:00pm ET).** Target submit: **Aug 31, 12pm ET.**
Category: **Taskmaster.** Entrant: solo individual (also eligible for the Individual/Hobbyist prize pool and the Best Architectural Design side prize).

## Mandatory tech (verify all three are visibly true in repo + video)
- [ ] Gemini 3.5+ via Gemini API or Vertex AI
- [ ] Google Agent Framework: **ADK (Python)**
- [ ] GCP infra service: **Cloud Run + Firestore**

## Submission form items
- [ ] Category selected: Taskmaster
- [ ] Text description: features, functionality, tech used, data sources (NASA ASRS via HF `elihoole/asrs-aviation-reports`), findings & learnings (they explicitly ask for learnings — include the caught-reward-hack story)
- [ ] Hosted project URL (Cloud Run .run.app — "highly encouraged" and keeps the live-proof story tight)
- [ ] Repo URL (public; if private instead, grant testing@devpost.com and cloudhackathons@google.com)
- [ ] README spin-up instructions (reproducibility is an explicit judging line item)
- [ ] Architecture diagram (export the mermaid to PNG; also embed in README)
- [ ] Video ≤4 min, public YouTube/Vimeo, English: problem + value prop + live demo + **GCP console proof on screen**
- [ ] Project built entirely within the Submission Period (started Aug 20 — compliant); disclose AI coding assistants used (Claude Code / Codex) and any third-party libs

## Compliance checks
- [ ] No third-party logos/trademarks in video or screenshots (mind browser tabs and desktop)
- [ ] Dataset licensing credited: Apache-2.0 (HF packaging) + NASA ASRS as source
- [ ] No employer data or references anywhere (also mind commit history and screen recordings)
- [ ] Judges' testing access works from a clean machine/incognito — test the hosted URL logged out

## Bonus points (Stage Three, up to +1.0)
- [ ] +0.2 — public build-story post (dev.to / Medium / YouTube) including the required line that it was created for entering this hackathon
- [ ] +0.2 — social post on LinkedIn or X with **#AllThingsAgentic** hashtag
- [ ] +0.2 (stretch) — integrate one more Google model (Gemma) for a real sub-task

## After submitting
- [ ] Confirmation email received; submission visible in gallery
- [ ] Scale Cloud Run to zero / disable services; check billing
- [ ] Keep the deployment resurrectable: judging runs Sep 1 – Oct 1 and judges may test the hosted URL during that window — min-instances 0 costs ~nothing, so leave the service up rather than deleting it
- [ ] Winners on/around Oct 8
