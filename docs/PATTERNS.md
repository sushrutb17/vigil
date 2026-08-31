# VIGIL × Agentic Design Patterns

Reference: Antonio Gulli, *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* (Springer, free release). Gulli is a Google engineering director; the book's examples are ADK/Gemini. It is the closest thing to a house pattern vocabulary inside Google's agent ecosystem — which is why it is worth speaking it back at a Google-judged hackathon with a **Best Architectural Design** side prize.

**Why this file exists:** VIGIL already implements ~14 of the 21 patterns. It does not have a design gap; it has a naming gap. This file closes the naming gap and fixes the language used in the README, the Devpost description and the video.

> **Re-verified against the code 2026-08-29.** Six rows below asserted mechanisms
> that were never built or were later cut (the `SequentialAgent` intake, the ADK
> `ParallelAgent`, the Critic bounce loop, the cosine-prefiltered dedup judge, the
> Pro call path, and full-corpus RAG). They are corrected in place rather than
> deleted, because "we claimed this pattern and then measured that we had not built
> it" is a more useful note to a future session than a clean table.

**What this file must not do:** grow the build. `BUILD_PLAN.md` is ~48h against ~45h capacity and already carries a cut list. Nothing below is a new milestone. If a pattern is not already in the architecture, the correct action is a sentence in the writeup, not a new agent.

---

## Coverage map

Legend — **✅ built** (in the architecture today) · **🏷️ name it** (built, currently unnamed — free points) · **⛔ omitted by design** (argue for it, don't hide it) · **➖ n/a**

| # | Pattern | Status | Where in VIGIL |
|---|---|---|---|
| 1 | Prompt Chaining | ⛔ | **Corrected.** The `intake` `SequentialAgent` exists in `agents/definitions.py` but is never invoked — Extractor/Dedup were cut from the operational path. The real chain is deterministic: ingest → cluster → assess → coordinate → verify, sequenced by plain Python. Do not claim this pattern. |
| 2 | Routing | 🏷️ | Stage 3→4 threshold gate against `config/frozen.yaml` — a deterministic router, currently described as a gate |
| 3 | Parallelization | ✅ | Stage 4: Precedent ∥ Risk ∥ Brief Writer — via plain-Python `ThreadPoolExecutor`, **not** ADK's `ParallelAgent`. Say it that way; the reason (per-call failure isolation for 2-of-3 tolerance) is the stronger architecture point. |
| 4 | Reflection | ✅ | Critic (LLM) reviews the assembled draft. **No bounce loop was built** — the deterministic gate runs unconditionally afterwards, which is a stronger guarantee than a re-ask, so a bounce would add a call without adding safety. Claim the review, not the loop. |
| 5 | Tool Use | ✅ | Clustering, embeddings, citation regex as plain Python tools |
| 6 | Planning | ⛔ | **Deliberate.** Orchestration is static Python, not a planner agent. See "Arguing the omissions" |
| 7 | Multi-Agent Collaboration | ✅ | Coordinator + 3 sub-agents; 9 agents total |
| 8 | Memory Management | ✅ | Firestore `reports/`, `clusters/`, `escalations/` (idempotency), `rejections/` (negative few-shot into future Analyst prompts) |
| 9 | Learning and Adaptation | ✅ | Offline extractor self-improvement loop; promotion gated on holdout + guards |
| 10 | Model Context Protocol | ⛔ | Single-tenant batch system. Future work |
| 11 | Goal Setting and Monitoring | 🏷️ | Risk score *is* the objective function; `agent_log/` is the monitor. Fold into the Evaluation story rather than claiming separately |
| 12 | Exception Handling and Recovery | ✅ | Retries + backoff, one JSON repair attempt, failed records don't kill the batch, DEGRADED brief on sub-agent loss (demonstrated live via `--fail-agent`). **"Resumable by ACN key" is overstated:** `put_report` uses `setdefault` so a re-run doesn't overwrite, but there is no skip-before-reprocessing. |
| 13 | Human-in-the-Loop | ✅ | Terminal human gate. Nothing is ever auto-actioned |
| 14 | Knowledge Retrieval (RAG) | 🏷️ | Precedent retrieves over the **current batch**, filtered to the same component — not a full-corpus vector index. That was an explicit scope decision, so describe it accurately rather than as corpus-wide RAG. |
| 15 | Inter-Agent Communication (A2A) | ⛔ | No cross-org agents. Future work |
| 16 | Resource-Aware Optimization | ✅ | **Flash everywhere, including the Brief Writer** (Pro was specced, never used). The real cost story is architectural, and stronger: the Analyst runs once per *cluster* (23 calls, not 5,000), the Coordinator only for clusters past the threshold — a full 5k-report live run is **~39 calls**. No cosine-prefiltered dedup judge exists; that stage was cut. |
| 17 | Reasoning Techniques | ➖ | Implicit in agent prompts. Don't claim it separately |
| 18 | Guardrails / Safety | ✅ | Immutable `frozen.yaml`; mandatory ACN citation; `eval/guards.py` reward-hack tripwires; sacred `data/holdout/` |
| 19 | Evaluation and Monitoring | ✅ | `EVAL.md` in full: ground-truth metrics, baselines, guards, runs ledger, `agent_log/` |
| 20 | Prioritization | ✅ | Clusters ranked by a frozen weighted sum `0.5·severity + 0.3·frequency + 0.2·trend` (not a product); only clusters ≥ 0.60 escalate. |
| 21 | Exploration and Discovery | 🏷️ | HDBSCAN surfacing **unnamed, emerging** hazards nobody queried for. This is the product thesis, currently written up as plumbing |

**Score to quote after the 2026-08-29 correction: 13 built + 3 named = 16 of 21, with 5 omitted deliberately** (Planning, MCP, A2A, Reasoning, and now Prompt Chaining, whose `SequentialAgent` is never invoked). Do not round this up — and note that the honest number went *down* when we checked. The omissions are the credible part.

---

## The three free wins

Doc-only. No code. Highest return per minute in the whole build.

### 16 — Resource-Aware Optimization
You do this well and never say it — but say the *true* version. Every agent runs on
Flash, and the cost discipline is architectural rather than model-selection: the
expensive stages sit behind the threshold router, so the Analyst runs once per
cluster and the Coordinator only for clusters that actually escalate.

> **Writeup line:** "A 5,000-report run costs 39 model calls, not 5,000. The Analyst
> runs once per *cluster*; the parallel Coordinator only for the clusters that cross
> a frozen threshold. Everything is Flash. The whole build fit inside a $150 credit
> without the budget alarm firing."

### 21 — Exploration and Discovery
Retrieval finds what you asked for; VIGIL finds what nobody asked for. That is the entire reason clustering is deterministic and unsupervised rather than a classifier over known hazard categories — a classifier can only ever return the taxonomy it was given, and emerging hazards are by definition outside it.

> **Writeup line:** "A search tool answers the question you knew to ask. VIGIL is built for the hazard nobody has named yet — which is why Stage 2 is unsupervised and has no LLM in it."

### 2 — Routing
The Stage 3→4 threshold gate is a router: it reads a risk score, compares it against frozen thresholds, and sends the cluster down the escalate path or the archive path. Calling it a gate hides that. Call it a **deterministic router** and note that the routing policy is read-only at runtime — the system cannot re-route itself into silence.

---

## Arguing the omissions

Omissions stated as decisions read as maturity. Omissions left silent read as gaps. Put these in the README and say the Planning one out loud in the video.

**6 — Planning.** VIGIL has no planner agent. Stage order is fixed in `pipeline/run_batch.py` and every branch point is plain Python. This is the deliberate trade: a dynamic planner would let the system re-sequence itself per batch, and would also mean no two runs are auditable against each other. In a safety-reporting system the run has to be reproducible before it is clever. Static orchestration, agents only where judgment is genuinely required.

> **Writeup line:** "Orchestration logic that can be plain Python *is* plain Python. We use nine agents and zero planners — because an investigator has to be able to ask why this cluster escalated last Tuesday and get the same answer today."

**10 / 15 — MCP and A2A.** VIGIL is a single-tenant batch pipeline with one human approver; there is no second organisation's agent to talk to and no external tool surface to expose. Both are named as future work: an MCP server over the cluster and brief store would let an investigator's own tooling query VIGIL's findings directly.

**17 — Reasoning Techniques.** Present inside prompts, not architecturally distinct. Claiming it would be padding.

---

## Where to spend these lines

| Surface | What goes there |
|---|---|
| README architecture section | The full coverage table above, plus the Planning omission paragraph |
| Devpost description | The three free-win writeup lines, verbatim |
| Devpost "findings & learnings" | The Planning trade-off + the three real failures in `docs/DEVPOST_DRAFT.md`. **Not** the caught-reward-hack story — it never happened. |
| Video (~4 min) | One sentence only: the Planning omission. It is the strongest architecture line available and it takes eight seconds |

---

## Standing rule

This file changes vocabulary, not architecture. If a future session proposes building a new agent "to cover pattern N," that is scope creep against a fixed deadline — check it against the cut list in `BUILD_PLAN.md` first. (The Aug 27 Day-7 gate this rule referenced has passed — see `docs/GATE_DECISION.md`; the full build shipped.) The only candidate ever worth reconsidering is a genuine Routing branch (hazard type → Precedent query strategy), and there is no longer time for it.
