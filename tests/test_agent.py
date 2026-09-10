import os

import pandas as pd
import pytest

from agent.controller import run_pipeline
from agent.question_classifier import classify_question
from data.loader import detect_comparison_columns

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "sample_datasets",
)

TWO_GROUP_QUESTION = "Is there a difference between group A and group B?"


@pytest.mark.parametrize(
    "csv_name, expected_status, expected_test",
    [
        ("normal_equal_variance.csv", "success", "student_t"),
        ("non_normal.csv", "success", "mann_whitney"),
        ("unequal_variance.csv", "success", "welch_t"),
        ("tiny_sample.csv", "aborted", None),
    ],
)
def test_pipeline_branch_outcomes(csv_name, expected_status, expected_test):
    csv_path = os.path.join(DATA_DIR, csv_name)
    result = run_pipeline(csv_path, TWO_GROUP_QUESTION)

    assert result["status"] == expected_status
    assert result["test_used"] == expected_test
    assert isinstance(result["decision_trail"], list)
    assert len(result["decision_trail"]) > 0
    assert result["reasoning"]

    if expected_status == "success":
        assert result["statistic"] is not None
        assert result["p_value"] is not None
        assert result["significant"] is not None
    else:
        assert result["statistic"] is None
        assert result["p_value"] is None
        assert result["significant"] is None


def test_pipeline_aborts_before_assumption_checks_on_tiny_sample():
    csv_path = os.path.join(DATA_DIR, "tiny_sample.csv")
    result = run_pipeline(csv_path, TWO_GROUP_QUESTION)

    assert result["status"] == "aborted"
    steps = [entry["step"] for entry in result["decision_trail"]]
    assert steps == ["LOAD", "DETECT_COLUMNS", "CLASSIFY", "VALIDATE_SIZE"]


def test_pipeline_unclear_question_short_circuits_before_load_dependent_steps():
    csv_path = os.path.join(DATA_DIR, "normal_equal_variance.csv")
    result = run_pipeline(csv_path, "Tell me something interesting about this dataset.")

    assert result["status"] == "needs_clarification"
    assert result["test_used"] is None
    steps = [entry["step"] for entry in result["decision_trail"]]
    assert steps == ["LOAD", "DETECT_COLUMNS", "CLASSIFY"]


@pytest.mark.parametrize(
    "question, expected",
    [
        ("Is there a difference between group A and group B?", "two_group"),
        ("How do outcomes vary among the treatment groups?", "multi_group"),
        ("Is there a correlation between age and income?", "correlation"),
        ("Tell me something interesting about this dataset.", "unclear"),
    ],
)
def test_classify_question(question, expected):
    assert classify_question(question) == expected


# ---------------------------------------------------------------------------
# Smart column detection: arbitrary CSVs, not pre-shaped into group_a/group_b
# ---------------------------------------------------------------------------

STUDENT_PERFORMANCE_ROWS = {
    # 3 numeric columns (not 2) so this doesn't hit the "direct" branch first
    # -- a real student-performance dataset would have more than 2 numeric
    # fields anyway, and "age" deliberately shares no keywords with either
    # test question below so it never wins the value-column selection.
    "gender": ["Male", "Female"] * 7,
    "final_exam_score": [78, 92, 82, 95, 75, 89, 90, 91, 85, 94, 79, 90, 88, 93],
    "attendance_percent": [85, 78, 90, 82, 80, 75, 95, 80, 88, 79, 82, 77, 91, 81],
    "age": [20, 21, 19, 22, 20, 21, 19, 22, 20, 21, 19, 22, 20, 21],
}


def _write_csv(tmp_path, name, data):
    path = tmp_path / name
    pd.DataFrame(data).to_csv(path, index=False)
    return str(path)


def test_direct_mode_generalizes_to_any_two_numeric_columns(tmp_path):
    """Direct mode must not be hardcoded to columns literally named
    group_a/group_b -- any CSV with exactly 2 numeric columns should work."""
    csv_path = _write_csv(
        tmp_path,
        "pre_post.csv",
        {
            "pre_score": [10, 12, 11, 13, 9, 14, 10, 12, 11, 13],
            "post_score": [15, 16, 14, 17, 13, 18, 15, 16, 14, 17],
        },
    )
    result = run_pipeline(csv_path, "Is there a difference between pre and post scores?")

    detect_entry = next(e for e in result["decision_trail"] if e["step"] == "DETECT_COLUMNS")
    assert detect_entry["result"]["mode"] == "direct"
    assert set(detect_entry["result"]["numeric_columns"]) == {"pre_score", "post_score"}
    assert result["status"] == "success"


@pytest.mark.parametrize(
    "question, expected_value_col",
    [
        ("Is there a difference in exam scores between male and female students?", "final_exam_score"),
        ("Is there a difference in attendance between male and female students?", "attendance_percent"),
    ],
)
def test_grouped_mode_selects_value_column_by_question_keywords(tmp_path, question, expected_value_col):
    csv_path = _write_csv(tmp_path, "student_performance.csv", STUDENT_PERFORMANCE_ROWS)
    result = run_pipeline(csv_path, question)

    detect_entry = next(e for e in result["decision_trail"] if e["step"] == "DETECT_COLUMNS")
    assert detect_entry["result"]["mode"] == "grouped"
    assert detect_entry["result"]["group_col"] == "gender"
    assert detect_entry["result"]["value_col"] == expected_value_col
    assert result["status"] in ("success", "aborted")  # column selection is what's under test, not the stats outcome


def test_ambiguous_when_question_matches_no_numeric_column(tmp_path):
    """Same dataset as the grouped-mode test, but a question with no keyword
    overlap with either numeric column -- must ask for clarification, not
    guess or crash."""
    csv_path = _write_csv(tmp_path, "student_performance.csv", STUDENT_PERFORMANCE_ROWS)
    result = run_pipeline(csv_path, "Is there a difference between male and female students?")

    assert result["status"] == "needs_clarification"
    assert result["test_used"] is None
    detect_entry = next(e for e in result["decision_trail"] if e["step"] == "DETECT_COLUMNS")
    assert detect_entry["result"]["mode"] == "ambiguous"
    assert set(detect_entry["result"]["candidates"]) == {"final_exam_score", "attendance_percent", "age"}
    assert "final_exam_score" in result["reasoning"] or "attendance_percent" in result["reasoning"]


def test_ambiguous_with_no_numeric_columns():
    df = pd.DataFrame({"gender": ["Male", "Female", "Male", "Female"], "city": ["A", "B", "A", "B"]})
    detection = detect_comparison_columns(df, "Is there a difference between male and female?")
    assert detection["mode"] == "ambiguous"
    assert "no numeric column" in detection["reason"]


def test_ambiguous_with_multiple_candidate_grouping_columns():
    # 3 numeric columns (not 2) so this doesn't hit the "direct" branch first --
    # the point being tested is the multiple-grouping-column ambiguity.
    df = pd.DataFrame(
        {
            "gender": ["Male", "Female", "Male", "Female"],
            "pass_fail": ["Pass", "Fail", "Pass", "Fail"],
            "score": [10, 20, 30, 40],
            "age": [18, 19, 20, 21],
            "height": [160, 170, 165, 175],
        }
    )
    detection = detect_comparison_columns(df, "Is there a difference in score?")
    assert detection["mode"] == "ambiguous"
    assert set(detection["candidates"]) == {"gender", "pass_fail"}


def test_grouped_mode_uses_only_numeric_column_without_needing_keyword_match():
    df = pd.DataFrame({"gender": ["Male", "Female", "Male", "Female"], "score": [10, 20, 30, 40]})
    detection = detect_comparison_columns(df, "Tell me something interesting.")
    assert detection["mode"] == "grouped"
    assert detection["group_col"] == "gender"
    assert detection["value_col"] == "score"
