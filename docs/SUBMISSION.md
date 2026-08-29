# Devpost Submission Checklist — All Things Agentic Hackathon

Deadline: **Aug 31 2026, 5:00pm PDT (8:00pm ET).** Target submit: **Aug 31, 12pm ET.**
Category: **Taskmaster.** Entrant: solo individual (also eligible for the Individual/Hobbyist prize pool and the Best Architectural Design side prize).

## Devpost description draft

### VIGIL — Aviation Safety Signal Triage

VIGIL turns a background stream of public aviation safety reports into a ranked
review queue and source-cited investigator briefs. It is built for the moment
between “thousands of reports arrived” and “a human safety analyst knows where to
look first.”

The project ingests NASA Aviation Safety Reporting System (ASRS) records,
normalizes their coded fields and narratives, removes same-event duplication,
clusters related reports, and applies a frozen risk policy based on severity,
frequency, and trend. Only clusters above the fixed escalation threshold trigger
the agent team. A Cluster Analyst names the hazard; a Coordinator fans work out
in parallel to Precedent, Risk, and Brief Writer agents; and a Critic removes any
factual claim that cannot be traced to an allowed ASRS accession number (ACN).
The result is a draft for human review—not an automated safety action.

This is a Taskmaster workflow because the system intercepts repetitive batch
triage in the background, carries it through several specialized steps, keeps
state across runs, and hands a completed artifact to the person who owns the
decision. A Cloud Run job performs the pipeline, Firestore records
reports, clusters, escalation history, decisions, and per-agent observability,
and a Streamlit service presents the human approval gate.

### Why this problem matters

The design deliberately mirrors the institution whose public data makes VIGIL
possible. NASA ASRS now receives more than 10,000 reports per month. Its public
processing description says every report is read by at least two experienced
safety analysts, while NASA's 2021 ASRS overview documents rapid screening and
the production of safety alert messages. When a report suggests a hazard, ASRS
relays de-identified information to an organization in a position of authority
for evaluation and possible corrective action. VIGIL mirrors that
intake → triage → alert-draft pattern while keeping the authority with the human.

Sources: [NASA ASRS report processing](https://asrs.arc.nasa.gov/overview/report.html),
[NASA ASRS 50-year retrospective](https://asrs.arc.nasa.gov/publications/callback/cb_555.html),
and [NASA NTRS document 20210023200](https://ntrs.nasa.gov/citations/20210023200).

### How it works

1. **Deterministic ingest and clustering.** Public ASRS Parquet data is
   normalized, embedded, and clustered with seeded HDBSCAN. There are no
   generative-model calls inside clustering.
2. **Frozen risk routing.** A read-only YAML policy computes the escalation
   score. Agents cannot silently lower or raise the safety threshold.
3. **Specialized agent fan-out.** Google ADK agents use Gemini Flash for cluster
   analysis, precedent search, risk interpretation, and criticism; the Brief
   Writer may use Pro. Independent Coordinator branches run concurrently and
   tolerate one failed branch by marking the output `DEGRADED`.
4. **Evidence gate.** Every factual brief line must contain a bracketed ACN, and
   that ACN must be one of the reports actually supplied to the agent. Uncited
   claims and fabricated identifiers are removed deterministically.
5. **Human terminal gate.** An analyst approves or rejects the draft in the UI.
   Rejections become negative examples in Firestore. VIGIL never files, sends,
   or auto-approves anything.

### The Twist

Every other demo shows what the agents can do; VIGIL's headline feature is what
they are structurally forbidden from doing.

The clusterer cannot call an LLM. The agents cannot edit the risk threshold.
The offline improvement loop cannot read the locked holdout except through the
one scoring entry point, and it is limited to the Extractor prompt—it cannot
retune the Analyst, Risk agent, or Critic. The human gate has no auto-approve
path. Finally, the citation critic is backed by a deterministic provenance
allow-list, so a fluent answer is still discarded when its evidence is wrong.

That last constraint came from a useful failure. An early live brief contained
perfectly formatted citations to plausible-looking ACNs that did not exist in
the source corpus. The first gate checked citation shape, so the fabricated IDs
passed. We changed the contract to supply the real member ACNs and changed the
gate to validate provenance, not typography. A claim with only invented sources
now disappears. In a safety system, a fabricated citation is worse than an
uncited sentence because it carries false authority; catching that distinction
became one of VIGIL's strongest design decisions.

> **TODO before submission:** replace this note with the measured offline
> self-improvement result only after Phase 5 is implemented and run. Do not claim
> that a ROUGE-gaming prompt revision was caught unless an `eval/runs/` receipt
> exists.

### Built with Google technology

- **Gemini:** `gemini-3.7-flash` for operational agents and
  `gemini-embedding-2` for embeddings; the Brief Writer may use Pro.
- **Google ADK (Python):** agent definitions, structured outputs, sessions, and
  model execution.
- **Google Cloud:** Cloud Run service for the Streamlit review UI, Cloud Run job
  for the batch pipeline, Firestore for workflow state and observability, and
  Secret Manager for the Gemini key.
- **Deterministic data stack:** Python 3.12, pandas, scikit-learn, HDBSCAN,
  PyArrow, pytest, and Ruff.

### Evaluation and findings

VIGIL uses ASRS coded fields as ground truth instead of relying on subjective
demo impressions. The evaluation plan reports extractor macro-F1, dedup
precision/recall, cluster purity and adjusted Rand index, noise fraction, and
the critic's seeded uncited-claim catch rate. Guard metrics prevent trivial
metric gaming such as shrinking clusters until purity looks perfect, predicting
only majority labels, or merging everything to inflate dedup recall.

| Measure | Result |
|---|---:|
| Extractor macro-F1 | **TODO — insert measured holdout value** |
| Dedup precision / recall | **TODO — insert measured holdout values** |
| Cluster purity / adjusted Rand index | **TODO — insert measured values** |
| Noise fraction | **TODO — insert measured value** |
| Critic uncited-claim catch rate | **TODO — insert measured value** |
| Live batch size / clusters / escalations | **TODO — insert verified run counts** |

### Links

- **Live app:** TODO — add the final hosted Cloud Run URL after the last redeploy
  and incognito verification.
- **Source code:** TODO — add the public repository URL.
- **Demo video:** TODO — add the public YouTube or Vimeo URL.
- **Interactive architecture:**
  [vigil-architecture.vercel.app](https://vigil-architecture.vercel.app)

### Data, licensing, and disclosure

VIGIL uses public NASA ASRS data packaged as the Hugging Face dataset
`elihoole/asrs-aviation-reports` (Apache-2.0 packaging). Historical records are
presented as a replay, never as a live feed. The project was built during the
hackathon submission period with Google ADK, Gemini, Google Cloud, open-source
Python libraries, and AI coding assistance from Claude Code and Codex.

## Judging rubric (verified 2026-08-29 against the published rules page)
- **Stage One is pass/fail:** all mandatory requirements present and properly applied. No live GCP proof = eliminated, regardless of architecture. This is why the live path (Phases 3–4) outranks every polish item.
- **Stage Two, scored 1–5 per criterion:**
  - **Innovation & Operational Utility — 40%:** "Does the system eliminate real-world friction? Is the 'Twist' present?" — "high-value, autonomous execution over simple chat queries"
  - **Architectural Discipline & Tech Stack — 30%:** "We are evaluating your engineering decisions, not just your ability to call an API" — decoupling, state management, robust agentic design
  - **Demo & Production Readiness — 30%:** "undeniable proof of execution" + clean, reproducible documentation
- **Taskmaster lens:** does the agent "intercept and complete a multi-step background workflow"? Plus BYOF ("Bring Your Own Friction") — a unique, personal friction story.
- **Stage Three bonus:** +0.2 content post, +0.2 social post, +0.2 per additional Google model (Gemma/Veo/Lyria) up to 0.6. **Decision: Gemma only, stretch only.** Do not chase Veo/Lyria or the Multimodal UX side prize — forcing them into a safety-triage tool costs 30%-criterion points to gain bonus decimals.

## Mandatory tech (verify all three are visibly true in repo + video)
- [ ] Gemini 3.5+ via Gemini API or Vertex AI
- [ ] Google Agent Framework: **ADK (Python)**
- [ ] GCP infra service: **Cloud Run + Firestore**

## Submission form items
- [ ] Category selected: Taskmaster
- [ ] Text description: features, functionality, tech used, data sources (NASA ASRS via HF `elihoole/asrs-aviation-reports`), findings & learnings (they explicitly ask for learnings — include the caught-reward-hack story)
  - [ ] Literal **"The Twist"** section: restraint made mechanical — no-LLM clustering, frozen thresholds the agents cannot touch, locked holdout, citation-stripping critic, and the guard that caught our own agent gaming ROUGE. Framing line: "Every other demo shows what the agents can do; VIGIL's headline feature is what they're structurally forbidden from doing."
  - [ ] ASRS institutional-mirror paragraph: NASA ASRS takes 100,000+ reports/yr; every report is screened by two expert analysts within 3 working days; the real-world output is an Alert Message to organizations in authority — VIGIL mirrors that exact triage→alert workflow (cite asrs.arc.nasa.gov + NTRS doc 20210023200)
- [ ] Hosted project URL (Cloud Run .run.app — "highly encouraged" and keeps the live-proof story tight)
- [ ] **Judge-explorable architecture viewer:** [vigil-architecture.vercel.app](https://vigil-architecture.vercel.app) — public Archify runtime map; include this as the architecture/demo companion URL during the final submission pass. Verify it logged out/incognito before submitting.
- [ ] Repo URL (public; if private instead, grant testing@devpost.com and cloudhackathons@google.com)
- [ ] README spin-up instructions (reproducibility is an explicit judging line item)
- [ ] Architecture diagram (export the mermaid to PNG; also embed in README)
- [ ] Video ≤4 min, public YouTube/Vimeo, English: problem + value prop + live demo + **GCP console proof on screen**; console segment includes ~3s of the Cloud Scheduler trigger config (background-workflow proof)
- [ ] Project built entirely within the Submission Period (started Aug 20 — compliant); disclose AI coding assistants used (Claude Code / Codex) and any third-party libs

## Compliance checks
- [ ] No third-party logos/trademarks in video or screenshots (mind browser tabs and desktop)
- [ ] Dataset licensing credited: Apache-2.0 (HF packaging) + NASA ASRS as source
- [ ] No employer data or references anywhere (also mind commit history and screen recordings)
- [ ] Judges' testing access works from a clean machine/incognito — test the hosted URL logged out

## Bonus points (Stage Three, up to +1.0)
- [ ] +0.2 — public build-story post (dev.to / Medium / YouTube) including the required line that it was created for entering this hackathon
- [ ] +0.2 — social post on LinkedIn or X with **#AllThingsAgentic** hashtag
- [ ] +0.2 (stretch) — integrate one more Google model (Gemma) for a real sub-task (rules allow +0.2 per extra model up to 0.6 — deliberate decision to stop at Gemma; see rubric section above)

## After submitting
- [ ] Confirmation email received; submission visible in gallery
- [ ] Scale Cloud Run to zero / disable services; check billing
- [ ] Keep the deployment resurrectable: judging runs Sep 1 – Oct 1 and judges may test the hosted URL during that window — min-instances 0 costs ~nothing, so leave the service up rather than deleting it
- [ ] Winners on/around Oct 8

## Final-stretch reminder

- [ ] Add the public Archify viewer URL to the final Devpost/README materials: <https://vigil-architecture.vercel.app>
- [ ] Open the viewer in a clean/incognito browser and confirm judges can explore the architecture, trace the main path, switch themes, and use the export controls.
