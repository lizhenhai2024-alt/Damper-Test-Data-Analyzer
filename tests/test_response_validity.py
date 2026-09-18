"""Regression for a force dip that returns to its starting plateau."""

from pathlib import Path

import numpy as np
import pandas as pd

from cdc_analyzer.dynamic_analysis import CURRENT, DISP, LOAD, TIME, ResponseConfig, ResponseStandard
from cdc_analyzer.parser import DataSet
from cdc_analyzer.response_v074 import _first_valid_force_crossing, analyze_response_time_v074


def test_dip_and_recovery_does_not_report_classical_timing():
    t = np.arange(0.0, 0.100, 1.0 / 4096.0)
    current = np.full_like(t, 1.5)
    ramp = (t >= 0.040) & (t < 0.041)
    current[ramp] = 1.5 - 0.5 * (t[ramp] - 0.040) / 0.001
    current[t >= 0.041] = 1.0
    force = np.full_like(t, 1940.0)
    falling = (t >= 0.042) & (t < 0.048)
    force[falling] = 1940.0 - 440.0 * (t[falling] - 0.042) / 0.006
    rising = (t >= 0.048) & (t < 0.060)
    force[rising] = 1500.0 + 440.0 * (t[rising] - 0.048) / 0.012
    frame = pd.DataFrame({TIME: t, DISP: t * 524.0, LOAD: force, CURRENT: current})

    result = analyze_response_time_v074(
        DataSet(frame, Path("dip.dat"), "synthetic"),
        ResponseConfig(standard=ResponseStandard.BMW),
    )
    row = result.events.iloc[0]
    assert row["Response Type"] == "Dip & Recovery"
    assert np.isnan(row["Switch Time t63 ms"])
    assert np.isnan(row["Switch Time t90 ms"])
    assert np.isnan(row["F90 N"])
    assert 400 < row["Force Dip N"] < 450
    assert row["Force Dip Area N s"] > 0
    assert row["Time to Force Minimum ms"] > 0
    assert row["Force Recovery Time ms"] > row["Time to Force Minimum ms"]
    assert np.isnan(row["Current Overshoot A"])
    enabled = analyze_response_time_v074(
        DataSet(frame, Path("dip.dat"), "synthetic"),
        ResponseConfig(standard=ResponseStandard.BMW, calculate_current_overshoot=True),
    ).events.iloc[0]
    assert np.isfinite(enabled["Current Overshoot A"])
    assert enabled["Current Overshoot A"] >= 0


def test_no_force_excursion_is_classified_without_timing():
    t = np.arange(0.0, 0.100, 1.0 / 4096.0)
    current = np.where(t < 0.040, 1.5, 1.0)
    frame = pd.DataFrame({TIME: t, DISP: t * 524.0, LOAD: np.full_like(t, 1940.0), CURRENT: current})
    result = analyze_response_time_v074(
        DataSet(frame, Path("no-response.dat"), "synthetic"),
        ResponseConfig(standard=ResponseStandard.BMW),
    )
    row = result.events.iloc[0]
    assert row["Response Type"] == "No Response"
    assert np.isnan(row["Switch Time t90 ms"])


def test_normal_step_retains_first_valid_crossing_and_settling():
    t = np.arange(0.0, 0.100, 1.0 / 4096.0)
    current = np.where(t < 0.040, 1.5, 1.0)
    force = np.full_like(t, 1940.0)
    after = t >= 0.042
    force[after] = 1500.0 + 440.0 * np.exp(-(t[after] - 0.042) / 0.004)
    frame = pd.DataFrame({TIME: t, DISP: t * 524.0, LOAD: force, CURRENT: current})
    result = analyze_response_time_v074(
        DataSet(frame, Path("normal.dat"), "synthetic"),
        ResponseConfig(standard=ResponseStandard.BMW),
    )
    row = result.events.iloc[0]
    assert row["Response Type"] == "Normal Response"
    assert 5 < row["Switch Time t90 ms"] < 25
    assert row["Force Settling Time ms"] >= row["Switch Time t90 ms"]


def test_short_spike_does_not_become_valid_t90_crossing():
    t = np.arange(0.0, 0.080, 0.001)
    force = np.zeros_like(t)
    force[(t >= 0.010) & (t < 0.012)] = 1.1
    force[t >= 0.040] = np.minimum((t[t >= 0.040] - 0.040) / 0.005, 1.0)
    crossing, settled = _first_valid_force_crossing(
        t, force, 0.9, 1, 1.0, 0.02, 0.010,
    )
    assert crossing is not None and 0.043 < crossing < 0.046
    assert np.isfinite(settled) and settled > crossing
