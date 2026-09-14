from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import ceil
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from .parser import DataSet, load_test_data

TIME = "Running Time"
DISP = "Axial Displacement"
LOAD = "Axial Load"
CURRENT = "CDC 1 Current FB_1"
VELOCITY = "Velocity m/s"


class ResponseStandard(str, Enum):
    AUDI = "audi"
    BMW = "bmw"
    HONGQI = "hongqi"
    DOMESTIC_OEM = "domestic_oem"
    LEAPMOTOR = "leapmotor"


class HysteresisStandard(str, Enum):
    AUDI = "audi"
    BMW = "bmw"


@dataclass(slots=True)
class ResponseConfig:
    standard: ResponseStandard = ResponseStandard.AUDI
    trigger_fraction: float = 0.10
    force_start_fraction: float = 0.01
    end_average_fraction: float = 0.02
    plateau_fraction: float = 0.15
    min_current_step_a: float = 0.05
    event_derivative_fraction: float = 0.20
    min_event_separation_s: float = 0.003
    t90_limit_ms: float | None = None


@dataclass(slots=True)
class ResponseAnalysisResult:
    processed: pd.DataFrame
    events: pd.DataFrame
    settings: dict[str, object]
    source_path: Path


@dataclass(slots=True)
class HysteresisConfig:
    standard: HysteresisStandard = HysteresisStandard.BMW
    current_decimals: int = 1
    zero_target_mm: float = 0.0
    limit_percent: float | None = None
    audi_soft_current_a: float | None = None
    audi_kfm_current_a: float | None = None
    audi_hard_current_a: float | None = None
    audi_min_mean_cycles: int = 4
    audi_smoothing_fraction_per_side: float = 0.03


@dataclass(slots=True)
class HysteresisAnalysisResult:
    processed: pd.DataFrame
    runs: pd.DataFrame
    summary: pd.DataFrame
    settings: dict[str, object]
    source_path: Path


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
    start_idx: int = 0,
    direction: int = 0,
) -> float | None:
    for i in range(max(0, start_idx), len(y) - 1):
        y0, y1 = float(y[i]), float(y[i + 1])
        if direction > 0 and y1 <= y0:
            continue
        if direction < 0 and y1 >= y0:
            continue
        if (y0 - target) * (y1 - target) <= 0 and y1 != y0:
            q = (target - y0) / (y1 - y0)
            if 0.0 <= q <= 1.0:
                return float(t[i] + q * (t[i + 1] - t[i]))
    return None


def _numeric_rows(path: Path, columns: int = 4) -> np.ndarray:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split("\t")
        if len(parts) < columns:
            continue
        try:
            values = [float(parts[i].strip()) for i in range(columns)]
        except (TypeError, ValueError):
            continue
        if all(np.isfinite(values)):
            rows.append(values)
    if len(rows) < 8:
        raise ValueError("Headerless numeric DAT does not contain enough four-channel numeric rows")
    return np.asarray(rows, dtype=float)


def _infer_headerless_channels(matrix: np.ndarray) -> tuple[pd.DataFrame, dict[str, object]]:
    if matrix.ndim != 2 or matrix.shape[1] != 4:
        raise ValueError("Channel inference expects four numeric columns")

    time_candidates: list[tuple[float, float, int]] = []
    for col in range(4):
        d = np.diff(matrix[:, col])
        positive = d[np.isfinite(d) & (d > 0)]
        positive_ratio = float(np.mean(d > 0)) if len(d) else 0.0
        if positive_ratio >= 0.98 and len(positive):
            median_step = float(np.median(positive))
            cv = float(np.std(positive) / max(abs(np.mean(positive)), 1e-12))
            time_candidates.append((median_step, cv, col))
    if not time_candidates:
        raise ValueError("Could not infer a monotonically increasing time channel")
    time_col = min(time_candidates, key=lambda item: (item[0], item[1]))[2]

    remaining = [col for col in range(4) if col != time_col]
    current_candidates: list[tuple[float, float, int]] = []
    for col in remaining:
        values = matrix[:, col]
        q99 = float(np.quantile(np.abs(values), 0.99))
        span = float(np.ptp(values))
        if q99 <= 10.0 and span >= 0.02:
            current_candidates.append((q99, -span, col))
    if not current_candidates:
        raise ValueError("Could not infer a current feedback channel")
    current_col = min(current_candidates)[2]

    remaining = [col for col in remaining if col != current_col]
    scales = sorted((float(np.quantile(np.abs(matrix[:, col]), 0.95)), col) for col in remaining)
    displacement_col = scales[0][1]
    load_col = scales[-1][1]

    frame = pd.DataFrame(
        {
            TIME: matrix[:, time_col],
            DISP: matrix[:, displacement_col],
            LOAD: matrix[:, load_col],
            CURRENT: matrix[:, current_col],
        }
    )
    frame["Block ID"] = 1
    frame["Source Row"] = range(1, len(frame) + 1)
    mapping = {
        "time_column_1based": time_col + 1,
        "load_column_1based": load_col + 1,
        "current_column_1based": current_col + 1,
        "displacement_column_1based": displacement_col + 1,
        "inference": "heuristic_monotonic_step_scale",
    }
    return frame, mapping


def load_dynamic_test_data(path: str | Path) -> DataSet:
    source = Path(path)
    try:
        return load_test_data(source)
    except ValueError:
        if source.suffix.lower() != ".dat":
            raise
    matrix = _numeric_rows(source, 4)
    frame, mapping = _infer_headerless_channels(matrix)
    return DataSet(
        data=frame,
        source_path=source,
        source_format="headerless_numeric_dat",
        metadata={"block_count": 1, "inferred_mapping": mapping},
    )


def _detect_current_events(frame: pd.DataFrame, config: ResponseConfig) -> list[int]:
    t = frame[TIME].to_numpy(float)
    current = frame[CURRENT].to_numpy(float)
    if len(current) < 8:
        return []
    smooth = pd.Series(current).rolling(3, center=True, min_periods=1).mean().to_numpy()
    slope = np.abs(np.gradient(smooth, t))
    peak = float(np.nanmax(slope))
    if not np.isfinite(peak) or peak <= 0:
        return []
    mask = slope >= config.event_derivative_fraction * peak
    groups: list[list[int]] = []
    active: list[int] = []
    for idx, state in enumerate(mask):
        if state:
            active.append(idx)
        elif active:
            groups.append(active)
            active = []
    if active:
        groups.append(active)
    candidates = [max(group, key=lambda i: slope[i]) for group in groups]
    events: list[int] = []
    for candidate in candidates:
        if not events or t[candidate] - t[events[-1]] >= config.min_event_separation_s:
            events.append(candidate)
        elif slope[candidate] > slope[events[-1]]:
            events[-1] = candidate
    return events


def analyze_response_time(dataset: DataSet, config: ResponseConfig | None = None) -> ResponseAnalysisResult:
    config = config or ResponseConfig()
    if not 0 < config.trigger_fraction < 1:
        raise ValueError("Trigger fraction must be between 0 and 1")
    if not 0 < config.force_start_fraction < 0.63:
        raise ValueError("Initial force fraction must be between 0 and 0.63")
    if not 0 < config.end_average_fraction <= 0.5:
        raise ValueError("End-average fraction must be in (0, 0.5]")

    cols = [TIME, DISP, LOAD, CURRENT]
    missing = [c for c in cols if c not in dataset.data.columns]
    if missing:
        raise ValueError(f"Missing dynamic response channel(s): {', '.join(missing)}")
    data = dataset.data[cols].dropna().sort_values(TIME).reset_index(drop=True).copy()
    if len(data) < 8:
        raise ValueError("Response-time analysis requires at least 8 valid samples")
    if np.any(np.diff(data[TIME].to_numpy(float)) <= 0):
        raise ValueError("Response-time data requires strictly increasing time")

    t = data[TIME].to_numpy(float)
    x = data[DISP].to_numpy(float)
    data[VELOCITY] = np.gradient(x, t) / 1000.0

    events = _detect_current_events(data, config)
    if not events:
        events = [int(np.argmax(np.abs(np.gradient(data[CURRENT].to_numpy(float), t))))]

    boundaries = [0]
    boundaries.extend((left + right) // 2 for left, right in zip(events[:-1], events[1:]))
    boundaries.append(len(data) - 1)

    rows: list[dict[str, object]] = []
    for event_no, event_index in enumerate(events, start=1):
        start = boundaries[event_no - 1]
        end = boundaries[event_no]
        segment = data.iloc[start : end + 1].reset_index(drop=True)
        if len(segment) < 10:
            continue
        ts = segment[TIME].to_numpy(float)
        xs = segment[DISP].to_numpy(float)
        fs = segment[LOAD].to_numpy(float)
        currents = segment[CURRENT].to_numpy(float)
        velocities = segment[VELOCITY].to_numpy(float)
        n = len(segment)
        plateau_n = max(3, int(round(config.plateau_fraction * n)))
        current_start = float(np.median(currents[:plateau_n]))
        current_end = float(np.median(currents[-plateau_n:]))
        delta_current = current_end - current_start
        if abs(delta_current) < config.min_current_step_a:
            continue

        trigger_current = current_start + config.trigger_fraction * delta_current
        t0 = _first_level_crossing(
            ts, currents, trigger_current, direction=1 if delta_current > 0 else -1
        )
        if t0 is None:
            continue
        force_0 = _interpolate_time(ts, fs, t0)
        x_0 = _interpolate_time(ts, xs, t0)
        velocity_0 = _interpolate_time(ts, velocities, t0)

        end_n = max(3, int(ceil(config.end_average_fraction * n)))
        force_100 = float(np.mean(fs[-end_n:]))
        delta_force = force_100 - force_0
        if abs(delta_force) < 1e-12:
            continue
        force_direction = 1 if delta_force > 0 else -1

        after_mask = ts > t0
        response_t = np.concatenate(([t0], ts[after_mask]))
        response_f = np.concatenate(([force_0], fs[after_mask]))
        thresholds: dict[float, tuple[float, float | None]] = {}
        for fraction in (config.force_start_fraction, 0.63, 0.90):
            target = force_0 + fraction * delta_force
            crossing = _first_level_crossing(
                response_t, response_f, target, start_idx=0, direction=force_direction
            )
            thresholds[fraction] = (target, crossing)

        def elapsed_ms(crossing: float | None) -> float:
            if crossing is None or crossing < t0:
                return float("nan")
            return float((crossing - t0) * 1000.0)

        t1 = thresholds[config.force_start_fraction][1]
        t63 = thresholds[0.63][1]
        t90 = thresholds[0.90][1]
        dt63_s = (t63 - t0) if t63 is not None else float("nan")
        dt90_s = (t90 - t0) if t90 is not None else float("nan")
        gradient63 = (
            abs(thresholds[0.63][0] - force_0) / dt63_s
            if np.isfinite(dt63_s) and dt63_s > 0
            else float("nan")
        )
        gradient90 = (
            abs(thresholds[0.90][0] - force_0) / dt90_s
            if np.isfinite(dt90_s) and dt90_s > 0
            else float("nan")
        )

        sample_rate = _sample_rate_hz(segment)
        issues: list[str] = []
        if config.standard == ResponseStandard.AUDI and np.isfinite(sample_rate) and sample_rate < 4000.0:
            issues.append(f"sample rate below Audi 4 kHz ({sample_rate:.2f} Hz)")
        if any(v[1] is None for v in thresholds.values()):
            issues.append("one or more force thresholds not crossed")
        local = segment[segment[TIME].between(t0 - 0.003, t0 + 0.003)][VELOCITY].abs()
        if len(local) >= 3 and float(local.mean()) > 0:
            speed_variation = float(local.std(ddof=0) / local.mean())
            if speed_variation > 0.10:
                issues.append("velocity variation around switching exceeds 10%")

        switch90 = elapsed_ms(t90)
        trigger_reference = f"I{config.trigger_fraction * 100:g}% current crossing"
        if config.t90_limit_ms is None:
            status = "Warning" if issues else "OK"
        elif not np.isfinite(switch90):
            status = "Invalid"
        else:
            status = "PASS" if switch90 <= config.t90_limit_ms else "FAIL"

        rows.append(
            {
                "Event ID": event_no,
                "OEM": config.standard.value.upper(),
                "Current Start A": current_start,
                "Current End A": current_end,
                "Current Delta A": delta_current,
                "Trigger Fraction": config.trigger_fraction,
                "Trigger Current A": trigger_current,
                "t0 s": t0,
                "Trigger Crossing Time s": t0,
                "Displacement at t0 mm": x_0,
                "Velocity at t0 m/s": velocity_0,
                "Direction": "Rebound" if velocity_0 > 0 else "Compression",
                "Force Change": "Build-up" if abs(force_100) > abs(force_0) else "Decay",
                "F0 N": force_0,
                "F100 N": force_100,
                "Delta F N": delta_force,
                "Force Start Fraction": config.force_start_fraction,
                "F1 N": thresholds[config.force_start_fraction][0],
                "Initial Force Threshold N": thresholds[config.force_start_fraction][0],
                "F63 N": thresholds[0.63][0],
                "F90 N": thresholds[0.90][0],
                "Dead Time t1 ms": elapsed_ms(t1),
                "Initial Force Response Time ms": elapsed_ms(t1),
                "Switch Time t63 ms": elapsed_ms(t63),
                "Switch Time t90 ms": switch90,
                "Gradient 63 N/s": gradient63,
                "Gradient 90 N/s": gradient90,
                "Sample Rate Hz": sample_rate,
                "Segment Start s": float(ts[0]),
                "Segment End s": float(ts[-1]),
                "Status": status,
                "Timing Reference": trigger_reference,
                "Issues": "; ".join(issues),
            }
        )

    events_frame = pd.DataFrame(rows)
    if events_frame.empty:
        raise ValueError("No valid current-step response event could be evaluated")
    settings = {
        "Analysis Mode": "Response Time",
        "OEM Profile": config.standard.value,
        "Trigger Fraction": config.trigger_fraction,
        "Force Start Fraction": config.force_start_fraction,
        "Timing Reference": (
            "Force-threshold crossing time minus "
            f"I{config.trigger_fraction * 100:g}% current crossing time"
        ),
        "End Average Fraction": config.end_average_fraction,
        "t90 Limit ms": config.t90_limit_ms,
        "Source Format": dataset.source_format,
        "Source File": dataset.source_path.name,
        "Inferred Mapping": (dataset.metadata or {}).get("inferred_mapping"),
    }
    return ResponseAnalysisResult(data, events_frame, settings, dataset.source_path)


def _zero_crossings_for_direction(
    frame: pd.DataFrame,
    direction: Literal["Rebound", "Compression"],
    target_mm: float = 0.0,
    force_column: str = LOAD,
) -> tuple[list[float], list[float], list[float]]:
    frame = frame.sort_values(TIME)
    t = frame[TIME].to_numpy(float)
    x = frame[DISP].to_numpy(float)
    force = frame[force_column].to_numpy(float)
    if len(frame) < 2:
        return [], [], []
    velocity = np.gradient(x, t) / 1000.0
    wanted = 1 if direction == "Rebound" else -1
    forces: list[float] = []
    speeds: list[float] = []
    times: list[float] = []
    for i in range(len(x) - 1):
        a, b = x[i] - target_mm, x[i + 1] - target_mm
        if a == 0 and i > 0:
            continue
        if a * b > 0 or x[i] == x[i + 1]:
            continue
        q = (target_mm - x[i]) / (x[i + 1] - x[i])
        if not 0 <= q <= 1:
            continue
        local_velocity = float(velocity[i] + q * (velocity[i + 1] - velocity[i]))
        if local_velocity * wanted <= 0:
            continue
        forces.append(float(force[i] + q * (force[i + 1] - force[i])))
        speeds.append(abs(local_velocity))
        times.append(float(t[i] + q * (t[i + 1] - t[i])))
    return forces, speeds, times


def _assign_sweep_directions(labels: list[float]) -> list[str]:
    directions: list[str] = []
    for i, label in enumerate(labels):
        previous = label - labels[i - 1] if i else 0.0
        following = labels[i + 1] - label if i + 1 < len(labels) else 0.0
        delta = previous if abs(previous) > 1e-12 else following
        directions.append("Up" if delta >= 0 else "Down")
    return directions


def _prepare_blocks(data: pd.DataFrame) -> list[tuple[int, pd.DataFrame]]:
    if "Block ID" in data.columns:
        return [(int(block_id), block.copy()) for block_id, block in data.groupby("Block ID", sort=False)]
    return [(1, data.copy())]


def _bmw_hysteresis(dataset: DataSet, config: HysteresisConfig) -> HysteresisAnalysisResult:
    data = dataset.data.copy()
    blocks = _prepare_blocks(data)
    labels = [
        round(float(np.median(block[CURRENT])), config.current_decimals)
        for _, block in blocks
    ]
    sweeps = _assign_sweep_directions(labels)
    run_rows: list[dict[str, object]] = []
    for order, ((block_id, block), label, sweep) in enumerate(zip(blocks, labels, sweeps), start=1):
        actual = float(np.median(block[CURRENT]))
        sample_rate = _sample_rate_hz(block)
        for motion in ("Rebound", "Compression"):
            forces, speeds, times = _zero_crossings_for_direction(block, motion, config.zero_target_mm)
            if not forces:
                continue
            run_rows.append(
                {
                    "Block Order": order,
                    "Block ID": block_id,
                    "Current Label A": label,
                    "Actual Current A": actual,
                    "Sweep Direction": sweep,
                    "Direction": motion,
                    "Force N": float(np.mean(forces)),
                    "Abs Force N": float(np.mean(np.abs(forces))),
                    "Speed m/s": float(np.mean(speeds)),
                    "Crossing Count": len(forces),
                    "Sample Rate Hz": sample_rate,
                }
            )
    runs = pd.DataFrame(run_rows)
    if runs.empty:
        raise ValueError("No center-stroke BMW hysteresis values could be extracted")

    summary_rows: list[dict[str, object]] = []
    for (current, motion), group in runs.groupby(["Current Label A", "Direction"], sort=True):
        up = group[group["Sweep Direction"] == "Up"]
        down = group[group["Sweep Direction"] == "Down"]
        if up.empty or down.empty:
            continue
        f_up = float(up["Force N"].mean())
        f_down = float(down["Force N"].mean())
        abs_up = abs(f_up)
        abs_down = abs(f_down)
        reference = 0.5 * (abs_up + abs_down)
        hysteresis_n = abs(abs_down - abs_up)
        hysteresis_pct = hysteresis_n / reference * 100.0 if reference > 0 else float("nan")
        if config.limit_percent is None:
            status = "Not evaluated"
        else:
            status = "PASS" if hysteresis_pct <= config.limit_percent else "FAIL"
        summary_rows.append(
            {
                "OEM": "BMW",
                "Current A": float(current),
                "Direction": motion,
                "Up Force N": f_up,
                "Down Force N": f_down,
                "Reference Damping Force N": reference,
                "Hysteresis N": hysteresis_n,
                "Hysteresis %": hysteresis_pct,
                "Limit %": config.limit_percent,
                "Status": status,
            }
        )
    summary = pd.DataFrame(summary_rows)
    settings = {
        "Analysis Mode": "Hysteresis",
        "OEM Profile": "bmw",
        "Zero Target mm": config.zero_target_mm,
        "Current Decimals": config.current_decimals,
        "Limit %": config.limit_percent,
        "Source File": dataset.source_path.name,
    }
    return HysteresisAnalysisResult(data, runs, summary, settings, dataset.source_path)


def _estimate_samples_per_stroke(block: pd.DataFrame) -> int:
    t = block[TIME].to_numpy(float)
    x = block[DISP].to_numpy(float)
    if len(block) < 5:
        return max(1, len(block))
    dx = np.gradient(x, t)
    signs = np.sign(dx)
    reversals = np.flatnonzero(signs[:-1] * signs[1:] < 0)
    if len(reversals) >= 2:
        return max(3, int(round(float(np.median(np.diff(reversals))))))
    return max(3, len(block) // 2)


def _smooth_audi_block(block: pd.DataFrame, fraction_per_side: float) -> pd.DataFrame:
    out = block.copy().sort_values(TIME).reset_index(drop=True)
    samples_per_stroke = _estimate_samples_per_stroke(out)
    side = max(1, int(ceil(fraction_per_side * samples_per_stroke)))
    window = 2 * side + 1
    out["Audi Smoothed Load"] = out[LOAD].rolling(window, center=True, min_periods=1).mean()
    return out


def _classify_audi_state(current: float, soft: float, kfm: float, hard: float) -> str:
    candidates = {"Soft": soft, "KFM": kfm, "Hard": hard}
    return min(candidates, key=lambda key: abs(current - candidates[key]))


def _audi_state_currents(blocks: list[tuple[int, pd.DataFrame]], config: HysteresisConfig) -> tuple[float, float, float]:
    currents = sorted({round(float(np.median(block[CURRENT])), config.current_decimals) for _, block in blocks})
    if len(currents) < 3 and any(
        value is None for value in (config.audi_soft_current_a, config.audi_kfm_current_a, config.audi_hard_current_a)
    ):
        raise ValueError("Audi hysteresis requires Soft, KFM and Hard current levels")
    soft = config.audi_soft_current_a if config.audi_soft_current_a is not None else currents[0]
    hard = config.audi_hard_current_a if config.audi_hard_current_a is not None else currents[-1]
    if config.audi_kfm_current_a is not None:
        kfm = config.audi_kfm_current_a
    else:
        mid = (soft + hard) / 2.0
        kfm = min(currents[1:-1], key=lambda v: abs(v - mid))
    return float(soft), float(kfm), float(hard)


def _audi_hysteresis(dataset: DataSet, config: HysteresisConfig) -> HysteresisAnalysisResult:
    data = dataset.data.copy()
    blocks = _prepare_blocks(data)
    soft, kfm, hard = _audi_state_currents(blocks, config)

    processed_parts: list[pd.DataFrame] = []
    run_rows: list[dict[str, object]] = []
    for order, (block_id, raw_block) in enumerate(blocks, start=1):
        block = _smooth_audi_block(raw_block, config.audi_smoothing_fraction_per_side)
        processed_parts.append(block)
        actual = float(np.median(block[CURRENT]))
        state = _classify_audi_state(actual, soft, kfm, hard)
        sample_rate = _sample_rate_hz(block)
        for motion in ("Rebound", "Compression"):
            forces, speeds, times = _zero_crossings_for_direction(
                block, motion, config.zero_target_mm, "Audi Smoothed Load"
            )
            if not forces:
                continue
            first_cycle_force = float(forces[0])
            retained = forces[1:]
            if len(retained) < config.audi_min_mean_cycles:
                mean_force = float("nan")
                status = "Insufficient cycles"
            else:
                mean_force = float(np.mean(retained))
                status = "OK" if (not np.isfinite(sample_rate) or sample_rate >= 1000.0) else "Warning"
            run_rows.append(
                {
                    "Block Order": order,
                    "Block ID": block_id,
                    "State": state,
                    "Current A": actual,
                    "Direction": motion,
                    "First Cycle Force N": first_cycle_force,
                    "Mean Force N": mean_force,
                    "Raw Cycle Count": len(forces),
                    "Retained Cycle Count": len(retained),
                    "Mean Speed m/s": float(np.mean(speeds[1:])) if len(speeds) > 1 else float("nan"),
                    "Sample Rate Hz": sample_rate,
                    "Status": status,
                }
            )
    processed = pd.concat(processed_parts, ignore_index=True) if processed_parts else data
    runs = pd.DataFrame(run_rows)
    if runs.empty:
        raise ValueError("No Audi hysteresis cycles could be evaluated")

    summary_rows: list[dict[str, object]] = []
    for motion in ("Rebound", "Compression"):
        motion_runs = runs[runs["Direction"] == motion].sort_values("Block Order")
        kfm_runs = motion_runs[(motion_runs["State"] == "KFM") & motion_runs["Mean Force N"].notna()]
        if len(kfm_runs) < 2:
            continue
        kfm_indices = list(kfm_runs.index)
        for left_index, right_index in zip(kfm_indices[:-1], kfm_indices[1:]):
            before = runs.loc[left_index]
            after = runs.loc[right_index]
            between = motion_runs[
                (motion_runs["Block Order"] > before["Block Order"])
                & (motion_runs["Block Order"] < after["Block Order"])
            ]
            if between.empty:
                continue
            extreme_rows = between[between["State"].isin(["Soft", "Hard"])]
            if extreme_rows.empty:
                continue
            extreme = extreme_rows.iloc[0]
            excursion_state = str(extreme["State"])
            before_force = float(before["Mean Force N"])
            after_force = float(after["Mean Force N"])
            hyst_n = abs(abs(after_force) - abs(before_force))

            soft_rows = motion_runs[(motion_runs["State"] == "Soft") & motion_runs["Mean Force N"].notna()]
            hard_rows = motion_runs[(motion_runs["State"] == "Hard") & motion_runs["Mean Force N"].notna()]
            if soft_rows.empty or hard_rows.empty:
                spread = float("nan")
            else:
                soft_mag = float(np.mean(np.abs(soft_rows["Mean Force N"])))
                hard_mag = float(np.mean(np.abs(hard_rows["Mean Force N"])))
                spread = abs(hard_mag - soft_mag)
            hyst_pct = hyst_n / spread * 100.0 if np.isfinite(spread) and spread > 0 else float("nan")
            first_delta = abs(abs(float(after["First Cycle Force N"])) - abs(before_force))

            if config.limit_percent is None:
                status = "Not evaluated"
            elif not np.isfinite(hyst_pct):
                status = "Invalid"
            else:
                status = "PASS" if hyst_pct <= config.limit_percent else "FAIL"
            summary_rows.append(
                {
                    "OEM": "AUDI",
                    "Direction": motion,
                    "Excursion State": excursion_state,
                    "KFM Before N": before_force,
                    "KFM After N": after_force,
                    "Hysteresis N": hyst_n,
                    "Spread Fmax-Fmin N": spread,
                    "Hysteresis %": hyst_pct,
                    "First Cycle Delta N": first_delta,
                    "Limit %": config.limit_percent,
                    "Status": status,
                }
            )
    summary = pd.DataFrame(summary_rows)
    settings = {
        "Analysis Mode": "Hysteresis",
        "OEM Profile": "audi",
        "Soft Current A": soft,
        "KFM Current A": kfm,
        "Hard Current A": hard,
        "Audi smoothing ± fraction per stroke": config.audi_smoothing_fraction_per_side,
        "First cycle excluded": True,
        "Minimum retained cycles": config.audi_min_mean_cycles,
        "Limit %": config.limit_percent,
        "Source File": dataset.source_path.name,
    }
    return HysteresisAnalysisResult(processed, runs, summary, settings, dataset.source_path)


def analyze_hysteresis(dataset: DataSet, config: HysteresisConfig | None = None) -> HysteresisAnalysisResult:
    config = config or HysteresisConfig()
    required = [TIME, DISP, LOAD, CURRENT]
    missing = [c for c in required if c not in dataset.data.columns]
    if missing:
        raise ValueError(f"Missing hysteresis channel(s): {', '.join(missing)}")
    if config.standard == HysteresisStandard.AUDI:
        return _audi_hysteresis(dataset, config)
    return _bmw_hysteresis(dataset, config)
