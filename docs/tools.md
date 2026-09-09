# Tools / functions inventory

Every tool or function the agent calls, in the order the orchestrator generally
invokes them. "Milestone" refers to the owning workstream, not a calendar date.
Update the **Status** column as work lands — this table should always reflect
current reality, not the plan.

| Name | Module | Purpose | Input | Output | Milestone | Status |
|---|---|---|---|---|---|---|
| `load_groups` | `data/loader.py` | Load a two-group CSV into numeric arrays, dropping NaNs | `csv_path` | `(group_a: np.ndarray, group_b: np.ndarray)` | data/ | **Done** |
| `classify_question` | `agent/question_classifier.py` | Pure keyword matching to categorize the plain-English question | `question: str` | `"two_group" \| "multi_group" \| "correlation" \| "unclear"` | agent/ | **Done** (no LLM — see docs/decisions.md) |
| `validate_sample_size` | `core/sample_size_validator.py` | Gate: abort early if either group has n < 5 | `group_a`, `group_b`, `min_n=5` | `{passed, n_a, n_b, reason}` | core/ (teammate) | **Placeholder** — real scipy-backed logic, pending teammate's version |
| `check_normality` | `core/assumption_checker.py` | Shapiro-Wilk test on both groups | `group_a`, `group_b`, `alpha=0.05` | `{passed, p_value_a, p_value_b, reason}` | core/ (teammate) | **Placeholder** — real scipy-backed logic, pending teammate's version |
| `check_equal_variance` | `core/assumption_checker.py` | Levene's test across both groups | `group_a`, `group_b`, `alpha=0.05` | `{passed, p_value, reason}` | core/ (teammate) | **Placeholder** — real scipy-backed logic, pending teammate's version |
| `select_test` | `core/test_selector.py` | Pure branch-logic decision: pick which test to run | `size_check`, `normality_check`, `variance_check` | `{action, test, reason}` | core/ (teammate) | **Placeholder** — logic-complete, pending teammate's version |
| `run_test` | `core/test_executor.py` | Execute the chosen statistical test | `test_name`, `group_a`, `group_b` | `{test_used, statistic, p_value, significant}` | core/ (teammate) | **Placeholder** — real scipy-backed logic, pending teammate's version |
| `run_pipeline` | `agent/controller.py` | Top-level orchestration state machine (LOAD→CLASSIFY→VALIDATE_SIZE→CHECK_NORMALITY→CHECK_VARIANCE→SELECT_TEST→EXECUTE→REPORT) with full `decision_trail` logging | `csv_path`, `question` | `{status, test_used, statistic, p_value, significant, reasoning, decision_trail}` | agent/ | **Done** |
| `format_trace` | `agent/reasoning_trace.py` | Render a `decision_trail` into a readable multi-line string | `decision_trail: list[dict]` | `str` | agent/ | **Done** |
| Streamlit app | `app.py` | UI: upload dataset, ask question, display branch trace + result | — | — | app.py | Not started |

Full I/O detail for every `core/` function is in
[docs/contract.md](contract.md) — this table is a summary/index, not the source of
truth for signatures.
