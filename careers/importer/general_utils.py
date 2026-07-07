# general_utils.py

from __future__ import annotations

from pathlib import Path
import logging
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)


# ============================================================================
# File Utilities
# ============================================================================

SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
    ".json",
    ".parquet",
}


def validate_file(filepath: Path) -> bool:
    """
    Validates that a file exists, is a file and has a supported extension.
    """

    if not isinstance(filepath, Path):
        logger.error("filepath must be a pathlib.Path instance.")
        return False

    if not filepath.exists():
        logger.error("File does not exist: %s", filepath)
        return False

    if not filepath.is_file():
        logger.error("Path is not a file: %s", filepath)
        return False

    if filepath.suffix.lower() not in SUPPORTED_EXTENSIONS:
        logger.error(
            "Unsupported file format '%s'. Supported formats: %s",
            filepath.suffix,
            ", ".join(sorted(SUPPORTED_EXTENSIONS)),
        )
        return False

    return True


# ============================================================================
# Reading Files
# ============================================================================

def read_source(filepath: Path) -> pd.DataFrame | None:
    """
    Reads supported tabular files into a DataFrame.

    Returns
    -------
    DataFrame
        Loaded dataframe.

    None
        If loading failed.
    """

    if not validate_file(filepath):
        return None

    try:

        ext = filepath.suffix.lower()

        match ext:

            case ".csv":
                df = pd.read_csv(filepath)

            case ".xlsx" | ".xls":
                df = pd.read_excel(filepath)

            case ".json":
                df = pd.read_json(filepath)

            case ".parquet":
                df = pd.read_parquet(filepath)

            case _:
                logger.error("Unsupported extension: %s", ext)
                return None

        if df.empty:
            logger.warning("Loaded dataframe is empty: %s", filepath)

        logger.info(
            "Loaded %d rows × %d columns from %s",
            len(df),
            len(df.columns),
            filepath.name,
        )

        return df

    except Exception:
        logger.exception("Failed reading '%s'", filepath)
        return None


# ============================================================================
# DataFrame Helpers
# ============================================================================

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize dataframe column names.

    Example

        Course Name -> course_name
        Cluster No. -> cluster_no
    """

    df = df.copy()

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
    )

    return df


def validate_required_columns(
    df: pd.DataFrame,
    required_columns: Iterable[str],
) -> bool:
    """
    Checks that every required column exists.
    """

    missing = set(required_columns) - set(df.columns)

    if missing:
        logger.error(
            "Missing required columns: %s",
            ", ".join(sorted(missing)),
        )
        return False

    return True


def remove_duplicate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes duplicated rows.
    """

    before = len(df)

    df = df.drop_duplicates()

    removed = before - len(df)

    if removed:
        logger.info("Removed %d duplicate rows.", removed)

    return df


def strip_whitespace(df: pd.DataFrame) -> pd.DataFrame:
    """
    Removes leading/trailing whitespace from string columns.
    """

    df = df.copy()

    object_columns = df.select_dtypes(include="object").columns

    for column in object_columns:
        df[column] = df[column].astype(str).str.strip()

    return df


def replace_nan(df: pd.DataFrame) -> pd.DataFrame:
    """
    Converts pandas NaN values into Python None.
    """

    return df.where(pd.notnull(df), None)


# ============================================================================
# Logging Helpers
# ============================================================================

def dataframe_summary(df: pd.DataFrame) -> None:
    """
    Logs useful dataframe statistics.
    """

    logger.info("Rows: %d", len(df))
    logger.info("Columns: %d", len(df.columns))
    logger.info("Column names: %s", ", ".join(df.columns))

    null_counts = df.isna().sum()

    for column, count in null_counts.items():
        if count:
            logger.warning("%s -> %d missing values", column, count)


# ============================================================================
# Validation Helpers
# ============================================================================

def ensure_not_empty(df: pd.DataFrame) -> bool:
    """
    Ensure dataframe contains records.
    """

    if df.empty:
        logger.error("DataFrame contains no records.")
        return False

    return True


def safe_string(value) -> str:
    """
    Safely converts values into cleaned strings.
    """

    if value is None:
        return ""

    if pd.isna(value):
        return ""

    return str(value).strip()


def safe_int(value, default=None):
    """
    Safe integer conversion.
    """

    try:
        if pd.isna(value):
            return default

        return int(value)

    except Exception:
        return default


def safe_float(value, default=None):
    """
    Safe float conversion.
    """

    try:
        if pd.isna(value):
            return default

        return float(value)

    except Exception:
        return default