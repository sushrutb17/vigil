# VIGIL Architecture

One-line: **batch triage pipeline that compresses "40 similar reports filed separately" → "one named hazard with a cited draft brief" — with a human gate before anything leaves the system.**

Diagram source: `docs/asrs-agent-architecture.mermaid` (export PNG for README + Devpost).

## Stage map → ADK constructs

| Stage | What | ADK construct | Model |
|---|---|---|---|
| 1a | **Extractor** — narrative → structured schema (aircraft, phase, component, factors) | `LlmAgent`, JSON output schema | Flash |
| 1b | **Dedup** — same-event detection, merge | `LlmAgent` on candidate pairs only (cheap pre-filter: embedding cosine > threshold) | Flash |
| 2 | **Cluster** — embeddings + HDBSCAN | Plain Python tool. **No LLM.** Seeded, deterministic | — |
| 3 | **Cluster Analyst** — name cluster, hazard statement, risk = severity × frequency × trend | `LlmAgent`, one call per cluster | Flash |
| 3→4 | **Threshold gate** — risk score vs `config/frozen.yaml` | Plain code, not an agent | — |
| 4 | **Coordinator** → **Precedent** (RAG over corpus) ∥ **Risk** (matrix scoring) ∥ **Brief Writer** | `ParallelAgent` with 3 sub-agents | Flash / Flash / Pro |
| 5a | **Critic** — strip any claim without an ACN citation; bounce brief back once max | `LlmAgent` + deterministic citation regex check | Flash |
| 5b | **Human gate** — approve / reject in Streamlit UI; approve also exports the brief as a Markdown download (workflow completes with an artifact in hand — still nothing auto-sent) | UI + Firestore write | — |

Pipeline wrapper: `SequentialAgent` for 1a→1b; stages orchestrated by `pipeline/run_batch.py` (a Cloud Run job), not by a mega-agent. Orchestration logic that can be plain Python **should be** plain Python — say this in the writeup; judges score architectural discipline.

## State & memory (Firestore)
- `reports/` — extracted records (keyed by ACN)
- `clusters/` — cluster id, members, analyst output, risk score, status: `new | escalated | briefed | approved | rejected`
- `escalations/` — idempotency ledger: a re-run never re-alerts on an already-escalated cluster (match by member-set overlap > 0.6); the same ledger drives the UI's **"NEW THIS RUN"** badge
- `rejections/` — human-rejected clusters stored as negative few-shot examples injected into future Analyst prompts
- `agent_log/` — every call: agent, model, tokens, latency, input hash. This is the observability/audit story.

## Failure tolerance (judged criterion — implement, don't just claim)
- Every `LlmAgent` call: max 2 retries w/ backoff; on JSON parse failure, one repair attempt, then mark record `failed` and continue the batch. A bad report never kills a run.
- Critic bounce loop is capped at 1 iteration → prevents agent ping-pong.
- Parallel fan-out: if one sub-agent fails, brief is assembled from the surviving two with a `DEGRADED` banner. Demo this deliberately if time allows.
- Batch job is resumable: skips ACNs already in Firestore (idempotent by key).

## Self-improvement loop (offline, extractor only)
```
run extractor on dev sample → eval/metrics vs coded fields → Evaluator agent reads failures
→ proposes prompt revision → re-run on dev → score on LOCKED holdout via eval/holdout_score.py
→ improved? promote prompt (versioned in config/) : discard
→ guards.py checks guard metrics either way (see EVAL.md)
```
Keep every prompt version + scores in `eval/runs/` — the climbing curve (and the one caught reward-hack) is a demo beat.

## Deliberately frozen
Risk thresholds (`config/frozen.yaml`) are never self-tuned. A safety system that quietly retunes its own severity bar is an audit failure. This restraint is a headline feature — put it in the video.

## Deploy
- **Cloud Run service:** Streamlit UI (`ui/streamlit_app.py`), min instances 0
- **Cloud Run job:** `pipeline/run_batch.py`, triggered manually for the demo ("simulate this week's report drop")
- **Cloud Scheduler:** weekly trigger on the batch job — makes "runs in the background, asynchronously" literal rather than claimed; show the trigger config briefly in the video's console segment
- Secrets via env; budget alert at $50; everything off after demo recording
