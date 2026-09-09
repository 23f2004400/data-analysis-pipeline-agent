# core/ ↔ agent/ contract

**Single source of truth for every function signature crossing the `core/`/`agent/`
boundary.** Both teammates and future sessions must check this file before changing
any function signature listed here, and update it in the same change if a signature
must move.

`core/` is pure, deterministic Python: no I/O, no LLM calls, no global state, no
knowledge of Streamlit or the LLM classifier. Every function takes plain numpy
arrays / sequences and returns plain dicts.

Owner of `core/`: teammate. Owner of the orchestration that calls it: me (`agent/`).

> **Status note (Milestone 2):** as of this milestone, `core/` had not been
> delivered by teammate, so all four functions below were implemented from the
> `agent/` side as fully-functional (not dummy) placeholders — they use real
> scipy statistics, not fixed mock values — so `agent/controller.py` could be
> built and tested end-to-end now. Every `core/*.py` file carries a docstring
> marking it as a placeholder. Teammate can replace any of them at any time
> without touching `agent/controller.py`, as long as the signature and return
> shape below are preserved.

---

## 1. `sample_size_validator.validate_sample_size`

Gate that runs **before** any assumption check.

**Signature**
```python
validate_sample_size(group_a, group_b, min_n=5) -> dict
```

**Input**
| name | type | notes |
|---|---|---|
| `group_a` | `np.ndarray[float]` | first group's numeric values |
| `group_b` | `np.ndarray[float]` | second group's numeric values |
| `min_n` | `int`, default `5` | minimum samples required per group |

**Output**
```python
{
    "passed": bool,
    "n_a": int,
    "n_b": int,
    "reason": str,
}
```

**Branch behavior**: if `passed` is `False`, the orchestrator ABORTS immediately
with status `"aborted"` and reports "insufficient data" — no assumption checks are
run on rejected data.

---

## 2. `assumption_checker.check_normality`

Runs Shapiro-Wilk on **both** groups in a single call.

**Signature**
```python
check_normality(group_a, group_b, alpha=0.05) -> dict
```

**Input**
| name | type | notes |
|---|---|---|
| `group_a` | `np.ndarray[float]` | |
| `group_b` | `np.ndarray[float]` | |
| `alpha` | `float`, default `0.05` | significance threshold |

**Output**
```python
{
    "passed": bool,        # True only if BOTH groups fail to reject normality
    "p_value_a": float,
    "p_value_b": float,
    "reason": str,
}
```

**Branch behavior**: if `passed` is `False` → Mann-Whitney U, and
`check_equal_variance` is never called. If `True` → proceed to variance check.

---

## 3. `assumption_checker.check_equal_variance`

Runs Levene's test across both groups. Only called when `check_normality` passed.

**Signature**
```python
check_equal_variance(group_a, group_b, alpha=0.05) -> dict
```

**Input**
| name | type | notes |
|---|---|---|
| `group_a` | `np.ndarray[float]` | |
| `group_b` | `np.ndarray[float]` | |
| `alpha` | `float`, default `0.05` | |

**Output**
```python
{
    "passed": bool,
    "p_value": float,
    "reason": str,
}
```

**Branch behavior**: if `passed` is `False` → Welch's t-test. If `True` → Student's
t-test.

---

## 4. `test_selector.select_test`

Pure decision function — no statistics computed here, just the branch logic
translated into a test name. This is the literal encoding of the agentic decision
point; the branch logic itself is documented canonically in
[CLAUDE.md](../CLAUDE.md) and must never drift from it.

**Signature**
```python
select_test(size_check, normality_check, variance_check) -> dict
```

**Input**
| name | type | notes |
|---|---|---|
| `size_check` | `dict` | output of `validate_sample_size` |
| `normality_check` | `dict` | output of `check_normality` |
| `variance_check` | `dict \| None` | output of `check_equal_variance`, or `None` if not run (normality already failed, or size check already failed) |

**Output**
```python
{
    "action": "abort" | "run_test",
    "test": "mann_whitney" | "welch_t" | "student_t" | None,
    "reason": str,
}
```

---

## 5. `test_executor.run_test`

Executes the selected test and returns final results.

**Signature**
```python
run_test(test_name, group_a, group_b) -> dict
```

**Input**
| name | type | notes |
|---|---|---|
| `test_name` | `"mann_whitney" \| "welch_t" \| "student_t"` | from `select_test` output |
| `group_a` | `np.ndarray[float]` | |
| `group_b` | `np.ndarray[float]` | |

Significance threshold for the `significant` flag is fixed internally at
`alpha=0.05` (not a parameter — `test_executor` has no `alpha` argument per
contract).

**Output**
```python
{
    "test_used": str,
    "statistic": float,
    "p_value": float,
    "significant": bool,
}
```

---

## End-to-end shape (what `agent/controller.run_pipeline` calls, in order)

```python
group_a, group_b = load_groups(csv_path)                       # data/loader.py

question_type = classify_question(question)                    # agent/question_classifier.py
if question_type != "two_group":
    return needs_clarification(...)

size_check = validate_sample_size(group_a, group_b)
if not size_check["passed"]:
    return abort("insufficient data", size_check["reason"])

normality_check = check_normality(group_a, group_b)

variance_check = None
if normality_check["passed"]:
    variance_check = check_equal_variance(group_a, group_b)

selection = select_test(size_check, normality_check, variance_check)
if selection["action"] != "run_test":
    return abort(selection["reason"])

result = run_test(selection["test"], group_a, group_b)
```

This sequence is implemented as an explicit state machine in
`agent/controller.py`: `LOAD -> CLASSIFY -> VALIDATE_SIZE -> CHECK_NORMALITY ->
CHECK_VARIANCE -> SELECT_TEST -> EXECUTE -> REPORT`, with early exits after
`CLASSIFY` (if `"unclear"`/`"multi_group"`/`"correlation"`) and after
`VALIDATE_SIZE` (if sample size fails). Every transition is recorded in
`decision_trail`.

## Notes / things to keep in sync

- All `passed` fields must be native Python `bool`, not `numpy.bool_` — scipy
  comparisons return numpy scalars, so implementations must wrap with `bool(...)`.
  (Milestone 2 hit this directly; see [docs/decisions.md](decisions.md).)
- Test name strings are locked to exactly `"mann_whitney"`, `"welch_t"`,
  `"student_t"` end to end — `test_selector` produces them and `test_executor`
  matches on them verbatim.
- `reason` / interpretation string wording is not contractually fixed — only keys
  and types are. Don't build logic that parses these strings; branch on
  `passed` / `action` / `test` / `significant` instead.

## Change protocol

If a signature in `core/` must change: update this file in the same commit/PR, and
update the summary table in [CLAUDE.md](../CLAUDE.md) if the change affects it.
