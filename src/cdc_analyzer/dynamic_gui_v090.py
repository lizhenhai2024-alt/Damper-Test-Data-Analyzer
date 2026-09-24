from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtWidgets

from .audi_items_20_21 import (
    ImportedMapFile,
    analyze_map_files,
    current_from_filename,
    discover_map_files,
    export_map_analysis_xlsx,
    inspect_map_file,
)
from .dynamic_gui_v085 import DynamicPagesController as _BaseController


class DynamicPagesController(_BaseController):
    def __init__(self, *args, **kwargs):
        self.map_files: list[ImportedMapFile] = []
        self.map_result = None
        super().__init__(*args, **kwargs)
        self._build_map_page()
        self._v090_language()

    def _build_map_page(self):
        self.map_page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(self.map_page)
        controls = QtWidgets.QHBoxLayout()
        self.map_folder_button = QtWidgets.QPushButton()
        self.map_remove_button = QtWidgets.QPushButton()
        self.map_analyze_button = QtWidgets.QPushButton()
        self.map_export_button = QtWidgets.QPushButton()
        self.map_soft_label = QtWidgets.QLabel()
        self.map_hard_label = QtWidgets.QLabel()
        self.map_show_points = QtWidgets.QCheckBox()
        self.map_soft_current = QtWidgets.QDoubleSpinBox()
        self.map_hard_current = QtWidgets.QDoubleSpinBox()
        for spin in (self.map_soft_current, self.map_hard_current):
            spin.setRange(0.0, 20.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setSuffix(" A")
        self.map_soft_current.setValue(0.3)
        self.map_hard_current.setValue(1.6)
        self.map_show_points.setChecked(True)
        self.map_folder_button.clicked.connect(self.open_map_folder)
        self.map_remove_button.clicked.connect(self.remove_selected_map_files)
        self.map_analyze_button.clicked.connect(self.analyze_map)
        self.map_export_button.clicked.connect(self.export_map)
        self.map_show_points.toggled.connect(self.refresh_map_plots)
        for widget in (self.map_folder_button, self.map_remove_button, self.map_soft_label, self.map_soft_current, self.map_hard_label, self.map_hard_current, self.map_show_points, self.map_analyze_button, self.map_export_button):
            controls.addWidget(widget)
        controls.addStretch(1)
        root.addLayout(controls)

        self.map_status = QtWidgets.QLabel()
        self.map_status.setWordWrap(True)
        self.map_status.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.map_status)

        self.map_file_table = self._new_table()
        self.map_file_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.map_file_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.map_file_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.map_file_table.setMaximumHeight(210)
        root.addWidget(self.map_file_table)

        self.map_views = QtWidgets.QTabWidget()
        self.map_linearity_plot = self.pg.GraphicsLayoutWidget()
        self.map_spread_plot = self.pg.GraphicsLayoutWidget()
        self.map_force_velocity_plot = self.pg.GraphicsLayoutWidget()
        self.map_force_current_plot = self.pg.GraphicsLayoutWidget()
        for plot_widget in (self.map_linearity_plot, self.map_spread_plot, self.map_force_velocity_plot, self.map_force_current_plot):
            plot_widget.setBackground("#ffffff")
        self.map_force_velocity_table = self._new_table()
        self.map_linearity_table = self._new_table()
        self.map_spread_table = self._new_table()
        self.map_run_table = self._new_table()
        self.map_views.addTab(self.map_linearity_plot, "")
        self.map_views.addTab(self.map_spread_plot, "")
        self.map_views.addTab(self.map_force_velocity_plot, "")
        self.map_views.addTab(self.map_force_current_plot, "")
        self.map_views.addTab(self.map_force_velocity_table, "")
        self.map_views.addTab(self.map_linearity_table, "")
        self.map_views.addTab(self.map_spread_table, "")
        self.map_views.addTab(self.map_run_table, "")
        root.addWidget(self.map_views, 1)
        self.window.tabs.addTab(self.map_page, "")
        self._refresh_map_file_table()

    def _v090_language(self):
        if not hasattr(self, "map_page"):
            return
        self.map_folder_button.setText(self._text("选择全电流数据文件夹…", "Select full-current data folder…"))
        self.map_remove_button.setText(self._text("移除所选数据", "Remove selected data"))
        self.map_soft_label.setText(self._text("软电流", "Soft current"))
        self.map_hard_label.setText(self._text("硬电流", "Hard current"))
        self.map_show_points.setText(self._text("显示数据点", "Show data points"))
        self.map_analyze_button.setText(self._text("全电流分析", "Full-current analysis"))
        self.map_export_button.setText(self._text("导出 Excel…", "Export Excel…"))
        self.map_views.setTabText(0, self._text("20 电流—力线性", "20 Current–force linearity"))
        self.map_views.setTabText(1, self._text("21 力值范围与放大倍数", "21 Spread and amplification"))
        self.map_views.setTabText(2, self._text("F-V 图", "F-V plot"))
        self.map_views.setTabText(3, self._text("F-I 图", "F-I plot"))
        self.map_views.setTabText(4, self._text("F-V 数据", "F-V data"))
        self.map_views.setTabText(5, self._text("20 结果数据", "20 Results"))
        self.map_views.setTabText(6, self._text("21 结果数据", "21 Results"))
        self.map_views.setTabText(7, self._text("工况明细", "Run Detail"))
        index = self.window.tabs.indexOf(self.map_page)
        if index >= 0:
            self.window.tabs.setTabText(index, self._text("全电流分析", "Full-current analysis"))
        if not self.map_files:
            self.map_status.setText(self._text(
                "加载全电流 MTS .PVP 或 CTW .dctw 文件；电流 A 必须从文件名自动识别。软电流默认 0.3 A，硬电流默认 1.6 A。",
                "Load full-current MTS .PVP or CTW .dctw files. Current A is read from each filename. Defaults: soft 0.3 A and hard 1.6 A.",
            ))

    def apply_language(self, language):
        super().apply_language(language)
        self._v090_language()

    def open_map_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self.window, self._text("选择数据文件夹", "Select data folder"), "")
        if not folder:
            return
        paths = discover_map_files(folder)
        if not paths:
            QtWidgets.QMessageBox.information(self.window, self._text("未找到数据", "No data found"), self._text("文件夹及子文件夹中没有 .PVP 或 .dctw 文件。", "No .PVP or .dctw files were found."))
            return
        self._add_map_paths(paths)

    def _add_map_paths(self, paths):
        existing = {str(item.path.resolve()).casefold() for item in self.map_files}
        errors = []
        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
        try:
            for path in paths:
                path = Path(path)
                if str(path.resolve()).casefold() in existing:
                    continue
                try:
                    current = current_from_filename(path)
                    probe = inspect_map_file(path)
                    self.map_files.append(probe)
                    existing.add(str(path.resolve()).casefold())
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.map_result = None
        self._refresh_map_file_table()
        self.map_status.setText(self._text(
            f"已加载 {len(self.map_files)} 个文件；电流 A 已从文件名自动识别。" + (f" 未加载：{'；'.join(errors)}" if errors else ""),
            f"Loaded {len(self.map_files)} file(s); Current A was read from filenames." + (f" Not loaded: {'; '.join(errors)}" if errors else ""),
        ))

    def _refresh_map_file_table(self):
        headers = [self._text("文件", "File"), self._text("格式", "Format"), self._text("电流 A", "Current A"), self._text("速度段", "Speed runs"), self._text("状态", "Status"), self._text("完整路径", "Full path")]
        table = self.map_file_table
        table.setRowCount(len(self.map_files))
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        for row, item in enumerate(self.map_files):
            values = [item.path.name, item.format, "" if not np.isfinite(item.current_a) else f"{item.current_a:g}", ", ".join(f"{s:g}" for s in item.speeds_mps), item.status, str(item.path)]
            for column, value in enumerate(values):
                cell = QtWidgets.QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                table.setItem(row, column, cell)
        table.resizeColumnsToContents()

    def remove_selected_map_files(self):
        rows = sorted({index.row() for index in self.map_file_table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            del self.map_files[row]
        self.map_result = None
        self._refresh_map_file_table()
        self.map_status.setText(self._text(f"已保留 {len(self.map_files)} 个文件。原始文件未删除。", f"{len(self.map_files)} file(s) retained. Source files were not deleted."))

    def analyze_map(self):
        if not self.map_files:
            QtWidgets.QMessageBox.information(self.window, self._text("全电流分析", "Full-current analysis"), self._text("请先添加 PVP 或 DCTW 文件。", "Add PVP or DCTW files first."))
            return
        cursor_set = False
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            cursor_set = True
            self.map_result = analyze_map_files(
                self.map_files,
                soft_current_a=self.map_soft_current.value(),
                hard_current_a=self.map_hard_current.value(),
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self.window, self._text("分析错误", "Analysis error"), str(exc))
            return
        finally:
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
        self._fill_table(self.map_linearity_table, self.map_result.current_force_linearity)
        self._fill_table(self.map_spread_table, self.map_result.spread_amplification)
        self._fill_table(self.map_force_velocity_table, self.map_result.force_velocity_table)
        self._fill_table(self.map_run_table, self.map_result.run_detail)
        self.refresh_map_plots()
        repeats = int(self.map_result.current_force_linearity["Repeat Count"].max())
        self.map_status.setText(self._text(
            f"分析完成：{len(self.map_files)} 个文件，{len(self.map_result.run_detail)} 个有效速度段；同工况最多 {repeats} 次重复，按保留数据求均值。",
            f"Analysis complete: {len(self.map_files)} files and {len(self.map_result.run_detail)} valid speed runs; up to {repeats} retained repeats were averaged.",
        ))

    def refresh_map_plots(self):
        self.map_linearity_plot.clear()
        self.map_spread_plot.clear()
        self.map_force_velocity_plot.clear()
        self.map_force_current_plot.clear()
        for widget in (self.map_linearity_plot, self.map_spread_plot, self.map_force_velocity_plot, self.map_force_current_plot):
            widget.setBackground("#ffffff")
        if self.map_result is None:
            return
        colors = ["#1565c0", "#c62828", "#00897b", "#ef6c00", "#6a1b9a", "#6d4c41", "#37474f", "#ad1457"]
        linearity = self.map_linearity_plot.addPlot(row=0, col=0)
        self._map_plot_style(linearity, self._text("归一化阻尼力差", "Normalized damping-force difference"), None, self._text("电流", "Current"), "A")
        linearity.setTitle(self._text("第20项：电流—阻尼力线性", "Item 20: current–force linearity"), color="#202020", size="11pt")
        linearity.showGrid(x=True, y=True, alpha=0.15)
        legend = linearity.addLegend(offset=(10, 10), labelTextSize="9pt")
        item20_speeds = sorted(self.map_result.current_force_linearity["Speed m/s"].unique())
        speed_colors = {speed: self.pg.intColor(index, hues=max(1, len(item20_speeds))) for index, speed in enumerate(item20_speeds)}
        for index, ((speed, direction), group) in enumerate(self.map_result.current_force_linearity.groupby(["Speed m/s", "Direction"], sort=True)):
            group = group.sort_values("Current A")
            pen = self.pg.mkPen(speed_colors[speed], width=2)
            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
            curve = linearity.plot(group["Current A"].to_numpy(float), group["Normalized Force"].to_numpy(float), pen=pen, symbol="o", symbolSize=6)
            if direction == "Rebound":
                legend.addItem(curve, f"{speed:g} m/s")
        linearity.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))
        soft_current = float(self.map_result.settings["Soft Current A"])
        hard_current = float(self.map_result.settings["Hard Current A"])
        ideal_pen = self.pg.mkPen("#202020", width=1.8, style=QtCore.Qt.PenStyle.DashLine)
        ideal_curve = linearity.plot([soft_current, hard_current], [0.0, 1.0], pen=ideal_pen)
        linearity.plot([soft_current, hard_current], [0.0, -1.0], pen=ideal_pen)
        legend.addItem(ideal_curve, self._text("45°理想线", "45° ideal line"))

        spread_data = self.map_result.spread_amplification
        directions = [direction for direction in ("Rebound", "Compression") if direction in set(spread_data["Direction"])]
        speeds = np.sort(spread_data["Speed m/s"].unique().astype(float))
        speed_positions = {float(speed): float(index) for index, speed in enumerate(speeds)}
        bar_colors = {"Rebound": "#f2aa00", "Compression": "#87a9d3"}
        line_colors = {"Rebound": "#d32f2f", "Compression": "#1565c0"}

        spread = self.map_spread_plot.addPlot(row=0, col=0)
        self._map_plot_style(spread, self._text("压缩 ← 阻尼力范围 → 复原", "Compression ← damping-force spread → rebound"), "N", self._text("速度", "Speed"), "m/s")
        spread.setTitle(self._text("第21项：阻尼力范围", "Item 21: damping-force spread"), color="#202020", size="11pt")
        spread.showGrid(x=True, y=True, alpha=0.15)
        spread.getAxis("bottom").setTicks([[(speed_positions[float(speed)], f"{speed:g}") for speed in speeds]])
        spread.setXRange(-0.6, max(0.6, len(speeds) - 0.4), padding=0)
        width = 0.55
        spread_legend = spread.addLegend(offset=(10, 10), labelTextSize="9pt")
        for index, direction in enumerate(directions):
            group = spread_data[spread_data["Direction"] == direction].sort_values("Speed m/s")
            x = np.asarray([speed_positions[float(speed)] for speed in group["Speed m/s"]], dtype=float)
            values = group["Damping Force Spread N"].to_numpy(float)
            color = bar_colors[direction]
            bars = self.pg.BarGraphItem(x=x, height=values, width=width, brush=self.pg.mkBrush(color), pen=self.pg.mkPen("#303030"))
            spread.addItem(bars)
            spread_legend.addItem(bars, self._localized_direction(direction))
            for x_value, value in zip(x, values):
                label = self.pg.TextItem(text=f"{value:.0f}", color="#202020", anchor=(0.5, 1.0 if value >= 0 else 0.0))
                label.setPos(float(x_value), float(value))
                spread.addItem(label)
        spread.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))

        amplify = self.map_spread_plot.addPlot(row=0, col=1)
        self._map_plot_style(amplify, self._text("放大倍数", "Amplification"), None, self._text("速度", "Speed"), "m/s")
        amplify.setTitle(self._text("第21项：放大倍数", "Item 21: amplification"), color="#202020", size="11pt")
        amplify.showGrid(x=True, y=True, alpha=0.15)
        amplify.getAxis("bottom").setTicks([[(speed_positions[float(speed)], f"{speed:g}") for speed in speeds]])
        amplify.setXRange(-0.6, max(0.6, len(speeds) - 0.4), padding=0)
        amplify_legend = amplify.addLegend(offset=(10, 10), labelTextSize="9pt")
        for index, direction in enumerate(directions):
            group = spread_data[spread_data["Direction"] == direction].sort_values("Speed m/s")
            x = np.asarray([speed_positions[float(speed)] for speed in group["Speed m/s"]], dtype=float)
            values = group["Amplification"].to_numpy(float)
            color = line_colors[direction]
            curve = amplify.plot(x, values, pen=self.pg.mkPen(color, width=2), symbol="o", symbolSize=6, symbolBrush=color)
            amplify_legend.addItem(curve, self._localized_direction(direction))
            for point_index, (x_value, value) in enumerate(zip(x, values)):
                label = self.pg.TextItem(text=f"{value:.2f}×", color=color, anchor=(0.5, 1.15 if point_index % 2 == 0 else -0.15))
                label.setPos(float(x_value), float(value))
                amplify.addItem(label)
        amplify.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))

        raw = self.map_result.current_force_linearity
        fv_plot = self.map_force_velocity_plot.addPlot(row=0, col=0)
        self._map_plot_style(fv_plot, self._text("压缩 ← 阻尼力 → 复原", "Compression ← damping force → rebound"), "N", self._text("速度", "Speed"), "m/s")
        fv_plot.setTitle(self._text("F-V 全电流曲线", "F-V full-current curves"), color="#202020", size="11pt")
        fv_plot.showGrid(x=True, y=True, alpha=0.15)
        fv_legend = fv_plot.addLegend(offset=(10, 10), labelTextSize="9pt")
        current_groups = list(raw.groupby("Current A", sort=True))
        point_symbol = "o" if self.map_show_points.isChecked() else None
        for index, (current, current_group) in enumerate(current_groups):
            color = self.pg.intColor(index, hues=max(1, len(current_groups)))
            legend_curve = None
            for direction in ("Rebound", "Compression"):
                group = current_group[current_group["Direction"] == direction].sort_values("Speed m/s")
                if group.empty:
                    continue
                pen = self.pg.mkPen(color, width=1.8)
                pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
                curve = fv_plot.plot(
                    group["Speed m/s"].to_numpy(float), group["Force N"].to_numpy(float),
                    pen=pen, symbol=point_symbol, symbolSize=5, connect="all", antialias=True,
                )
                if legend_curve is None:
                    legend_curve = curve
            if legend_curve is not None:
                fv_legend.addItem(legend_curve, f"{current:g} A")
        fv_plot.addLine(y=0, pen=self.pg.mkPen("#606060", width=0.8))

        fi_plot = self.map_force_current_plot.addPlot(row=0, col=0)
        self._map_plot_style(fi_plot, self._text("压缩 ← 阻尼力 → 复原", "Compression ← damping force → rebound"), "N", self._text("电流", "Current"), "A")
        fi_plot.setTitle(self._text("F-I 不同速度曲线", "F-I curves by speed"), color="#202020", size="11pt")
        fi_plot.showGrid(x=True, y=True, alpha=0.15)
        fi_legend = fi_plot.addLegend(offset=(10, 10), labelTextSize="9pt")
        fi_speeds = sorted(raw["Speed m/s"].unique())
        fi_colors = {speed: self.pg.intColor(index, hues=max(1, len(fi_speeds))) for index, speed in enumerate(fi_speeds)}
        for index, ((speed, direction), group) in enumerate(raw.groupby(["Speed m/s", "Direction"], sort=True)):
            group = group.sort_values("Current A")
            color = fi_colors[speed]
            pen = self.pg.mkPen(color, width=1.8)
            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
            curve = fi_plot.plot(
                group["Current A"].to_numpy(float), group["Force N"].to_numpy(float),
                pen=pen, symbol=point_symbol, symbolSize=5, connect="all", antialias=True,
            )
            if direction == "Rebound":
                fi_legend.addItem(curve, f"{speed:g} m/s")
        fi_plot.addLine(y=0, pen=self.pg.mkPen("#606060", width=0.8))

    def _map_plot_style(self, plot, left, left_units, bottom, bottom_units):
        self._axis_style(plot, left, left_units)
        plot.setLabel("bottom", bottom, units=bottom_units, **{"font-size": "10pt", "font-weight": "normal"})
        for side in ("left", "bottom"):
            plot.getAxis(side).setPen(self.pg.mkPen("#202020"))
            plot.getAxis(side).setTextPen(self.pg.mkPen("#202020"))

    def export_map(self):
        if self.map_result is None:
            QtWidgets.QMessageBox.information(self.window, self._text("导出", "Export"), self._text("请先完成全电流分析。", "Run full-current analysis first."))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, self._text("导出全电流分析结果", "Export full-current analysis"), "Full_Current_Analysis.xlsx", "Excel (*.xlsx)")
        if path:
            output = export_map_analysis_xlsx(self.map_result, path)
            self.map_status.setText(self._text(f"已导出：{output}", f"Exported: {output}"))
