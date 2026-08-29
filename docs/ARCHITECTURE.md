# VIGIL Architecture

One-line: **batch triage pipeline that compresses "40 similar reports filed separately" → "one named hazard with a cited draft brief" — with a human gate before anything leaves the system.**

> **This file describes what is actually built and running**, re-verified against the
> source on 2026-08-29. It was previously an Aug 20 design-intent document and had
> drifted from the code in seven places; those are listed under *Design intent that
> did not survive contact* at the bottom, because the deltas are themselves the
> engineering story. **`docs/PHASES.md` remains the authoritative status board** —
> every row there carries a verified-by-running note. This file explains *shape*;
> PHASES.md records *state*.

Diagrams: `docs/architecture.png` (live path) and `docs/self-improvement-loop.png`
(offline loop), generated from the `.mermaid` sources beside them.

## Stage map → what actually runs

| Stage | What | Construct | Model | Calls per batch |
|---|---|---|---|---|
| 1 | **Ingest** — ASRS coded columns → typed `ASRSReport` | Plain Python (`pipeline/ingest.py`). **No LLM.** | — | 0 |
| 2 | **Cluster** — TF-IDF/embeddings → seeded SVD → HDBSCAN | Plain Python (`pipeline/cluster.py`). **No LLM.** Deterministic | — | 0 |
| 3a | **Analyst** — names the cluster, writes the hazard statement | `LlmAgent`, one call **per cluster** | Flash | 23 on the 5k slice |
| 3b | **Risk scoring** — `0.5·severity + 0.3·frequency + 0.2·trend` | Plain Python (`pipeline/risk.py`), thresholds from `config/frozen.yaml` | — | 0 |
| 3→4 | **Threshold router** — `total ≥ 0.60` | Plain code, read-only policy | — | 0 |
| 4 | **Coordinator** — Precedent ∥ Risk Explainer ∥ Brief Writer | `ThreadPoolExecutor`, per-call error isolation | Flash ×3 | 3 per **escalated** cluster |
| 5a | **Critic** — removes uncited claims | `LlmAgent` | Flash | 1 per escalated cluster |
| 5b | **Citation gate** — `strip_uncited_claims`, provenance-checked | Plain Python. **Always runs last**, even if the Critic died | — | 0 |
| 5c | **Human gate** — Approve/Reject in Streamlit; Approve exports Markdown | UI + Firestore write | — | 0 |

A full live run on the 5,000-report slice is **~39 model calls**, not 5,000. That
is the point of putting the expensive stage behind the threshold router.

### Agents that exist but are not in the batch path

`agents/definitions.py` builds an `intake` `SequentialAgent` (Extractor → Dedup)
and a `coordinator` `ParallelAgent`. **Neither is invoked by
`pipeline/run_batch.py`.** They are kept because they document the intended
Sequential/Parallel shape of the graph, while the batch orchestrator drives the
individual agents directly.

- **Extractor** — offline evaluation target only (`eval/extractor_eval.py`). ASRS
  codes its own fields, so a per-report extraction pass would be ~5,000 calls to
  reproduce data the source already provides. It is the one prompt the
  self-improvement loop may revise.
- **Dedup** — not run at all. ASRS pre-merges Report 1 / Report 2 into one row per
  ACN, so there is no cross-report dedup work at runtime. The *escalation* dedup
  (member-set Jaccard) is a separate, deterministic mechanism in `pipeline/store.py`.

Orchestration logic that can be plain Python **is** plain Python — the fan-out in
stage 4 is a deliberate example, not an omission. See the trade-off note below.

## State & memory (Firestore)
- `reports/` — records keyed by ACN (`setdefault`, so a re-run never overwrites)
- `clusters/` — id, members, analyst output (name **and** hazard statement), risk
  score, brief, `status: new | escalated | approved | rejected`
  - ⚠ **Naming wart, deliberately unchanged:** `status: "new"` means "not escalated
    *this* run", so a cluster seen on a previous run reads as `new`. The UI and
    tests depend on these strings; renaming is a separate tested change. The UI's
    **NEW THIS RUN** badge therefore uses a distinct `newly_escalated` boolean.
- `escalations/` — idempotency ledger; a re-run does not re-alert on a cluster whose
  member set overlaps a previous escalation by Jaccard > 0.6
- `rejections/` — human-rejected clusters stored as negative examples
- `agent_log/` — every call: agent, model, tokens, latency, input hash. The audit
  and observability story.

## Failure tolerance (implemented and demonstrated)
- Every model call: capped retries with backoff, one JSON repair attempt; a failed
  record is raised to the batch caller, which continues. A bad report never kills a run.
- **Parallel fan-out:** one sub-agent lost → brief assembled from the surviving two
  and stamped `DEGRADED`. Fewer than two → `CoordinatorFailure`, and `_brief_for`
  falls back to the deterministic template rather than dropping the cluster.
- **The `DEGRADED` banner is re-asserted by code after the gate.** The Critic's
  response is used verbatim as the brief, so the banner previously survived only if
  the model echoed it. Whether a sub-agent failed is a fact the orchestrator knows;
  it is no longer inferred from model output.
- **Fault injection for the demo:** `--fail-agent {precedent,risk,brief_writer,critic}`
  raises a real exception at the call site, so the demo travels the genuine failure
  path rather than simulating it. Requires `--live`; prints a loud stderr banner.
- **Empty-section backfill:** the gate is line-based and always keeps headings, so a
  section whose every line lacked a citation used to survive as a bare heading —
  byte-identical to a section whose agent never ran. `_backfill_empty_sections`
  restores a member-ACN-cited line after the gate, passing the same gate it repairs.

## The citation gate — provenance, not shape
`strip_uncited_claims` removes any factual claim without a bracketed `[ACN 1234567]`,
and validates each citation against an allow-list of ACNs that actually exist in the
batch (cluster members plus the precedent candidates actually supplied, since
Precedent legitimately cites outside the cluster). A well-formed ACN belonging to no
real report is stripped. Long member lists are capped by `format_citations` at 12
inline citations plus a stated remainder — guardrail #4 requires every claim to cite
*an* ACN, not every ACN.

Measured: **1.000** catch rate on 400 seeded uncited/fabricated claims, with **1.000**
retention of correctly cited claims (the retention control matters — a gate that
deleted everything would score 1.000 on catch rate alone).

## Self-improvement loop (offline, extractor only)
```
dev sample (VALIDATION split) → score vs coded fields, against a majority-class baseline
→ Evaluator reads the frequency-ranked confusion list → candidate prompt → score on dev
→ GUARDS  → fail: record and stop, the holdout is never read
          → pass: DEV GAIN? → no: record and stop, the holdout is never read
                            → yes: score on the LOCKED holdout → improved? promote : discard
→ every outcome written to eval/runs/
```
Guards run **before** the holdout, not after. A promotion writes `config/prompts/`
and never `config/frozen.yaml`. Result of the first live run: extractor v1 → v2,
dev macro-F1 0.0056 → 0.4099, holdout 0.0081 → 0.4219.

## Deliberately frozen
Risk thresholds (`config/frozen.yaml`) are never self-tuned, by any agent, including
the Evaluator, which has no code path to that file. A safety system that quietly
retunes its own severity bar is an audit failure. This restraint is a headline feature.

## Deploy
- **Cloud Run service:** Streamlit UI, min instances 0, service account `vigil-ui-run`
  (`roles/datastore.user` only — the UI never calls a model)
- **Cloud Run job:** `pipeline/run_batch.py`, service account `vigil-batch-run`
  (`secretAccessor` on one secret + `roles/datastore.user`)
- **Cloud Scheduler:** `vigil-weekly-triage`, Monday 09:00 `America/Toronto`,
  authenticated as `vigil-scheduler-run` with job-level `roles/run.invoker` only
- Secrets in Secret Manager; budget alert at $50; neither service uses the default
  compute service account, which carries project-wide Editor

## Design intent that did not survive contact
Recorded because the deltas are the engineering story, and because this file
asserted all of these as fact until 2026-08-29.

| Original design | What shipped, and why |
|---|---|
| Extractor + Dedup as operational stages 1a/1b | Cut. ASRS pre-merges duplicates and codes its own fields; the pass would have been ~5,000 calls to reproduce existing data. Extractor became the offline eval target. |
| `risk = severity × frequency × trend`, computed by the Analyst | Weighted **sum** with frozen weights, computed by deterministic code. The Analyst only names and writes prose — verified by risk scores being byte-identical with and without `--live`. |
| Stage 4 as ADK `ParallelAgent` | Plain-Python `ThreadPoolExecutor`. Per-call `try/except` makes 2-of-3 partial-failure isolation straightforward in a way the framework construct did not. |
| Brief Writer on **Pro** | Flash. Kept as a config knob in `models.yaml`; the quality gap did not justify the cost on this budget. |
| Critic bounce loop, capped at 1 iteration | **Not built.** The deterministic gate runs unconditionally afterwards, which is the stronger guarantee, so a bounce would have added a call without adding safety. |
| Precedent as RAG over the whole corpus | Same-batch, same-component filter. A full-corpus vector index was an explicit scope decision against, not an oversight. |
| Resumable batch: "skips ACNs already in Firestore" | Partial. `put_report` uses `setdefault` so a re-run does not overwrite, but there is no skip-before-reprocessing, so a re-run still redoes clustering. |
| "Keep the one caught reward-hack as a demo beat" | **Never happened.** No revision ever gamed a metric. One guard did fire, and on inspection the guard's own metric was wrong. Do not claim this anywhere — `eval/runs/` is committed and checkable. |
