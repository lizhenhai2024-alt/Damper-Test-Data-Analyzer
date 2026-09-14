from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np

from . import response_v074 as _v074
from . import response_v075 as _v075
from .dynamic_analysis import ResponseAnalysisResult, ResponseConfig, ResponseStandard
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
