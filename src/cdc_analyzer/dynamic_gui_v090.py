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
        self.map_add_button = QtWidgets.QPushButton()
        self.map_folder_button = QtWidgets.QPushButton()
        self.map_remove_button = QtWidgets.QPushButton()
        self.map_analyze_button = QtWidgets.QPushButton()
        self.map_export_button = QtWidgets.QPushButton()
        self.map_add_button.clicked.connect(self.open_map_files)
        self.map_folder_button.clicked.connect(self.open_map_folder)
        self.map_remove_button.clicked.connect(self.remove_selected_map_files)
        self.map_analyze_button.clicked.connect(self.analyze_map)
        self.map_export_button.clicked.connect(self.export_map)
        for widget in (self.map_add_button, self.map_folder_button, self.map_remove_button, self.map_analyze_button, self.map_export_button):
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
        self.map_file_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked | QtWidgets.QAbstractItemView.EditTrigger.EditKeyPressed)
        self.map_file_table.setMaximumHeight(210)
        root.addWidget(self.map_file_table)

        self.map_views = QtWidgets.QTabWidget()
        self.map_linearity_plot = self.pg.GraphicsLayoutWidget()
        self.map_spread_plot = self.pg.GraphicsLayoutWidget()
        self.map_linearity_table = self._new_table()
        self.map_spread_table = self._new_table()
        self.map_run_table = self._new_table()
        self.map_views.addTab(self.map_linearity_plot, "")
        self.map_views.addTab(self.map_spread_plot, "")
        self.map_views.addTab(self.map_linearity_table, "")
        self.map_views.addTab(self.map_spread_table, "")
        self.map_views.addTab(self.map_run_table, "")
        root.addWidget(self.map_views, 1)
        self.window.tabs.addTab(self.map_page, "")
        self._refresh_map_file_table()

    def _v090_language(self):
        if not hasattr(self, "map_page"):
            return
        self.map_add_button.setText(self._text("添加 PVP / DCTW 文件…", "Add PVP / DCTW files…"))
        self.map_folder_button.setText(self._text("递归扫描文件夹…", "Scan folder recursively…"))
        self.map_remove_button.setText(self._text("移除所选数据", "Remove selected data"))
        self.map_analyze_button.setText(self._text("分析第20/21项", "Analyze items 20/21"))
        self.map_export_button.setText(self._text("导出 Excel…", "Export Excel…"))
        self.map_views.setTabText(0, self._text("20 电流—力线性", "20 Current–force linearity"))
        self.map_views.setTabText(1, self._text("21 力值范围与放大倍数", "21 Spread and amplification"))
        self.map_views.setTabText(2, self._text("20 结果数据", "20 Results"))
        self.map_views.setTabText(3, self._text("21 结果数据", "21 Results"))
        self.map_views.setTabText(4, self._text("工况明细", "Run Detail"))
        index = self.window.tabs.indexOf(self.map_page)
        if index >= 0:
            self.window.tabs.setTabText(index, self._text("第20/21项", "Items 20/21"))
        if not self.map_files:
            self.map_status.setText(self._text(
                "加载不同电流的 MTS .PVP 或 CTW .dctw 文件；可多选或递归扫描子文件夹。移除只影响本次分析，不删除原文件。",
                "Load MTS .PVP or CTW .dctw files from different currents. Removal affects this analysis only and never deletes source files.",
            ))

    def apply_language(self, language):
        super().apply_language(language)
        self._v090_language()

    def open_map_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self.window, self._text("添加第20/21项试验数据", "Add item 20/21 test data"), "",
            self._text("阻尼器 MAP 数据 (*.pvp *.PVP *.dctw *.DCTW);;所有文件 (*)", "Damper MAP data (*.pvp *.PVP *.dctw *.DCTW);;All files (*)"),
        )
        if paths:
            self._add_map_paths([Path(path) for path in paths])

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
                    try:
                        current = current_from_filename(path)
                    except ValueError:
                        current = np.nan
                    probe = inspect_map_file(path, 0.0 if not np.isfinite(current) else current)
                    probe.current_a = current
                    if not np.isfinite(current):
                        probe.status = self._text("请填写电流", "Enter current")
                    self.map_files.append(probe)
                    existing.add(str(path.resolve()).casefold())
                except Exception as exc:
                    errors.append(f"{path.name}: {exc}")
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        self.map_result = None
        self._refresh_map_file_table()
        self.map_status.setText(self._text(
            f"已加载 {len(self.map_files)} 个文件；双击“电流 A”可修改。" + (f" 失败：{'；'.join(errors)}" if errors else ""),
            f"Loaded {len(self.map_files)} file(s); double-click Current A to edit." + (f" Errors: {'; '.join(errors)}" if errors else ""),
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
                if column != 2:
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

    def _sync_map_currents(self):
        for row, item in enumerate(self.map_files):
            text = self.map_file_table.item(row, 2).text().strip().replace(",", ".")
            try:
                value = float(text)
            except ValueError as exc:
                raise ValueError(self._text(f"第 {row + 1} 行电流无效。", f"Invalid current in row {row + 1}.")) from exc
            if not np.isfinite(value) or value < 0:
                raise ValueError(self._text(f"第 {row + 1} 行电流必须为非负有限值。", f"Current in row {row + 1} must be finite and non-negative."))
            item.current_a = value

    def analyze_map(self):
        if not self.map_files:
            QtWidgets.QMessageBox.information(self.window, self._text("第20/21项", "Items 20/21"), self._text("请先添加 PVP 或 DCTW 文件。", "Add PVP or DCTW files first."))
            return
        cursor_set = False
        try:
            self._sync_map_currents()
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            cursor_set = True
            self.map_result = analyze_map_files(self.map_files)
        except Exception as exc:
            QtWidgets.QMessageBox.critical(self.window, self._text("分析错误", "Analysis error"), str(exc))
            return
        finally:
            if cursor_set:
                QtWidgets.QApplication.restoreOverrideCursor()
        self._fill_table(self.map_linearity_table, self.map_result.current_force_linearity)
        self._fill_table(self.map_spread_table, self.map_result.spread_amplification)
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
        if self.map_result is None:
            return
        colors = ["#1565c0", "#c62828", "#00897b", "#ef6c00", "#6a1b9a", "#6d4c41", "#37474f", "#ad1457"]
        linearity = self.map_linearity_plot.addPlot(row=0, col=0)
        self._axis_style(linearity, self._text("归一化阻尼力", "Normalized damping force"))
        linearity.setLabel("bottom", self._text("电流", "Current"), units="A", **{"font-size": "10pt"})
        linearity.showGrid(x=True, y=True, alpha=0.15)
        legend = linearity.addLegend(offset=(10, 10), labelTextSize="9pt")
        for index, ((speed, direction), group) in enumerate(self.map_result.current_force_linearity.groupby(["Speed m/s", "Direction"], sort=True)):
            group = group.sort_values("Current A")
            pen = self.pg.mkPen(colors[index % len(colors)], width=2)
            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
            curve = linearity.plot(group["Current A"].to_numpy(float), group["Normalized Force"].to_numpy(float), pen=pen, symbol="o", symbolSize=6)
            legend.addItem(curve, f"{speed:g} m/s {self._localized_direction(direction)}")
        linearity.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))

        spread_data = self.map_result.spread_amplification
        spread = self.map_spread_plot.addPlot(row=0, col=0)
        self._axis_style(spread, self._text("阻尼力范围", "Damping force spread"), "N")
        spread.setLabel("bottom", self._text("速度", "Speed"), units="m/s", **{"font-size": "10pt"})
        spread.showGrid(x=True, y=True, alpha=0.15)
        directions = [direction for direction in ("Rebound", "Compression") if direction in set(spread_data["Direction"])]
        width = 0.008
        for index, direction in enumerate(directions):
            group = spread_data[spread_data["Direction"] == direction].sort_values("Speed m/s")
            x = group["Speed m/s"].to_numpy(float) + (index - (len(directions) - 1) / 2) * width
            bars = self.pg.BarGraphItem(x=x, height=group["Damping Force Spread N"].to_numpy(float), width=width * 0.86, brush=self.pg.mkBrush(colors[index]), pen=self.pg.mkPen(colors[index]))
            spread.addItem(bars)
        spread.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))

        amplification = self.map_spread_plot.addPlot(row=1, col=0)
        self._axis_style(amplification, self._text("放大倍数", "Amplification"))
        amplification.setLabel("bottom", self._text("速度", "Speed"), units="m/s", **{"font-size": "10pt"})
        amplification.showGrid(x=True, y=True, alpha=0.15)
        legend2 = amplification.addLegend(offset=(10, 10), labelTextSize="9pt")
        for index, direction in enumerate(directions):
            group = spread_data[spread_data["Direction"] == direction].sort_values("Speed m/s")
            curve = amplification.plot(group["Speed m/s"].to_numpy(float), group["Amplification"].to_numpy(float), pen=self.pg.mkPen(colors[index], width=2), symbol="o", symbolSize=6)
            legend2.addItem(curve, self._localized_direction(direction))

    def export_map(self):
        if self.map_result is None:
            QtWidgets.QMessageBox.information(self.window, self._text("导出", "Export"), self._text("请先完成第20/21项分析。", "Analyze items 20/21 first."))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, self._text("导出第20/21项结果", "Export item 20/21 results"), "Audi_Items_20_21.xlsx", "Excel (*.xlsx)")
        if path:
            output = export_map_analysis_xlsx(self.map_result, path)
            self.map_status.setText(self._text(f"已导出：{output}", f"Exported: {output}"))
