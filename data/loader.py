"""Load two-group numeric data out of a CSV for the pipeline to compare."""

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("group_a", "group_b")


def load_groups(csv_path):
    """Read csv_path and return (group_a, group_b) as 1-D numpy float arrays.

    NaNs are dropped independently per column, so group_a and group_b may end
    up different lengths -- that's expected for uneven sample sizes and every
    downstream statistical test tolerates unequal-length groups.

    Raises ValueError with a clear message if the file is missing, empty,
    missing a required column, or contains non-numeric values.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise ValueError(f"CSV file not found: {csv_path}")
    except pd.errors.EmptyDataError:
        raise ValueError(f"CSV file is empty: {csv_path}")

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
