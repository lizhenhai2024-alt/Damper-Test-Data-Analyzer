from __future__ import annotations

from . import dynamic_gui_v074 as _dynamic_gui_v074_module
from .dynamic_analysis import ResponseStandard
from .dynamic_gui_v079 import DynamicPagesController as _V079DynamicPagesController
from .response_v080 import (
    analyze_response_time_v080,
    default_target_speeds,
    parse_target_speeds,
)


class DynamicPagesController(_V079DynamicPagesController):
    """V0.8.0 response target-speed configuration.

    Customer profile and test speed are deliberately separated. Each profile
    populates convenient default speeds, but the operator may enter any positive
    customer speed list (for example 0.1, 0.3, 0.6, 1.0 m/s).
    """

    def _build_response_page(self):
        super()._build_response_page()

        for standard, zh_label, en_label in (
            (ResponseStandard.HONGQI, "红旗", "Hongqi"),
            (ResponseStandard.DOMESTIC_OEM, "国内主机", "Domestic OEM"),
            (ResponseStandard.LEAPMOTOR, "零跑", "Leapmotor"),
        ):
            self.response_standard.addItem(
                self._text(zh_label, en_label), standard.value
            )

        controls = self.response_page.layout().itemAt(0).layout()
        self.response_target_speed_label = self.QtWidgets.QLabel()
        self.response_target_speeds = self.QtWidgets.QLineEdit()
        self.response_target_speeds.setMinimumWidth(190)
        self.response_target_speeds.setMaximumWidth(260)
        self.response_target_speeds.setClearButtonEnabled(True)

        standard_index = controls.indexOf(self.response_standard)
        insert_at = standard_index + 1 if standard_index >= 0 else 0
        controls.insertWidget(insert_at, self.response_target_speed_label)
        controls.insertWidget(insert_at + 1, self.response_target_speeds)

        self.response_standard.currentIndexChanged.connect(
            self._reset_target_speeds_for_standard
        )
        self._reset_target_speeds_for_standard()
        self._apply_target_speed_text()

    def _current_standard(self) -> ResponseStandard:
        return ResponseStandard(self.response_standard.currentData())

    def _format_speed_list(self, values) -> str:
        return ", ".join(f"{float(value):g}" for value in values)

    def _reset_target_speeds_for_standard(self, *_args):
        if not hasattr(self, "response_target_speeds"):
            return
        standard = self._current_standard()
        text = self._format_speed_list(default_target_speeds(standard))
        if standard == ResponseStandard.LEAPMOTOR:
            text = "0.15, 0.70"
        self.response_target_speeds.setText(text)

    def _apply_target_speed_text(self):
        if not hasattr(self, "response_target_speed_label"):
            return
        for standard, zh_label, en_label in (
            (ResponseStandard.HONGQI, "红旗", "Hongqi"),
            (ResponseStandard.DOMESTIC_OEM, "国内主机", "Domestic OEM"),
            (ResponseStandard.LEAPMOTOR, "零跑", "Leapmotor"),
        ):
            index = self.response_standard.findData(standard.value)
            if index >= 0:
                self.response_standard.setItemText(index, self._text(zh_label, en_label))
        self.response_target_speed_label.setText(
            self._text("目标速度", "Target speed")
        )
        self.response_target_speeds.setPlaceholderText(
            self._text(
                "例如 0.1, 0.3, 0.6, 1.0",
                "e.g. 0.1, 0.3, 0.6, 1.0",
            )
        )
        self.response_target_speeds.setToolTip(
            self._text(
                "可输入任意客户目标速度，单位 m/s；多个速度用逗号分隔。选择规范时自动载入该客户预设速度。",
                "Enter any customer target speeds in m/s, separated by commas. Selecting a profile loads its speed preset.",
            )
        )

    def apply_language(self, language: str):
        super().apply_language(language)
        self._apply_target_speed_text()

    def analyze_response(self):
        try:
            target_speeds = parse_target_speeds(self.response_target_speeds.text())
        except ValueError as exc:
            self.QtWidgets.QMessageBox.information(
                self.window,
                self._text("目标速度", "Target speed"),
                str(exc),
            )
            return

        original_analyzer = _dynamic_gui_v074_module.analyze_response_time_v074

        def configured_analyzer(dataset, config, *, target_speed_tolerance=0.10):
            return analyze_response_time_v080(
                dataset,
                config,
                target_speeds_mps=target_speeds,
                target_speed_tolerance=target_speed_tolerance,
            )

        _dynamic_gui_v074_module.analyze_response_time_v074 = configured_analyzer
        try:
            super().analyze_response()
        finally:
            _dynamic_gui_v074_module.analyze_response_time_v074 = original_analyzer
