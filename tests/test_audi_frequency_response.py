import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.audi_frequency_response import (
    FREQUENCIES_HZ, SPEEDS_M_S, analyze_frequency_step, compile_frequency_response,
)
from cdc_analyzer.dynamic_analysis import DISP, LOAD, TIME


def _step(frequency=8, speed=0.2, rate=4000, stiffness=20, damping=0.3):
    time = np.arange(0, 10 / frequency, 1 / rate)
    omega = 2 * np.pi * frequency
    displacement = speed * 1000 / omega * np.sin(omega * time)
    force = stiffness * displacement + damping * omega * speed * 1000 / omega * np.cos(omega * time)
    return pd.DataFrame({TIME: time, DISP: displacement, LOAD: force})


def test_frequency_step_uses_first_harmonic_for_four_required_metrics():
    result = analyze_frequency_step(_step(), frequency_hz=8, target_speed_m_s=0.2)
    expected_dynamic = np.hypot(20, 0.3 * 2 * np.pi * 8)
    assert result.dynamic_stiffness_n_mm == pytest.approx(expected_dynamic, rel=1e-5)
    assert result.elastic_stiffness_n_mm == pytest.approx(20, rel=1e-5)
    assert result.damping_constant_ns_mm == pytest.approx(0.3, rel=1e-5)
    assert result.loss_angle_deg == pytest.approx(np.degrees(np.arctan2(0.3 * 2 * np.pi * 8, 20)), rel=1e-5)


def test_frequency_step_rejects_low_rate_and_wrong_speed():
    with pytest.raises(ValueError, match="4 kHz"):
        analyze_frequency_step(_step(rate=1000), frequency_hz=8, target_speed_m_s=0.2)
    with pytest.raises(ValueError, match="Peak speed"):
        analyze_frequency_step(_step(speed=0.1), frequency_hz=8, target_speed_m_s=0.2)


def test_full_grid_requires_all_frequencies_and_speeds_in_order():
    result = analyze_frequency_step(_step(), frequency_hz=8, target_speed_m_s=0.2)
    with pytest.raises(ValueError, match="Incomplete"):
        compile_frequency_response({("soft", 0.2, 8): result}, regulated=True)
    steps = {(current, speed, frequency): analyze_frequency_step(_step(frequency, speed), frequency_hz=frequency, target_speed_m_s=speed)
             for current in ("soft", "medium") for speed in SPEEDS_M_S for frequency in FREQUENCIES_HZ}
    report = compile_frequency_response(steps, regulated=True)
    assert len(report) == 150
    assert report.iloc[0]["Frequency Hz"] == 25
    assert report.iloc[24]["Frequency Hz"] == 1

