"""First-harmonic frequency response per AUDI VR-EF-33-2 section 17."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .dynamic_analysis import DISP, LOAD, TIME


FREQUENCIES_HZ = tuple(range(25, 0, -1))
SPEEDS_M_S = (0.1, 0.2, 0.3)


@dataclass(frozen=True)
class FrequencyStepResult:
    frequency_hz: int
    target_speed_m_s: float
    measured_speed_m_s: float
    sample_rate_hz: float
    cycles: float
    loss_angle_deg: float
    dynamic_stiffness_n_mm: float
    elastic_stiffness_n_mm: float
    damping_constant_ns_mm: float


def analyze_frequency_step(frame: pd.DataFrame, *, frequency_hz: int, target_speed_m_s: float) -> FrequencyStepResult:
    """Evaluate one ten-cycle steady sine block without filtering raw samples.

    Displacement is millimetres, load newtons, time seconds. Sensor force sign
    must be set consistently by the test bench. The input block must not
    include a frequency transition or preconditioning interval.
    """
    if frequency_hz not in FREQUENCIES_HZ:
        raise ValueError("AUDI section 17 uses integer frequency steps from 25 to 1 Hz")
    if target_speed_m_s not in SPEEDS_M_S:
        raise ValueError("AUDI section 17 uses 0.1, 0.2 or 0.3 m/s target speed")
    missing = {TIME, DISP, LOAD} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    values = frame[[TIME, DISP, LOAD]].to_numpy(float)
    if len(values) < 50 or not np.isfinite(values).all():
        raise ValueError("Frequency block has too few samples or non-finite values")
    t, x, force = values.T
    dt = np.diff(t)
    if np.any(dt <= 0):
        raise ValueError("Time must increase strictly")
    rate = 1.0 / float(np.median(dt))
    if rate < 4000 * (1 - 1e-6):
        raise ValueError(f"AUDI section 17 requires 4 kHz sampling; measured {rate:.1f} Hz")
    cycles = (t[-1] - t[0]) * frequency_hz
    if not 9.95 <= cycles <= 10.5:
        raise ValueError(f"AUDI section 17 requires ten cycles per frequency; measured {cycles:.2f}")
    phase = 2 * np.pi * frequency_hz * (t - t[0])
    basis = np.column_stack((np.ones(len(t)), np.sin(phase), np.cos(phase)))
    x_fit = np.linalg.lstsq(basis, x, rcond=None)[0]
    force_fit = np.linalg.lstsq(basis, force, rcond=None)[0]
    amplitude_mm = float(np.hypot(x_fit[1], x_fit[2]))
    if amplitude_mm <= 1e-9:
        raise ValueError("Displacement fundamental is zero")
    measured_speed = amplitude_mm * 2 * np.pi * frequency_hz / 1000.0
    if abs(measured_speed - target_speed_m_s) > target_speed_m_s * 0.05:
        raise ValueError(f"Peak speed {measured_speed:.3f} m/s is outside ±5% of the selected target")
    x_residual = x - basis @ x_fit
    if float(np.sqrt(np.mean(x_residual ** 2))) > amplitude_mm * 0.05:
        raise ValueError("Displacement is not a steady sinusoid at the selected frequency")
    complex_stiffness = complex(force_fit[1], force_fit[2]) / complex(x_fit[1], x_fit[2])
    return FrequencyStepResult(
        frequency_hz=frequency_hz,
        target_speed_m_s=target_speed_m_s,
        measured_speed_m_s=measured_speed,
        sample_rate_hz=rate,
        cycles=cycles,
        loss_angle_deg=float(np.degrees(np.angle(complex_stiffness))),
        dynamic_stiffness_n_mm=float(abs(complex_stiffness)),
        elastic_stiffness_n_mm=float(complex_stiffness.real),
        damping_constant_ns_mm=float(complex_stiffness.imag / (2 * np.pi * frequency_hz)),
    )


def compile_frequency_response(steps: Mapping[tuple[str, float, int], FrequencyStepResult], *, regulated: bool) -> pd.DataFrame:
    """Require the standard's full current, speed and descending-frequency grid."""
    currents = ("soft", "medium") if regulated else ("passive",)
    expected = [(current, speed, frequency) for current in currents for speed in SPEEDS_M_S for frequency in FREQUENCIES_HZ]
    if set(steps) != set(expected):
        missing = [key for key in expected if key not in steps]
        extra = [key for key in steps if key not in expected]
        raise ValueError(f"Incomplete AUDI section 17 grid: {len(missing)} missing, {len(extra)} unexpected; first missing {missing[:1]}")
    rows = []
    for current, speed, frequency in expected:
        result = steps[current, speed, frequency]
        if result.frequency_hz != frequency or result.target_speed_m_s != speed:
            raise ValueError(f"Frequency step metadata mismatch: {(current, speed, frequency)}")
        rows.append({
            "Current": current,
            "Target speed m/s": speed,
            "Frequency Hz": frequency,
            "Measured speed m/s": result.measured_speed_m_s,
            "Loss angle deg": result.loss_angle_deg,
            "Dynamic stiffness N/mm": result.dynamic_stiffness_n_mm,
            "Elastic stiffness N/mm": result.elastic_stiffness_n_mm,
            "Damping constant Ns/mm": result.damping_constant_ns_mm,
        })
    return pd.DataFrame(rows)

