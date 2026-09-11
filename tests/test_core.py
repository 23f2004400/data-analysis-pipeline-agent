import numpy as np
import pytest

from core.test_executor import run_test


@pytest.mark.parametrize("test_name", ["student_t", "welch_t"])
def test_run_test_returns_invalid_result_for_constant_groups(test_name):
    """Two constant-value (zero-variance) groups make the t-test statistic and
    p-value mathematically undefined (0/0 -> NaN). This must surface as
    status='invalid_result', never as a misleading 'significant': False."""
    group_a = np.array([5.0, 5.0, 5.0, 5.0, 5.0])
    group_b = np.array([5.0, 5.0, 5.0, 5.0, 5.0])

    result = run_test(test_name, group_a, group_b)

    assert result["status"] == "invalid_result"
    assert result["test_used"] == test_name
    assert result["significant"] is None
    assert result["reason"]
    assert np.isnan(result["statistic"])
    assert np.isnan(result["p_value"])


@pytest.mark.parametrize("test_name", ["student_t", "welch_t", "mann_whitney"])
def test_run_test_returns_ok_status_for_valid_data(test_name):
    """Regression guard: normal, well-behaved data must still produce a real
    result with status='ok', not get swept into the new invalid_result path."""
    group_a = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 2.5, 3.5])
    group_b = np.array([6.0, 7.0, 8.0, 9.0, 10.0, 7.5, 8.5])

    result = run_test(test_name, group_a, group_b)

    assert result["status"] == "ok"
    assert result["reason"] is None
    assert result["significant"] is not None
    assert not np.isnan(result["statistic"])
    assert not np.isnan(result["p_value"])


def test_run_test_raises_on_unknown_test_name():
    with pytest.raises(ValueError):
        run_test("not_a_real_test", np.array([1.0, 2.0]), np.array([3.0, 4.0]))
