from __future__ import annotations

from math import ceil

import numpy as np
import pandas as pd

from .dynamic_analysis import (
    CURRENT,
    DISP,
    LOAD,
    TIME,
    VELOCITY,
    ResponseAnalysisResult,
    ResponseConfig,
    ResponseStandard,
)
from .parser import DataSet

BMW_TARGET_SPEEDS_MPS = (0.0131, 0.524, 1.048)
AUDI_TARGET_SPEEDS_MPS = (0.052, 0.131, 0.262, 0.524)
DEFAULT_TARGET_SPEED_TOLERANCE = 0.10
LOW_SPEED_TOLERANCE_FLOOR_MPS = 0.002
MIN_POST_TARGET_WINDOW_S = 0.004
MAX_TARGET_SPEED_GAP_S = 0.008


def _sample_rate_hz(frame: pd.DataFrame) -> float:
    t = frame[TIME].to_numpy(float)
    dt = np.diff(t)
    dt = dt[np.isfinite(dt) & (dt > 0)]
    return float(1.0 / np.median(dt)) if len(dt) else float("nan")


def _interpolate_time(t: np.ndarray, y: np.ndarray, target_t: float) -> float:
    return float(np.interp(target_t, t, y))


def _first_level_crossing(
    t: np.ndarray,
    y: np.ndarray,
    target: float,
    *,
    direction: int = 0,
) -> float | None:
    for i in range(len(y) - 1):
        y0 = float(y[i])
        y1 = float(y[i + 1])
        if direction > 0 and y1 <= y0:
            continue
        if direction < 0 and y1 >= y0:
            continue
        if (y0 - target) * (y1 - target) <= 0 and y1 != y0:
            q = (target - y0) / (y1 - y0)
            if 0.0 <= q <= 1.0:
                return float(t[i] + q * (t[i + 1] - t[i]))
    return None


def _robust_noise(values: np.ndarray) -> float:
    median = float(np.median(values))
    return float(1.4826 * np.median(np.abs(values - median)))


def _settled_time(
    t: np.ndarray, values: np.ndarray, center: float, band: float,
    start: float, dwell_s: float,
) -> float:
    """First entry into a band maintained for the full dwell interval."""
    for idx in np.flatnonzero((t >= start) & (np.abs(values - center) <= band)):
        end = int(np.searchsorted(t, t[idx] + dwell_s, side="left"))
        if end < len(t) and np.all(np.abs(values[idx : end + 1] - center) <= band):
            return float(t[idx])
    return float("nan")


def _first_valid_force_crossing(
    t: np.ndarray, values: np.ndarray, threshold: float, direction: int,
    final_force: float, band: float, dwell_s: float,
) -> tuple[float | None, float]:
    """Accept a directed F90 crossing sustained for the required dwell."""
    start = 0
    unverified: float | None = None
    while start < len(t) - 1:
        crossing = _first_level_crossing(t[start:], values[start:], threshold, direction=direction)
        if crossing is None:
            break
        settled = _settled_time(t, values, final_force, band, crossing, dwell_s)
        dwell_end = crossing + dwell_s
        if dwell_end <= t[-1]:
            dwell_values = values[(t > crossing) & (t < dwell_end)]
            dwell_values = np.concatenate((dwell_values, [np.interp(dwell_end, t, values)]))
            if np.all(direction * (dwell_values - threshold) >= -band):
                return crossing, settled
        if t[-1] - crossing < dwell_s and unverified is None:
            unverified = crossing
        start = int(np.searchsorted(t, crossing, side="right"))
    return unverified, float("nan")


def _target_speeds(standard: ResponseStandard) -> tuple[float, ...]:
    return BMW_TARGET_SPEEDS_MPS if standard == ResponseStandard.BMW else AUDI_TARGET_SPEEDS_MPS


def _smooth_signal(values: np.ndarray, sample_rate_hz: float, window_ms: float) -> np.ndarray:
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        window = 5
    else:
        window = max(3, int(round(sample_rate_hz * window_ms / 1000.0)))
    if window % 2 == 0:
        window += 1
    return (
        pd.Series(values)
        .rolling(window, center=True, min_periods=1)
        .median()
        .to_numpy(float)
    )


def _detect_current_events(data: pd.DataFrame, config: ResponseConfig) -> list[int]:
    t = data[TIME].to_numpy(float)
    current = data[CURRENT].to_numpy(float)
    if len(current) < 8:
        return []
    sample_rate = _sample_rate_hz(data)
    smooth = _smooth_signal(current, sample_rate, 0.75)
    slope = np.abs(np.gradient(smooth, t))
    finite = slope[np.isfinite(slope)]
    if not len(finite):
        return []
    peak = float(np.max(finite))
    if peak <= 0:
        return []
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    robust_noise = median + 8.0 * max(mad, 1e-12)
    relative = min(max(float(config.event_derivative_fraction), 0.02), 0.10) * peak
    threshold = max(robust_noise, relative)
    mask = slope >= threshold

    groups: list[list[int]] = []
    active: list[int] = []
    for idx, state in enumerate(mask):
        if bool(state):
            active.append(idx)
        elif active:
            groups.append(active)
            active = []
    if active:
        groups.append(active)

    candidates = [max(group, key=lambda i: slope[i]) for group in groups if group]
    accepted: list[int] = []
    for candidate in candidates:
        if not accepted:
            accepted.append(candidate)
            continue
        if t[candidate] - t[accepted[-1]] >= config.min_event_separation_s:
            accepted.append(candidate)
        elif slope[candidate] > slope[accepted[-1]]:
            accepted[-1] = candidate
    return accepted


def _event_boundaries(length: int, events: list[int]) -> list[tuple[int, int]]:
    if not events:
        return []
    bounds: list[tuple[int, int]] = []
    for i, event_idx in enumerate(events):
        if i == 0:
            start = (
                max(0, event_idx - (events[i + 1] - event_idx) // 2)
                if len(events) > 1
                else 0
            )
        else:
            start = (events[i - 1] + event_idx) // 2
        if i == len(events) - 1:
            end = (
                min(length - 1, event_idx + (event_idx - events[i - 1]) // 2)
                if len(events) > 1
                else length - 1
            )
        else:
            end = (event_idx + events[i + 1]) // 2
        bounds.append((max(0, start), min(length - 1, end)))
    return bounds


def _local_plateau_levels(
    segment: pd.DataFrame,
    plateau_fraction: float,
) -> tuple[float, float]:
    current = segment[CURRENT].to_numpy(float)
    if len(current) < 6:
        split = max(1, len(current) // 3)
        return float(np.median(current[:split])), float(np.median(current[-split:]))
    count = max(5, int(round(max(0.05, min(0.30, plateau_fraction)) * len(current))))
    return float(np.median(current[:count])), float(np.median(current[-count:]))


def _nearest_target_speed(
    measured_speed_mps: float,
    standard: ResponseStandard,
    tolerance_fraction: float,
) -> tuple[float, float, float, bool]:
    magnitude = abs(float(measured_speed_mps))
    targets = _target_speeds(standard)
    target = min(targets, key=lambda value: abs(magnitude - value))
    tolerance = max(target * tolerance_fraction, LOW_SPEED_TOLERANCE_FLOOR_MPS)
    error = abs(magnitude - target)
    error_pct = error / target * 100.0 if target > 0 else float("nan")
    return float(target), float(tolerance), float(error_pct), bool(error <= tolerance)


def _target_speed_component(
    segment: pd.DataFrame,
    t0: float,
    signed_target_mps: float,
    tolerance_mps: float,
) -> tuple[int, int] | None:
    t = segment[TIME].to_numpy(float)
    v = segment[VELOCITY].to_numpy(float)
    if len(segment) < 3:
        return None
    sign = 1.0 if signed_target_mps >= 0 else -1.0
    target_mag = abs(signed_target_mps)
    mask = (v * sign > 0) & (np.abs(np.abs(v) - target_mag) <= tolerance_mps)

    if len(mask) >= 5:
        ratio = pd.Series(mask.astype(float)).rolling(5, center=True, min_periods=1).mean().to_numpy()
        mask = mask | (ratio >= 0.60)

    # MTS displacement feedback can produce a short velocity ripple even while
    # the rig remains in its commanded constant-speed stroke.  Do not let one
    # such ripple split an otherwise continuous evaluation window.  A gap is
    # bridged only when valid target-speed samples bound it on both sides, so a
    # real stroke reversal or sustained speed departure remains excluded.
    invalid = np.flatnonzero(~mask)
    cursor = 0
    while cursor < len(invalid):
        run_end = cursor
        while run_end + 1 < len(invalid) and invalid[run_end + 1] == invalid[run_end] + 1:
            run_end += 1
        left = int(invalid[cursor]) - 1
        right = int(invalid[run_end]) + 1
        if (
            left >= 0
            and right < len(mask)
            and mask[left]
            and mask[right]
            and float(t[right] - t[left]) <= MAX_TARGET_SPEED_GAP_S
        ):
            mask[left + 1 : right] = True
        cursor = run_end + 1

    center = int(np.argmin(np.abs(t - t0)))
    if not mask[center]:
        nearby = np.flatnonzero(mask & (np.abs(t - t0) <= 0.0015))
        if not len(nearby):
            return None
        center = int(nearby[np.argmin(np.abs(t[nearby] - t0))])

    left = center
    while left > 0 and mask[left - 1]:
        left -= 1
    right = center
    while right + 1 < len(mask) and mask[right + 1]:
        right += 1
    return left, right


def _apply_stage_labels(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events
    out = events.copy()
    evidence: dict[float, list[float]] = {}
    for _, row in out.iterrows():
        start_level = round(float(row["Current Start A"]), 1)
        end_level = round(float(row["Current End A"]), 1)
        evidence.setdefault(start_level, []).append(abs(float(row["F0 N"])))
        evidence.setdefault(end_level, []).append(abs(float(row["F100 N"])))

    state_map: dict[float, str] = {}
    if 2 <= len(evidence) <= 3:
        ranked = sorted(
            ((float(np.median(values)), level) for level, values in evidence.items()),
            key=lambda item: item[0],
        )
        magnitudes = [item[0] for item in ranked]
        if len(magnitudes) == 2:
            denom = max(magnitudes[-1], 1.0)
            clear = (magnitudes[-1] - magnitudes[0]) / denom >= 0.03
            if clear:
                state_map[ranked[0][1]] = "Soft"
                state_map[ranked[-1][1]] = "Hard"
        elif len(magnitudes) == 3:
            denom = max(magnitudes[-1], 1.0)
            clear = min(
                magnitudes[1] - magnitudes[0],
                magnitudes[2] - magnitudes[1],
            ) / denom >= 0.02
            if clear:
                state_map[ranked[0][1]] = "Soft"
                state_map[ranked[1][1]] = "Medium"
                state_map[ranked[2][1]] = "Hard"

    stages: list[str] = []
    transitions: list[str] = []
    for _, row in out.iterrows():
        start = float(row["Current Start A"])
        end = float(row["Current End A"])
        start_level = round(start, 1)
        end_level = round(end, 1)
        transitions.append(f"{start:.3f}A→{end:.3f}A")
        if start_level in state_map and end_level in state_map:
            stages.append(f"{state_map[start_level]}→{state_map[end_level]}")
        else:
            stages.append(f"{start:.2f}A→{end:.2f}A")
    out.insert(2, "Stage", stages)
    out.insert(3, "Current Transition", transitions)
    return out


def analyze_response_time_v074(
    dataset: DataSet,
    config: ResponseConfig | None = None,
    *,
    target_speed_tolerance: float = DEFAULT_TARGET_SPEED_TOLERANCE,
) -> ResponseAnalysisResult:
    config = config or ResponseConfig()
    if not 0 < config.trigger_fraction < 1:
        raise ValueError("Trigger fraction must be between 0 and 1")
    if not 0 < config.force_start_fraction < 0.63:
        raise ValueError("Initial force fraction must be between 0 and 0.63")
    if not 0 < config.end_average_fraction <= 0.5:
        raise ValueError("End-average fraction must be in (0, 0.5]")
    if not 0 < target_speed_tolerance <= 0.5:
        raise ValueError("Target-speed tolerance must be in (0, 0.5]")
    if config.force_separation_noise_factor <= 0 or config.force_separation_fraction < 0:
        raise ValueError("Force separation thresholds must be nonnegative")
    if config.response_dwell_s <= 0:
        raise ValueError("Response dwell must be positive")

    cols = [TIME, DISP, LOAD, CURRENT]
    missing = [column for column in cols if column not in dataset.data.columns]
    if missing:
        raise ValueError(f"Missing dynamic response channel(s): {', '.join(missing)}")

    data = dataset.data[cols].dropna().sort_values(TIME).reset_index(drop=True).copy()
    if len(data) < 8:
        raise ValueError("Response-time analysis requires at least 8 valid samples")
    t = data[TIME].to_numpy(float)
    if np.any(np.diff(t) <= 0):
        raise ValueError("Response-time data requires strictly increasing time")

    x = data[DISP].to_numpy(float)
    sample_rate_all = _sample_rate_hz(data)
    raw_velocity = np.gradient(x, t) / 1000.0
    data[VELOCITY] = _smooth_signal(raw_velocity, sample_rate_all, 1.0)

    candidates = _detect_current_events(data, config)
    if not candidates:
        raise ValueError("No current-step transition could be detected in the full file")
    boundaries = _event_boundaries(len(data), candidates)

    rows: list[dict[str, object]] = []
    rejected_non_target = 0
    rejected_invalid = 0
    for detected_no, (event_index, (start, end)) in enumerate(zip(candidates, boundaries), start=1):
        segment = data.iloc[start : end + 1].reset_index(drop=True)
        if len(segment) < 10:
            rejected_invalid += 1
            continue
        ts = segment[TIME].to_numpy(float)
        xs = segment[DISP].to_numpy(float)
        fs = segment[LOAD].to_numpy(float)
        currents = segment[CURRENT].to_numpy(float)
        velocities = segment[VELOCITY].to_numpy(float)
        event_time = float(data.iloc[event_index][TIME])
        sample_rate = _sample_rate_hz(segment)

        current_start, current_end = _local_plateau_levels(segment, config.plateau_fraction)
        delta_current = current_end - current_start
        if abs(delta_current) < config.min_current_step_a:
            rejected_invalid += 1
            continue

        trigger_current = current_start + config.trigger_fraction * delta_current
        search_mask = (ts >= event_time - 0.010) & (ts <= event_time + 0.015)
        if np.count_nonzero(search_mask) < 3:
            search_mask = np.ones_like(ts, dtype=bool)
        t_search = ts[search_mask]
        i_search = currents[search_mask]
        t0 = _first_level_crossing(
            t_search,
            i_search,
            trigger_current,
            direction=1 if delta_current > 0 else -1,
        )
        if t0 is None:
            rejected_invalid += 1
            continue

        velocity_0 = _interpolate_time(ts, velocities, t0)
        target_mag, target_tolerance_mps, speed_error_pct, on_target = _nearest_target_speed(
            velocity_0,
            config.standard,
            target_speed_tolerance,
        )
        if not on_target:
            rejected_non_target += 1
            continue

        signed_target = target_mag if velocity_0 >= 0 else -target_mag
        component = _target_speed_component(segment, t0, signed_target, target_tolerance_mps)
        if component is None:
            rejected_non_target += 1
            continue
        target_left, target_right = component
        target_segment = segment.iloc[target_left : target_right + 1].reset_index(drop=True)
        eval_t = target_segment[TIME].to_numpy(float)
        eval_f = target_segment[LOAD].to_numpy(float)
        eval_x = target_segment[DISP].to_numpy(float)

        if float(eval_t[-1] - t0) < MIN_POST_TARGET_WINDOW_S:
            rejected_non_target += 1
            continue

        pre_force = eval_f[eval_t < t0]
        force_0 = float(np.median(pre_force)) if len(pre_force) >= 5 else _interpolate_time(eval_t, eval_f, t0)
        x_0 = _interpolate_time(eval_t, eval_x, t0)

        post_mask = eval_t > t0
        post_force = eval_f[post_mask]
        if len(post_force) < 4:
            rejected_invalid += 1
            continue
        end_n = max(3, int(ceil(config.end_average_fraction * len(post_force))))
        end_force = post_force[-end_n:]
        force_100 = float(np.median(end_force))
        delta_force = force_100 - force_0
        noise_before = _robust_noise(pre_force) if len(pre_force) >= 5 else float("nan")
        noise_after = _robust_noise(end_force)
        noise = max(noise_before if np.isfinite(noise_before) else 0.0, noise_after, 1.0)
        separation_limit = max(
            config.force_separation_noise_factor * noise,
            config.force_separation_fraction * max(abs(force_0), abs(force_100)),
        )
        classical_valid = abs(delta_force) > separation_limit
        dip_index = int(np.argmin(post_force))
        dip_force = float(post_force[dip_index])
        dip_time = float(eval_t[post_mask][dip_index])
        dip_depth = force_0 - dip_force
        is_dip = not classical_valid and dip_depth > separation_limit
        response_type = "Normal Response" if classical_valid else (
            "Dip & Recovery" if is_dip else "No Response"
        )
        force_recovery_time = (
            _settled_time(eval_t, eval_f, force_0,
                          max(0.02 * abs(force_0), 3.0 * noise),
                          dip_time, config.response_dwell_s)
            if is_dip else float("nan")
        )
        dip_start = (
            _first_level_crossing(
                np.concatenate(([t0], eval_t[post_mask])),
                np.concatenate(([_interpolate_time(eval_t, eval_f, t0)], post_force)),
                force_0 - 0.1 * dip_depth, direction=-1,
            ) if is_dip else None
        )
        area_end = force_recovery_time if np.isfinite(force_recovery_time) else float(eval_t[-1])
        area_mask = (eval_t >= t0) & (eval_t <= area_end)
        dip_area = float(np.trapezoid(np.maximum(force_0 - eval_f[area_mask], 0), eval_t[area_mask])) if is_dip else float("nan")
        current_min = current_undershoot = current_max = current_overshoot = float("nan")
        if config.calculate_current_undershoot:
            response_current = currents[(ts >= t0) & (ts <= eval_t[-1])]
            if delta_current < 0:
                current_min = float(np.min(response_current))
                current_undershoot = max(0.0, current_end - current_min)
            else:
                current_max = float(np.max(response_current))
                current_overshoot = max(0.0, current_max - current_end)
        current_settle = _settled_time(ts, currents, current_end,
                                       max(0.02 * abs(current_end), 0.01),
                                       t0, config.response_dwell_s)

        force_direction = 1 if delta_force > 0 else -1
        response_t = np.concatenate(([t0], eval_t[post_mask]))
        response_f = np.concatenate(([force_0], eval_f[post_mask]))
        thresholds: dict[float, tuple[float, float | None]] = {}
        for fraction in (config.force_start_fraction, 0.63, 0.90):
            target_force = force_0 + fraction * delta_force
            crossing = _first_level_crossing(
                response_t,
                response_f,
                target_force,
                direction=force_direction,
            ) if classical_valid else None
            thresholds[fraction] = (target_force if classical_valid else float("nan"), crossing)

        force_settle = float("nan")
        if classical_valid:
            valid_90, force_settle = _first_valid_force_crossing(
                response_t, response_f, thresholds[0.90][0], force_direction,
                force_100, max(0.02 * abs(force_0), 3.0 * noise),
                config.response_dwell_s,
            )
            thresholds[0.90] = (thresholds[0.90][0], valid_90)
            start_cross = thresholds[config.force_start_fraction][1]
            middle_cross = thresholds[0.63][1]
            if (valid_90 is not None and start_cross is not None and middle_cross is not None
                    and not (start_cross < middle_cross < valid_90
                             and (not np.isfinite(force_settle) or valid_90 <= force_settle))):
                thresholds[0.90] = (thresholds[0.90][0], None)
                force_settle = float("nan")

        def elapsed_ms(crossing: float | None) -> float:
            if crossing is None or crossing < t0:
                return float("nan")
            return float((crossing - t0) * 1000.0)

        t1_cross = thresholds[config.force_start_fraction][1]
        t63_cross = thresholds[0.63][1]
        t90_cross = thresholds[0.90][1]
        t63_s = (t63_cross - t0) if t63_cross is not None else float("nan")
        t90_s = (t90_cross - t0) if t90_cross is not None else float("nan")
        gradient63 = (
            abs(thresholds[0.63][0] - force_0) / t63_s
            if np.isfinite(t63_s) and t63_s > 0
            else float("nan")
        )
        gradient90 = (
            abs(thresholds[0.90][0] - force_0) / t90_s
            if np.isfinite(t90_s) and t90_s > 0
            else float("nan")
        )

        direction_probe = float(np.median(eval_f[np.abs(eval_t - t0) <= 0.001]))
        if not np.isfinite(direction_probe) or abs(direction_probe) < 5.0:
            direction_probe = force_0
        direction = "Rebound" if direction_probe > 0 else "Compression"

        issues: list[str] = []
        if config.standard == ResponseStandard.AUDI and np.isfinite(sample_rate) and sample_rate < 4000.0:
            issues.append(f"sample rate below Audi 4 kHz ({sample_rate:.2f} Hz)")
        if not classical_valid:
            issues.append("steady-state force separation insufficient; classical t63/t90 not applicable")
        elif any(value[1] is None for value in thresholds.values()):
            issues.append("one or more force thresholds not crossed inside target-speed window")
        elif not np.isfinite(force_settle):
            issues.append("t90 crossing observed, but target-speed window too short to verify settling dwell")
        local_velocity = target_segment[target_segment[TIME].between(t0 - 0.003, t0 + 0.003)][VELOCITY].abs()
        if len(local_velocity) >= 3 and float(local_velocity.mean()) > 0:
            variation = float(local_velocity.std(ddof=0) / local_velocity.mean())
            if variation > 0.10:
                issues.append("velocity variation around switching exceeds 10%")

        switch90 = elapsed_ms(t90_cross)
        trigger_reference = f"I{config.trigger_fraction * 100:g}% current crossing"
        if not classical_valid:
            status = "Invalid" if not is_dip else "Warning"
        elif config.t90_limit_ms is None:
            status = "Warning" if issues else "OK"
        elif not np.isfinite(switch90):
            status = "Invalid"
        else:
            status = "PASS" if switch90 <= config.t90_limit_ms else "FAIL"

        display_start = max(float(eval_t[0]), t0 - 0.015)
        display_end = min(float(eval_t[-1]), t0 + 0.035)
        if np.isfinite(switch90):
            display_end = min(float(eval_t[-1]), max(display_end, t0 + 1.5 * switch90 / 1000.0))

        rows.append(
            {
                "Event ID": len(rows) + 1,
                "Detected Event ID": detected_no,
                "OEM": config.standard.value.upper(),
                "Current Start A": current_start,
                "Current End A": current_end,
                "Current Delta A": delta_current,
                "Trigger Fraction": config.trigger_fraction,
                "Trigger Current A": trigger_current,
                "Current 100% A": current_end,
                "t0 s": t0,
                "I10 Crossing Time s": t0,
                "Trigger Crossing Time s": t0,
                "F1 Crossing Time s": float(t1_cross) if t1_cross is not None else float("nan"),
                "Initial Force Crossing Time s": float(t1_cross) if t1_cross is not None else float("nan"),
                "F63 Crossing Time s": float(t63_cross) if t63_cross is not None else float("nan"),
                "F90 Crossing Time s": float(t90_cross) if t90_cross is not None else float("nan"),
                "Timing Reference": trigger_reference,
                "Displacement at t0 mm": x_0,
                "Velocity at t0 m/s": velocity_0,
                "Target Velocity m/s": signed_target,
                "Target Speed Error %": speed_error_pct,
                "Target Window Start s": float(eval_t[0]),
                "Target Window End s": float(eval_t[-1]),
                "Display Start s": display_start,
                "Display End s": display_end,
                "Direction": direction,
                "Response Type": response_type,
                "Force Separation Limit N": separation_limit,
                "Force Noise Before N": noise_before,
                "Force Noise After N": noise_after,
                "Force Dip N": dip_depth if is_dip else float("nan"),
                "Force Minimum N": dip_force if is_dip else float("nan"),
                "Force Minimum Time s": dip_time if is_dip else float("nan"),
                "Dip Delay ms": (dip_start - t0) * 1000 if dip_start is not None else float("nan"),
                "Time to Force Minimum ms": (dip_time - t0) * 1000 if is_dip else float("nan"),
                "Force Recovery Time ms": (force_recovery_time - t0) * 1000 if np.isfinite(force_recovery_time) else float("nan"),
                "Force Settling Time ms": (force_settle - t0) * 1000 if np.isfinite(force_settle) else float("nan"),
                "Force Dip Area N s": dip_area,
                "Current Minimum A": current_min,
                "Current Undershoot A": current_undershoot,
                "Current Undershoot %": 100 * current_undershoot / abs(delta_current) if delta_current < 0 else float("nan"),
                "Current Maximum A": current_max,
                "Current Overshoot A": current_overshoot,
                "Current Overshoot %": 100 * current_overshoot / abs(delta_current) if delta_current > 0 else float("nan"),
                "Current Settling Time ms": (current_settle - t0) * 1000 if np.isfinite(current_settle) else float("nan"),
                "Force Change": "Build-up" if abs(force_100) > abs(force_0) else "Decay",
                "F0 N": force_0,
                "F100 N": force_100,
                "Delta F N": delta_force,
                "Force Start Fraction": config.force_start_fraction,
                "F1 N": thresholds[config.force_start_fraction][0],
                "Initial Force Threshold N": thresholds[config.force_start_fraction][0],
                "F63 N": thresholds[0.63][0],
                "F90 N": thresholds[0.90][0],
                "Dead Time t1 ms": elapsed_ms(t1_cross),
                "Initial Force Response Time ms": elapsed_ms(t1_cross),
                "Switch Time t63 ms": elapsed_ms(t63_cross),
                "Switch Time t90 ms": switch90,
                "Gradient 63 N/s": gradient63,
                "Gradient 90 N/s": gradient90,
                "Sample Rate Hz": sample_rate,
                "Segment Start s": float(ts[0]),
                "Segment End s": float(ts[-1]),
                "Status": status,
                "Issues": "; ".join(issues),
            }
        )

    events = pd.DataFrame(rows)
    if events.empty:
        raise ValueError(
            f"Detected {len(candidates)} current-step transition(s), but none produced a valid response "
            f"inside the ±{target_speed_tolerance * 100:.0f}% OEM target-speed window."
        )

    events = _apply_stage_labels(events)
    settings = {
        "Analysis Mode": "Response Time V0.7.4",
        "OEM Profile": config.standard.value,
        "Trigger Fraction": config.trigger_fraction,
        "Force Start Fraction": config.force_start_fraction,
        "Timing Reference": (
            "Force-threshold crossing time minus "
            f"I{config.trigger_fraction * 100:g}% current crossing time"
        ),
        "End Average Fraction": config.end_average_fraction,
        "Force Separation Noise Factor": config.force_separation_noise_factor,
        "Force Separation Fraction": config.force_separation_fraction,
        "Response Dwell ms": config.response_dwell_s * 1000,
        "Calculate Current Undershoot": config.calculate_current_undershoot,
        "Target Speed Tolerance %": target_speed_tolerance * 100.0,
        "Target Speeds m/s": ", ".join(f"{v:g}" for v in _target_speeds(config.standard)),
        "Detected Current Events": len(candidates),
        "Accepted Target-Speed Events": len(events),
        "Rejected Non-target Events": rejected_non_target,
        "Rejected Invalid Events": rejected_invalid,
        "t90 Limit ms": config.t90_limit_ms,
        "Source Format": dataset.source_format,
        "Source File": dataset.source_path.name,
        "Inferred Mapping": (dataset.metadata or {}).get("inferred_mapping"),
        "BMW Endpoint Note": (
            "Current implementation evaluates F100 inside the continuous target-speed window; "
            "BMW F Anfang/F Ende normative extraction remains project-spec dependent."
            if config.standard == ResponseStandard.BMW
            else ""
        ),
    }
    return ResponseAnalysisResult(data, events, settings, dataset.source_path)


analyze_response_time = analyze_response_time_v074
