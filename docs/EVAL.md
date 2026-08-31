# VIGIL Evaluation Protocol

Why this file exists: almost no hackathon entry has ground truth. We do. Measured numbers are our credibility weapon — and unmeasured self-improvement is theatre. Every claim in the video traces to a number produced by code in `eval/`.

> **Status as of 2026-08-29 — which of these actually ran.** This file is the
> *protocol*; it was written Aug 20 and describes intent. Three of the five primary
> metrics have been run on real data, two have not. The results are in
> `eval/runs/*.json` (committed) and summarised in the README.
>
> | Metric | Ran? | Result |
> |---|---|---|
> | Extractor field accuracy / macro-F1 | ✅ | v1 **0.0056** → promoted v2 **0.4099** dev, **0.4219** holdout; baseline 0.0515 |
> | Clustering purity + ARI + noise | ✅ | purity **0.301** (baseline 0.219), ARI **0.0018**, noise **0.837** — ⚠ **breaches the < 0.40 guard below** |
> | Critic uncited-claim catch rate | ✅ | **1.000** catch, **1.000** retention of valid claims |
> | Dedup precision/recall | ❌ | Never run — the Dedup stage was cut from the operational path |
> | Brief ROUGE-L + factual coverage | ❌ | Never run. Do not quote a number for it |
>
> Regenerate the deterministic ones with `make eval-offline`; the extractor loop with
> `make improve` (601 live calls).

## Primary metrics

| Component | Metric | Ground truth |
|---|---|---|
| Extractor | Field-level accuracy / F1 (primary problem, contributing factors, human factors, phase, component) | ASRS coded columns |
| Dedup | Precision/recall on same-event pairs | `Report 2_Narrative` presence (positives) + random cross-event pairs (negatives) |
| Clustering | Purity + Adjusted Rand vs `Events_Anomaly`; report noise fraction | Coded anomaly labels |
| Brief / summary | ROUGE-L vs expert synopsis **+ factual coverage** (fraction of synopsis facts present, judged by a Flash grader with fixed rubric) | `Report 1.2_Synopsis` |
| Critic | % uncited claims caught (seed briefs with deliberate uncited claims) | Synthetic injection |

## Guard metrics — reward-hacking tripwires
Every promoted prompt revision must not degrade these. `eval/guards.py` runs them automatically and refuses promotion on violation.

| Optimized metric | Known hack | Guard |
|---|---|---|
| Cluster purity | Shrink clusters until purity is trivially high | Cluster count in sane band; median cluster size ≥ 5; noise fraction < 40% |
| ROUGE-L | Mimic synopsis phrasing without content | Factual coverage must not drop; length within ±40% of synopsis |
| Extractor accuracy | Predict the majority label everywhere | Per-class F1 floor (macro-F1, not just accuracy) |
| Dedup recall | Merge everything | Precision floor 0.9 |

**Demo beat — this did NOT happen, and must not be claimed.** The plan was to keep
one loop iteration where a revision gamed a metric and a guard caught it. Across the
runs actually performed, no revision ever gamed a metric. One guard *did* fire, and
on inspection the guard's own metric was wrong — it measured raw output diversity, so
it rewarded the incumbent's free-text sprawl and punished a correctly
vocabulary-constrained candidate. We fixed the metric to in-vocabulary coverage,
which made the guard *stricter*, and wrote the episode up in `PROGRESS.md` because
changing a tripwire right after it blocks you is the move that most needs an audit
trail.

The honest substitute, which is about the safety mechanism rather than the model:
**the citation gate was validating shape instead of provenance** and kept five
fabricated ACNs (`1000001`–`1000005`) that exist in none of the 38,655 reports. That
is a real caught failure, it is documented, and `eval/runs/` is committed so a
reviewer can check everything here.

⚠ **Guard status:** the `noise_fraction < 0.40` tripwire below is currently
**breached** — measured 0.837 on the real slice. `evaluate_guards` implements the
check but is only ever invoked on the extractor promotion loop, so nothing had run it
against the clustering stage it was written for. Left as a measured failure rather
than tuned under deadline; see `docs/PHASES.md`.

## Holdout protocol (non-negotiable)
1. `data/download.py` copies the HF **test** split to `data/holdout/` once; directory then treated as read-only.
2. Self-improvement iterates on **validation** only.
3. `eval/holdout_score.py` is the only reader of holdout; it runs at promotion decisions and once at the end for headline numbers.
4. Report both dev and holdout numbers side by side. A big gap = overfitting to dev; say so honestly in the writeup — honesty here reads as engineering maturity.

## Baselines (so the numbers mean something)
- Extractor baseline: majority-class + keyword rules.
- Clustering baseline: KMeans (k = # anomaly categories) on TF-IDF.
- Report deltas over baselines, not raw scores alone.

**Both baselines have now been run, and both were informative in an uncomfortable
way.** The majority-class + keyword extractor baseline (0.0515 macro-F1) *beat* the
hand-written v1 extractor (0.0056) by roughly 9×, which is the only reason we knew v2
was a repair rather than a triumph. The clustering purity baseline — the score a
single undifferentiated blob would get — is 0.219 against our 0.301. Baselines are
what turn both numbers into meaning.

## Runs ledger
Every eval run → `eval/runs/<timestamp>-extractor.json` (prompt version, split, metrics, guards, pass/fail) or `<timestamp>-offline.json` (clustering + Critic). **Committed to the repo** via a deliberate `.gitignore` exception, so a reviewer can check any number in the README against the run that produced it. The improvement curve in the video is generated from this ledger — never hand-drawn.
