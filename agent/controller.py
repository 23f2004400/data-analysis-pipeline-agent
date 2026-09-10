"""
Top-level orchestration for the data-analysis-pipeline-agent.

run_pipeline() is the explicit state machine that IS the agentic core of this
project:

    LOAD -> DETECT_COLUMNS -> CLASSIFY -> VALIDATE_SIZE -> CHECK_NORMALITY
    -> CHECK_VARIANCE -> SELECT_TEST -> EXECUTE -> REPORT

with three early-exit branches:
  - stop right after DETECT_COLUMNS if which columns to compare is genuinely
    ambiguous -- never guess a grouping/value column
  - stop right after CLASSIFY if the question is "unclear" -- never guess
    which columns to compare on a load-dependent statistical step
  - stop right after VALIDATE_SIZE if the sample size check fails -- never
    run assumption checks on data that can't statistically support them

Every state transition appends a structured record to decision_trail, so the
exact reasoning chain -- including which branch was taken and why -- is fully
inspectable after the fact. See CLAUDE.md for why this live branching, not a
fixed sequence, is what makes the system agentic.
"""

from agent.question_classifier import classify_question
from core.assumption_checker import check_equal_variance, check_normality
from core.sample_size_validator import validate_sample_size
from core.test_executor import run_test
from core.test_selector import select_test
from data.loader import (
    detect_comparison_columns,
    extract_direct_groups,
    load_dataframe,
    split_by_group,
)


def _early_exit(status, reasoning, decision_trail):
    return {
        "status": status,
        "test_used": None,
        "statistic": None,
        "p_value": None,
        "significant": None,
        "reasoning": reasoning,
        "decision_trail": decision_trail,
    }


def run_pipeline(csv_path, question):
    decision_trail = []

    # --- LOAD ---
    try:
        df = load_dataframe(csv_path)
    except ValueError as exc:
        decision_trail.append({
            "step": "LOAD",
            "input": {"csv_path": csv_path},
            "result": {"error": str(exc)},
            "decision": "abort: failed to load dataset",
        })
        return _early_exit("aborted", f"Could not load dataset: {exc}", decision_trail)

    decision_trail.append({
        "step": "LOAD",
        "input": {"csv_path": csv_path},
        "result": {"n_rows": len(df), "columns": list(df.columns)},
        "decision": "loaded dataset, proceeding to DETECT_COLUMNS",
    })

    # --- DETECT_COLUMNS ---
    detection = detect_comparison_columns(df, question)

    if detection["mode"] == "direct":
        detect_decision = (
            f"exactly 2 numeric columns found ({', '.join(detection['numeric_columns'])}); "
            f"using them directly, proceeding to CLASSIFY"
        )
    elif detection["mode"] == "grouped":
        detect_decision = (
            f"auto-selected '{detection['group_col']}' as grouping column and "
            f"'{detection['value_col']}' as value column ({detection['reason']}), "
            f"proceeding to CLASSIFY"
        )
    else:
        detect_decision = f"ambiguous: {detection['reason']}; stopping for clarification"

    decision_trail.append({
        "step": "DETECT_COLUMNS",
        "input": {"columns": list(df.columns), "question": question},
        "result": detection,
        "decision": detect_decision,
    })

    if detection["mode"] == "ambiguous":
        candidates = detection["candidates"] or []
        reasoning = (
            f"Could not automatically determine which columns to compare: "
            f"{detection['reason']}."
            + (f" Candidate columns: {', '.join(candidates)}." if candidates else "")
            + " Please specify which columns represent the two groups to compare."
        )
        return _early_exit("needs_clarification", reasoning, decision_trail)

    if detection["mode"] == "direct":
        group_a, group_b = extract_direct_groups(df, detection["numeric_columns"])
        source_sentence = (
            f"Compared columns '{detection['numeric_columns'][0]}' and "
            f"'{detection['numeric_columns'][1]}' directly. "
        )
    else:
        try:
            group_a, group_b = split_by_group(df, detection["group_col"], detection["value_col"])
        except ValueError as exc:
            decision_trail.append({
                "step": "DETECT_COLUMNS",
                "input": {"group_col": detection["group_col"], "value_col": detection["value_col"]},
                "result": {"error": str(exc)},
                "decision": "abort: could not split data by the detected grouping column",
            })
            return _early_exit(
                "aborted", f"Could not split data by '{detection['group_col']}': {exc}", decision_trail
            )
        source_sentence = (
            f"Compared '{detection['value_col']}' grouped by '{detection['group_col']}' "
            f"({detection['reason']}). "
        )

    # --- CLASSIFY ---
    question_type = classify_question(question)
    decision_trail.append({
        "step": "CLASSIFY",
        "input": {"question": question},
        "result": {"question_type": question_type},
        "decision": (
            "question classified as 'two_group', proceeding to VALIDATE_SIZE"
            if question_type == "two_group"
            else f"question classified as '{question_type}', stopping for clarification"
        ),
    })

    if question_type != "two_group":
        reasoning = (
            f"The question could not be confidently classified as a two-group "
            f"comparison (classified as '{question_type}' instead). This "
            f"pipeline currently only supports two-group comparisons, so it "
            f"stopped rather than guessing which columns to compare."
        )
        return _early_exit("needs_clarification", reasoning, decision_trail)

    # --- VALIDATE_SIZE ---
    size_check = validate_sample_size(group_a, group_b)
    decision_trail.append({
        "step": "VALIDATE_SIZE",
        "input": {"n_a": len(group_a), "n_b": len(group_b)},
        "result": size_check,
        "decision": (
            "sample size sufficient, proceeding to CHECK_NORMALITY"
            if size_check["passed"]
            else "abort: insufficient sample size"
        ),
    })

    if not size_check["passed"]:
        reasoning = (
            f"The pipeline aborted before running any statistical test because "
            f"the sample size check failed: {size_check['reason']}"
        )
        return _early_exit("aborted", reasoning, decision_trail)

    # --- CHECK_NORMALITY ---
    normality_check = check_normality(group_a, group_b)
    decision_trail.append({
        "step": "CHECK_NORMALITY",
        "input": {"n_a": len(group_a), "n_b": len(group_b)},
        "result": normality_check,
        "decision": (
            "normality holds, proceeding to CHECK_VARIANCE"
            if normality_check["passed"]
            else "normality violated, skipping variance check, proceeding to SELECT_TEST"
        ),
    })

    # --- CHECK_VARIANCE (only reached if normality passed) ---
    variance_check = None
    if normality_check["passed"]:
        variance_check = check_equal_variance(group_a, group_b)
        decision_trail.append({
            "step": "CHECK_VARIANCE",
            "input": {"n_a": len(group_a), "n_b": len(group_b)},
            "result": variance_check,
            "decision": "proceeding to SELECT_TEST",
        })

    # --- SELECT_TEST ---
    selection = select_test(size_check, normality_check, variance_check)
    decision_trail.append({
        "step": "SELECT_TEST",
        "input": {
            "size_check": size_check,
            "normality_check": normality_check,
            "variance_check": variance_check,
        },
        "result": selection,
        "decision": (
            f"proceeding to EXECUTE with '{selection['test']}'"
            if selection["action"] == "run_test"
            else "abort: test selector declined to select a test"
        ),
    })

    if selection["action"] != "run_test":
        reasoning = f"The pipeline aborted at test selection: {selection['reason']}"
        return _early_exit("aborted", reasoning, decision_trail)

    # --- EXECUTE ---
    result = run_test(selection["test"], group_a, group_b)
    decision_trail.append({
        "step": "EXECUTE",
        "input": {"test": selection["test"], "n_a": len(group_a), "n_b": len(group_b)},
        "result": result,
        "decision": "proceeding to REPORT",
    })

    # --- REPORT ---
    variance_sentence = (
        f" Variance check {'passed' if variance_check['passed'] else 'failed'} "
        f"({variance_check['reason']})."
        if variance_check is not None
        else ""
    )
    reasoning = (
        source_sentence +
        f"Loaded {len(group_a)} samples for group_a and {len(group_b)} for group_b. "
        f"The question was classified as a two-group comparison. The sample size "
        f"check passed ({size_check['reason']}). Normality check "
        f"{'passed' if normality_check['passed'] else 'failed'} "
        f"({normality_check['reason']})."
        f"{variance_sentence} "
        f"Selected {selection['test']} ({selection['reason']}). "
        f"Result: statistic={result['statistic']:.4f}, p_value={result['p_value']:.4f} -- "
        f"{'a statistically significant' if result['significant'] else 'no statistically significant'} "
        f"difference was found between the two groups."
    )

    decision_trail.append({
        "step": "REPORT",
        "input": result,
        "result": {"status": "success"},
        "decision": "pipeline completed successfully",
    })

    return {
        "status": "success",
        "test_used": result["test_used"],
        "statistic": result["statistic"],
        "p_value": result["p_value"],
        "significant": result["significant"],
        "reasoning": reasoning,
        "decision_trail": decision_trail,
    }
