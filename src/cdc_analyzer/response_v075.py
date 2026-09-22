from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .dynamic_analysis import CURRENT, DISP, TIME, ResponseAnalysisResult, ResponseConfig, ResponseStandard
from .parser import DataSet
from .response_v074 import (
    AUDI_TARGET_SPEEDS_MPS,
    BMW_TARGET_SPEEDS_MPS,
    DEFAULT_TARGET_SPEED_TOLERANCE,
    _detect_current_events,
    _sample_rate_hz,
    analyze_response_time_v074,
)

VELOCITY_DISPLACEMENT_SMOOTH_MS = 5.0
CURRENT_PREFILTER_MS = 1.0


def _odd_window(sample_rate_hz: float, window_ms: float, minimum: int = 3) -> int:
    if not np.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        window = minimum
    else:
        window = max(minimum, int(round(sample_rate_hz * window_ms / 1000.0)))
    if window % 2 == 0:
        window += 1
    return window


def _prepare_response_dataset(dataset: DataSet) -> tuple[DataSet, pd.DataFrame]:
    """Create an analysis-only copy with robust current/displacement prefilters.

    The raw channels are retained separately and restored into the returned
    processed frame. This reduces derivative noise at Audi 0.131 m/s without
    changing the source data or exported raw traces.
    """

    raw = dataset.data.copy()
    prepared = dataset.data.copy()
    required = [TIME, DISP, CURRENT]
    if any(column not in prepared.columns for column in required):
        return dataset, raw

    valid = prepared[required].dropna().sort_values(TIME)
    sample_rate = _sample_rate_hz(valid)
    disp_window = _odd_window(sample_rate, VELOCITY_DISPLACEMENT_SMOOTH_MS, 5)
    current_window = _odd_window(sample_rate, CURRENT_PREFILTER_MS, 3)

    prepared[DISP] = (
        pd.Series(prepared[DISP].to_numpy(float))
        .rolling(disp_window, center=True, min_periods=1)
        .mean()
        .to_numpy(float)
    )
    prepared[CURRENT] = (
        pd.Series(prepared[CURRENT].to_numpy(float))
        .rolling(current_window, center=True, min_periods=1)
        .median()
        .to_numpy(float)
    )
    analysis_dataset = DataSet(
        data=prepared,
        source_path=dataset.source_path,
        source_format=dataset.source_format,
        metadata=dict(dataset.metadata or {}),
    )
    return analysis_dataset, raw


def _restore_raw_plot_channels(result: ResponseAnalysisResult, raw: pd.DataFrame) -> None:
    if TIME not in raw.columns:
        return
    source = raw.dropna(subset=[TIME]).sort_values(TIME)
    if source.empty:
        return
    target_t = result.processed[TIME].to_numpy(float)
    source_t = source[TIME].to_numpy(float)
    for column in (DISP, CURRENT):
        if column not in source.columns:
            continue
        values = source[column].to_numpy(float)
        finite = np.isfinite(source_t) & np.isfinite(values)
        if np.count_nonzero(finite) >= 2:
            result.processed[column] = np.interp(target_t, source_t[finite], values[finite])


def _event_speed_estimates(dataset: DataSet, config: ResponseConfig) -> list[float]:
    prepared, _raw = _prepare_response_dataset(dataset)
    data = prepared.data[[TIME, DISP, CURRENT]].dropna().sort_values(TIME).reset_index(drop=True)
    if len(data) < 8:
        return []
    t = data[TIME].to_numpy(float)
    x = data[DISP].to_numpy(float)
    velocity = np.gradient(x, t) / 1000.0
    events = _detect_current_events(data, config)
    estimates: list[float] = []
    for index in events:
        event_time = float(data.iloc[index][TIME])
        local = np.abs(velocity[np.abs(t - event_time) <= 0.004])
        local = local[np.isfinite(local)]
        if len(local):
            estimates.append(float(np.median(local)))
    return estimates


def _profile_hint(dataset: DataSet, config: ResponseConfig) -> str | None:
    speeds = _event_speed_estimates(dataset, config)
    if not speeds:
        return None
    rounded = float(np.median(speeds))
    audi = min(AUDI_TARGET_SPEEDS_MPS, key=lambda value: abs(rounded - value))
    bmw = min(BMW_TARGET_SPEEDS_MPS, key=lambda value: abs(rounded - value))
    audi_error = abs(rounded - audi) / audi if audi else float("inf")
    bmw_error = abs(rounded - bmw) / bmw if bmw else float("inf")

    if config.standard == ResponseStandard.BMW and audi_error <= 0.12 and bmw_error > 0.12:
        return (
            f"检测到电流切换附近的典型速度约 {rounded:.3f} m/s，最接近 Audi 目标速度 "
            f"{audi:g} m/s；当前选择 BMW，BMW Profile 不包含该速度。请切换到 Audi 后重新分析。"
        )
    if config.standard == ResponseStandard.AUDI and bmw_error <= 0.12 and audi_error > 0.12:
        return (
            f"检测到电流切换附近的典型速度约 {rounded:.3f} m/s，最接近 BMW 目标速度 "
            f"{bmw:g} m/s；请检查当前规范选择。"
        )
    return None


def _bmw_state(current_a: float) -> str:
    value = float(current_a)
    if abs(value) < 0.05:
        return "Off"
    if abs(value - 0.30) <= 0.20:
        return "Soft"
    if abs(value - 1.60) <= 0.25:
        return "Hard"
    return "Medium"


def _apply_bmw_current_stage_labels(result: ResponseAnalysisResult) -> None:
    if result.events.empty:
        return
    stages: list[str] = []
    transitions: list[str] = []
    for _, row in result.events.iterrows():
        start = float(row["Current Start A"])
        end = float(row["Current End A"])
        stages.append(f"{_bmw_state(start)}→{_bmw_state(end)}")
        transitions.append(f"{start:.2f}A→{end:.2f}A")
    result.events["Stage"] = stages
    result.events["Current Transition"] = transitions


def analyze_response_time_v075(
    dataset: DataSet,
    config: ResponseConfig | None = None,
    *,
    target_speed_tolerance: float = DEFAULT_TARGET_SPEED_TOLERANCE,
) -> ResponseAnalysisResult:
    """V0.7.5 response evaluator.

    Adds robust low-speed velocity estimation for Audi 0.131 m/s files and
    explicit profile-mismatch diagnostics while retaining the V0.7.4 OEM
    target-speed-window calculation rules.
    """

    config = config or ResponseConfig()
    prepared, raw = _prepare_response_dataset(dataset)
    try:
        result = analyze_response_time_v074(
            prepared,
            config,
            target_speed_tolerance=target_speed_tolerance,
        )
    except ValueError as exc:
        message = str(exc)
        if "none produced a valid response" in message or "No current-step transition" in message:
            hint = _profile_hint(dataset, config)
            if hint:
                raise ValueError(hint) from exc
            raise ValueError(
                "未在当前 OEM 目标速度窗口内找到有效响应。请检查规范选择、试验目标速度以及电流切换是否发生在恒速区。"
                f"\n原始诊断：{message}"
            ) from exc
        raise

    _restore_raw_plot_channels(result, raw)
    if config.standard == ResponseStandard.BMW:
        _apply_bmw_current_stage_labels(result)

    result.settings["Analysis Mode"] = "Response Time V0.7.5"
    result.settings["Velocity Estimator"] = (
        f"{VELOCITY_DISPLACEMENT_SMOOTH_MS:g} ms centered displacement smoothing + derivative"
    )
    result.settings["Current Detection Prefilter"] = f"{CURRENT_PREFILTER_MS:g} ms median"
    return result


analyze_response_time = analyze_response_time_v075
