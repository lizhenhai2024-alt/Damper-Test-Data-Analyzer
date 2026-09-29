import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.audi_edge_sensitivity import analyze_edge_sensitivity
from cdc_analyzer.dynamic_analysis import DISP, LOAD, TIME, VELOCITY


def _five_cycles(sample_rate=5000, first_extra=42.0, displacement_sign=1):
    frequency = 16.68
    time = np.arange(0, 5 / frequency, 1 / sample_rate)
    phase = 2 * np.pi * frequency * time
    displacement = displacement_sign * (-5 * np.cos(phase))
    velocity = displacement_sign * (5 * 2 * np.pi * frequency * np.sin(phase) / 1000)
    compression_velocity = velocity * displacement_sign
    compression_half = compression_velocity > 0
    first_half = time < 0.5 / frequency
    force = 100 * compression_velocity + 7 * np.cos(phase)
    force += first_extra * (compression_half & first_half)
    return pd.DataFrame({TIME: time, DISP: displacement, LOAD: force, VELOCITY: velocity})


def test_section_16_first_cycle_compared_separately_on_both_fv_branches():
    result = analyze_edge_sensitivity(_five_cycles(), compression_displacement_sign=1)
    assert result.sample_rate_hz == pytest.approx(5000)
    assert result.cycles["Cycle"].nunique() == 5
    assert set(result.comparison["Branch"]) == {"accelerating", "decelerating"}
    assert result.comparison["First minus following N"].to_numpy() == pytest.approx([42, 42], abs=0.2)


def test_section_16_rejects_wrong_rate_and_first_motion():
    with pytest.raises(ValueError, match="at least 4 kHz"):
        analyze_edge_sensitivity(_five_cycles(sample_rate=2000), compression_displacement_sign=1)
    with pytest.raises(ValueError, match="first movement"):
        analyze_edge_sensitivity(_five_cycles(displacement_sign=-1), compression_displacement_sign=1)

