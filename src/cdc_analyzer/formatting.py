from __future__ import annotations

from numbers import Number

import pandas as pd

# Presentation-only precision rules. Analysis data always keeps full precision internally.
FORCE_RESULT_COLUMNS = {"Rebound N", "Compression N"}
FORCE_RESULT_SUFFIXES = ("Force N", "Hysteresis N")
ONE_DECIMAL_COLUMNS = {"Current Label A", "Current Label"}
INTEGER_HINTS = (" ID", " Count")
INTEGER_COLUMNS = {"Block ID", "Source Row", "Run Count"}


def decimals_for_column(column: str) -> int:
    """Return the display precision for a result/output column."""
    if column in FORCE_RESULT_COLUMNS or column.endswith(FORCE_RESULT_SUFFIXES):
        return 0
    if column in ONE_DECIMAL_COLUMNS:
        return 1
    if column in INTEGER_COLUMNS or column.endswith(INTEGER_HINTS):
        return 0
    if column.endswith(" m/s") and column.startswith(("Rebound", "Compression")):
        return 0
    return 2


def format_value(column: str, value: object) -> str:
    """Format a scalar for CLI/GUI display without modifying the stored value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, Number) and not isinstance(value, bool):
        decimals = decimals_for_column(column)
        return f"{float(value):.{decimals}f}"
    return str(value)


def dataframe_formatters(df: pd.DataFrame) -> dict[str, object]:
    """Build pandas ``to_string`` formatters for numeric output columns."""
    formatters: dict[str, object] = {}
    for column in df.columns:
        if pd.api.types.is_numeric_dtype(df[column]):
            formatters[column] = lambda value, c=column: format_value(c, value)
    return formatters


def excel_number_format(column: str) -> str:
    """Return an Excel number format matching the UI/CLI output precision."""
    decimals = decimals_for_column(column)
    return "0" if decimals == 0 else "0." + ("0" * decimals)
