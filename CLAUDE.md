# data-analysis-pipeline-agent

Built for the **Agentic AI Hackathon** (Tech Zephyr 4.0, IIT Bhubaneswar).
**Deadline: 12–13 Sep 2026.** Speed and reliability beat sophistication — this file
exists so no session has to re-derive context from scratch.

## The problem

Given a raw dataset and a plain-English comparison question (e.g. "is there a
difference between group A and B?"), most people either run an invalid statistical
test (skipping assumption checks) or don't know which test is appropriate at all.
This system autonomously runs the correct checks and picks/switches the statistical
test based on what those checks reveal.

## Why this is agentic (do not simplify this away)

The test that runs is decided by **live intermediate results**, not a fixed code
path. A different assumption-check outcome provably leads to a different action —
not just different output text. This is the observe → decide → act → evaluate →
adapt loop the hackathon judges are scoring for. If any implementation collapses
this into "always run test X" or precomputes the branch outside the run, it defeats
the entire point of the project. Never hardcode the sequence.

## The branch logic (verbatim — never let this drift)

1. **Sample size < 5 per group** → ABORT, report "insufficient data"
2. **Normality check fails** (Shapiro-Wilk) → use **Mann-Whitney U test**
3. **Normality passes, variance check fails** (Levene's) → use **Welch's t-test**
4. **Normality passes, variance passes** → use **Student's t-test**

The sample-size gate always runs first, before any assumption check. See
[docs/decisions.md](docs/decisions.md) for why.

## Team split

- **Teammate owns `core/`** — pure deterministic Python, zero LLM involvement,
  already contracted with a fixed input/output shape per function:
  `sample_size_validator.py`, `assumption_checker.py`, `test_selector.py`,
  `test_executor.py`.
- **I own `agent/`, `data/`, `app.py`, `docs/`** — orchestration, data loading, the
  Streamlit UI, and project documentation.

`core/` may be real tested code, placeholder mocks, or entirely missing at any given
time depending on teammate progress. **Always check current state of `core/` before
assuming it exists or behaves a certain way** — build against the contract in
[docs/contract.md](docs/contract.md) regardless of what's actually there, and stub
around gaps rather than blocking on them.

## Shared contract (summary — full detail in docs/contract.md)

All five functions below live in `core/` and are pure/deterministic (no I/O, no
LLM calls, no global state):

| Function | Module | Input | Output |
|---|---|---|---|
| `validate_sample_size(group_a, group_b, min_n=5)` | `sample_size_validator.py` | two numeric arrays | `{passed, n_a, n_b, reason}` |
| `check_normality(group_a, group_b, alpha=0.05)` | `assumption_checker.py` | two numeric arrays | `{passed, p_value_a, p_value_b, reason}` |
| `check_equal_variance(group_a, group_b, alpha=0.05)` | `assumption_checker.py` | two numeric arrays | `{passed, p_value, reason}` |
| `select_test(size_check, normality_check, variance_check)` | `test_selector.py` | three result dicts (`variance_check` may be `None`) | `{action, test, reason}` |
| `run_test(test_name, group_a, group_b)` | `test_executor.py` | test name + two numeric arrays | `{test_used, statistic, p_value, significant}` |

Never change these signatures without updating [docs/contract.md](docs/contract.md)
and notifying the other side of the split.

As of Milestone 2, `core/` had not been delivered by teammate yet, so all four
functions above were implemented from the `agent/` side as fully-functional
placeholders (real scipy statistics, not dummy data) so the orchestration layer
could be built and tested end-to-end. Each `core/*.py` file is clearly marked as
a placeholder in its module docstring and can be swapped for teammate's real
implementation without touching `agent/controller.py`, as long as the contract
above is preserved.

## Hard constraints

- **No vector database, no RAG, no multi-agent framework.** None are needed and the
  hackathon explicitly says they're not mandatory. Stay as simple as possible while
  remaining genuinely agentic per the branch logic above.
- **Zero external API dependency, full stop.** `agent/question_classifier.py` was
  originally scoped to allow one *optional* LLM call with an offline fallback; as of
  Milestone 2 that was deliberately narrowed to pure deterministic keyword matching
  with no external calls of any kind — see
  [docs/decisions.md](docs/decisions.md#llm-classifier-rejected-in-favor-of-keyword-matching).
  If an LLM-assisted upgrade is added later, it must remain strictly optional with
  this keyword matcher as the always-available fallback, never the only path.
- **No unnecessary dependencies.** Prefer the standard library + scipy/numpy/pandas
  + streamlit over adding new packages.
- **Never commit API keys, secrets, or credentials.** Use `.env` (already
  gitignored) or Streamlit secrets, never hardcode.
- Prefer clean, simple, well-tested code over clever abstractions — judges inspect
  the repo directly, and this is a 2-person team under deadline pressure.

## Build status

Update this section as milestones complete. Do not let it go stale.

- [x] Project scaffolding: repo, `.gitignore`, `README.md`
- [x] Core documentation: `CLAUDE.md`, `docs/tools.md`, `docs/decisions.md`, `docs/contract.md`
- [x] **Milestone 2 — Agent Orchestration** (this milestone):
  - [x] `core/` — placeholder implementations (real scipy-backed, not dummy data)
        for all four contract functions, pending teammate's real versions
  - [x] `data/loader.py` — `load_groups(csv_path)`, plus 4 sample CSVs
        (`normal_equal_variance`, `non_normal`, `unequal_variance`, `tiny_sample`)
        that exercise all four branch outcomes
  - [x] `agent/question_classifier.py` — pure keyword-based classifier (no LLM;
        see docs/decisions.md for why the LLM approach was rejected here)
  - [x] `agent/controller.py` — `run_pipeline()` state machine with full
        `decision_trail` logging
  - [x] `agent/reasoning_trace.py` — `format_trace()` for readable trail display
  - [x] `tests/test_agent.py` — 10 tests, all passing, covering all 4 branch
        outcomes + both early-exit paths + classifier categories
- [ ] `app.py` — Streamlit UI
- [ ] `agent/question_classifier.py` optional LLM layer (currently offline-only by
      design; an LLM-assisted upgrade path remains open, see docs/decisions.md)
- [ ] End-to-end demo run
