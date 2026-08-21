# VIGIL × Agentic Design Patterns

Reference: Antonio Gulli, *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* (Springer, free release). Gulli is a Google engineering director; the book's examples are ADK/Gemini. It is the closest thing to a house pattern vocabulary inside Google's agent ecosystem — which is why it is worth speaking it back at a Google-judged hackathon with a **Best Architectural Design** side prize.

**Why this file exists:** VIGIL already implements ~14 of the 21 patterns. It does not have a design gap; it has a naming gap. This file closes the naming gap and fixes the language used in the README, the Devpost description and the video.

**What this file must not do:** grow the build. `BUILD_PLAN.md` is ~48h against ~45h capacity and already carries a cut list. Nothing below is a new milestone. If a pattern is not already in the architecture, the correct action is a sentence in the writeup, not a new agent.

---

## Coverage map

Legend — **✅ built** (in the architecture today) · **🏷️ name it** (built, currently unnamed — free points) · **⛔ omitted by design** (argue for it, don't hide it) · **➖ n/a**

| # | Pattern | Status | Where in VIGIL |
|---|---|---|---|
| 1 | Prompt Chaining | ✅ | `SequentialAgent`: Extractor (1a) → Dedup (1b) |
| 2 | Routing | 🏷️ | Stage 3→4 threshold gate against `config/frozen.yaml` — a deterministic router, currently described as a gate |
| 3 | Parallelization | ✅ | Stage 4 `ParallelAgent`: Precedent ∥ Risk ∥ Brief Writer |
| 4 | Reflection | ✅ | Critic reviews the brief, bounces once, cap enforced |
| 5 | Tool Use | ✅ | Clustering, embeddings, citation regex as plain Python tools |
| 6 | Planning | ⛔ | **Deliberate.** Orchestration is static Python, not a planner agent. See "Arguing the omissions" |
| 7 | Multi-Agent Collaboration | ✅ | Coordinator + 3 sub-agents; 9 agents total |
| 8 | Memory Management | ✅ | Firestore `reports/`, `clusters/`, `escalations/` (idempotency), `rejections/` (negative few-shot into future Analyst prompts) |
| 9 | Learning and Adaptation | ✅ | Offline extractor self-improvement loop; promotion gated on holdout + guards |
| 10 | Model Context Protocol | ⛔ | Single-tenant batch system. Future work |
| 11 | Goal Setting and Monitoring | 🏷️ | Risk score *is* the objective function; `agent_log/` is the monitor. Fold into the Evaluation story rather than claiming separately |
| 12 | Exception Handling and Recovery | ✅ | Retries + backoff, one JSON repair attempt, `failed` records don't kill the batch, DEGRADED brief on sub-agent loss, resumable by ACN key |
| 13 | Human-in-the-Loop | ✅ | Terminal human gate. Nothing is ever auto-actioned |
| 14 | Knowledge Retrieval (RAG) | ✅ | Precedent agent over the training corpus |
| 15 | Inter-Agent Communication (A2A) | ⛔ | No cross-org agents. Future work |
| 16 | Resource-Aware Optimization | 🏷️ | Flash everywhere except Brief Writer; batched embeddings; cosine pre-filter before the LLM dedup judge; budget alert at $50 |
| 17 | Reasoning Techniques | ➖ | Implicit in agent prompts. Don't claim it separately |
| 18 | Guardrails / Safety | ✅ | Immutable `frozen.yaml`; mandatory ACN citation; `eval/guards.py` reward-hack tripwires; sacred `data/holdout/` |
| 19 | Evaluation and Monitoring | ✅ | `EVAL.md` in full: ground-truth metrics, baselines, guards, runs ledger, `agent_log/` |
| 20 | Prioritization | ✅ | Clusters ranked by severity × frequency × trend; only the top band escalates |
| 21 | Exploration and Discovery | 🏷️ | HDBSCAN surfacing **unnamed, emerging** hazards nobody queried for. This is the product thesis, currently written up as plumbing |

**Score to quote: 14 built + 4 named = 18 of 21, with 3 omitted deliberately.** Do not round this up. The omissions are the credible part.

---

## The three free wins

Doc-only. No code. Highest return per minute in the whole build.

### 16 — Resource-Aware Optimization
You do this well and never say it. Every model choice in VIGIL is a cost decision: Flash for eight agents, Pro reserved for the one job where prose quality is the deliverable; embeddings batched; a cheap cosine pre-filter so the LLM dedup judge only ever sees candidate pairs instead of the O(n²) cross-product. Judges reward visible cost discipline, and it is currently invisible.

> **Writeup line:** "Nine agents, one Pro call path. The dedup judge never sees the O(n²) pair space — a cosine pre-filter cuts it to candidates first. Whole demo corpus runs inside a $150 credit with the budget alarm never firing."

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
| Devpost "findings & learnings" | The Planning trade-off + the caught-reward-hack story from `EVAL.md` |
| Video (~4 min) | One sentence only: the Planning omission. It is the strongest architecture line available and it takes eight seconds |

---

## Standing rule

This file changes vocabulary, not architecture. If a future session proposes building a new agent "to cover pattern N," that is scope creep against a fixed deadline — check it against the cut list in `BUILD_PLAN.md` first. The only candidate ever worth reconsidering is a genuine Routing branch (hazard type → Precedent query strategy), and only if the **Day-7 gate on Aug 27 clears ahead of schedule**.
