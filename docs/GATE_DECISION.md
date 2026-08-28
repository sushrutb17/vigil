# Day-7 Gate Decision

BUILD_PLAN.md called for this decision on Thu Aug 27. It's being made on Fri Aug 28
evening instead, after the fact — see `PROGRESS.md` for how the timeline actually
went (most of the pipeline was built in one sitting on Aug 21, then untouched).

## Decision: ship the full build

**Options considered** (per BUILD_PLAN.md):
- Full build: coordinator fan-out (Precedent ∥ Risk ∥ Brief Writer), Firestore
  idempotency, Critic with citation gate, Streamlit UI.
- Cut to floor: Brief Writer only, no parallel fan-out.

**Chosen: full build.** Both options already exist as working code as of tonight's
verification (14/14 tests pass, lint clean, demo runs end-to-end on the bundled
fixture). Cutting to the floor now would mean deleting and un-testing code that
already works, not saving remaining time. The actual bottleneck for the last 3 days
is not feature scope — it's making the build public (GitHub), real (actual ASRS
data), and live (real GCP: Firestore instance, Cloud Run deploy, live Gemini calls).
Those are true regardless of which scope option was chosen, so scope-cutting buys
nothing here.

**Demo slice size:** not yet finalized — decide when real data is downloaded and the
EDA pass is done (open item in PROGRESS.md).

**Scale-up (10k? full train?):** deferred until after a real-data pipeline run
confirms timing/cost; default to the smaller demo slice unless there's clear
headroom in both time and the $150/$50-alert credit budget.

## What this does NOT change

The cut list in BUILD_PLAN.md still applies if something breaks between now and
Aug 31 — Gemma bonus first, then UI polish, then loop iterations, then the Precedent
agent, then (last resort) the whole parallel fan-out. This decision just says: don't
preemptively cut something that already works.
