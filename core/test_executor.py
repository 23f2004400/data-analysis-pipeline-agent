"""
PLACEHOLDER IMPLEMENTATION -- owned by core/, written from the agent/ side because
core/ had not been delivered yet as of Milestone 2. Fully functional (not dummy
data), so agent/ can be built and tested end-to-end now.

Teammate: replace this file with your own implementation whenever ready. The
function signature and return shape below are LOCKED per docs/contract.md --
do not change them without updating that file (and notifying the other side).
"""

import math

from scipy import stats

ALPHA = 0.05


def run_test(test_name, group_a, group_b):
    if test_name == "student_t":
        statistic, p_value = stats.ttest_ind(group_a, group_b, equal_var=True)
    elif test_name == "welch_t":
        statistic, p_value = stats.ttest_ind(group_a, group_b, equal_var=False)
    elif test_name == "mann_whitney":
        statistic, p_value = stats.mannwhitneyu(group_a, group_b, alternative="two-sided")
    else:
        raise ValueError(f"Unknown test_name: {test_name!r}")

    statistic = float(statistic)
    p_value = float(p_value)

    if math.isnan(statistic) or math.isnan(p_value):
        return {
            "status": "invalid_result",
            "test_used": test_name,
            "statistic": statistic,
            "p_value": p_value,
            "significant": None,
            "reason": (
                "the test produced an undefined result (likely because one or "
                "both groups have zero variance / identical values)"
            ),
        }

    return {
        "status": "ok",
        "test_used": test_name,
        "statistic": statistic,
        "p_value": p_value,
        "significant": bool(p_value < ALPHA),
        "reason": None,
    }
