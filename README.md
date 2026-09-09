# data-analysis-pipeline-agent

An agent that picks the *statistically correct* test for a two-group comparison by
actually running the assumption checks first — instead of defaulting to a t-test
and hoping the data cooperates.

Built for the **Agentic AI Hackathon** (Tech Zephyr 4.0, IIT Bhubaneswar).

## Problem statement

Given a raw dataset and a plain-English comparison question (e.g. "is there a
difference between group A and group B?"), most people either run an invalid
statistical test — skipping assumption checks entirely — or don't know which test
is appropriate in the first place. Choosing the wrong test (e.g. a Student's t-test
on non-normal or unequal-variance data) silently produces an unreliable p-value.

**Target users:** students, researchers, and analysts who need a quick, defensible
two-group comparison without first having to remember (or look up) which assumption
checks apply and which test each outcome implies.

## Why this needs to be agentic

The test that runs is decided by **live intermediate results**, not fixed code
order. A different assumption-check outcome provably changes which action runs
next — this is not a single LLM call summarizing the data, and it is not a
hardcoded script that always runs the same test:

| Condition | Action |
|---|---|
| Sample size < 5 per group | **ABORT** before running any checks — "insufficient sample size" |
| Normality check (Shapiro-Wilk) fails | Skip the variance check entirely — use **Mann-Whitney U** |
| Normality passes, variance check (Levene's) fails | Use **Welch's t-test** |
| Normality passes, variance check passes | Use **Student's t-test** |

Each row is a genuine branch: the *result* of one check determines whether the next
check even runs, and which of three different statistical tests gets executed. Feed
the same code path a different dataset and it provably takes a different route —
that live observe → decide → act → evaluate → adapt loop is the entire point of the
system, not incidental to it.

## Features

- **Dynamic test selection** — Student's t-test, Welch's t-test, or Mann-Whitney U
  is chosen at runtime from live Shapiro-Wilk and Levene's results, never hardcoded.
- **Live decision trail** — every step (`LOAD → CLASSIFY → VALIDATE_SIZE →
  CHECK_NORMALITY → CHECK_VARIANCE → SELECT_TEST → EXECUTE → REPORT`) is recorded
  as a structured record and shown in full, not just the final answer.
- **Visual adaptation highlighting** — the UI visually flags the exact moment a
  branch decision happens (`SELECT_TEST`) and the moment normality fails and the
  pipeline diverges from the default path (`CHECK_NORMALITY`), so the adaptation is
  visible, not buried in a log.
- **Offline-first** — zero external API dependency anywhere in the system.
- **Graceful handling of edge cases** — aborts cleanly with a clear reason on
  insufficient sample size, and asks for clarification rather than guessing when a
  question can't be confidently classified as a two-group comparison.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the full flowchart. In short:
a deterministic `agent/controller.py` state machine calls into `data/` for loading,
`agent/question_classifier.py` for question classification, and `core/` for every
statistical decision (sample size validation, normality/variance checks, test
selection, test execution) — no LLM is involved at any point in that chain.

## Tech stack

| Tool | Why |
|---|---|
| **Python** | Implementation language for the whole pipeline. |
| **scipy** | Well-established, peer-reviewed implementations of Shapiro-Wilk, Levene's, Student's/Welch's t-tests, and Mann-Whitney U — defensible under Q&A in a way a custom-written statistical routine would not be. |
| **pandas** | CSV loading and column validation. |
| **numpy** | The numeric array representation shared by scipy and pandas throughout the pipeline. |
| **Streamlit** | Fastest path to an interactive, demoable UI with no separate frontend build step — appropriate for a hackathon timeline. |

## Setup

This project uses [uv](https://github.com/astral-sh/uv) for virtual environment
management.

```bash
uv venv --python 3.11
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\Activate.ps1       # Windows (PowerShell)
uv pip install -r requirements.txt
```

## Running locally

```bash
streamlit run app.py
```

## Running tests

```bash
pytest tests/ -v
```

## Environment variables

**None required.** No API keys, no `.env` file — the entire system runs offline.
The only place a network dependency was ever considered (an LLM-assisted question
classifier) was deliberately rejected in favor of a fully deterministic,
keyword-based classifier; see [docs/decisions.md](docs/decisions.md) for why.

**No API keys, passwords, or credentials are committed to this repository, and
none are required to run it.**

## Known limitations

- Only two-group comparisons are actioned end-to-end. Multi-group and correlation
  phrasings are correctly *detected* by the question classifier but currently
  route to "needs clarification" rather than running a different analysis.
- Question classification uses a fixed keyword vocabulary. Phrasings outside that
  vocabulary are correctly flagged as unclear (never silently misclassified), but
  the system won't understand novel wording without a vocabulary update.
- No persistent history across sessions — each run is stateless, and results are
  not saved unless the user copies them out of the UI.

## Future work

- Multi-group ANOVA support, extending `test_selector.py`'s branch logic rather
  than replacing it.
- Effect size reporting (Cohen's d / rank-biserial correlation) alongside p-values,
  for practical as well as statistical significance.
- Visual normality plots (Q-Q plot / histogram) so a user can see, not just read,
  why a normality check passed or failed.

## Team

- **Tanya Sheemar** — `agent/` orchestration, `data/` loading, `app.py` (Streamlit
  UI), documentation.
- **[Teammate name]** — `core/` statistical logic (sample size validation,
  assumption checks, test selection, test execution).
