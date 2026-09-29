"""Signal evaluations referenced by Audi VR-EF-33-2 sections 6 and 14.

EP 56300.11 (2003-04) specifies six increasing speed stages and using the
third cycle of each stage. EP 56300.13 (2003-04) primarily requires visual
inspection of unfiltered force-displacement loops; it gives no numeric
threshold for a force-build-up delay before mid-stroke.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .analysis import AnalyzerConfig, EvaluationProfile, detect_complete_cycles
from .dynamic_analysis import DISP, LOAD, TIME


HIGH_SPEED_STAGES = ((100, 0.5236), (200, 1.04), (300, 1.57), (400, 2.09), (500, 2.62), (600, 2.98))


@dataclass(frozen=True)
class HighSpeedStageResult:
    rpm: int
    nominal_speed_m_s: float
    measured_peak_speed_m_s: float
    tensile_max_n: float
    compressive_max_n: float
    cycle_count: int
    measured_cycle_number: int
    measurement_cycle: pd.DataFrame


@dataclass(frozen=True)
class FoamingRunResult:
    cycles: list[pd.DataFrame]
    stroke_mm: float
    frequency_hz: float
    center_mm: float
    compression_displacement_sign: int


def _valid_frame(frame: pd.DataFrame) -> pd.DataFrame:
    missing = {TIME, DISP, LOAD} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    data = frame[[TIME, DISP, LOAD]].copy()
    for name in (TIME, DISP, LOAD):
        data[name] = pd.to_numeric(data[name], errors="coerce")
    if len(data) < 30 or data.isna().any().any() or not np.isfinite(data.to_numpy(float)).all():
        raise ValueError("Raw recording needs finite time, displacement and force samples")
    if np.any(np.diff(data[TIME].to_numpy(float)) <= 0):
        raise ValueError("Time must increase strictly")
    return data.reset_index(drop=True)


def _cycles(data: pd.DataFrame) -> list[tuple[int, int]]:
    return detect_complete_cycles(data, AnalyzerConfig(profile=EvaluationProfile.AUDI))


def analyze_high_speed_stage(
    frame: pd.DataFrame, *, rpm: int, tensile_force_sign: int, force_zero_n: float = 0.0
) -> HighSpeedStageResult:
    """Evaluate the third complete cycle of one EP 56300.11 speed stage."""
    nominal = dict(HIGH_SPEED_STAGES).get(rpm)
    if nominal is None:
        raise ValueError("EP 56300.11 specifies 100, 200, 300, 400, 500 and 600 rpm")
    if tensile_force_sign not in (-1, 1) or not np.isfinite(force_zero_n):
        raise ValueError("Select tensile force sign and a finite TL 295 reference zero")
    data = _valid_frame(frame)
    time = data[TIME].to_numpy(float)
    period = 60.0 / rpm
    recorded_cycles = (time[-1] - time[0]) / period
    if not 2.95 <= recorded_cycles <= 3.10:
        raise ValueError(f"EP 56300.11 stage file must contain three cycles; measured {recorded_cycles:.2f}")
    measured = data.loc[data[TIME] >= time[0] + 2 * period].copy()
    if len(measured) < 30:
        raise ValueError("Third measurement cycle has too few samples")
    x = measured[DISP].to_numpy(float)
    t = measured[TIME].to_numpy(float)
    stroke = float(np.ptp(x))
    if not 95 <= stroke <= 105:
        raise ValueError(f"EP 56300.11 requires 100 mm total stroke; measured {stroke:.1f} mm")
    frequency = 1.0 / (t[-1] - t[0])
    if abs(frequency - rpm / 60) > rpm / 60 * 0.10:
        raise ValueError(f"Selected cycle frequency {frequency:.2f} Hz differs from {rpm} rpm")
    force = (measured[LOAD].to_numpy(float) - force_zero_n) * tensile_force_sign
    velocity = np.gradient(x, t) / 1000.0
    return HighSpeedStageResult(
        rpm=rpm, nominal_speed_m_s=nominal,
        measured_peak_speed_m_s=float(np.max(np.abs(velocity))),
        tensile_max_n=float(np.max(force)),
        compressive_max_n=float(np.max(-force)),
        cycle_count=3, measured_cycle_number=3,
        measurement_cycle=measured,
    )


def analyze_foaming_run(frame: pd.DataFrame, *, compression_displacement_sign: int) -> FoamingRunResult:
    """Prepare unfiltered EP 56300.13 force-displacement cycles for review."""
    if compression_displacement_sign not in (-1, 1):
        raise ValueError("Select compression displacement direction")
    data = _valid_frame(frame)
    bounds = _cycles(data)
    if not bounds:
        raise ValueError("No complete foaming-test cycle found")
    cycles = [data.iloc[start:end + 1].copy() for start, end in bounds]
    stroke = float(np.median([np.ptp(cycle[DISP].to_numpy(float)) for cycle in cycles]))
    frequency = float(np.median([1.0 / (cycle[TIME].iloc[-1] - cycle[TIME].iloc[0]) for cycle in cycles]))
    if not 47.5 <= stroke <= 52.5:
        raise ValueError(f"EP 56300.13 requires 50 mm total stroke; measured {stroke:.1f} mm")
    if not 9.0 <= frequency <= 11.0:
        raise ValueError(f"EP 56300.13 requires 600 rpm (10 Hz); measured {frequency:.2f} Hz")
    center = (float(data[DISP].max()) + float(data[DISP].min())) / 2
    return FoamingRunResult(cycles, stroke, frequency, center, compression_displacement_sign)


def foaming_delay_extends_beyond_center(result: FoamingRunResult, delay_end_displacement_mm: float) -> bool:
    """Assess an operator-marked delay endpoint against the normative center boundary."""
    if not np.isfinite(delay_end_displacement_mm):
        raise ValueError("Delay endpoint must be finite")
    return bool(result.compression_displacement_sign * (delay_end_displacement_mm - result.center_mm) > 0)

