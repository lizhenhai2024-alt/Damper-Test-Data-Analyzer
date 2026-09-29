import pandas as pd
import pytest

from cdc_analyzer.audi_signal_io import load_audi_signals
from cdc_analyzer.dynamic_analysis import DISP, LOAD, TIME


def test_audi_csv_accepts_three_required_raw_signals_without_current(tmp_path):
    path = tmp_path / "frequency.csv"
    pd.DataFrame({"time": [0.0, 0.00025], "stroke": [-5, -4.9], "force": [10, 11]}).to_csv(path, index=False)
    frame = load_audi_signals(path)
    assert {TIME, DISP, LOAD} <= set(frame)
    assert frame[LOAD].tolist() == [10, 11]


def test_audi_csv_rejects_missing_force(tmp_path):
    path = tmp_path / "incomplete.csv"
    pd.DataFrame({"time": [0.0], "stroke": [0.0]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="Missing signal columns"):
        load_audi_signals(path)

