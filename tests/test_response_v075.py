from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.dynamic_analysis import CURRENT, DISP, LOAD, TIME, ResponseConfig, ResponseStandard
from cdc_analyzer.parser import DataSet
from cdc_analyzer.response_v075 import _bmw_state, analyze_response_time_v075


def _dataset(frame: pd.DataFrame, name: str = "audi_0131.dat") -> DataSet:
    return DataSet(frame, Path(name), "synthetic")


def _audi_0131_noisy(fs: float = 4096.0) -> pd.DataFrame:
    t = np.arange(0.0, 0.090, 1.0 / fs)
    velocity = np.full_like(t, 0.131)
    displacement = np.cumsum(velocity) / fs * 1000.0
    # Representative high-frequency displacement noise: pointwise derivative is
    # visibly noisier than the true 0.131 m/s constant-speed motion.
    displacement += 0.010 * np.sin(2.0 * np.pi * 650.0 * t)

    current = np.full_like(t, 0.30)
    at = 0.040
    ramp = (t >= at) & (t <= at + 0.0012)
    current[ramp] = 0.30 + (1.60 - 0.30) * (t[ramp] - at) / 0.0012
    current[t > at + 0.0012] = 1.60
    current += 0.002 * np.sin(2.0 * np.pi * 900.0 * t)

    force = np.full_like(t, 1800.0)
    response_start = at + 0.0002
    mask = t >= response_start
    tau = 0.0045
    force[mask] = 3600.0 - 1800.0 * np.exp(-(t[mask] - response_start) / tau)

    return pd.DataFrame({TIME: t, DISP: displacement, LOAD: force, CURRENT: current})


def test_audi_0131_mps_response_survives_low_speed_noise():
    result = analyze_response_time_v075(
        _dataset(_audi_0131_noisy()),
        ResponseConfig(standard=ResponseStandard.AUDI),
    )

    assert len(result.events) == 1
    row = result.events.iloc[0]
    assert abs(float(row["Target Velocity m/s"])) == pytest.approx(0.131, abs=1e-6)
    assert float(row["Switch Time t63 ms"]) > 0
    assert float(row["Switch Time t90 ms"]) > float(row["Switch Time t63 ms"])
    assert result.settings["Analysis Mode"] == "Response Time V0.7.5"
    assert "5 ms" in str(result.settings["Velocity Estimator"])


def test_0131_mps_with_bmw_profile_is_accepted():
    result = analyze_response_time_v075(
        _dataset(_audi_0131_noisy()),
        ResponseConfig(standard=ResponseStandard.BMW),
    )

    assert len(result.events) == 1
    row = result.events.iloc[0]
    assert abs(float(row["Target Velocity m/s"])) == pytest.approx(0.131, abs=1e-6)
    assert row["Stage"] == "Soft→Hard"
    assert float(row["Switch Time t90 ms"]) > float(row["Switch Time t63 ms"])


def test_bmw_current_states_follow_engineering_definition():
    assert _bmw_state(0.00) == "Off"
    assert _bmw_state(0.30) == "Soft"
    assert _bmw_state(0.34) == "Soft"
    assert _bmw_state(0.80) == "Medium"
    assert _bmw_state(0.90) == "Medium"
    assert _bmw_state(0.95) == "Medium"
    assert _bmw_state(1.60) == "Hard"
    assert _bmw_state(1.62) == "Hard"
