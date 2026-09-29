"""AUDI VR-EF-33-2 section 16 force comparison for five 5 mm cycles.

The two crossings of 0.2 m/s on each compression stroke are kept separate.
The standard does not select an acceleration branch, so merging them would
hide a potentially material difference in an F-v hysteresis loop.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .dynamic_analysis import DISP, LOAD, TIME, VELOCITY


@dataclass(frozen=True)
class EdgeSensitivityResult:
    cycles: pd.DataFrame
    comparison: pd.DataFrame
    sample_rate_hz: float
    source_rows: int


def _crossing_force(v: np.ndarray, force: np.ndarray, target: float, rising: bool) -> float:
    delta = v - target
    indices = np.flatnonzero((delta[:-1] <= 0) & (delta[1:] > 0)) if rising else np.flatnonzero((delta[:-1] >= 0) & (delta[1:] < 0))
    if len(indices) != 1:
        raise ValueError(f"Expected one {'accelerating' if rising else 'decelerating'} 0.2 m/s crossing per compression stroke; found {len(indices)}")
    i = int(indices[0])
    fraction = (target - v[i]) / (v[i + 1] - v[i])
    return float(force[i] + fraction * (force[i + 1] - force[i]))


def analyze_edge_sensitivity(
    frame: pd.DataFrame,
    *,
    compression_displacement_sign: int,
    target_velocity_m_s: float = 0.2,
) -> EdgeSensitivityResult:
    """Compare first-cycle compression force with the following four cycles.

    The input must be the recorded five-cycle section, starting from rest at
    the extension endpoint with the first motion in compression. Force sign
    is preserved as measured.
    This function verifies signal shape and sampling but cannot verify rig
    temperature, current setting, preconditioning or filter cutoff.
    """
    if compression_displacement_sign not in (-1, 1):
        raise ValueError("Select whether compression decreases (-1) or increases (+1) displacement")
    if target_velocity_m_s <= 0:
        raise ValueError("Target velocity must be positive")
    missing = {TIME, DISP, LOAD} - set(frame.columns)
    if missing:
        raise ValueError(f"Missing signal columns: {', '.join(sorted(missing))}")
    data = frame[[TIME, DISP, LOAD] + ([VELOCITY] if VELOCITY in frame else [])].copy()
    if data.isna().any().any() or len(data) < 100:
        raise ValueError("Five-cycle recording has missing values or too few samples")
    t = data[TIME].to_numpy(float)
    x = data[DISP].to_numpy(float)
    force = data[LOAD].to_numpy(float)
    dt = np.diff(t)
    if not np.all(np.isfinite(t)) or not np.all(np.isfinite(x)) or not np.all(np.isfinite(force)) or np.any(dt <= 0):
        raise ValueError("Signals must be finite and time must increase strictly")
    sample_rate = 1.0 / float(np.median(dt))
    if sample_rate < 4000 * (1 - 1e-6):
        raise ValueError(f"AUDI section 16 requires at least 4 kHz; measured {sample_rate:.1f} Hz")
    velocity = data[VELOCITY].to_numpy(float) if VELOCITY in data else np.gradient(x, t) / 1000.0
    if not np.all(np.isfinite(velocity)):
        raise ValueError("Velocity contains non-finite values")
    signed_x = x * compression_displacement_sign
    signed_v = velocity * compression_displacement_sign
    center = (float(np.percentile(signed_x, 1)) + float(np.percentile(signed_x, 99))) / 2.0
    amplitude = (float(np.percentile(signed_x, 99)) - float(np.percentile(signed_x, 1))) / 2.0
    if not 4.5 <= amplitude <= 5.5:
        raise ValueError(f"AUDI section 16 requires 5 mm displacement amplitude; measured {amplitude:.2f} mm")
    peak_speed = float(np.percentile(np.abs(signed_v), 99))
    if not 0.48 <= peak_speed <= 0.57:
        raise ValueError(f"AUDI section 16 requires 0.524 m/s peak speed; measured {peak_speed:.3f} m/s")
    if signed_x[0] > center - amplitude * 0.8 or np.median(signed_v[: max(2, round(sample_rate * 0.003))]) <= 0:
        raise ValueError("Recording must start at the extension endpoint with compression as the first movement")
    period = 1.0 / 16.68
    if not 4.75 * period <= t[-1] - t[0] <= 5.25 * period:
        raise ValueError("AUDI section 16 requires a recording of five 16.68 Hz cycles")
    starts = []
    ends = []
    for cycle in range(5):
        start_window = np.flatnonzero(np.abs(t - (t[0] + cycle * period)) <= period * 0.10)
        end_window = np.flatnonzero(np.abs(t - (t[0] + (cycle + 0.5) * period)) <= period * 0.10)
        if not len(start_window) or not len(end_window):
            raise ValueError("The five-cycle recording is incomplete")
        starts.append(int(start_window[np.argmin(signed_x[start_window])]))
        ends.append(int(end_window[np.argmax(signed_x[end_window])]))
    rows = []
    for number, (start, end) in enumerate(zip(starts, ends), 1):
        if end - start < sample_rate * period * 0.35:
            raise ValueError(f"Compression stroke {number} is too short")
        stroke_v = signed_v[start:end + 1]
        stroke_f = force[start:end + 1]
        for branch, rising in (("accelerating", True), ("decelerating", False)):
            rows.append({"Cycle": number, "Branch": branch, "Force N": _crossing_force(stroke_v, stroke_f, target_velocity_m_s, rising)})
    cycles = pd.DataFrame(rows)
    comparisons = []
    for branch, group in cycles.groupby("Branch", sort=False):
        first = float(group.loc[group["Cycle"] == 1, "Force N"].item())
        following = float(group.loc[group["Cycle"] > 1, "Force N"].mean())
        comparisons.append({"Branch": branch, "Velocity m/s": target_velocity_m_s, "First cycle N": first,
                            "Following four mean N": following, "First minus following N": first - following})
    return EdgeSensitivityResult(cycles, pd.DataFrame(comparisons), sample_rate, len(data))

