"""
PLACEHOLDER IMPLEMENTATION -- owned by core/, written from the agent/ side because
core/ had not been delivered yet as of Milestone 2. Fully functional (not dummy
data), so agent/ can be built and tested end-to-end now.

Teammate: replace this file with your own implementation whenever ready. The
function signature and return shape below are LOCKED per docs/contract.md --
do not change them without updating that file (and notifying the other side).

This is the literal encoding of the project's branch logic (see CLAUDE.md):
  - size_check failed             -> abort, "insufficient data"
  - normality_check failed        -> mann_whitney
  - normality passed, variance failed -> welch_t
  - normality passed, variance passed -> student_t
No statistics are computed here -- this function only inspects prior results.
"""


def select_test(size_check, normality_check, variance_check):
    if not size_check["passed"]:
        return {
            "action": "abort",
            "test": None,
            "reason": f"insufficient data: {size_check['reason']}",
        }

    if not normality_check["passed"]:
        return {
            "action": "run_test",
            "test": "mann_whitney",
            "reason": (
                f"normality check failed ({normality_check['reason']}); "
                f"using Mann-Whitney U test"
            ),
        }

    if variance_check is None:
        return {
            "action": "abort",
            "test": None,
            "reason": "normality passed but variance check was not run",
        }

    if not variance_check["passed"]:
        return {
            "action": "run_test",
            "test": "welch_t",
            "reason": (
                f"normality passed but variance check failed "
                f"({variance_check['reason']}); using Welch's t-test"
            ),
        }

    return {
        "action": "run_test",
        "test": "student_t",
        "reason": (
            f"normality and variance checks both passed "
            f"({variance_check['reason']}); using Student's t-test"
        ),
    }
