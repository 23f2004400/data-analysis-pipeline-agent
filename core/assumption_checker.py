"""
PLACEHOLDER IMPLEMENTATION -- owned by core/, written from the agent/ side because
core/ had not been delivered yet as of Milestone 2. Fully functional (not dummy
data), so agent/ can be built and tested end-to-end now.

Teammate: replace this file with your own implementation whenever ready. The
function signatures and return shapes below are LOCKED per docs/contract.md --
do not change them without updating that file (and notifying the other side).
"""

from scipy import stats


def check_normality(group_a, group_b, alpha=0.05):
    """Shapiro-Wilk normality test, run independently on each group."""
    _, p_value_a = stats.shapiro(group_a)
    _, p_value_b = stats.shapiro(group_b)

    passed = bool(p_value_a >= alpha and p_value_b >= alpha)

    if passed:
        reason = (
            f"both groups fail to reject normality "
            f"(p_a={p_value_a:.4f}, p_b={p_value_b:.4f} >= alpha={alpha})"
        )
    else:
        failing = []
        if p_value_a < alpha:
            failing.append(f"group_a (p={p_value_a:.4f})")
        if p_value_b < alpha:
            failing.append(f"group_b (p={p_value_b:.4f})")
        reason = f"normality rejected for {', '.join(failing)} at alpha={alpha}"

    return {
        "passed": passed,
        "p_value_a": float(p_value_a),
        "p_value_b": float(p_value_b),
        "reason": reason,
    }


def check_equal_variance(group_a, group_b, alpha=0.05):
    """Levene's test for equality of variance across both groups."""
    _, p_value = stats.levene(group_a, group_b)
    passed = bool(p_value >= alpha)

    reason = (
        f"Levene's test fails to reject equal variance (p={p_value:.4f} >= alpha={alpha})"
        if passed
        else f"Levene's test rejects equal variance (p={p_value:.4f} < alpha={alpha})"
    )

    return {
        "passed": passed,
        "p_value": float(p_value),
        "reason": reason,
    }
