from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from .audi_items_20_21 import (
    ImportedMapFile,
    analyze_map_files,
    current_from_filename,
    discover_map_files,
    export_map_analysis_xlsx,
    inspect_map_file,
)
from .dynamic_gui_v091 import DynamicPagesController as _BaseController


class DynamicPagesController(_BaseController):
    def __init__(self, *args, **kwargs):
        self.damper_files: list[ImportedMapFile] = []
        self.damper_result = None
        self.damper_linearity_legend = None
        self.damper_spread_legend = None
        self.damper_amplify_legend = None
        self.damper_fv_legend = None
        self.damper_fi_legend = None
        super().__init__(*args, **kwargs)
        self._build_damper_page()
        self._v092_language()

    def _build_damper_page(self):
        self.damper_page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(self.damper_page)
        controls = QtWidgets.QHBoxLayout()
        self.damper_file_button = QtWidgets.QPushButton()
        self.damper_folder_button = QtWidgets.QPushButton()
        self.damper_remove_button = QtWidgets.QPushButton()
        self.damper_profile_label = QtWidgets.QLabel()
        self.damper_profile_combo = QtWidgets.QComboBox()
        self.damper_profile_combo.addItem("AUDI", "AUDI")
        self.damper_profile_combo.addItem("BMW", "BMW")
        self.damper_analyze_button = QtWidgets.QPushButton()
        self.damper_export_button = QtWidgets.QPushButton()
        self.damper_soft_label = QtWidgets.QLabel()
        self.damper_hard_label = QtWidgets.QLabel()
        self.damper_show_points = QtWidgets.QCheckBox()
        self.damper_soft_current = QtWidgets.QDoubleSpinBox()
        self.damper_hard_current = QtWidgets.QDoubleSpinBox()
        for spin in (self.damper_soft_current, self.damper_hard_current):
            spin.setRange(0.0, 20.0)
            spin.setDecimals(3)
            spin.setSingleStep(0.1)
            spin.setSuffix(" A")
        self.damper_soft_current.setValue(0.3)
        self.damper_hard_current.setValue(1.6)
        self.damper_show_points.setChecked(True)
        self.damper_file_button.clicked.connect(self.open_damper_files)
        self.damper_folder_button.clicked.connect(self.open_damper_folder)
        self.damper_remove_button.clicked.connect(self.remove_selected_damper_files)
        self.damper_analyze_button.clicked.connect(self.analyze_damper)
        self.damper_export_button.clicked.connect(self.export_damper)
        self.damper_show_points.toggled.connect(self.refresh_damper_plots)
        for widget in (self.damper_file_button, self.damper_folder_button, self.damper_remove_button, self.damper_profile_label, self.damper_profile_combo, self.damper_soft_label, self.damper_soft_current, self.damper_hard_label, self.damper_hard_current, self.damper_show_points, self.damper_analyze_button, self.damper_export_button):
            controls.addWidget(widget)
        controls.addStretch(1)
        root.addLayout(controls)

        self.damper_status = QtWidgets.QLabel()
        self.damper_status.setWordWrap(True)
        self.damper_status.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.damper_status)

        self.damper_file_table = self._new_table()
        self.damper_file_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.damper_file_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.damper_file_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.damper_file_table.setMaximumHeight(210)
        root.addWidget(self.damper_file_table)
        self._damper_table_filling = False
        self.damper_file_table.itemChanged.connect(self._on_damper_check_changed)

        self.damper_views = QtWidgets.QTabWidget()
        self.damper_linearity_plot = self.pg.GraphicsLayoutWidget()
        self.damper_spread_plot = self.pg.GraphicsLayoutWidget()
        self.damper_force_velocity_plot = self.pg.GraphicsLayoutWidget()
        self.damper_force_current_plot = self.pg.GraphicsLayoutWidget()
        for plot_widget in (self.damper_linearity_plot, self.damper_spread_plot, self.damper_force_velocity_plot, self.damper_force_current_plot):
            plot_widget.setBackground("#ffffff")
        self.damper_force_velocity_table = self._new_table()
        self.damper_linearity_table = self._new_table()
        self.damper_spread_table = self._new_table()
        self.damper_run_table = self._new_table()
        self.damper_views.addTab(self.damper_linearity_plot, "")
        self.damper_views.addTab(self.damper_spread_plot, "")
        self.damper_views.addTab(self.damper_force_velocity_plot, "")
        self.damper_views.addTab(self.damper_force_current_plot, "")
        self.damper_views.addTab(self.damper_force_velocity_table, "")
        self.damper_views.addTab(self.damper_linearity_table, "")
        self.damper_views.addTab(self.damper_spread_table, "")
        self.damper_views.addTab(self.damper_run_table, "")
        root.addWidget(self.damper_views, 1)
        self.window.tabs.addTab(self.damper_page, "")
        self._refresh_damper_file_table()

    def _v092_language(self):
        if not hasattr(self, "damper_page"):
            return
        self.damper_file_button.setText(self._text("添加文件…", "Add files…"))
        self.damper_folder_button.setText(self._text("添加数据文件夹…", "Add data folder…"))
        self.damper_remove_button.setText(self._text("移除所选数据", "Remove selected data"))
        self.damper_profile_label.setText(self._text("规范", "Profile"))
        self.damper_soft_label.setText(self._text("软电流", "Soft current"))
        self.damper_hard_label.setText(self._text("硬电流", "Hard current"))
        self.damper_show_points.setText(self._text("显示数据点", "Show data points"))
        self.damper_analyze_button.setText(self._text("阻尼力分析", "Damping-force analysis"))
        self.damper_export_button.setText(self._text("导出 Excel…", "Export Excel…"))
        self.damper_views.setTabText(0, self._text("20 电流—力线性", "20 Current–force linearity"))
        self.damper_views.setTabText(1, self._text("21 力值范围与放大倍数", "21 Spread and amplification"))
        self.damper_views.setTabText(2, self._text("F-V 图", "F-V plot"))
        self.damper_views.setTabText(3, self._text("F-I 图", "F-I plot"))
        self.damper_views.setTabText(4, self._text("F-V 数据", "F-V data"))
        self.damper_views.setTabText(5, self._text("20 结果数据", "20 Results"))
        self.damper_views.setTabText(6, self._text("21 结果数据", "21 Results"))
        self.damper_views.setTabText(7, self._text("工况明细", "Run Detail"))
        index = self.window.tabs.indexOf(self.damper_page)
        if index >= 0:
            self.window.tabs.setTabText(index, self._text("阻尼力测试分析", "Damping-force analysis"))
        if not self.damper_files:
            self.damper_status.setText(self._text(
                "加载 MTS .PVP 或 CTW .dctw 阻尼力数据文件；电流 A 必须从文件名自动识别。规范可选 AUDI 或 BMW；软电流默认 0.3 A，硬电流默认 1.6 A。",
                "Load MTS .PVP or CTW .dctw damping-force data files. Current A is read from each filename. Profile: AUDI or BMW; soft 0.3 A and hard 1.6 A by default.",
            ))

    def apply_language(self, language):
        super().apply_language(language)
        self._v092_language()

    def open_damper_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self.window, self._text("选择数据文件夹", "Select data folder"), "")
        if not folder:
            return
        paths = discover_map_files(folder)
        if not paths:
            QtWidgets.QMessageBox.information(self.window, self._text("未找到数据", "No data found"), self._text("文件夹及子文件夹中没有 .PVP 或 .dctw 文件。", "No .PVP or .dctw files were found."))
            return
        self.damper_files = []
        self.damper_result = None
        self._add_damper_paths(paths)
        self.refresh_damper_plots()

    def open_damper_files(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self.window,
            self._text("选择阻尼力数据文件", "Select damping-force data files"),
            "",
            self._text("阻尼力数据 (*.pvp *.dctw);;所有文件 (*)", "Damping-force data (*.pvp *.dctw);;All files (*)"),
        )
        if not files:
            return
        selected = [path for path in files if Path(path).suffix.lower() in {".pvp", ".dctw"}]
        if not selected:
            QtWidgets.QMessageBox.information(self.window, self._text("未找到数据", "No data found"), self._text("所选文件中没有 .PVP 或 .dctw 文件。", "No .PVP or .dctw files were selected."))
            return
        self.damper_result = None
        self._add_damper_paths(selected)

    def _add_damper_paths(self, paths):
        existing = {str(item.path.resolve()).casefold() for item in self.damper_files}
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
                    self.damper_files.append(probe)
                    existing.add(str(path.resolve()).casefold())
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.damper_result = None
        self._refresh_damper_file_table()
        self.damper_status.setText(self._text(
            f"已加载 {len(self.damper_files)} 个文件；电流 A 已从文件名自动识别。" + (f" 未加载：{'；'.join(errors)}" if errors else ""),
            f"Loaded {len(self.damper_files)} file(s); Current A was read from filenames." + (f" Not loaded: {'; '.join(errors)}" if errors else ""),
        ))

    def _refresh_damper_file_table(self):
        headers = [self._text("计算", "Include"), self._text("文件", "File"), self._text("格式", "Format"), self._text("电流 A", "Current A"), self._text("速度段", "Speed runs"), self._text("状态", "Status"), self._text("完整路径", "Full path")]
        table = self.damper_file_table
        self._damper_table_filling = True
        try:
            table.setRowCount(len(self.damper_files))
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            for row, item in enumerate(self.damper_files):
                check = QtWidgets.QTableWidgetItem()
                check.setFlags(QtCore.Qt.ItemFlag.ItemIsUserCheckable | QtCore.Qt.ItemFlag.ItemIsEnabled)
                check.setCheckState(QtCore.Qt.CheckState.Checked)
                table.setItem(row, 0, check)
                values = [item.path.name, item.format, "" if not np.isfinite(item.current_a) else f"{item.current_a:g}", ", ".join(f"{s:g}" for s in item.speeds_mps), item.status, str(item.path)]
                for column, value in enumerate(values):
                    cell = QtWidgets.QTableWidgetItem(value)
                    cell.setFlags(cell.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
                    table.setItem(row, column + 1, cell)
            table.resizeColumnsToContents()
        finally:
            self._damper_table_filling = False

    def _on_damper_check_changed(self, item):
        if self._damper_table_filling or item.column() != 0:
            return
        if self.damper_result is not None:
            self.damper_result = None
            self.refresh_damper_plots()
            self.damper_status.setText(self._text(
                "勾选状态已变化，之前的分析结果已清空，请重新分析。",
                "Selection changed; previous results were cleared. Run analysis again.",
            ))

    def remove_selected_damper_files(self):
        rows = sorted({index.row() for index in self.damper_file_table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            del self.damper_files[row]
        self.damper_result = None
        self._refresh_damper_file_table()
        self.damper_status.setText(self._text(f"已保留 {len(self.damper_files)} 个文件。原始文件未删除。", f"{len(self.damper_files)} file(s) retained. Source files were not deleted."))

    def analyze_damper(self):
        if not self.damper_files:
            QtWidgets.QMessageBox.information(self.window, self._text("阻尼力测试分析", "Damping-force analysis"), self._text("请先添加 PVP 或 DCTW 文件。", "Add PVP or DCTW files first."))
            return
        selected_files = [
            item for row, item in enumerate(self.damper_files)
            if self.damper_file_table.item(row, 0) is not None
            and self.damper_file_table.item(row, 0).checkState() == QtCore.Qt.CheckState.Checked
        ]
        if not selected_files:
            QtWidgets.QMessageBox.information(self.window, self._text("阻尼力测试分析", "Damping-force analysis"), self._text("请至少勾选一个文件参与计算。", "Select at least one file to include."))
            return
        skipped = len(self.damper_files) - len(selected_files)
        profile = str(self.damper_profile_combo.currentData())
        cursor_set = False
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            cursor_set = True
            self.damper_result = analyze_map_files(
                selected_files,
                soft_current_a=self.damper_soft_current.value(),
                hard_current_a=self.damper_hard_current.value(),
                profile=profile,
            )
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self.window, self._text("分析错误", "Analysis error"), str(exc))
            return
        finally:
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
        self._fill_table(self.damper_linearity_table, self.damper_result.current_force_linearity)
        self._fill_table(self.damper_spread_table, self.damper_result.spread_amplification)
        self._fill_table(self.damper_force_velocity_table, self.damper_result.force_velocity_table)
        self._fill_table(self.damper_run_table, self.damper_result.run_detail)
        self.refresh_damper_plots()
        repeats = int(self.damper_result.current_force_linearity["Repeat Count"].max())
        soft_a = float(self.damper_result.settings["Soft Current A"])
        hard_a = float(self.damper_result.settings["Hard Current A"])
        standard = str(self.damper_result.settings["Standard"])
        self.damper_status.setText(self._text(
            f"分析完成：{len(selected_files)} 个文件" + (f"（{skipped} 个未勾选已跳过），" if skipped else "，") + f"{len(self.damper_result.run_detail)} 个有效速度段；同工况最多 {repeats} 次重复，取最后一个重复。规范：{standard}。软/硬电流自动取最软/最硬档 {soft_a:g} A / {hard_a:g} A。",
            f"Analysis complete: {len(selected_files)} file(s)" + (f" ({skipped} unchecked skipped), " if skipped else ", ") + f"{len(self.damper_result.run_detail)} valid speed runs; up to {repeats} retained repeats, the last repeat is used. Profile: {standard}. Soft/hard anchors are the softest/hardest current steps {soft_a:g} A / {hard_a:g} A.",
        ))

    def refresh_damper_plots(self):
        self.damper_linearity_plot.clear()
        self.damper_spread_plot.clear()
        self.damper_force_velocity_plot.clear()
        self.damper_force_current_plot.clear()
        for widget in (self.damper_linearity_plot, self.damper_spread_plot, self.damper_force_velocity_plot, self.damper_force_current_plot):
            widget.setBackground("#ffffff")
        if self.damper_result is None:
            return
        colors = ["#1565c0", "#c62828", "#00897b", "#ef6c00", "#6a1b9a", "#6d4c41", "#37474f", "#ad1457"]
        linearity = self.damper_linearity_plot.addPlot(row=0, col=0)
        self._damper_plot_style(linearity, self._text("归一化阻尼力差", "Normalized damping-force difference"), None, self._text("电流", "Current"), "A")
        linearity.setTitle(self._text("第20项：电流—阻尼力线性", "Item 20: current–force linearity"), color="#202020", size="11pt")
        linearity.showGrid(x=True, y=True, alpha=0.15)
        legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.damper_linearity_plot.addItem(legend, row=0, col=1)
        self.damper_linearity_legend = legend
        self.damper_linearity_plot.ci.layout.setColumnStretchFactor(0, 4)
        self.damper_linearity_plot.ci.layout.setColumnStretchFactor(1, 1)
        raw = self.damper_result.current_force_linearity
        item20_speeds = sorted(raw["Speed m/s"].unique())
        speed_colors = {speed: self.pg.intColor(index, hues=max(1, len(item20_speeds))) for index, speed in enumerate(item20_speeds)}
        for ((speed, direction), group) in raw.groupby(["Speed m/s", "Direction"], sort=True):
            group = group.sort_values("Current A")
            color = speed_colors[speed]
            pen = self.pg.mkPen(color, width=2)
            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
            curve = linearity.plot(
                group["Current A"].to_numpy(float), group["Normalized Force"].to_numpy(float),
                pen=pen, symbol="o", symbolSize=6,
            )
            if direction == "Rebound":
                legend.addItem(curve, self._text(f"{speed:g} m/s", f"{speed:g} m/s"))
        linearity.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))
        soft_current = float(self.damper_result.settings["Soft Current A"])
        hard_current = float(self.damper_result.settings["Hard Current A"])
        linearity.getAxis("left").setTicks([[(value, f"{int(value * 100)}%") for value in (-1.0, -0.5, 0.0, 0.5, 1.0)]])
        linearity.setYRange(-1.1, 1.1, padding=0)
        band_pen = self._dash_pen("#b0bec5", 1.2, (16, 12))
        linearity.addLine(y=1.0, pen=band_pen)
        linearity.addLine(y=-1.0, pen=band_pen)
        ideal_pen = self._dash_pen("#1565c0", 1.8, (16, 12))
        ideal_curve = linearity.plot([soft_current, hard_current], [0.0, 1.0], pen=ideal_pen)
        legend.addItem(ideal_curve, self._text("45°理想线", "45° ideal line"))
        linearity.plot([soft_current, hard_current], [0.0, -1.0], pen=ideal_pen)

        spread_data = self.damper_result.spread_amplification
        directions = [direction for direction in ("Rebound", "Compression") if direction in set(spread_data["Direction"])]
        speeds = np.sort(spread_data["Speed m/s"].unique().astype(float))
        speed_positions = {float(speed): float(index) for index, speed in enumerate(speeds)}
        bar_colors = {"Rebound": "#f2aa00", "Compression": "#87a9d3"}
        line_colors = {"Rebound": "#d32f2f", "Compression": "#1565c0"}

        spread = self.damper_spread_plot.addPlot(row=0, col=0)
        self._damper_plot_style(spread, self._text("压缩 ← 阻尼力范围 → 复原", "Compression ← damping-force spread → rebound"), "N", self._text("速度", "Speed"), "m/s")
        spread.setTitle(self._text("第21项：阻尼力范围", "Item 21: damping-force spread"), color="#202020", size="11pt")
        spread.showGrid(x=True, y=True, alpha=0.15)
        spread.getAxis("bottom").setTicks([[(speed_positions[float(speed)], f"{speed:g}") for speed in speeds]])
        spread.setXRange(-0.6, max(0.6, len(speeds) - 0.4), padding=0)
        width = 0.55
        spread_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        spread_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.damper_spread_plot.addItem(spread_legend, row=0, col=2)
        self.damper_spread_legend = spread_legend
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

        amplify = self.damper_spread_plot.addPlot(row=0, col=1)
        self._damper_plot_style(amplify, self._text("放大倍数", "Amplification"), None, self._text("速度", "Speed"), "m/s")
        amplify.setTitle(self._text("第21项：放大倍数", "Item 21: amplification"), color="#202020", size="11pt")
        amplify.showGrid(x=True, y=True, alpha=0.15)
        amplify.getAxis("bottom").setTicks([[(speed_positions[float(speed)], f"{speed:g}") for speed in speeds]])
        amplify.setXRange(-0.6, max(0.6, len(speeds) - 0.4), padding=0)
        amplify_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        amplify_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.damper_spread_plot.addItem(amplify_legend, row=0, col=3)
        self.damper_amplify_legend = amplify_legend
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
        self.damper_spread_plot.ci.layout.setColumnStretchFactor(0, 3)
        self.damper_spread_plot.ci.layout.setColumnStretchFactor(1, 3)
        self.damper_spread_plot.ci.layout.setColumnStretchFactor(2, 1)
        self.damper_spread_plot.ci.layout.setColumnStretchFactor(3, 1)

        raw = self.damper_result.current_force_linearity
        fv_plot = self.damper_force_velocity_plot.addPlot(row=0, col=0)
        self._damper_plot_style(fv_plot, self._text("压缩 ← 阻尼力 → 复原", "Compression ← damping force → rebound"), "N", self._text("速度", "Speed"), "m/s")
        fv_plot.setTitle(self._text("F-V 全电流曲线", "F-V full-current curves"), color="#202020", size="11pt")
        fv_plot.showGrid(x=True, y=True, alpha=0.15)
        fv_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        fv_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.damper_force_velocity_plot.addItem(fv_legend, row=0, col=1)
        self.damper_fv_legend = fv_legend
        self.damper_force_velocity_plot.ci.layout.setColumnStretchFactor(0, 4)
        self.damper_force_velocity_plot.ci.layout.setColumnStretchFactor(1, 1)
        current_groups = list(raw.groupby("Current A", sort=True))
        point_symbol = "o" if self.damper_show_points.isChecked() else None
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

        fi_plot = self.damper_force_current_plot.addPlot(row=0, col=0)
        self._damper_plot_style(fi_plot, self._text("压缩 ← 阻尼力 → 复原", "Compression ← damping force → rebound"), "N", self._text("电流", "Current"), "A")
        fi_plot.setTitle(self._text("F-I 不同速度曲线", "F-I curves by speed"), color="#202020", size="11pt")
        fi_plot.showGrid(x=True, y=True, alpha=0.15)
        fi_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        fi_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.damper_force_current_plot.addItem(fi_legend, row=0, col=1)
        self.damper_fi_legend = fi_legend
        self.damper_force_current_plot.ci.layout.setColumnStretchFactor(0, 4)
        self.damper_force_current_plot.ci.layout.setColumnStretchFactor(1, 1)
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

    def _damper_plot_style(self, plot, left, left_units, bottom, bottom_units):
        self._axis_style(plot, left, left_units)
        plot.setLabel("bottom", bottom, units=bottom_units, **{"font-size": "10pt", "font-weight": "normal"})
        for side in ("left", "bottom"):
            plot.getAxis(side).setPen(self.pg.mkPen("#202020"))
            plot.getAxis(side).setTextPen(self.pg.mkPen("#202020"))

    def _dash_pen(self, color, width=1.5, pattern=(16, 12)):
        pen = QtGui.QPen(QtGui.QColor(color), width)
        pen.setDashPattern([float(value) for value in pattern])
        return pen

    def export_damper(self):
        if self.damper_result is None:
            QtWidgets.QMessageBox.information(self.window, self._text("导出", "Export"), self._text("请先完成阻尼力测试分析。", "Run damping-force analysis first."))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, self._text("导出阻尼力测试分析结果", "Export damping-force analysis"), "Damping_Force_Analysis.xlsx", "Excel (*.xlsx)")
        if path:
            output = export_map_analysis_xlsx(self.damper_result, path)
            self.damper_status.setText(self._text(f"已导出：{output}", f"Exported: {output}"))
