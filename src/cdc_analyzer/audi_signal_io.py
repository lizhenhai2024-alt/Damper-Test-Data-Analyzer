"""Import raw Audi signal tables without requiring a current feedback channel."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .dynamic_analysis import DISP, LOAD, TIME, load_dynamic_test_data
from .parser import _canonicalize_columns


def load_audi_signals(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".dat":
        return load_dynamic_test_data(source).data
    if suffix == ".csv":
        frame = pd.read_csv(source)
    elif suffix in {".xlsx", ".xlsm"}:
        frame = pd.read_excel(source)
    else:
        raise ValueError(f"Unsupported Audi signal file: {suffix}")
    frame = frame.rename(columns=_canonicalize_columns(frame.columns))
    missing = {TIME, DISP, LOAD} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    for name in (TIME, DISP, LOAD):
        frame[name] = pd.to_numeric(frame[name], errors="coerce")
    if frame[[TIME, DISP, LOAD]].isna().any().any():
        raise ValueError("Signal table contains missing or non-numeric time, displacement or force values")
    return frame

