import numpy as np
import pandas as pd
import pytest

from cdc_analyzer.audi_ep_56300 import (
    HIGH_SPEED_STAGES, analyze_foaming_run, analyze_high_speed_stage,
    foaming_delay_extends_beyond_center,
)
from cdc_analyzer.dynamic_analysis import DISP, LOAD, TIME


def _sinusoid(rpm, cycles, stroke, force_by_cycle=None):
    frequency = rpm / 60
    time = np.arange(0, cycles / frequency, 1 / 4000)
    displacement = stroke / 2 * np.sin(2 * np.pi * frequency * time)
    cycle_number = np.floor(time * frequency).astype(int)
    scale = np.array(force_by_cycle or [100] * cycles)[np.minimum(cycle_number, cycles - 1)]
    return pd.DataFrame({TIME: time, DISP: displacement, LOAD: scale * np.sin(2 * np.pi * frequency * time)})


def test_high_speed_program_uses_third_stage_cycle_and_keeps_nominal_order():
    assert [rpm for rpm, _ in HIGH_SPEED_STAGES] == [100, 200, 300, 400, 500, 600]
    result = analyze_high_speed_stage(_sinusoid(100, 3, 100, [40, 60, 120]), rpm=100, tensile_force_sign=1)
    assert result.cycle_count == 3
    assert result.measured_cycle_number == 3
    assert result.tensile_max_n == pytest.approx(120, rel=1e-3)
    assert result.compressive_max_n == pytest.approx(120, rel=1e-3)
    assert result.measured_peak_speed_m_s == pytest.approx(0.5236, rel=0.01)


def test_high_speed_requires_full_stage_and_correct_stroke():
    with pytest.raises(ValueError, match="three cycles"):
        analyze_high_speed_stage(_sinusoid(100, 2, 100), rpm=100, tensile_force_sign=1)
    with pytest.raises(ValueError, match="100 mm"):
        analyze_high_speed_stage(_sinusoid(100, 3, 80), rpm=100, tensile_force_sign=1)


def test_foaming_keeps_cycles_for_visual_review_and_checks_center_rule():
    result = analyze_foaming_run(_sinusoid(600, 8, 50), compression_displacement_sign=1)
    assert len(result.cycles) >= 6
    assert result.stroke_mm == pytest.approx(50, rel=0.01)
    assert result.frequency_hz == pytest.approx(10, rel=0.01)
    assert not foaming_delay_extends_beyond_center(result, -1)
    assert foaming_delay_extends_beyond_center(result, 1)

