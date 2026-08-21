# VIGIL Evaluation Protocol

Why this file exists: almost no hackathon entry has ground truth. We do. Measured numbers are our credibility weapon — and unmeasured self-improvement is theatre. Every claim in the video traces to a number produced by code in `eval/`.

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

**Demo beat:** deliberately keep one loop iteration where a revision gamed a metric and the guard caught it. Screenshot it. "We caught our own agent cheating" is worth more than a clean curve.

## Holdout protocol (non-negotiable)
1. `data/download.py` copies the HF **test** split to `data/holdout/` once; directory then treated as read-only.
2. Self-improvement iterates on **validation** only.
3. `eval/holdout_score.py` is the only reader of holdout; it runs at promotion decisions and once at the end for headline numbers.
4. Report both dev and holdout numbers side by side. A big gap = overfitting to dev; say so honestly in the writeup — honesty here reads as engineering maturity.

## Baselines (so the numbers mean something)
- Extractor baseline: majority-class + keyword rules.
- Clustering baseline: KMeans (k = # anomaly categories) on TF-IDF.
- Report deltas over baselines, not raw scores alone.

## Runs ledger
Every eval run → `eval/runs/<timestamp>.json` (prompt version, split, metrics, guards, pass/fail). The improvement curve chart in the video is generated from this ledger — never hand-drawn.
