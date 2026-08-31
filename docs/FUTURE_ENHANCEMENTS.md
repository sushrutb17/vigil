# VIGIL — Future Enhancements

*Written 2026-08-29 from a full review of the shipped system (code, deployed
services, and the measured eval results in `PHASES.md`). Ordered by value to the
**end user** — the safety analyst who opens the triage queue, reviews escalated
hazard clusters, and approves/rejects/carries briefs onward — not by
implementation convenience. Each item says what the user gets, what exists today,
and a concrete build sketch. Items marked ⚠ address a measured failure rather
than adding a feature.*

*Nothing here changes the project's guardrails. Where an enhancement touches one
(the human gate, the frozen policy, the extractor-only improvement loop), the
item says explicitly how the guardrail is preserved.*

---

## Tier 1 — Highest analyst value

### 1. ⚠ A "severe but unclustered" queue — stop silently dropping 84% of reports

**The gap, in user terms.** The measured noise fraction is **0.837** (breaching
the project's own declared `noise_fraction < 0.40` guard — see the 🚫 row in
`PHASES.md` Phase 3). Concretely: on the 5k slice, 4,182 of 4,998 reports fall
into HDBSCAN noise and **never appear anywhere in the UI**. A one-off
catastrophic report — the kind ASRS exists to catch — is invisible to the
analyst if no similar reports arrived the same batch. Clustering is the lens,
but right now it is also the filter.

**What the user gets.** A second sidebar section, "Severe singletons," listing
noise-labelled reports whose `results`/`anomaly_labels` intersect the frozen
policy's `severe_results`/`severe_events` sets — the exact deterministic check
`pipeline/risk.py::score_cluster` already performs per cluster, applied
per report. No LLM calls, no new policy knobs, no threshold tuning: the frozen
severity vocabulary is reused read-only.

**Build sketch.** `run_batch.py` already keeps noise assessments (the UI filters
`noise-*` cluster ids out). Emit a per-report severity flag during triage,
carry it into the artifact, render a third queue section in
`ui/streamlit_app.py::_sorted_choices`. Roughly a day, fully deterministic,
testable offline.

**Why this stands out.** It converts the project's most visible measured failure
into a designed-for property: "clustering surfaces *patterns*; a deterministic
severity check surfaces *outliers*; nothing severe is dropped on the floor."
That is a stronger story than quietly tuning `min_cluster_size` until the guard
passes — which `HANDOFF.md` correctly identifies as the reward-hack this project
is built to resist.

### 2. Show the evidence: ACN click-through to the source narrative

**The gap.** The citation gate proves every cited ACN **exists** (provenance,
1.000 measured catch rate). But the analyst cannot check a citation is
**relevant** without leaving the tool and searching the ASRS database by hand.
Today the UI shows a bare comma-separated ACN list in an expander
(`streamlit_app.py:153-154`) and briefs full of `[ACN 1234567]` markers that go
nowhere.

**What the user gets.** Click (or select) any cited ACN → the report's narrative
excerpt, date, flight phase, and anomaly labels in a side panel. Trust in a
draft brief comes from spot-checking two or three citations; making that a
5-second action instead of a context switch is the single biggest UX win
available.

**Build sketch.** The artifact currently stores only `member_acns`. Add a
per-cluster `evidence` map (ACN → first ~500 chars of narrative + key coded
fields) when writing `artifacts/demo_run.json` and the Firestore `clusters/`
doc. Render with `st.expander` per ACN or a `st.selectbox` + detail pane.
Narrative text is already in the parquet; no model calls. Watch artifact size —
cap the excerpt, not the ACN count.

### 3. Edit-before-approve, and a required rejection reason

**The gap.** The human gate is binary: Approve or Reject, wholesale
(`streamlit_app.py:164-175`). Real analysts amend drafts — soften a claim, cut a
recommendation, fix a hazard name. Today their only option for a 90%-right brief
is Reject (losing it) or Approve-then-edit-offline (losing the record of what
they changed). And Reject stores the cluster payload but **no reason**, which
undercuts the stated purpose of `rejections/` as negative examples for future
prompt revision — a bare rejected brief teaches a future Evaluator almost
nothing; "rejected because the risk section overstates severity" teaches it
exactly the right thing.

**What the user gets.**
- An editable draft (`st.text_area` seeded with the brief) whose edited version
  is what Approve persists and Download exports — with **both** versions stored
  (`brief_draft`, `brief_approved`), so the diff is an audit record of human
  judgment.
- A short free-text "reason" field required on Reject, stored in the
  `rejections/` doc.

**Guardrail check.** #6 untouched — the human still carries the brief onward;
VIGIL still sends nothing. The citation gate should re-run on the edited text
before persisting, so a human edit cannot accidentally introduce an uncited
claim into the system of record — the gate applies to everyone, which is itself
a good demo beat.

### 4. Hazard identity across weeks — real trend, not within-batch trend

**The gap.** The system is deployed as a **weekly** Cloud Scheduler job, but
each run's clusters are born fresh; only the escalation ledger (member-set
Jaccard) links runs, and only to *suppress* re-alerts. The trend component of
the risk score (`risk.py::_trend_score`) is computed from report dates *within
one batch*. The question an analyst actually asks — "is this hazard growing?" —
is unanswerable today.

**What the user gets.** A persistent hazard identity: when a new cluster
overlaps a previous one (the Jaccard machinery already exists in
`pipeline/store.py::previously_escalated`), link it to the same `hazards/` doc
and append a `(run_date, member_count, risk_total)` point. The UI then shows a
per-hazard history line — "3rd consecutive week, 12 → 19 → 31 reports" — which
is a far stronger escalation signal than any single-batch score. This also
subsumes the ⬜ "trend sparkline" stretch item in `PHASES.md` Phase 6 with
data worth sparkline-ing.

**Guardrail check.** Display only. The frozen risk weights and threshold are
not touched; cross-run growth is shown to the human, not fed back into the
score, unless a future `frozen.yaml` **version** (see item 9) deliberately adds
it.

---

## Tier 2 — Signal quality (the pipeline's honesty debt)

### 5. ⚠ Re-measure clustering with real Gemini embeddings, against the guard

**The gap.** The measured clustering numbers (purity 0.301, ARI 0.0018, noise
0.837) come from the TF-IDF fallback path. `pipeline/embeddings.py` has a
verified live `gemini-embedding-2` call (3072-dim), but the batch path has never
been *evaluated* on real embeddings. Semantic embeddings plausibly move all
three numbers on narrative text where TF-IDF sees only vocabulary overlap.

**How to do it honestly** (this is the part that matters): decide the evaluation
protocol **before** looking at results — embed the 5k slice once (batched, ~5k
embedding calls, cheap), run `make eval-offline` on the embedding-based
clustering, and report the numbers whatever they are, next to the TF-IDF
numbers. If noise fraction still breaches 0.40, the guard threshold argument
(`HANDOFF.md` option b: most ASRS reports genuinely are one-offs) can then be
made from two independent representations instead of one. Do **not** iterate
`min_cluster_size` against the guard on the same slice — that is the tuning
loop the project explicitly refused hours before deadline, and it does not
become legitimate after the deadline without a held-out slice.

### 6. Precedent as real retrieval over the full corpus

**The gap.** Precedent currently filters same-batch, same-component candidates
(`agents/orchestrate.py::_precedent_candidates`) — an explicit scope cut
(`ARCHITECTURE.md`, "Design intent that did not survive contact"). So a 2026
fume-event cluster cannot cite the 2019 fume events sitting in the other 33,655
reports. For an investigator, "has this happened before?" is *the* precedent
question, and today the honest answer is limited to this week's batch.

**What the user gets.** Precedent grounded in the full 38,655-report corpus:
top-k nearest reports by embedding, filtered to non-members, handed to the
existing Precedent agent as candidates. The citation gate's allow-list
(`strip_uncited_claims(allowed_acns=...)`) already accommodates out-of-cluster
citations — the plumbing for provenance is done; only retrieval is missing.

**Build sketch.** One-time embedding of the corpus into a Vertex AI Vector
Search index (or, at this scale, a flat numpy matrix + cosine top-k loaded from
GCS — 38k × 3072 floats is ~450MB in float32, ~110MB in int8; boring wins).
This is also the natural fix for the demo fixture's structurally-empty
Precedent section.

### 7. Extend the improvement loop to the Analyst — fueled by human decisions

**The gap.** Guardrail #7 restricts the offline loop to the extractor, enforced
by `REVISABLE == {"extractor"}`. The extractor result (v1 0.0056 → v2 0.4099
macro-F1) proved the loop works; but the extractor is not in the operational
path, so the loop currently improves the one prompt users never feel. The
Analyst's hazard names and statements — what the analyst reads first — are
"judged by reading their output, not by a metric" (`PHASES.md` Phase 3).

**What the user gets.** Briefs and hazard names that improve week over week
from *their own* Approve/Reject decisions. `rejections/` (especially with
reasons, item 3) plus approvals are exactly the labeled data the loop needs: an
offline eval where a candidate Analyst prompt is scored against
human-approved outputs, behind the same guard machinery (`eval/guards.py`), the
same run ledger (`eval/runs/`), and the same never-touches-`frozen.yaml`
constraint.

**Guardrail check.** This is a *deliberate, versioned* relaxation of #7, not a
drift: extend `REVISABLE` to `{"extractor", "analyst"}` in a commit that also
updates CLAUDE.md, keep the loop offline-only, and keep the Critic and Risk
agents out — the agents that *gate* content must never be optimized by the loop
that produces content. That asymmetry (generators improvable, judges frozen) is
worth stating in the README as a design principle; it generalizes.

### 8. Weekly Cloud Run job on real data

**The gap.** The deployed `vigil-batch` job runs the 6-report demo fixture
(`data/raw` is correctly excluded from the image); real-data runs are
local-only (`make run-live`). The ⬜ row exists in `PHASES.md` Phase 4. Until
this lands, the weekly Scheduler cadence, the NEW-THIS-RUN badge, and the
cross-week hazard history (item 4) all run on data that never changes — the
"living system" story is deployed but idling.

**Build sketch.** Upload the seeded 5k slice (or a rolling monthly slice) to a
GCS bucket; the job downloads it at startup (`google-cloud-storage`, a few
lines). Holdout stays out of the bucket entirely — guardrail #3 by
construction, not by ignore-file.

---

## Tier 3 — Trust, audit, and operations

### 9. Surface provenance in the UI: policy version, prompt version, agent log

**What.** Every number and sentence the analyst sees has machine-readable
provenance that today lives only in Firestore: `frozen.yaml`'s
`policy_version`, the active Analyst/extractor prompt version
(`config/prompts/*/active.yaml`), and `agent_log`'s per-call model/tokens/
latency. A small "Provenance" expander per cluster — *scored under policy v1;
brief drafted by gemini-3.7-flash on 2026-08-29, 1,289 tokens; citation gate:
0 claims removed* — turns the observability story into something the end user
(and an auditor) can see without a GCP console. Cheap: the data is already
logged; this is a read path.

**Corollary.** "N claims removed by the citation gate" per brief is currently
discarded. Showing it is honest in both directions: a brief where the gate cut
nothing earns more trust; one where it cut five lines tells the analyst to read
skeptically.

### 10. A notification digest that points, never sends content

**What.** The weekly job runs Monday 09:00, but nothing tells the analyst.
A digest (email via a human-configured channel, or even a Firestore-backed
"inbox" page) saying "VIGIL: 2 new escalations this run — open the triage
queue" with a link and **no brief content**. Guardrail #6 review: the rail says
VIGIL never *sends, files, or actions* reports — a content-free pointer to the
human gate arguably strengthens the gate (an unmanned queue is a gate no one
attends). Ship it only with that framing documented, and keep brief content out
of the message so nothing leaves the system unapproved even in summary form.

### 11. Resumable batch (finish the 🔶)

**What.** `put_report` already uses `setdefault`, but a re-run redoes
clustering and re-spends Analyst/Coordinator calls. Skip-before-reprocess
(check the escalation ledger and `clusters/` before calling the Analyst on an
unchanged member set) makes re-runs nearly free — which matters exactly when
the weekly job meets real data (item 8) and someone re-executes after a partial
failure. The Jaccard-overlap machinery to detect "unchanged cluster" already
exists.

### 12. Beyond ASRS: the same skeleton for any confidential reporting system

**What.** The architecture — deterministic ingest → no-LLM clustering → frozen
escalation policy → cited drafts → terminal human gate — is not aviation-
specific. Rail (C3RS), medical incident reporting, and industrial near-miss
systems share the shape: high-volume narrative reports, a severity taxonomy, an
overloaded human review queue, and a hard requirement that no machine files
anything. A thin adapter layer (report schema + severity vocabulary + citation
id format per domain) would make VIGIL a *pattern*, not a demo. This is the
long-term "stands out" story: the guardrails that read as hackathon discipline
are exactly the properties a regulated domain procures for.

---

## Explicitly not recommended

- **Auto-approve thresholds, "trusted cluster" fast paths, or any convenience
  flag around the human gate.** Guardrail #6 is the product.
- **Letting any loop touch `config/frozen.yaml`**, including a future Analyst
  loop (item 7). Policy changes are human commits with version bumps.
- **Tuning clustering parameters against the noise-fraction guard on the same
  data that showed the breach** (see item 5 for the honest protocol).
- **A Critic bounce loop.** Already considered and cut (`ARCHITECTURE.md`): the
  deterministic gate runs last unconditionally, which is the stronger
  guarantee; a bounce adds a model call without adding safety.

## Suggested order of attack (post-submission)

1. Severe-singleton queue (item 1) — one day, deterministic, converts the
   measured failure into a feature.
2. ACN evidence click-through (item 2) — one day, biggest single trust win.
3. Edit-before-approve + rejection reasons (item 3) — unlocks item 7's data.
4. Real-embedding clustering re-measurement (item 5) — settles the guard-breach
   question honestly.
5. Real-data weekly job + hazard history (items 8, 4) — makes the deployed
   system a living one.
6. Full-corpus precedent (item 6), Analyst loop (item 7), then Tier 3.
