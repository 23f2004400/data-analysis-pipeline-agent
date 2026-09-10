"""Load and interpret two-group comparison data out of a CSV.

Two loading paths exist side by side:
  - load_groups(csv_path): the original, fixed-shape loader requiring columns
    literally named group_a/group_b. Still used by the project's own
    sample_datasets/ and by app.py's dataset preview -- unchanged.
  - load_dataframe(csv_path) + detect_comparison_columns(df, question): the
    generalized path for arbitrary CSVs that aren't pre-shaped into
    group_a/group_b. It looks for either two numeric columns to use directly,
    or a two-value categorical column to group by plus a numeric column
    picked via keyword overlap with the question. Anything genuinely unclear
    (no numeric column, multiple candidate grouping columns, or a keyword-match
    tie between numeric columns) is reported back as "ambiguous" rather than
    guessed -- see detect_comparison_columns().
"""

import re

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("group_a", "group_b")


def _read_csv(csv_path):
    try:
        return pd.read_csv(csv_path)
    except FileNotFoundError:
        raise ValueError(f"CSV file not found: {csv_path}")
    except pd.errors.EmptyDataError:
        raise ValueError(f"CSV file is empty: {csv_path}")


def load_dataframe(csv_path):
    """Read csv_path (a path or a file-like object) into a raw DataFrame."""
    return _read_csv(csv_path)


def load_groups(csv_path):
    """Read csv_path and return (group_a, group_b) as 1-D numpy float arrays.

    Requires columns literally named group_a/group_b. For arbitrary CSVs, use
    load_dataframe() + detect_comparison_columns() instead.

    NaNs are dropped independently per column, so group_a and group_b may end
    up different lengths -- that's expected for uneven sample sizes and every
    downstream statistical test tolerates unequal-length groups.

    Raises ValueError with a clear message if the file is missing, empty,
    missing a required column, or contains non-numeric values.
    """
    df = _read_csv(csv_path)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"CSV at {csv_path} is missing required column(s) {missing}; "
            f"found columns: {list(df.columns)}"
        )

    try:
        group_a = pd.to_numeric(df["group_a"], errors="raise").dropna().to_numpy(dtype=float)
        group_b = pd.to_numeric(df["group_b"], errors="raise").dropna().to_numpy(dtype=float)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"CSV at {csv_path} contains non-numeric values in group_a/group_b: {exc}"
        )

    return group_a, group_b


# ---------------------------------------------------------------------------
# Smart column detection for arbitrary CSVs
# ---------------------------------------------------------------------------

def _numeric_columns(df):
    return list(df.select_dtypes(include=[np.number]).columns)


def _two_value_categorical_columns(df):
    numeric = set(_numeric_columns(df))
    candidates = []
    for col in df.columns:
        if col in numeric:
            continue
        if df[col].dropna().nunique() == 2:
            candidates.append(col)
    return candidates


def _tokenize(name):
    return [w for w in re.split(r"[^a-z0-9]+", str(name).lower()) if w]


def _keyword_score(column_name, question):
    """Count how many of column_name's constituent words appear as a
    substring of the question. Substring (not exact-word) matching is
    deliberate -- it lets "score" match a question containing "scores"
    without needing real stemming."""
    question_lower = question.lower()
    words = _tokenize(column_name)
    return sum(1 for w in words if w in question_lower)


def detect_comparison_columns(df, question):
    """Decide which column(s) represent the two groups to compare.

    Returns a dict:
        {
            "mode": "direct" | "grouped" | "ambiguous",
            "group_col": str | None,       # populated for "grouped"
            "value_col": str | None,       # populated for "grouped"
            "numeric_columns": list | None,  # the 2 columns to use, for "direct"
            "candidates": list | None,       # candidate columns, for "ambiguous"
            "reason": str,
        }

    Priority order:
      1. Exactly 2 numeric columns -> "direct" (matches the project's own
         sample_datasets/, and generalizes to any 2-numeric-column CSV
         regardless of column names).
      2. Else, exactly one categorical column with exactly 2 unique values
         -> "grouped", picking the numeric value column by keyword overlap
         with the question (or the only numeric column, if there's just one).
      3. Else (no numeric columns, multiple candidate grouping columns, no
         grouping column at all, or a genuine tie between equally-matching
         numeric columns) -> "ambiguous", never guessed.
    """
    numeric_cols = _numeric_columns(df)

    if len(numeric_cols) == 2:
        return {
            "mode": "direct",
            "group_col": None,
            "value_col": None,
            "numeric_columns": numeric_cols,
            "candidates": None,
            "reason": f"exactly 2 numeric columns found: {numeric_cols[0]}, {numeric_cols[1]}",
        }

    grouping_candidates = _two_value_categorical_columns(df)

    if not numeric_cols:
        return {
            "mode": "ambiguous",
            "group_col": None,
            "value_col": None,
            "numeric_columns": None,
            "candidates": grouping_candidates,
            "reason": "no numeric column found to compare",
        }

    if len(grouping_candidates) > 1:
        return {
            "mode": "ambiguous",
            "group_col": None,
            "value_col": None,
            "numeric_columns": numeric_cols,
            "candidates": grouping_candidates,
            "reason": (
                f"multiple candidate grouping columns found "
                f"({', '.join(grouping_candidates)}); cannot tell which one to use"
            ),
        }

    if not grouping_candidates:
        return {
            "mode": "ambiguous",
            "group_col": None,
            "value_col": None,
            "numeric_columns": numeric_cols,
            "candidates": numeric_cols,
            "reason": "no column with exactly two categories found to group by",
        }

    group_col = grouping_candidates[0]

    if len(numeric_cols) == 1:
        return {
            "mode": "grouped",
            "group_col": group_col,
            "value_col": numeric_cols[0],
            "numeric_columns": None,
            "candidates": None,
            "reason": "only one numeric column available",
        }

    scores = {col: _keyword_score(col, question) for col in numeric_cols}
    best_score = max(scores.values())
    top_columns = [col for col, score in scores.items() if score == best_score]

    if best_score == 0 or len(top_columns) > 1:
        tied = top_columns if best_score > 0 else numeric_cols
        return {
            "mode": "ambiguous",
            "group_col": group_col,
            "value_col": None,
            "numeric_columns": numeric_cols,
            "candidates": tied,
            "reason": (
                "question keywords do not clearly match one numeric column "
                f"(tied candidates: {', '.join(tied)})"
            ),
        }

    value_col = top_columns[0]
    return {
        "mode": "grouped",
        "group_col": group_col,
        "value_col": value_col,
        "numeric_columns": None,
        "candidates": None,
        "reason": f"question keyword match selected '{value_col}' (score={best_score})",
    }


def extract_direct_groups(df, numeric_columns):
    """Given exactly 2 numeric column names, return (group_a, group_b) as
    1-D numpy float arrays, NaNs dropped independently per column."""
    col_a, col_b = numeric_columns
    group_a = pd.to_numeric(df[col_a], errors="raise").dropna().to_numpy(dtype=float)
    group_b = pd.to_numeric(df[col_b], errors="raise").dropna().to_numpy(dtype=float)
    return group_a, group_b


def split_by_group(df, group_col, value_col):
    """Split df[value_col] into two numeric arrays based on the two unique
    values of df[group_col]. Rows with a NaN in either column are dropped
    first. Categories are sorted (as strings) for a deterministic group_a
    vs. group_b assignment across runs.

    Raises ValueError if fewer/more than 2 categories remain after dropping
    NaNs (e.g. one category's rows all had a missing value_col) -- the
    controller treats this as an abort, not a crash.
    """
    clean = df[[group_col, value_col]].dropna()
    categories = sorted(clean[group_col].unique(), key=str)
    if len(categories) != 2:
        raise ValueError(
            f"expected exactly 2 categories in '{group_col}' after dropping "
            f"missing values, found {len(categories)}: {list(categories)}"
        )

    group_a = pd.to_numeric(
        clean.loc[clean[group_col] == categories[0], value_col], errors="raise"
    ).to_numpy(dtype=float)
    group_b = pd.to_numeric(
        clean.loc[clean[group_col] == categories[1], value_col], errors="raise"
    ).to_numpy(dtype=float)
    return group_a, group_b
