# Stage Three bonus posts — ready to paste

Two items, **+0.2 each**, from `SUBMISSION.md`'s bonus section:

1. A public build-story post (dev.to / Medium / YouTube) that **must include a
   line stating it was created for entering this hackathon**.
2. A social post on LinkedIn or X carrying **#AllThingsAgentic**.

> **Check the exact required wording against the live rules page before posting.**
> `SUBMISSION.md` paraphrases the requirement as "the required line that it was
> created for entering this hackathon". The declaration line below satisfies that
> reading, but the rules page is the authority and this is +0.2 riding on one
> sentence.

Every number below was re-verified against a committed file on 2026-08-30 —
`eval/runs/*.json` for the metrics, `artifacts/demo_run.json` for the run counts,
`docs/PHASES.md` for the harness details (the "200 trials" figure lives there,
not in the JSON). Nothing here is rounded in our favour.

---

# Post 1 — build story (dev.to / Medium)

**Suggested title:** *Three things my AI safety system got wrong, and why I shipped the numbers anyway*

**Suggested subtitle:** *Building VIGIL: an aviation hazard triage pipeline on Gemini, ADK and Cloud Run — where the interesting part was the failures.*

**Tags:** `ai`, `googlecloud`, `python`, `machinelearning`

---

NASA's Aviation Safety Reporting System takes in more than 100,000 confidential
safety reports a year. Every one is read by two expert analysts within three
working days. When a pattern is confirmed, ASRS issues an Alert Message to the
organisation that can actually fix it.

That process works. It just doesn't scale to every safety-critical intake queue
that has the same shape — rail, medical devices, energy — where reports pile up
and the pattern across forty of them surfaces months later in a quarterly review.

I spent eleven days building **VIGIL**, a multi-agent system that mirrors that
triage workflow on public ASRS data: cluster reports into emerging hazard
patterns, score each pattern against a frozen risk policy, and for the severe
ones, fan out parallel agents to draft a source-cited investigator brief. A human
approves every output. The system never sends, files, or actions anything.

The build went fine. What I want to write about is the three things that went
wrong, because they were more instructive than anything that worked — and because
I decided to put all three in the submission rather than quietly fix the numbers.

## 1. My citation gate was checking that claims *looked* sourced

The core safety guarantee is simple: every factual claim in a brief must cite a
report ID (an ACN), and a deterministic pass strips any claim that doesn't. It
runs after the LLM critic, and it runs even if the critic call died — so the
guarantee never depends on a model having cooperated.

Then I read a brief. The Risk Assessment section cited `[ACN 1000001]` through
`[ACN 1000005]`.

The cluster's actual members were 1044401, 1461959, 1640441, 1748192 and 1799467.
I checked the source data: ACNs 1000001–1000005 appear in **none** of the 38,655
reports. The model had invented a tidy placeholder sequence, and my gate had
waved it through.

The bug was one regular expression. The gate matched `\[ACN\s+\d{4,}\]` — any
bracketed number with four or more digits. It was enforcing *shape*, not
*provenance*.

And the root cause was mine, not the model's. I had told the Risk agent to cite
"the ACNs supplied with the cluster" while the message I actually built for it
supplied a member *count* and no ACNs at all. Asked to cite sources it had never
been given, it produced the most plausible-looking thing available.

The part worth internalising: **a fabricated citation is worse than a missing
one.** An uncited claim gets stripped and disappears. A fabricated one survives,
carrying false authority, and an investigator who pulls that ACN gets an
unrelated report. The failure mode I had defended against was strictly less
dangerous than the one I had created.

The gate now takes an allow-list of ACNs that genuinely exist in the run, and
removes invalid citations surgically — a claim keeps its real sources and loses
only the invented ones. Artifact construction now fails outright if a brief cites
an ACN the run can't resolve, so an uncheckable citation can't reach a reviewer
at all.

Measured afterwards on 400 seeded claims across 200 trials: **1.000 catch rate**
for both uncited claims and fabricated-but-well-formed ACNs. The number I care
about more is the control — **1.000 retention** of correctly cited claims, because
a gate that simply deleted everything would also score a perfect catch rate.

## 2. My LLM extractor lost to a baseline with no model in it

I built an offline self-improvement loop: score the current extractor prompt on a
dev sample, let an evaluator agent read the failures and propose a revision, score
the candidate, run anti-reward-hacking guards, and only then consult a locked
holdout for the promote-or-discard decision.

Before trusting any of that, I scored it against a majority-class-plus-keyword
baseline. Standard practice, and I nearly skipped it.

| | dev macro-F1 |
|---|---|
| majority-class + keyword baseline | 0.0515 |
| my hand-written v1 extractor | **0.0056** |

My prompt was roughly nine times worse than a heuristic with no model in it at
all. It was emitting free-text paraphrases — "Approach", "Takeoff" — against a
closed ASRS coded vocabulary where the real value is "Initial Approach". Nothing
matched.

The loop found the cause I'd missed: v1 never told the model the labels were a
*closed vocabulary*. The revision did.

| | dev macro-F1 | holdout macro-F1 |
|---|---|---|
| baseline | 0.0515 | — |
| v1 | 0.0056 | 0.0081 |
| v2 (promoted) | **0.4099** | **0.4219** |

The holdout gain (+0.4139) exceeded the dev gain (+0.4043) — the opposite of
overfitting, and the strongest evidence the loop fixed a real defect rather than
memorising the sample.

Report the baseline. Without that 0.0515 row, "0.41 macro-F1" is a number with
nothing to lean on, and "we improved 73×" is a sentence that means nothing.

## 3. A guard fired, and the guard was the thing that was wrong

On an early run, a guard called `label_diversity_not_collapsed` blocked the
revision. For about ten minutes I thought I had the perfect story: my loop caught
its own agent gaming the metric.

It hadn't. The guard was buggy.

Diversity was computed as `distinct_predicted / distinct_expected`, which rewarded
v1's free-text sprawl — 19 unique strings over 8 reports, scoring 2.33 — and
punished a correctly vocabulary-constrained candidate scoring 1.00. It was
measuring the disease as health.

I replaced it with in-vocabulary label coverage, bounded to [0,1], which actually
tightens the guard against the hack it was written for: predicting one label
everywhere on an 18-class field now scores ~0.06, well under the 0.15 floor.

Then I wrote the whole thing down in the progress log, because *"we changed a
tripwire immediately after it blocked us"* is precisely the sequence of events
that needs an audit trail — whatever the justification, and especially when the
justification is good.

## The one I couldn't fix

The clustering is bad, and I'm reporting it that way.

| Clustering vs NASA's own anomaly taxonomy (4,998 reports) | |
|---|---|
| Purity | 0.301 (majority-class baseline 0.219) |
| Adjusted Rand | 0.0018 |
| Noise fraction | **0.837** |

I had predeclared a tripwire at `noise_fraction < 0.40`. I hit 0.837 — 84% of
reports unclustered, more than double my own limit. The guard existed in code but
had only ever been wired to the extractor loop, so nothing had checked it against
the stage it was written for until I ran it.

I could have tuned the clustering parameters until it passed. With no held-out
check on that stage, hours before a deadline, that is *exactly* the behaviour the
rest of the system exists to prevent. Tuning until the tripwire stops ringing is
not passing the test; it's removing it.

So the number stands. What I changed instead was what happens to the reports
clustering fails on. An 84% noise fraction is only a safety problem if noise means
*discarded* — so it no longer does. Every unclustered report is still checked
against the frozen severe-outcome vocabulary, and the **1,328** that match are
routed to their own analyst queue with their evidence attached. They get no name,
no risk score and no brief, because one report is not a pattern and dressing it up
as one would be the same overreach in a different costume.

That doesn't make the clustering better. It makes its failure non-silent, which
is a smaller and more honest claim.

## The actual thesis

Every other demo shows what the agents *can* do. VIGIL's headline feature is what
they are structurally forbidden from doing:

- **No LLM call can reach the clustering stage.** It's embeddings plus seeded
  HDBSCAN, deterministic and reproducible. A test asserts the module contains no
  model client at all.
- **The risk thresholds are frozen.** `config/frozen.yaml` is loaded read-only and
  no agent — including the self-improvement loop — has a code path to it. A safety
  system that quietly lowers its own alerting threshold is an audit failure.
- **The holdout is locked**, chmod 0444, read by exactly one module, and consulted
  only after the candidate prompt is already fixed.
- **The gate has no exception for a human.** A reviewer can edit a draft before
  approving — and the same citation gate runs on their edit. The privileged
  reviewer is the most plausible person to smuggle an unsourced claim into a
  safety document, so they're the last person who should get an exemption.
- **The human gate is terminal.** There is no auto-approve flag, and adding one is
  a prohibited change in the repo's own guardrails.

Restraint as a mechanism, not a disclaimer in a README.

Built solo in eleven days on **Gemini 3.7 Flash**, the **Google Agent Development
Kit** (Python), **Cloud Run** and **Firestore**, on public NASA ASRS data. The
repo is public and `eval/runs/` is committed, so every number above can be checked
against the JSON that produced it — including the ones I'd rather not have
published.

- Live: https://vigil-ui-715230861973.us-central1.run.app
- Code: https://github.com/sushrutb17/vigil

*This project was created for entry into the All Things Agentic Hackathon.*

---

# Post 2 — social (LinkedIn)

> Paste as-is. Attach `docs/architecture.png`, or a screenshot of the live UI
> showing the hazard queue.

I spent 11 days building an AI system for aviation safety triage, and the most
useful thing I can tell you about it is what it got wrong.

VIGIL ingests public NASA ASRS safety reports, clusters them into emerging hazard
patterns, and drafts source-cited investigator briefs for the severe ones. A human
approves everything. It never sends or files anything itself.

Three failures I found — and shipped, rather than quietly fixed:

→ My citation gate was validating that claims *looked* sourced, not that they were.
A model invented five report IDs that exist in none of the 38,655 real reports, and
the gate kept them. A fabricated citation is worse than a missing one: the missing
one gets stripped, the fabricated one survives carrying false authority.

→ My hand-written extractor prompt scored 0.0056 macro-F1 against a
majority-class baseline's 0.0515 — nine times worse than a heuristic with no model
in it. The self-improvement loop found the reason I'd missed and took it to 0.42,
and the gain held on a holdout the loop isn't allowed to read.

→ 84% of reports end up unclustered, against a 0.40 tripwire I set myself. I
didn't tune the parameters until it passed. Tuning until the alarm stops ringing
isn't passing the test, it's removing it. The number is in the submission.

The thesis: every other demo shows what the agents can do. This one's headline
feature is what they're structurally forbidden from doing — no LLM anywhere near
the clustering stage, risk thresholds no agent can rewrite, a locked holdout, and
a citation gate that has no exception even for the human reviewer.

Built on Gemini, Google ADK, Cloud Run and Firestore. Repo and eval ledgers are
public, so every number above can be checked against the JSON that produced it.

Live: https://vigil-ui-715230861973.us-central1.run.app
Code: https://github.com/sushrutb17/vigil

Created for entry into the All Things Agentic Hackathon.

#AllThingsAgentic

---

## X / Twitter variant (if you post there instead or as well)

> Thread opener, then the three failures as replies. Keep #AllThingsAgentic on
> the first post so it's attached to the thread root.

**1/** I spent 11 days building an AI system for aviation safety triage. The most
useful thing I can tell you is what it got wrong — and why I shipped the numbers
instead of fixing them quietly. 🧵 #AllThingsAgentic

**2/** My citation gate checked that claims *looked* sourced, not that they were.
A model invented 5 report IDs existing in none of the 38,655 real ones. The gate
kept them. A fabricated citation is worse than a missing one — the missing one
gets stripped, the fake one survives carrying authority.

**3/** My hand-written extractor scored 0.0056 macro-F1. A majority-class baseline
scored 0.0515. My LLM prompt was 9× worse than a heuristic with no model in it.
The self-improvement loop found why and took it to 0.42 — and the gain held on a
holdout the loop can't read.

**4/** 84% of reports end up unclustered, against a 0.40 tripwire I set myself. I
didn't tune the parameters until it passed. Tuning until the alarm stops ringing
isn't passing the test, it's removing it. The number is in the submission.

**5/** The thesis: every other demo shows what the agents can do. This one's
headline feature is what they're *forbidden* from doing. No LLM near the
clustering stage. Frozen risk thresholds. Locked holdout. A citation gate with no
exception even for the human.

**6/** Built solo on Gemini, Google ADK, Cloud Run + Firestore, on public NASA
ASRS data. Repo and eval ledgers public — every number checkable against the JSON
that produced it.
Live: https://vigil-ui-715230861973.us-central1.run.app
Code: https://github.com/sushrutb17/vigil
