"""
PLACEHOLDER IMPLEMENTATION -- owned by core/, written from the agent/ side because
core/ had not been delivered yet as of Milestone 2. Fully functional (not dummy
data), so agent/ can be built and tested end-to-end now.

Teammate: replace this file with your own implementation whenever ready. The
function signature and return shape below are LOCKED per docs/contract.md --
do not change them without updating that file (and notifying the other side).
"""


def validate_sample_size(group_a, group_b, min_n=5):
    n_a = len(group_a)
    n_b = len(group_b)
    passed = n_a >= min_n and n_b >= min_n

    if passed:
        reason = (
            f"group_a has {n_a} samples and group_b has {n_b} samples; "
            f"both meet the minimum of {min_n}"
        )
    else:
        shortfalls = []
        if n_a < min_n:
            shortfalls.append(f"group_a has {n_a} samples")
        if n_b < min_n:
            shortfalls.append(f"group_b has {n_b} samples")
        reason = f"{'; '.join(shortfalls)}; minimum required is {min_n} per group"

    return {
        "passed": passed,
        "n_a": n_a,
        "n_b": n_b,
        "reason": reason,
    }
