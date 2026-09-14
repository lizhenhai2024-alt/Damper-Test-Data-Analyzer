from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np

from . import response_v074 as _v074
from . import response_v075 as _v075
from .dynamic_analysis import CURRENT, TIME, ResponseAnalysisResult, ResponseConfig, ResponseStandard
from .parser import DataSet

# Corrected BMW response speeds from the current engineering input.
BMW_TARGET_SPEEDS_MPS = (0.131, 0.524, 1.048)
AUDI_TARGET_SPEEDS_MPS = (0.052, 0.131, 0.262, 0.524)
HONGQI_TARGET_SPEEDS_MPS = (0.131, 0.262, 0.524, 1.047)
DOMESTIC_OEM_TARGET_SPEEDS_MPS = (0.1, 0.3, 0.6)
LEAPMOTOR_TARGET_SPEEDS_MPS = (0.15, 0.70)
DEFAULT_TARGET_SPEED_TOLERANCE = _v074.DEFAULT_TARGET_SPEED_TOLERANCE


TARGET_SPEED_PRESETS = {
    ResponseStandard.BMW: BMW_TARGET_SPEEDS_MPS,
    ResponseStandard.AUDI: AUDI_TARGET_SPEEDS_MPS,
    ResponseStandard.HONGQI: HONGQI_TARGET_SPEEDS_MPS,
    ResponseStandard.DOMESTIC_OEM: DOMESTIC_OEM_TARGET_SPEEDS_MPS,
    ResponseStandard.LEAPMOTOR: LEAPMOTOR_TARGET_SPEEDS_MPS,
}


def default_target_speeds(standard: ResponseStandard) -> tuple[float, ...]:
    return TARGET_SPEED_PRESETS[ResponseStandard(standard)]


def parse_target_speeds(value: str | Iterable[float]) -> tuple[float, ...]:
    """Parse an operator-defined target-speed list."""
    if isinstance(value, str):
        tokens = [token for token in re.split(r"[,;，；\s]+", value.strip()) if token]
        if not tokens:
            raise ValueError("请至少输入一个目标速度。")
        try:
            raw = [float(token) for token in tokens]
        except ValueError as exc:
            raise ValueError("目标速度格式无效；多个速度请用逗号分隔，例如 0.1, 0.3, 0.6, 1.0。") from exc
    else:
        raw = [float(item) for item in value]

    cleaned: list[float] = []
    for speed in raw:
        if not np.isfinite(speed) or speed <= 0:
            raise ValueError("目标速度必须是大于 0 的有限数值。")
        if not any(abs(speed - existing) <= 1e-12 for existing in cleaned):
            cleaned.append(float(speed))
    if not cleaned:
        raise ValueError("请至少输入一个目标速度。")
    return tuple(cleaned)


def _directed_level_crossings(
    time_s: np.ndarray,
    signal: np.ndarray,
    level: float,
    direction: float,
) -> list[float]:
    """Return linearly interpolated crossings that follow the step direction."""
    crossings: list[float] = []
    for left in range(len(time_s) - 1):
        y0, y1 = float(signal[left]), float(signal[left + 1])
        if not all(np.isfinite((time_s[left], time_s[left + 1], y0, y1))):
            continue
        delta = y1 - y0
        if delta * direction <= 0 or (y0 - level) * (y1 - level) > 0:
            continue
        fraction = (level - y0) / delta
        if 0 <= fraction <= 1:
            crossing = float(time_s[left] + fraction * (time_s[left + 1] - time_s[left]))
            if not crossings or abs(crossing - crossings[-1]) > 1e-12:
                crossings.append(crossing)
    return crossings


def _add_current_10_90_metrics(result: ResponseAnalysisResult) -> None:
    """Add fixed I10/I90 current-response intersections to each event."""
    data = result.processed
    t = data[TIME].to_numpy(float)
    current = data[CURRENT].to_numpy(float)
    records = []
    for _, row in result.events.iterrows():
        start = float(row["Current Start A"])
        end = float(row["Current End A"])
        delta = end - start
        segment_mask = (t >= float(row["Segment Start s"])) & (t <= float(row["Segment End s"]))
        ts, values = t[segment_mask], current[segment_mask]
        i10 = start + 0.10 * delta
        i90 = start + 0.90 * delta
        direction = 1.0 if delta > 0 else -1.0
        crossings10 = _directed_level_crossings(ts, values, i10, direction)
        crossings90 = _directed_level_crossings(ts, values, i90, direction)
        pairs = [(left, right) for left in crossings10 for right in crossings90 if right >= left]
        if pairs:
            trigger = float(row["Trigger Crossing Time s"])
            t10, t90 = min(
                pairs,
                key=lambda pair: abs(pair[0] - trigger) + abs(pair[1] - trigger),
            )
            elapsed_ms = (t90 - t10) * 1000.0
        else:
            t10 = t90 = elapsed_ms = float("nan")
        force_t90 = float(row.get("F90 Crossing Time s", np.nan))
        force_response_ms = (
            (force_t90 - t10) * 1000.0
            if np.isfinite(t10) and np.isfinite(force_t90)
            else float("nan")
        )
        records.append((i10, i90, t10, t90, elapsed_ms, force_response_ms))

    values = np.asarray(records, dtype=float)
    result.events["Current 10% A"] = values[:, 0]
    result.events["Current 90% A"] = values[:, 1]
    result.events["I10 Crossing Time s"] = values[:, 2]
    result.events["I90 Crossing Time s"] = values[:, 3]
    result.events["Current Response I10-I90 ms"] = values[:, 4]
    result.events["Damping Response I10-F90 ms"] = values[:, 5]
    result.settings["Current Response Timing"] = "I90% crossing time minus I10% crossing time"
    result.settings["Dual-axis Response Timing"] = "F90% force crossing time minus I10% current crossing time"


def analyze_response_time_v080(
    dataset: DataSet,
    config: ResponseConfig | None = None,
    *,
    target_speeds_mps: Iterable[float] | None = None,
    target_speed_tolerance: float = DEFAULT_TARGET_SPEED_TOLERANCE,
) -> ResponseAnalysisResult:
    """V0.8.0 response evaluator with operator-configurable target speeds.

    OEM selection controls the evaluation profile, while target speed is an
    independent test condition. Legacy V0.7.x module constants are deliberately
    left untouched so importing V0.8.0 cannot change older regression behavior.
    """
    config = config or ResponseConfig()
    targets = parse_target_speeds(
        target_speeds_mps if target_speeds_mps is not None else default_target_speeds(config.standard)
    )

    prepared, raw = _v075._prepare_response_dataset(dataset)
    original_target_selector = _v074._target_speeds
    _v074._target_speeds = lambda _standard: targets
    try:
        try:
            result = _v074.analyze_response_time_v074(
                prepared,
                config,
                target_speed_tolerance=target_speed_tolerance,
            )
        except ValueError as exc:
            message = str(exc)
            if "none produced a valid response" in message or "No current-step transition" in message:
                targets_text = ", ".join(f"{value:g}" for value in targets)
                raise ValueError(
                    "未在设定目标速度窗口内找到有效响应。"
                    f" 当前目标速度：{targets_text} m/s；"
                    "请检查目标速度、电流切换位置及恒速区间。"
                    f"\n原始诊断：{message}"
                ) from exc
            raise
    finally:
        _v074._target_speeds = original_target_selector

    _v075._restore_raw_plot_channels(result, raw)
    _add_current_10_90_metrics(result)
    if config.standard == ResponseStandard.BMW:
        _v075._apply_bmw_current_stage_labels(result)

    result.settings["Analysis Mode"] = "Response Time V0.8.0"
    result.settings["Target Speeds m/s"] = ", ".join(f"{value:g}" for value in targets)
    result.settings["Target Speed Source"] = "operator configurable"
    result.settings["Velocity Estimator"] = (
        f"{_v075.VELOCITY_DISPLACEMENT_SMOOTH_MS:g} ms centered displacement smoothing + derivative"
    )
    result.settings["Current Detection Prefilter"] = f"{_v075.CURRENT_PREFILTER_MS:g} ms median"
    return result


analyze_response_time = analyze_response_time_v080
