import os

import pytest

from agent.controller import run_pipeline
from agent.question_classifier import classify_question

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
    assert steps == ["LOAD", "CLASSIFY", "VALIDATE_SIZE"]


def test_pipeline_unclear_question_short_circuits_before_load_dependent_steps():
    csv_path = os.path.join(DATA_DIR, "normal_equal_variance.csv")
    result = run_pipeline(csv_path, "Tell me something interesting about this dataset.")

    assert result["status"] == "needs_clarification"
    assert result["test_used"] is None
    steps = [entry["step"] for entry in result["decision_trail"]]
    assert steps == ["LOAD", "CLASSIFY"]


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
