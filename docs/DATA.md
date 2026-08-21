# VIGIL Data Reference

## Source
- HF dataset: **`elihoole/asrs-aviation-reports`** — 47,723 NASA ASRS incident reports, Apache-2.0, English
- Use the **Parquet exports** (`refs/convert/parquet`): train 38.7k (51 MB) / test 4.8k / validation 4.3k
- Underlying data is NASA ASRS (voluntary, confidential, de-identified reports; 1988→~2022). Public data; safe for a public Devpost repo. Credit both NASA ASRS and the HF dataset in the README.

## Split policy (do not deviate)
- **train** → corpus for clustering, precedent RAG, and the live demo batches
- **validation** → dev set for the self-improvement loop (extractor iteration)
- **test** → **LOCKED HOLDOUT.** Copied once to `data/holdout/`, read only by `eval/holdout_score.py`. Never in a prompt, never in an example, never eyeballed for prompt ideas.

## Schema: 111 columns, all strings (cast numerics on load). The ones that matter:

| Column | Role |
|---|---|
| `acn_num_ACN` | Primary key; the citation unit for briefs |
| `Report 1_Narrative` | Main free text → extraction + embedding input |
| `Report 2_Narrative` | Second reporter, **same event** → labelled dedup pairs, free |
| `Report 1.2_Synopsis` | NASA expert summary → brief/summary eval ground truth (ROUGE + coverage) |
| `Report 1.1_Callback` / `Report 2.1_Callback` | Analyst follow-up notes → precedent RAG enrichment |
| `Events_Anomaly` | Coded event type(s), `;`-separated → cluster purity labels |
| `Assessments.1_Primary Problem` | Root-cause label → extractor eval target |
| `Assessments_Contributing Factors / Situations` | Multi-label → extractor eval target |
| `Person 1.7_Human Factors` | e.g. `Confusion; Situational Awareness` → extractor eval target |
| `Aircraft 1.2_Make Model Name` | Aircraft type → cluster facet |
| `Aircraft 1.9_Flight Phase` | Landing / Cruise / etc. → cluster facet |
| `Component_Aircraft Component` | e.g. `Throttle/Power Lever` → cluster facet |
| `Events.5_Result`, `Events.1_Miss Distance` | Severity inputs for risk scoring |
| `Time_Date` | `YYYYMM` string → trend slope (parse to period) |

## Known quirks (handle in `pipeline/ingest.py`)
1. **Anonymized locations:** `ZZZ.Airport` etc. → airport-level trends are impossible; cluster on type × phase × component instead. Never present a ZZZ facet in the UI.
2. Multi-value cells are `;`-separated → split to lists on load.
3. Large block of `(UAS)` drone columns, mostly empty for airline reports → drop at ingest.
4. Empty string ≠ null → normalize `"" → None`.
5. `Report 2_*` present only when a second reporter filed → presence itself is the dedup label.
6. Coverage ends ~2022 → demo framing is "replay a historical week/quarter," never "live feed."
7. Narratives use ASRS abbreviations (FO, PM, EICAS…) → keep a small expansion map for UI display only; embed the raw text.

## Demo slice
For the recorded demo: one deterministic slice (e.g. 5k train reports, fixed seed) named "this quarter's intake." Full-corpus run is a stretch goal, not the demo path.
