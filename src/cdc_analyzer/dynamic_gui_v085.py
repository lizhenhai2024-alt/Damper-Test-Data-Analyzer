from __future__ import annotations

import html
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from . import dynamic_gui as _base
from .dynamic_analysis import CURRENT, LOAD, TIME, VELOCITY, load_dynamic_test_data
from .dynamic_gui_v084 import DynamicPagesController as _BaseController
from .hysteresis_v085 import analyze_hysteresis_v085, combine_hysteresis_datasets
from .plot_layout_v085 import FlowLayout, IntersectionLabels


def discover_hysteresis_dat_files(folder: str | Path) -> list[Path]:
    """Return all DAT files below a selected folder in stable path order."""
    root = Path(folder)
    return sorted(
        (path for path in root.rglob("*") if path.is_file() and path.suffix.lower() == ".dat"),
        key=lambda path: str(path).casefold(),
    )


class DynamicPagesController(_BaseController):
    _SUBSCRIPT_TRANSLATION = str.maketrans("0123456789-", "₀₁₂₃₄₅₆₇₈₉₋")
    _CURRENT_COLOR = "#1565c0"
    _FORCE_COLOR = "#c62828"

    @classmethod
    def _threshold_label(cls, symbol: str, fraction: float) -> str:
        percent = f"{float(fraction) * 100:g}".translate(cls._SUBSCRIPT_TRANSLATION)
        return f"{symbol}{percent}%"

    def _build_response_page(self):
        super()._build_response_page()
        controls = self.response_page.layout().itemAt(0).layout()

        self.response_force_start_label = QtWidgets.QLabel()
        self.response_force_start_fraction = QtWidgets.QDoubleSpinBox()
        self.response_force_start_fraction.setRange(0.1, 62.9)
        self.response_force_start_fraction.setDecimals(1)
        self.response_force_start_fraction.setSingleStep(0.5)
        self.response_force_start_fraction.setValue(1.0)
        self.response_force_start_fraction.setSuffix(" %")
        self.response_force_start_fraction.setMaximumWidth(105)

        self.response_show_f1 = QtWidgets.QCheckBox()
        self.response_show_f1.setChecked(True)
        self.response_show_f63 = QtWidgets.QCheckBox()
        self.response_show_f63.setChecked(True)
        self.response_show_f1.toggled.connect(self.refresh_response_plot)
        self.response_show_f63.toggled.connect(self.refresh_response_plot)
        self.response_force_start_fraction.valueChanged.connect(
            self._update_response_threshold_texts
        )
        self.response_force_start_fraction.editingFinished.connect(
            self._reanalyze_response_threshold
        )

        self.response_plot_mode_label = QtWidgets.QLabel()
        self.response_plot_mode = QtWidgets.QComboBox()
        self.response_plot_mode.addItem("", "stacked")
        self.response_plot_mode.addItem("", "dual_axis_i10_f90")
        self.response_plot_mode.currentIndexChanged.connect(self.refresh_response_plot)

        insert_at = controls.indexOf(self.response_trigger) + 1
        for widget in (
            self.response_force_start_label,
            self.response_force_start_fraction,
            self.response_show_f1,
            self.response_show_f63,
        ):
            controls.insertWidget(insert_at, widget)
            insert_at += 1

    def _update_response_threshold_texts(self, *_args):
        if not hasattr(self, "response_force_start_fraction"):
            return
        label = self._threshold_label(
            "F", self.response_force_start_fraction.value() / 100.0
        )
        self.response_force_start_label.setText(
            self._text("起始载荷阈值", "Initial force threshold")
        )
        self.response_show_f1.setText(
            self._text(f"显示 {label}", f"Show {label}")
        )
        self.response_show_f63.setText(
            self._text("显示 F₆₃%", "Show F₆₃%")
        )

    def _reanalyze_response_threshold(self):
        self._update_response_threshold_texts()
        if self.response_dataset is not None and self.response_result is not None:
            self.analyze_response()

    def _font(self):
        font = QtGui.QFont(QtWidgets.QApplication.font())
        font.setPointSizeF(10.0)
        font.setBold(False)
        return font

    def _axis_style(self, plot, left, units=None):
        super()._axis_style(plot, left, units)
        for side in ("left", "bottom"):
            axis = plot.getAxis(side)
            axis.setLabel(axis.labelText, units=axis.labelUnits, **{"font-size": "10pt", "font-weight": "normal"})
            axis.label.setFont(self._font())
            axis.setStyle(tickFont=self._font())
            axis.enableAutoSIPrefix(False)
        plot.setTitle("")

    def _flow_controls(self, page, groups, source, status):
        root = page.layout()
        # Remove only the original top row; keep hidden compatibility widgets
        # parented to the page for inherited language/configuration methods.
        old = root.takeAt(0).layout()
        while old.count():
            old.takeAt(0)
        old.deleteLater()
        source.setMinimumWidth(0)
        source.setWordWrap(True)
        source.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        root.insertWidget(0, source)
        flow = FlowLayout()
        for widgets in groups:
            group = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(group)
            layout.setContentsMargins(0, 0, 0, 0)
            for widget in widgets:
                widget.setMaximumWidth(16777215)
                layout.addWidget(widget)
            flow.addWidget(group)
        root.insertLayout(1, flow)
        status.setWordWrap(True)
        status.setMinimumWidth(0)
        return flow

    def configure_responsive_layout(self):
        self.response_flow = self._flow_controls(self.response_page, [
            [self.response_standard_label, self.response_standard],
            [self.response_target_speed_label, self.response_target_speeds],
            [self.response_trigger_label, self.response_trigger],
            [self.response_force_start_label, self.response_force_start_fraction],
            [self.response_show_f1, self.response_show_f63],
            [self.response_limit_label, self.response_t90_limit],
            [self.response_plot_mode_label, self.response_plot_mode],
            [self.response_analyze_button],
        ], self.response_file_label, self.response_status)
        self.response_target_speeds.setMinimumWidth(160)
        self.response_event_combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.response_event_combo.setMinimumContentsLength(22)
        self.response_event_combo.setMinimumWidth(0)
        event_row = self.response_page.layout().itemAt(2).layout()
        if event_row is not None:
            event_row.removeWidget(self.response_status)
            self.response_page.layout().insertWidget(3, self.response_status)
        graph_layout = self.response_graph_page.layout()
        graph_layout.removeWidget(self.response_plot_area)
        self.response_scroll = QtWidgets.QScrollArea()
        self.response_scroll.setWidgetResizable(True)
        self.response_plot_area.setMinimumSize(480, 740)
        self.response_scroll.setWidget(self.response_plot_area)
        graph_layout.addWidget(self.response_scroll)

        self.hysteresis_speed_tolerance = QtWidgets.QDoubleSpinBox()
        self.hysteresis_speed_tolerance.setRange(0, 20)
        self.hysteresis_speed_tolerance.setValue(3)
        self.hysteresis_speed_tolerance.setSuffix(" %")
        self.speed_tolerance_label = QtWidgets.QLabel()
        self.hysteresis_multi_file_button = QtWidgets.QPushButton()
        self.hysteresis_multi_file_button.clicked.connect(self.open_hysteresis_files)
        self.hysteresis_folder_button = QtWidgets.QPushButton()
        self.hysteresis_folder_button.clicked.connect(self.open_hysteresis_folder)
        self._flow_controls(self.hysteresis_page, [
            [self.hysteresis_standard_label, self.hysteresis_standard],
            [self.hysteresis_limit_label, self.hysteresis_limit],
            [self.speed_tolerance_label, self.hysteresis_speed_tolerance],
            [self.hysteresis_multi_file_button],
            [self.hysteresis_folder_button],
            [self.hysteresis_analyze_button],
        ], self.hysteresis_file_label, self.hysteresis_status)
        self.hysteresis_view_combo = QtWidgets.QComboBox()
        self.hysteresis_view_combo.currentIndexChanged.connect(self.refresh_hysteresis_plot)
        self.hysteresis_page.layout().insertWidget(2, self.hysteresis_view_combo)
        # Give plots a full page; tables remain accessible in their own tab.
        splitter = self.hysteresis_plot_area.parentWidget()
        self.hysteresis_page.layout().removeWidget(splitter)
        self.hysteresis_plot_area.setParent(None)
        self.hysteresis_tables.setParent(None)
        splitter.hide()
        splitter.deleteLater()
        self.hysteresis_view_tabs = QtWidgets.QTabWidget()
        self.hysteresis_view_tabs.addTab(self.hysteresis_plot_area, "")
        self.hysteresis_view_tabs.addTab(self.hysteresis_tables, "")
        self.hysteresis_page.layout().addWidget(self.hysteresis_view_tabs, 1)

        self.window.tabs.setUsesScrollButtons(True)
        self.window.tabs.tabBar().setExpanding(False)
        for form in self.window.findChildren(QtWidgets.QFormLayout):
            form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)
        self._v085_language()

    def _v085_language(self):
        if not hasattr(self, "hysteresis_view_combo"):
            return
        self.speed_tolerance_label.setText(self._text("速度分组容差", "Speed grouping tolerance"))
        self.hysteresis_multi_file_button.setText(self._text("加载多速度迟滞数据…", "Load multi-speed hysteresis data…"))
        self.hysteresis_folder_button.setText(self._text("扫描迟滞数据文件夹…", "Scan hysteresis data folder…"))
        self.response_plot_mode_label.setText(self._text("响应图", "Response plot"))
        self.response_plot_mode.setItemText(0, self._text("三联响应图", "Three-panel response"))
        self.response_plot_mode.setItemText(1, self._text("双Y轴 I₁₀%→F₉₀%", "Dual-axis I₁₀%→F₉₀%"))
        self._update_response_threshold_texts()
        self._update_shared_source_labels()
        self.hysteresis_view_tabs.setTabText(0, self._text("图形分析", "Plot Analysis"))
        self.hysteresis_view_tabs.setTabText(1, self._text("结果数据", "Result Data"))
        self._rebuild_hysteresis_views()

    def apply_language(self, language):
        super().apply_language(language)
        self._v085_language()

    def set_shared_dataset(self, dataset, path=None):
        self.hysteresis_paths = []
        super().set_shared_dataset(dataset, path)

    def _update_shared_source_labels(self):
        super()._update_shared_source_labels()
        paths = getattr(self, "hysteresis_paths", [])
        if paths:
            names = ", ".join(f"{path.parent.name}/{path.name}" for path in paths)
            self.hysteresis_file_label.setText(self._text(
                f"多速度迟滞数据：{len(paths)} 个文件｜{names}",
                f"Multi-speed hysteresis data: {len(paths)} files | {names}",
            ))

    def refresh_response_plot(self):
        self._clear_response_dual_axis()
        for manager in getattr(self, "response_annotations", []):
            manager.plot.vb.sigResized.disconnect(manager.update)
            manager.plot.vb.sigRangeChanged.disconnect(manager.update)
        self.response_plot_area.clear()
        self.response_annotations = []
        if self.response_result is None or self.response_result.events.empty:
            return
        events = self.response_result.events
        event_id = self.response_event_combo.currentData()
        selected = events[events["Event ID"] == event_id]
        row = selected.iloc[0] if len(selected) else events.iloc[0]
        self._sync_response_table_selection(int(row["Event ID"]))
        start = float(row.get("Display Start s", row["Segment Start s"]))
        end = max(float(row.get("Display End s", row["Segment End s"])), float(row.get("Target Window End s", row["Segment End s"])))
        data = self.response_result.processed
        data = data[data[TIME].between(start, end)]
        if data.empty:
            return
        t = data[TIME].to_numpy(float)
        t0 = float(row["t0 s"])
        trigger_fraction = float(row.get("Trigger Fraction", 0.10))
        force_start_fraction = float(row.get("Force Start Fraction", 0.01))
        current_trigger_label = self._threshold_label("I", trigger_fraction)
        force_start_label = self._threshold_label("F", force_start_fraction)
        time_start_label = self._threshold_label("t", force_start_fraction)
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        if getattr(self, "response_plot_mode", None) is not None and self.response_plot_mode.currentData() == "dual_axis_i10_f90":
            self._refresh_response_dual_axis(row, data, t, foreground)
            return
        current = self.response_plot_area.addPlot(row=0, col=0)
        force = self.response_plot_area.addPlot(row=1, col=0)
        velocity = self.response_plot_area.addPlot(row=2, col=0)
        force.setXLink(current)
        velocity.setXLink(current)
        for plot, signal, title, units in (
            (current, data[CURRENT].to_numpy(float), self._text("阀电流", "Valve current"), "A"),
            (force, data[LOAD].to_numpy(float) / 1000, self._text("阻尼力", "Damping force"), "kN"),
            (velocity, data[VELOCITY].to_numpy(float), self._text("速度", "Velocity"), "m/s"),
        ):
            self._axis_style(plot, title, units)
            plot.plot(t, signal, pen=self._signal_pen())
            span = max(float(np.ptp(signal)), 0.02)
            plot.setYRange(float(np.min(signal)) - 0.24 * span, float(np.max(signal)) + 0.30 * span, padding=0)
        current.setTitle(self._text("电流", "Current") + " | " + self._localized_stage(row.get("Stage", "")) + " | " + self._localized_direction(row.get("Direction", "")), size="10pt")
        for plot, values, levels, markers in (
            (current, data[CURRENT].to_numpy(float),
             [("", row["Trigger Current A"]), ("I₁₀₀%", row["Current 100% A"])],
             [(current_trigger_label, t0)]),
            (force, data[LOAD].to_numpy(float) / 1000,
             [
                 (label, row[key] / 1000)
                 for label, key, visible in (
                     (force_start_label, "F1 N", self.response_show_f1.isChecked()),
                     ("F₆₃%", "F63 N", self.response_show_f63.isChecked()),
                     ("F₉₀%", "F90 N", True),
                     ("F₁₀₀%", "F100 N", True),
                 )
                 if visible
             ],
             [("t₀", t0)] + [(f"{label} = {row[key]:.2f} ms", t0 + row[key] / 1000)
              for label, key, visible in (
                  (time_start_label, "Dead Time t1 ms", self.response_show_f1.isChecked()),
                  ("t₆₃%", "Switch Time t63 ms", self.response_show_f63.isChecked()),
                  ("t₉₀%", "Switch Time t90 ms", True),
              ) if visible and np.isfinite(row[key])]),
        ):
            annotations = IntersectionLabels(plot, self.pg, self._font(), foreground, self._marker_pen())
            level_x = t[0] + (t[-1] - t[0]) * 0.015
            for label, value in sorted(levels, key=lambda pair: -pair[1]):
                annotations.guide(value, vertical=False)
                if label:
                    annotations.label(label, level_x, value, level=True, placement="above-left")
            xs, ys = [], []
            response_marker_index = 0
            for label, x in markers:
                if t[0] <= x <= t[-1]:
                    y = float(np.interp(x, t, values))
                    annotations.guide(x, vertical=True)
                    if plot is current:
                        placement = "above-left"
                    elif label == "t₀":
                        placement = "below-left"
                    else:
                        side = "above" if response_marker_index % 2 == 0 else "below"
                        response_marker_index += 1
                        delta = max((t[-1] - t[0]) * 0.002, np.finfo(float).eps)
                        slope = float(np.interp(min(t[-1], x + delta), t, values)
                                      - np.interp(max(t[0], x - delta), t, values))
                        horizontal = "left" if (slope >= 0) == (side == "above") else "right"
                        placement = f"{side}-{horizontal}"
                    annotations.label(label, x, y, placement=placement)
                    xs.append(x)
                    ys.append(y)
            dots = self.pg.ScatterPlotItem(xs, ys, symbol="o", size=7, pen=self.pg.mkPen("#1565c0"), brush=self.pg.mkBrush("#1565c0"), pxMode=True)
            dots.setZValue(10)
            plot.addItem(dots, ignoreBounds=True)
            self.response_annotations.append(annotations)
        velocity.addLine(y=float(row["Target Velocity m/s"]), pen=self._marker_pen())
        current.setXRange(float(t[0]), float(t[-1]), padding=0.04)
        for annotations in self.response_annotations:
            annotations.update()

    def _clear_response_dual_axis(self):
        state = getattr(self, "response_dual_axis", None)
        if state is None:
            return
        plot, force_view, update_views = state
        try:
            plot.vb.sigResized.disconnect(update_views)
        except (RuntimeError, TypeError):
            pass
        try:
            scene = force_view.scene()
            if scene is not None:
                scene.removeItem(force_view)
        except RuntimeError:
            pass
        self.response_dual_axis = None
        self.response_dual_items = {}

    def _refresh_response_dual_axis(self, row, data, t, foreground):
        current_values = data[CURRENT].to_numpy(float)
        force_values = data[LOAD].to_numpy(float) / 1000.0
        plot = self.response_plot_area.addPlot(row=0, col=0)
        self._axis_style(plot, self._text("阀电流", "Valve current"), "A")
        plot.setLabel("bottom", self._text("时间", "Time"), units="s", **{"font-size": "10pt"})
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.setTitle(
            self._text("电流触发—阻尼力 F₉₀% 响应", "Current trigger–force F₉₀% response")
            + " | " + self._localized_stage(row.get("Stage", ""))
            + " | " + self._localized_direction(row.get("Direction", "")),
            size="10pt",
        )

        current_pen = self.pg.mkPen(self._CURRENT_COLOR, width=1.8)
        force_pen = self.pg.mkPen(self._FORCE_COLOR, width=1.8)
        current_curve = plot.plot(t, current_values, pen=current_pen)
        left_axis = plot.getAxis("left")
        left_axis.setLabel(
            self._text("阀电流", "Valve current"),
            units="A",
            color=self._CURRENT_COLOR,
            **{"font-size": "10pt", "font-weight": "normal"},
        )
        left_axis.label.setFont(self._font())
        left_axis.setPen(current_pen)
        left_axis.setTextPen(current_pen)

        plot.showAxis("right")
        force_view = self.pg.ViewBox()
        plot.scene().addItem(force_view)
        right_axis = plot.getAxis("right")
        right_axis.linkToView(force_view)
        right_axis.setGrid(False)
        force_view.setXLink(plot)
        right_axis.setLabel(
            self._text("阻尼力", "Damping force"),
            units="kN",
            color=self._FORCE_COLOR,
            **{"font-size": "10pt", "font-weight": "normal"},
        )
        right_axis.label.setFont(self._font())
        right_axis.setStyle(tickFont=self._font())
        right_axis.enableAutoSIPrefix(False)
        right_axis.setPen(force_pen)
        right_axis.setTextPen(force_pen)
        force_curve = self.pg.PlotCurveItem(t, force_values, pen=force_pen)
        force_view.addItem(force_curve)

        def update_views():
            force_view.setGeometry(plot.vb.sceneBoundingRect())
            force_view.linkedViewChanged(plot.vb, force_view.XAxis)

        update_views()
        plot.vb.sigResized.connect(update_views)
        self.response_dual_axis = (plot, force_view, update_views)

        current_span = max(float(np.ptp(current_values)), 0.02)
        force_span = max(float(np.ptp(force_values)), 0.02)
        plot.setYRange(
            float(np.min(current_values)) - 0.24 * current_span,
            float(np.max(current_values)) + 0.34 * current_span,
            padding=0,
        )
        force_view.setYRange(
            float(np.min(force_values)) - 0.24 * force_span,
            float(np.max(force_values)) + 0.30 * force_span,
            padding=0,
        )
        plot.setXRange(float(t[0]), float(t[-1]), padding=0.04)

        t10 = float(row.get("I10 Crossing Time s", np.nan))
        force_t90 = float(row.get("F90 Crossing Time s", np.nan))
        elapsed = float(row.get("Damping Response I10-F90 ms", np.nan))
        valid_crossings = np.isfinite([t10, force_t90, elapsed]).all()
        guides = []
        current_points = None
        force_points = None
        labels = []
        if valid_crossings and t[0] <= t10 <= force_t90 <= t[-1]:
            guide_pen = self.pg.mkPen(foreground, width=0.8, style=QtCore.Qt.PenStyle.DashLine)
            for crossing in (t10, force_t90):
                guide = self.pg.InfiniteLine(pos=crossing, angle=90, pen=guide_pen)
                guide.setZValue(5)
                plot.addItem(guide, ignoreBounds=True)
                guides.append(guide)

            current_y = float(np.interp(t10, t, current_values))
            force_y = np.interp([t10, force_t90], t, force_values)
            current_points = self.pg.ScatterPlotItem(
                [t10], [current_y], symbol="o", size=8,
                pen=self.pg.mkPen(self._CURRENT_COLOR), brush=self.pg.mkBrush(self._CURRENT_COLOR), pxMode=True,
            )
            force_points = self.pg.ScatterPlotItem(
                [t10, force_t90], force_y, symbol="o", size=8,
                pen=self.pg.mkPen(self._FORCE_COLOR), brush=self.pg.mkBrush(self._FORCE_COLOR), pxMode=True,
            )
            current_points.setZValue(10)
            force_points.setZValue(10)
            plot.addItem(current_points, ignoreBounds=True)
            force_view.addItem(force_points, ignoreBounds=True)

            current_label = self.pg.TextItem(
                text="I₁₀%", color=self._CURRENT_COLOR, anchor=(1.0, 1.0)
            )
            current_label.setFont(self._font())
            current_label.setPos(float(t10), current_y)
            current_label.setZValue(20)
            plot.addItem(current_label, ignoreBounds=True)
            labels.append(current_label)

            for text, x, y, anchor in (
                (f"F(I₁₀%) = {force_y[0]:.3g} kN", t10, force_y[0], (1.0, 0.0)),
                (f"F₉₀% = {force_y[1]:.3g} kN", force_t90, force_y[1], (0.0, 1.0)),
            ):
                label = self.pg.TextItem(text=text, color=self._FORCE_COLOR, anchor=anchor)
                label.setFont(self._font())
                label.setPos(float(x), float(y))
                label.setZValue(20)
                force_view.addItem(label, ignoreBounds=True)
                labels.append(label)

            delta_label = self.pg.TextItem(
                text=f"t₉₀% = t(F₉₀%) − t(I₁₀%) = {elapsed:.2f} ms",
                color=self._CURRENT_COLOR,
                anchor=(0.5, 1.0),
            )
            delta_label.setFont(self._font())
            delta_label.setPos(float((t10 + force_t90) / 2), float(np.max(current_values) + 0.24 * current_span))
            delta_label.setZValue(20)
            plot.addItem(delta_label, ignoreBounds=True)
            labels.append(delta_label)

        legend = plot.addLegend(offset=(10, 10), labelTextSize="10pt")
        legend.addItem(current_curve, self._text("电流", "Current"))
        legend.addItem(force_curve, self._text("阻尼力", "Damping force"))
        self.response_dual_items = {
            "plot": plot,
            "force_view": force_view,
            "current_curve": current_curve,
            "force_curve": force_curve,
            "guides": guides,
            "current_points": current_points,
            "force_points": force_points,
            "labels": labels,
        }

    def analyze_hysteresis(self):
        previous = _base.analyze_hysteresis
        tolerance = self.hysteresis_speed_tolerance.value() / 100 if hasattr(self, "hysteresis_speed_tolerance") else 0.03
        _base.analyze_hysteresis = lambda dataset, config: analyze_hysteresis_v085(dataset, config, speed_tolerance=tolerance)
        try:
            super().analyze_hysteresis()
        finally:
            _base.analyze_hysteresis = previous
        self._rebuild_hysteresis_views()
        if self.hysteresis_result is not None:
            count = self.hysteresis_result.runs["Speed Group m/s"].nunique()
            speeds = ", ".join(f"{v:.4g}" for v in sorted(self.hysteresis_result.runs["Speed Group m/s"].unique()))
            results = len(self.hysteresis_result.summary)
            self.hysteresis_status.setText(self._text(
                f"分析完成：检测到 {count} 个速度组（{speeds} m/s），{results} 条迟滞结果",
                f"Analysis complete: {count} speed group(s) ({speeds} m/s), {results} hysteresis result(s)",
            ))

    def open_hysteresis_files(self):
        paths, _ = self.QtWidgets.QFileDialog.getOpenFileNames(
            self.window,
            self._text("加载多速度迟滞数据", "Load multi-speed hysteresis data"),
            "",
            self._file_filter(),
        )
        if not paths:
            return
        self._load_hysteresis_paths([Path(path) for path in paths])

    def open_hysteresis_folder(self):
        folder = self.QtWidgets.QFileDialog.getExistingDirectory(
            self.window,
            self._text("选择迟滞数据文件夹", "Select hysteresis data folder"),
            "",
        )
        if not folder:
            return
        paths = discover_hysteresis_dat_files(folder)
        if not paths:
            self.QtWidgets.QMessageBox.information(
                self.window,
                self._text("未找到数据", "No data found"),
                self._text(
                    "所选文件夹及其子文件夹中没有 .dat 文件。",
                    "No .dat files were found in the selected folder or its subfolders.",
                ),
            )
            return
        self._load_hysteresis_paths(paths)

    def _load_hysteresis_paths(self, paths):
        try:
            datasets = [load_dynamic_test_data(path) for path in paths]
            self.hysteresis_dataset = combine_hysteresis_datasets(datasets)
            self.hysteresis_paths = [Path(path) for path in paths]
            self.hysteresis_path = self.hysteresis_paths[0]
            self.hysteresis_result = None
            self._update_shared_source_labels()
            self.hysteresis_status.setText(self._text(
                f"已合并 {len(paths)} 个文件；点击“分析迟滞”按实测速度分组。",
                f"Combined {len(paths)} files; click Analyze Hysteresis to group measured speeds.",
            ))
        except Exception as exc:
            self.QtWidgets.QMessageBox.critical(self.window, self._text("导入错误", "Import error"), str(exc))

    def _rebuild_hysteresis_views(self):
        if not hasattr(self, "hysteresis_view_combo"):
            return
        combo = self.hysteresis_view_combo
        previous = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(self._text("全部速度：电流—阻尼力", "All speeds: current–force"), ("all", None))
        if self.hysteresis_result is not None:
            runs = self.hysteresis_result.runs
            summary = self.hysteresis_result.summary
            has_current_hysteresis = (
                not summary.empty
                and "Hysteresis N" in summary
                and (
                    "Current A" in summary
                    or np.isfinite(float(self.hysteresis_result.settings.get("KFM Current A", np.nan)))
                )
            )
            if has_current_hysteresis:
                combo.addItem(
                    self._text("电流—迟滞力柱状图", "Current–hysteresis force bars"),
                    ("hysteresis_bar", None),
                )
            for speed in sorted(runs["Speed Group m/s"].unique()):
                combo.addItem(self._text(f"速度 {speed:.4g} m/s：电流—阻尼力迟滞", f"Speed {speed:.4g} m/s: current–force hysteresis"), ("speed", float(speed)))
            for current in sorted(runs["Current Label A"].unique()):
                combo.addItem(self._text(f"电流 {current:g} A：速度—阻尼力迟滞", f"Current {current:g} A: speed–force hysteresis"), ("current", float(current)))
        index = combo.findData(previous)
        combo.setCurrentIndex(max(0, index))
        combo.blockSignals(False)
        self.refresh_hysteresis_plot()

    def refresh_hysteresis_plot(self):
        self.hysteresis_plot_area.clear()
        if self.hysteresis_result is None or self.hysteresis_result.runs.empty:
            return
        runs = self.hysteresis_result.runs.copy()
        if "Speed Group m/s" not in runs:
            return
        selected = self.hysteresis_view_combo.currentData() if hasattr(self, "hysteresis_view_combo") else None
        mode, value = selected or ("all", None)
        if mode == "hysteresis_bar":
            self._plot_current_hysteresis_bars()
            return
        if mode == "speed":
            runs = runs[runs["Speed Group m/s"] == value]
        elif mode == "current":
            runs = runs[runs["Current Label A"] == value]
        plot = self.hysteresis_plot_area.addPlot(row=0, col=0)
        self._axis_style(plot, html.escape(self._text("压缩<--阻尼力(N)-->复原", "Compression<--Damping force (N)-->Rebound")))
        plot.setLabel("bottom", self._text("速度", "Speed") if mode == "current" else self._text("电流", "Current"), units="m/s" if mode == "current" else "A", **{"font-size": "10pt"})
        plot.showGrid(x=True, y=True, alpha=0.15)
        legend = self.pg.LegendItem(labelTextSize="10pt", colCount=2 if self.hysteresis_plot_area.width() < 850 else 4)
        self.hysteresis_plot_area.addItem(legend, row=1, col=0)
        plot.setTitle(
            self._text("迟滞曲线：全部使用实线", "Hysteresis curves: all solid lines")
            if "Sweep Direction" in runs
            else self._text("按实测电流平台顺序连接（实线）", "Connected in measured plateau order (solid)"),
            size="10pt",
        )
        legend_keys = set()
        speeds = sorted(runs["Speed Group m/s"].unique())
        colors = ["#1565c0", "#c62828", "#00897b", "#ef6c00", "#6a1b9a", "#6d4c41", "#37474f", "#ad1457"]
        force_column = "Force N" if "Force N" in runs else "Mean Force N"
        group_columns = ["Direction"] if mode == "current" else ["Speed Group m/s", "Direction"]
        if "Sweep Direction" in runs:
            group_columns.append("Sweep Direction")
        plotted_y = []
        for index, (key, group) in enumerate(runs.groupby(group_columns, sort=True)):
            direction = str(group["Direction"].iloc[0])
            sweep = str(group["Sweep Direction"].iloc[0]) if "Sweep Direction" in group else "Sequence"
            speed = float(group["Speed Group m/s"].iloc[0])
            color_index = (0 if mode == "current" else speeds.index(speed) * 2) + (direction == "Compression")
            color = colors[color_index % len(colors)]
            # Draw one uninterrupted polyline. Point symbols made the previous
            # rendering look dashed at normal zoom even though the QPen style
            # itself was SolidLine.
            pen = self.pg.mkPen(color, width=2.0)
            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
            pen.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(QtCore.Qt.PenJoinStyle.RoundJoin)
            x_column = "Speed Group m/s" if mode == "current" else "Current Label A"
            # BMW uses ordered sweep points; Audi uses acquisition sequence to
            # retain its KFM excursions. Never connect different speed groups.
            group = group.sort_values(x_column if mode == "current" else "Block Order")
            y = np.abs(group[force_column].to_numpy(float)) * (1 if direction == "Rebound" else -1)
            plotted_y.extend(y[np.isfinite(y)])
            speed_name = "" if mode == "current" else f"{group['Speed Group m/s'].iloc[0]:.4g} m/s "
            sweep_name = self._text({"Up": "升电流", "Down": "降电流", "Sequence": "平台顺序"}[sweep], sweep)
            name = f"{speed_name}{self._localized_direction(direction)} {sweep_name}"
            curve = plot.plot(
                group[x_column].to_numpy(float),
                y,
                pen=pen,
                symbol=None,
                connect="all",
                antialias=True,
            )
            legend_key = (speed_name, direction)
            if legend_key not in legend_keys:
                legend.addItem(curve, f"{speed_name}{self._localized_direction(direction)}")
                legend_keys.add(legend_key)
        plot.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))
        if plotted_y:
            lower, upper = float(np.min(plotted_y)), float(np.max(plotted_y))
            span = max(upper - lower, abs(upper), abs(lower), 1.0)
            plot.setYRange(min(0.0, lower) - 0.08 * span, max(0.0, upper) + 0.08 * span, padding=0)

    def _plot_current_hysteresis_bars(self):
        """Plot current against hysteresis force for every speed and direction."""
        summary = self.hysteresis_result.summary.copy()
        if "Current A" not in summary:
            summary["Current A"] = float(
                self.hysteresis_result.settings.get("KFM Current A", np.nan)
            )
        required = ["Current A", "Hysteresis N", "Direction"]
        summary = summary.dropna(subset=required)
        if summary.empty:
            return

        group_columns = ["Current A", "Direction"]
        if "Speed Group m/s" in summary:
            group_columns.insert(1, "Speed Group m/s")
        summary = summary.groupby(group_columns, as_index=False)["Hysteresis N"].mean()
        currents = sorted(summary["Current A"].unique())
        positions = {current: index for index, current in enumerate(currents)}
        series_columns = [column for column in ("Speed Group m/s", "Direction") if column in summary]
        series = list(summary.groupby(series_columns, sort=True))

        plot = self.hysteresis_plot_area.addPlot(row=0, col=0)
        self._axis_style(plot, self._text("迟滞力", "Hysteresis force"), "N")
        plot.setLabel("bottom", self._text("电流", "Current"), units="A", **{"font-size": "10pt"})
        plot.getAxis("bottom").setTicks([[(float(i), f"{current:g}") for i, current in enumerate(currents)]])
        plot.showGrid(x=False, y=True, alpha=0.18)
        plot.setTitle(self._text("电流—迟滞力柱状图", "Current–hysteresis force bar chart"), size="10pt")
        legend = self.pg.LegendItem(labelTextSize="10pt", colCount=2 if self.hysteresis_plot_area.width() < 850 else 4)
        self.hysteresis_plot_area.addItem(legend, row=1, col=0)

        colors = ["#1565c0", "#c62828", "#00897b", "#ef6c00", "#6a1b9a", "#6d4c41", "#37474f", "#ad1457"]
        total_width = 0.82
        bar_width = total_width / max(len(series), 1)
        maximum = 0.0
        foreground = getattr(self.window, "_plot_foreground_color", "#202020")
        for series_index, (key, group) in enumerate(series):
            key = key if isinstance(key, tuple) else (key,)
            x = np.array([positions[current] for current in group["Current A"]], dtype=float)
            x += -total_width / 2 + bar_width * (series_index + 0.5)
            heights = group["Hysteresis N"].to_numpy(float)
            maximum = max(maximum, float(np.max(heights)))
            color = colors[series_index % len(colors)]
            bars = self.pg.BarGraphItem(
                x=x,
                height=heights,
                width=bar_width * 0.88,
                brush=self.pg.mkBrush(color),
                pen=self.pg.mkPen(color, width=1.0),
            )
            plot.addItem(bars)
            labels = dict(zip(series_columns, key))
            speed_text = (
                f"{float(labels['Speed Group m/s']):.4g} m/s "
                if "Speed Group m/s" in labels
                else ""
            )
            direction_text = self._localized_direction(str(labels.get("Direction", "")))
            legend.addItem(bars, f"{speed_text}{direction_text}".strip())
            for x_value, height in zip(x, heights):
                label = self.pg.TextItem(
                    text=f"{height:.0f}",
                    color=foreground,
                    anchor=(0.5, 1.0),
                )
                label.setFont(self._font())
                label.setPos(float(x_value), float(height))
                plot.addItem(label, ignoreBounds=True)
        plot.setXRange(-0.55, max(len(currents) - 0.45, 0.55), padding=0)
        plot.setYRange(0, max(maximum * 1.18, 1.0), padding=0)

    def _prepare_hysteresis_plot_for_export(self):
        self.window.tabs.setCurrentWidget(self.hysteresis_page)
        if hasattr(self, "hysteresis_view_tabs"):
            self.hysteresis_view_tabs.setCurrentWidget(self.hysteresis_plot_area)
        self.refresh_hysteresis_plot()
        QtWidgets.QApplication.processEvents()

    def export_hysteresis_png(self):
        if self.hysteresis_result is not None:
            self._prepare_hysteresis_plot_for_export()
        super().export_hysteresis_png()

    def _append_hysteresis_plot(self, workbook_path):
        from openpyxl import load_workbook
        from openpyxl.drawing.image import Image
        workbook = load_workbook(workbook_path)
        if "Hysteresis Plot" in workbook:
            del workbook["Hysteresis Plot"]
        sheet = workbook.create_sheet("Hysteresis Plot")
        original = self.hysteresis_view_combo.currentIndex()
        original_page = self.window.tabs.currentWidget()
        original_view = self.hysteresis_view_tabs.currentWidget()
        self._prepare_hysteresis_plot_for_export()
        with TemporaryDirectory(prefix="hysteresis_v085_") as tmp:
            try:
                anchor_row = 1
                for i in range(self.hysteresis_view_combo.count()):
                    self.hysteresis_view_combo.setCurrentIndex(i)
                    self.refresh_hysteresis_plot()
                    QtWidgets.QApplication.processEvents()
                    path = self._export_plot_widget_png(self.hysteresis_plot_area, Path(tmp) / f"plot_{i}.png")
                    sheet.cell(anchor_row, 1, self.hysteresis_view_combo.itemText(i))
                    picture = Image(str(path))
                    picture.height *= 1000 / picture.width
                    picture.width = 1000
                    sheet.add_image(picture, f"A{anchor_row + 1}")
                    anchor_row += int(np.ceil(picture.height / 20)) + 5
                workbook.save(workbook_path)
            finally:
                self.hysteresis_view_combo.setCurrentIndex(original)
                self.refresh_hysteresis_plot()
                self.hysteresis_view_tabs.setCurrentWidget(original_view)
                self.window.tabs.setCurrentWidget(original_page)
