from __future__ import annotations

import numpy as np

from .dynamic_analysis import (
    CURRENT,
    LOAD,
    TIME,
    VELOCITY,
    ResponseConfig,
    ResponseStandard,
)
from .dynamic_gui import DynamicPagesController as _BaseDynamicPagesController
from .response_v074 import analyze_response_time_v074


class DynamicPagesController(_BaseDynamicPagesController):
    """V0.7.4 response-page upgrade.

    Hysteresis behavior remains inherited from the released controller. Only
    response event selection, target-speed evaluation display, plot density and
    readability are changed here.
    """

    def _new_table(self):
        table = super()._new_table()
        font = table.font()
        font.setPointSize(max(10, font.pointSize()))
        table.setFont(font)
        header_font = table.horizontalHeader().font()
        header_font.setPointSize(max(10, header_font.pointSize()))
        header_font.setBold(True)
        table.horizontalHeader().setFont(header_font)
        table.verticalHeader().setDefaultSectionSize(30)
        table.setSelectionBehavior(
            self.QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        return table

    def _build_response_page(self):
        super()._build_response_page()
        self.response_event_combo.setMinimumWidth(360)
        self.response_table.currentCellChanged.connect(
            self._select_response_event_from_table
        )

    def _select_response_event_from_table(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ):
        if (
            self.response_result is None
            or current_row < 0
            or current_row >= len(self.response_result.events)
        ):
            return
        event_id = int(self.response_result.events.iloc[current_row]["Event ID"])
        index = self.response_event_combo.findData(event_id)
        if index >= 0 and index != self.response_event_combo.currentIndex():
            self.response_event_combo.setCurrentIndex(index)

    def analyze_response(self):
        if self.response_dataset is None:
            self.QtWidgets.QMessageBox.information(
                self.window,
                self._text("响应时间", "Response Time"),
                self._text(
                    "请先打开响应时间原始数据。",
                    "Open response-time raw data first.",
                ),
            )
            return
        try:
            standard = ResponseStandard(self.response_standard.currentData())
            limit = self.response_t90_limit.value() or None
            config = ResponseConfig(
                standard=standard,
                trigger_fraction=self.response_trigger.value() / 100.0,
                force_start_fraction=(
                    self.response_force_start_fraction.value() / 100.0
                    if hasattr(self, "response_force_start_fraction")
                    else 0.01
                ),
                end_average_fraction=self.response_end_fraction.value() / 100.0,
                t90_limit_ms=limit,
                response_dwell_s=(
                    self.response_dwell_ms.value() / 1000.0
                    if hasattr(self, "response_dwell_ms") else 0.010
                ),
                current_settling_band_fraction=(
                    self.response_settling_band_pct.value() / 100.0
                    if hasattr(self, "response_settling_band_pct") else 0.02
                ),
                force_recovery_band_fraction=(
                    self.response_recovery_band_pct.value() / 100.0
                    if hasattr(self, "response_recovery_band_pct") else 0.02
                ),
                force_recovery_sigma_factor=(
                    self.response_recovery_sigma.value()
                    if hasattr(self, "response_recovery_sigma") else 3.0
                ),
                calculate_current_overshoot=(
                    self.response_current_undershoot.isChecked()
                    if hasattr(self, "response_current_undershoot") else False
                ),
            )
            self.response_result = analyze_response_time_v074(
                self.response_dataset,
                config,
                target_speed_tolerance=0.10,
            )
            self._fill_table(self.response_table, self.response_result.events)

            self.response_event_combo.blockSignals(True)
            self.response_event_combo.clear()
            for _, row in self.response_result.events.iterrows():
                stage = str(row.get("Stage", ""))
                direction = (
                    self._text("复原(+)", "Rebound (+)")
                    if row["Direction"] == "Rebound"
                    else self._text("压缩(-)", "Compression (-)")
                )
                target = float(row["Target Velocity m/s"])
                current_transition = str(row.get("Current Transition", ""))
                text = (
                    f"{stage} | {direction} | {current_transition} | "
                    f"{self._text('目标速度', 'Target')} {target:+.4g} m/s"
                )
                self.response_event_combo.addItem(text, int(row["Event ID"]))
            self.response_event_combo.blockSignals(False)

            if self.response_event_combo.count():
                self.response_event_combo.setCurrentIndex(0)
            self.refresh_response_plot()

            settings = self.response_result.settings
            detected = int(settings.get("Detected Current Events", len(self.response_result.events)))
            accepted = int(settings.get("Accepted Target-Speed Events", len(self.response_result.events)))
            rejected = int(settings.get("Rejected Non-target Events", 0))
            invalid = int(settings.get("Rejected Invalid Events", 0))
            sample_rate = float(self.response_result.events["Sample Rate Hz"].iloc[0])
            self.response_status.setText(
                self._text(
                    (
                        f"目标速度响应：检测 {detected} 个电流切换，保留 {accepted} 个，"
                        f"排除非目标速度 {rejected} 个、无效 {invalid} 个；"
                        f"采样率约 {sample_rate:.2f} Hz"
                    ),
                    (
                        f"Target-speed response: {detected} current steps detected, "
                        f"{accepted} retained, {rejected} off-target and {invalid} invalid "
                        f"event(s) excluded; sample rate ≈ {sample_rate:.2f} Hz"
                    ),
                )
            )
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(
                self.window,
                self._text("分析错误", "Analysis error"),
                str(exc),
            )

    def _axis_style(self, plot, left: str, units: str | None = None):
        plot.showGrid(x=True, y=False, alpha=0.12)
        label_style = {"font-size": "11pt"}
        plot.setLabel("left", left, units=units, **label_style)
        plot.setLabel(
            "bottom",
            self._text("时间", "Time"),
            units="ms",
            **label_style,
        )
        plot.setClipToView(True)
        plot.setDownsampling(auto=True, mode="peak")
        background = getattr(self.window, "_plot_background_color", "#ffffff")
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        plot.getAxis("left").setTextPen(foreground)
        plot.getAxis("bottom").setTextPen(foreground)
        tick_font = self.QtWidgets.QApplication.font()
        tick_font.setPointSize(max(10, tick_font.pointSize()))
        plot.getAxis("left").setStyle(tickFont=tick_font)
        plot.getAxis("bottom").setStyle(tickFont=tick_font)
        self.response_plot_area.setBackground(background)
        self.hysteresis_plot_area.setBackground(background)

    def _marker_pen(self):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        return self.pg.mkPen(
            foreground,
            width=1.1,
            style=self.QtCore.Qt.PenStyle.DashLine,
        )

    def _signal_pen(self):
        return self.pg.mkPen("#1565c0", width=2.2)

    def _add_plot_text(self, plot, text: str, x: float, y: float, *, anchor=(0, 0.5), bold=False):
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        item = self.pg.TextItem(text=text, color=foreground, anchor=anchor)
        font = self.QtWidgets.QApplication.font()
        font.setPointSize(max(10, font.pointSize()))
        font.setBold(bool(bold))
        item.setFont(font)
        item.setPos(float(x), float(y))
        plot.addItem(item)
        return item

    def _sync_response_table_selection(self, event_id: int):
        if self.response_result is None or self.response_result.events.empty:
            return
        matches = np.flatnonzero(
            self.response_result.events["Event ID"].to_numpy(int) == int(event_id)
        )
        if not len(matches):
            return
        row_index = int(matches[0])
        if self.response_table.currentRow() == row_index:
            return
        self.response_table.blockSignals(True)
        self.response_table.selectRow(row_index)
        self.response_table.blockSignals(False)

    def refresh_response_plot(self):
        self.response_plot_area.clear()
        if self.response_result is None or self.response_result.events.empty:
            return

        event_id = self.response_event_combo.currentData()
        if event_id is None:
            event_id = int(self.response_result.events["Event ID"].iloc[0])
        row = self.response_result.events[
            self.response_result.events["Event ID"] == event_id
        ].iloc[0]
        self._sync_response_table_selection(int(event_id))

        start = float(row.get("Display Start s", row["Segment Start s"]))
        end = float(row.get("Display End s", row["Segment End s"]))
        data = self.response_result.processed[
            self.response_result.processed[TIME].between(start, end)
        ]
        if data.empty:
            return

        t_ms = data[TIME].to_numpy(float) * 1000.0
        t0_ms = float(row["t0 s"]) * 1000.0
        x_left = float(t_ms[0])
        x_right = float(t_ms[-1])
        x_label = x_left + 0.02 * max(x_right - x_left, 1e-6)
        marker_pen = self._marker_pen()
        signal_pen = self._signal_pen()

        current_plot = self.response_plot_area.addPlot(row=0, col=0)
        self._axis_style(current_plot, self._text("阀电流", "Valve current"), "A")
        current_plot.plot(
            t_ms,
            data[CURRENT].to_numpy(float),
            pen=signal_pen,
        )
        current_plot.addLine(x=t0_ms, pen=marker_pen)
        current_levels = (
            ("10%", float(row["Trigger Current A"])),
            ("100%", float(row["Current 100% A"])),
        )
        for label, value in current_levels:
            current_plot.addLine(y=value, pen=marker_pen)
            self._add_plot_text(current_plot, label, x_label, value)
        current_plot.setTitle(
            self._text(
                f"电流｜{row.get('Stage', '')}｜{row['Direction']}",
                f"Current | {row.get('Stage', '')} | {row['Direction']}",
            )
        )

        force_plot = self.response_plot_area.addPlot(row=1, col=0)
        force_plot.setXLink(current_plot)
        self._axis_style(force_plot, self._text("阻尼力", "Damping force"), "kN")
        force_kn = data[LOAD].to_numpy(float) / 1000.0
        force_plot.plot(t_ms, force_kn, pen=signal_pen)
        force_plot.addLine(x=t0_ms, pen=marker_pen)

        force_levels = (
            ("1%", float(row["F1 N"]) / 1000.0),
            ("63%", float(row["F63 N"]) / 1000.0),
            ("90%", float(row["F90 N"]) / 1000.0),
            ("100%", float(row["F100 N"]) / 1000.0),
        )
        for label, value in force_levels:
            force_plot.addLine(y=value, pen=marker_pen)
            self._add_plot_text(force_plot, label, x_label, value)

        response_markers = (
            ("t1", float(row["Dead Time t1 ms"])),
            ("t63", float(row["Switch Time t63 ms"])),
            ("t90", float(row["Switch Time t90 ms"])),
        )
        finite_marker_positions: list[tuple[str, float]] = []
        for label, elapsed_ms in response_markers:
            if np.isfinite(elapsed_ms):
                x_value = t0_ms + elapsed_ms
                force_plot.addLine(x=x_value, pen=marker_pen)
                finite_marker_positions.append((label, x_value))
        if len(force_kn):
            y_min = float(np.nanmin(force_kn))
            y_max = float(np.nanmax(force_kn))
            y_span = max(y_max - y_min, 0.1)
            for index, (label, x_value) in enumerate(finite_marker_positions):
                y = y_max - (0.08 + 0.12 * index) * y_span
                self._add_plot_text(force_plot, label, x_value, y, anchor=(0.5, 0.5))

        direction_text = (
            self._text("复原（+）", "Rebound (+)")
            if row["Direction"] == "Rebound"
            else self._text("压缩（-）", "Compression (-)")
        )
        if len(force_kn):
            direction_y = float(np.nanmax(force_kn)) if row["Direction"] == "Rebound" else float(np.nanmin(force_kn))
            self._add_plot_text(
                force_plot,
                direction_text,
                x_left + 0.55 * max(x_right - x_left, 1e-6),
                direction_y,
                anchor=(0.5, 1.0 if row["Direction"] == "Rebound" else 0.0),
                bold=True,
            )

        velocity_plot = self.response_plot_area.addPlot(row=2, col=0)
        velocity_plot.setXLink(current_plot)
        self._axis_style(velocity_plot, self._text("速度", "Velocity"), "m/s")
        velocity_plot.plot(
            t_ms,
            data[VELOCITY].to_numpy(float),
            pen=signal_pen,
        )
        velocity_plot.addLine(x=t0_ms, pen=marker_pen)
        target_velocity = float(row["Target Velocity m/s"])
        velocity_plot.addLine(y=target_velocity, pen=marker_pen)
        self._add_plot_text(
            velocity_plot,
            self._text(
                f"目标 {target_velocity:+.4g} m/s",
                f"Target {target_velocity:+.4g} m/s",
            ),
            x_label,
            target_velocity,
            bold=True,
        )

        current_plot.setXRange(x_left, x_right, padding=0.01)
