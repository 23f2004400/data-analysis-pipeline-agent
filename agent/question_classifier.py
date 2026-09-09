"""
Deterministic keyword-based question classifier.

No external calls of any kind -- classification is pure string matching. This
was a deliberate choice over an LLM call; see docs/decisions.md for why (demo
reliability + auditability under Q&A).
"""

import re

_CORRELATION_PATTERNS = (
    r"correlat",
    r"relationship between",
    r"associated with",
)

_MULTI_GROUP_PATTERNS = (
    r"\bamong\b",
    r"across groups",
    r"multiple groups",
)

_TWO_GROUP_PATTERNS = (
    r"\bbetween\b",
    r"\bcompare\b",
    r"\bcomparison\b",
    r"\bvs\.?\b",
    r"\bversus\b",
    r"\bdifference\b",
)


def _matches_any(patterns, text):
    return any(re.search(pattern, text) for pattern in patterns)


def classify_question(question):
    """Classify a plain-English comparison question.

    Returns one of "two_group", "multi_group", "correlation", "unclear".

    Checked in that priority order: correlation and multi-group phrasings are
    more specific and should win over a loosely-matching two-group keyword
    (e.g. "relationship between" contains "between" but is a correlation
    question, not a two-group one). "unclear" means the controller must ask
    for clarification -- it must never guess which columns to compare.
    """
    text = question.lower()

    if _matches_any(_CORRELATION_PATTERNS, text):
        return "correlation"
    if _matches_any(_MULTI_GROUP_PATTERNS, text):
        return "multi_group"
    if _matches_any(_TWO_GROUP_PATTERNS, text):
        return "two_group"
    return "unclear"
