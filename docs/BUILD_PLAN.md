# VIGIL Build Plan — Aug 20 → Aug 31, 2026

> **⚠ This is the original calendar, kept as a historical planning artifact. It is
> NOT the status board and its checkboxes are NOT maintained.**
>
> The build did not follow this schedule — most of the pipeline landed in one session
> on Aug 21 and was then untouched until Aug 28, after which it was worked in relay by
> multiple harness sessions. Retro-ticking these boxes would invent a history that did
> not happen.
>
> **For what is actually built and verified → [`docs/PHASES.md`](PHASES.md).**
> For why decisions were made → [`docs/PROGRESS.md`](PROGRESS.md).
> For the Aug 27 gate outcome → [`docs/GATE_DECISION.md`](GATE_DECISION.md).
>
> What this file is still good for: the **capacity model**, the **cut list**, and the
> **anti-stall rules** at the bottom, all of which held up and were used.

Deadline: **Aug 31, 5:00pm PDT = 8:00pm ET.** You are in ET.
Capacity model: ~2.5–3h weekday evenings, ~6–8h weekend days ≈ 45h. The plan below is ~48h, so the **cut list is part of the plan**, not a failure mode.

## Tonight — Thu Aug 20 (setup, ~3h) — DO THESE FIRST
- [ ] **Submit the $150 GCP credit form** (closes Aug 28 12pm PT *or while supplies last*; review takes up to 72 business hours — tonight is not optional)
- [ ] Register on Devpost for the hackathon
- [ ] Create GCP project; enable Vertex AI/Gemini API, Cloud Run, Firestore; **set budget alert at $50**
- [ ] `git init` public repo `vigil`; drop in this doc set; commit
- [ ] `data/download.py`: pull Parquet splits from HF; lock `data/holdout/`
- [ ] 30-min EDA: verify DATA.md quirks on real rows (ZZZ rate, `;` splitting, Report 2 frequency)
- [ ] Queue the *Build a Self-Evolving Agent* webinar recording for the weekend (the 9pm PT live slot is midnight ET — skip live)

## Fri Aug 21 (~3h) — Extractor
- [ ] ADK hello-world: one `LlmAgent` running end to end (env, auth, model ID verified against current docs)
- [ ] Extractor v1 with JSON schema output on a 200-row dev sample
- [ ] `eval/metrics.py` extractor scoring vs coded fields — first real number tonight

## Sat Aug 22 (~7h) — Dedup + clustering
- [ ] Embedding pipeline (batched) on 5k train slice; cache to Parquet
- [ ] HDBSCAN, seeded; purity/ARI vs `Events_Anomaly` + guard metrics
- [ ] Dedup: cosine pre-filter → LlmAgent pair judge; eval vs Report-2 pairs
- [ ] KMeans/TF-IDF + majority-class baselines (EVAL.md)

## Sun Aug 23 (~7h) — Analyst + memory = MILESTONE: triage core works
- [ ] Cluster Analyst agent (name, hazard statement, risk score from frozen config)
- [ ] Firestore collections + idempotency ledger; re-run does not re-alert
- [ ] `pipeline/run_batch.py` end to end on demo slice
- [ ] **Checkpoint:** ingest → clusters → ranked hazards, reproducible with one command

## Mon Aug 24 (~2.5h) — Coordinator skeleton
- [ ] `ParallelAgent`: Precedent (RAG over train corpus) ∥ Risk ∥ Brief Writer (stub)

## Tue Aug 25 (~2.5h) — Brief + Critic
- [ ] Brief Writer (Pro) w/ mandatory ACN citations; Critic + regex citation check; 1-bounce cap
- [ ] Critic eval: seeded uncited claims → catch rate

## Wed Aug 26 (~2.5h) — UI + deploy
- [ ] Streamlit: cluster list → cluster detail → brief view → Approve/Reject (writes rejections as negative examples)
- [ ] Deploy UI (Cloud Run service) + batch (Cloud Run job); screenshot the console **now** for the video

## Thu Aug 27 — **DAY-7 GATE** (~2.5h)
Decision, written into the repo as `docs/GATE_DECISION.md`:
- Coordinator + Critic solid → **full build ships.** Remaining time = loop + polish.
- Behind → **cut Stage 4 to Brief Writer only** (no parallel fan-out); triage core is still a complete Taskmaster entry. Do not carry a broken coordinator into the final weekend.
- Also decide: demo slice size final; any scale-up (10k? full train?) happens tonight or never.

## Fri Aug 28 (~2.5h) — Self-improvement loop (offline)
- [ ] Evaluator agent + prompt-revision loop on extractor, dev split, 2–3 iterations
- [ ] Guards on every promotion; keep the caught-hack artifact for the video
- [ ] Final holdout scoring → headline numbers

## Sat Aug 29 (~7h) — Polish + full run + video prep
- [ ] Failure-tolerance demo path (kill one sub-agent → DEGRADED brief)
- [ ] Full demo-slice run on Cloud Run; capture terminal logs + Firestore writes on screen
- [ ] README: spin-up steps, architecture PNG, metrics table, NASA ASRS + HF credits
- [ ] Write video script from DEMO_SCRIPT.md; record screen segments
- [ ] Stretch bonus (+0.2): Gemma for a small task (e.g., abbreviation expansion) — only if everything above is done

## Sun Aug 30 (~7h) — Video + submission draft
- [ ] Record + edit ≤4-min video; **must show GCP console/Cloud Run proof + unedited live execution**; upload public YouTube
- [ ] Devpost draft: description, category=Taskmaster, repo URL, hosted URL, video URL, diagram
- [ ] Bonus posts: dev.to/Medium build writeup ("created for the #AllThingsAgentic Hackathon" language) + LinkedIn post with hashtag

## Mon Aug 31 — Buffer + SUBMIT
- [ ] Fix whatever Sunday exposed. **Submit by 12pm ET** — never at 7:50pm ET against an 8pm ET deadline
- [ ] After submission confirmation: scale services to zero / tear down (credits!)

## How it actually went (added 2026-08-29)

| Planned for | Reality |
|---|---|
| Fri 21 — Extractor + first eval number | Extractor written; **its eval did not run until Aug 29**, and when it did, v1 lost to the majority-class baseline |
| Sat 22 — Dedup + clustering + baselines | Clustering shipped. **Dedup was cut entirely** — ASRS pre-merges duplicate reports, so the stage had no work to do |
| Sun 23 — Analyst + memory | Landed, though the real Firestore verification came Aug 29 |
| Mon 24 / Tue 25 — Coordinator, Brief, Critic | Landed. The **Critic bounce loop was never built** — the deterministic gate afterwards is the stronger guarantee |
| Wed 26 — UI + deploy | Slipped to Aug 29 |
| Thu 27 — Day-7 gate | Held late, on Aug 28. Full build shipped |
| Fri 28 — Self-improvement loop | Slipped to Aug 29; ran, promoted v1 → v2 |
| Sat 29 — polish, full run, video prep | Polish and the full run landed. **Video not recorded** |
| Sun 30 / Mon 31 — video + submit | Outstanding at time of writing |

Cut in the end: Dedup stage, the Critic bounce loop, full-corpus RAG, the Pro call
path, the Gemma bonus, and the trend sparkline. The floor described below — ingest →
cluster → analyst → brief → critic → human gate, deployed and measured — shipped.

## Cut list (in order, when behind)
1. Gemma bonus → 2. UI polish beyond functional → 3. Loop iterations 3→2 → 4. Precedent agent (Brief Writer cites cluster members directly) → 5. **Day-7 gate: whole parallel fan-out**
The floor that still ships: ingest → cluster → analyst → brief → critic → human gate, deployed, measured, on video.

## Anti-stall rules (self-knowledge clauses)
- Stuck > 45 min on infra/auth → simplify (e.g., API key over service-account gymnastics) and move on.
- No refactors after Aug 27.
- Every session ends with a commit and a runnable state. If a session must be skipped, skip a **stretch** item, not the gate.
