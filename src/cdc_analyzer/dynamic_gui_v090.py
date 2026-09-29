from __future__ import annotations

from pathlib import Path

import numpy as np
from pandas import ExcelWriter
from PySide6 import QtCore, QtGui, QtWidgets

from .audi_items_20_21 import (
    ImportedMapFile,
    analyze_map_files,
    current_from_filename,
    discover_map_files,
    export_map_analysis_xlsx,
    inspect_map_file,
)
from .audi_test_program import AudiSpecimen, compile_audi_test_report
from .audi_edge_sensitivity import analyze_edge_sensitivity
from .dynamic_analysis import DISP, LOAD, TIME, VELOCITY, load_dynamic_test_data
from .dynamic_gui_v085 import DynamicPagesController as _BaseController


class DynamicPagesController(_BaseController):
    def __init__(self, *args, **kwargs):
        self.map_files: list[ImportedMapFile] = []
        self.map_result = None
        self.audi_edge_result = None
        self.audi_edge_path = None
        self.map_linearity_legend = None
        self.map_spread_legend = None
        self.map_amplify_legend = None
        self.map_fv_legend = None
        self.map_fi_legend = None
        super().__init__(*args, **kwargs)
        self._build_map_page()
        self._build_audi_program_page()
        self._build_audi_edge_page()
        self._v090_language()

    def _build_audi_program_page(self):
        self.audi_program_page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(self.audi_program_page)
        controls = QtWidgets.QHBoxLayout()
        self.audi_program_type_label = QtWidgets.QLabel()
        self.audi_program_type = QtWidgets.QComboBox()
        self.audi_program_type.addItem("", True)
        self.audi_program_type.addItem("", False)
        self.audi_program_type.currentIndexChanged.connect(self.refresh_audi_program)
        self.audi_program_refresh = QtWidgets.QPushButton()
        self.audi_program_refresh.clicked.connect(self.refresh_audi_program)
        self.audi_program_export = QtWidgets.QPushButton()
        self.audi_program_export.clicked.connect(self.export_audi_program)
        controls.addWidget(self.audi_program_type_label)
        controls.addWidget(self.audi_program_type)
        controls.addWidget(self.audi_program_refresh)
        controls.addWidget(self.audi_program_export)
        controls.addStretch(1)
        root.addLayout(controls)
        self.audi_program_note = QtWidgets.QLabel()
        self.audi_program_note.setWordWrap(True)
        root.addWidget(self.audi_program_note)
        self.audi_program_table = self._new_table()
        self.audi_program_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.audi_program_table.cellDoubleClicked.connect(self._open_audi_section)
        root.addWidget(self.audi_program_table, 1)
        self.window.tabs.addTab(self.audi_program_page, "")
        self.refresh_audi_program()

    def refresh_audi_program(self):
        if not hasattr(self, "audi_program_table"):
            return
        records = []
        if self.response_result is not None and self.response_result.settings.get("OEM Profile") == "audi":
            records.append({"section": "18", "evidence": str(self.response_result.source_path)})
        if self.hysteresis_result is not None and self.hysteresis_result.settings.get("OEM Profile") == "audi":
            records.append({"section": "19", "evidence": str(self.hysteresis_result.source_path)})
        if self.map_result is not None:
            evidence = "; ".join(self.map_result.files["File"].astype(str))
            records.extend(({"section": section, "evidence": evidence}) for section in ("20", "21"))
        if self.audi_edge_result is not None and self.audi_edge_path is not None:
            records.append({"section": "16", "evidence": str(self.audi_edge_path)})
        report = compile_audi_test_report(AudiSpecimen(regulated=bool(self.audi_program_type.currentData())), records)
        self.audi_program_report = report
        table = self.audi_program_table
        table.setRowCount(len(report))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels((
            self._text("章节", "Section"), self._text("规范试验", "Standard test"),
            self._text("适用", "Applies"), self._text("分析/证据", "Analysis / evidence"),
        ))
        for row_index, row in enumerate(report.itertuples(index=False)):
            applies = row.Applicable
            scope = self._text("待核实", "Verify") if applies is None else self._text("是", "Yes") if applies else self._text("否", "No")
            analysis = row.Evidence or (self._text("已有相关分析入口", "Related analyzer available") if row.Analyzer != "manual evidence" else self._text("待接入数据或人工证据", "Data or manual evidence needed"))
            for column, value in enumerate((row.Section, row.Test, scope, analysis)):
                table.setItem(row_index, column, QtWidgets.QTableWidgetItem(str(value)))
        table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)

    def _open_audi_section(self, row: int, _column: int):
        section = self.audi_program_report.iloc[row]["Section"]
        if section == "4":
            self.window.tabs.setCurrentWidget(self.window.plot_page)
        elif section == "18":
            self.window.tabs.setCurrentWidget(self.response_page)
        elif section == "19":
            self.window.tabs.setCurrentWidget(self.hysteresis_page)
        elif section in {"20", "21"}:
            self.window.tabs.setCurrentWidget(self.map_page)
            self.map_views.setCurrentIndex(0 if section == "20" else 1)
        elif section == "16":
            self.window.tabs.setCurrentWidget(self.audi_edge_page)

    def _build_audi_edge_page(self):
        self.audi_edge_page = QtWidgets.QWidget()
        root = QtWidgets.QVBoxLayout(self.audi_edge_page)
        controls = QtWidgets.QHBoxLayout()
        self.audi_edge_open = QtWidgets.QPushButton()
        self.audi_edge_open.clicked.connect(self.open_audi_edge_file)
        controls.addWidget(self.audi_edge_open)
        self.audi_edge_sign_label = QtWidgets.QLabel()
        controls.addWidget(self.audi_edge_sign_label)
        self.audi_edge_sign = QtWidgets.QComboBox()
        self.audi_edge_sign.addItem("", -1)
        self.audi_edge_sign.addItem("", 1)
        controls.addWidget(self.audi_edge_sign)
        self.audi_edge_export = QtWidgets.QPushButton()
        self.audi_edge_export.clicked.connect(self.export_audi_edge)
        controls.addWidget(self.audi_edge_export)
        controls.addStretch(1)
        root.addLayout(controls)
        self.audi_edge_status = QtWidgets.QLabel()
        self.audi_edge_status.setWordWrap(True)
        root.addWidget(self.audi_edge_status)
        self.audi_edge_table = self._new_table()
        root.addWidget(self.audi_edge_table)
        self.audi_edge_plot = self.pg.GraphicsLayoutWidget()
        self.audi_edge_plot.setBackground("#ffffff")
        root.addWidget(self.audi_edge_plot, 1)
        self.window.tabs.addTab(self.audi_edge_page, "")

    def open_audi_edge_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.window, self._text("选择第16章五循环原始数据", "Select section 16 five-cycle data"),
            "", "Test data (*.dat *.csv *.xlsx *.xlsm)",
        )
        if not path:
            return
        try:
            dataset = load_dynamic_test_data(path)
            result = analyze_edge_sensitivity(
                dataset.data, compression_displacement_sign=int(self.audi_edge_sign.currentData())
            )
        except (ValueError, OSError) as exc:
            QtWidgets.QMessageBox.warning(self.window, self._text("数据不符合第16章", "Section 16 data rejected"), str(exc))
            return
        self.audi_edge_result = result
        self.audi_edge_path = Path(path)
        self.audi_edge_status.setText(self._text(
            f"已计算 {result.source_rows} 点，采样率 {result.sample_rate_hz:.0f} Hz；试验温度、软电流、预处理、滤波器和项目限值仍须核实。",
            f"Calculated {result.source_rows} samples at {result.sample_rate_hz:.0f} Hz. Verify temperature, soft current, preconditioning, filter and project limit.",
        ))
        table = self.audi_edge_table
        table.setRowCount(len(result.comparison))
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(("Branch", "First cycle N", "Following four mean N", "First minus following N"))
        for i, row in result.comparison.iterrows():
            for j, value in enumerate((row["Branch"], row["First cycle N"], row["Following four mean N"], row["First minus following N"])):
                table.setItem(i, j, QtWidgets.QTableWidgetItem(str(value) if j == 0 else f"{value:.2f}"))
        self.audi_edge_plot.clear()
        plot = self.audi_edge_plot.addPlot(title=self._text("第16章：全部五循环 F-v", "Section 16: all five F-v cycles"))
        plot.setLabel("bottom", self._text("压缩正向速度", "Compression-positive velocity"), units="m/s")
        plot.setLabel("left", self._text("测量力", "Measured force"), units="N")
        data = dataset.data
        t = data[TIME].to_numpy(float)
        v = data[VELOCITY].to_numpy(float) if VELOCITY in data else np.gradient(data[DISP].to_numpy(float), t) / 1000.0
        for cycle in range(5):
            mask = (t >= t[0] + cycle / 16.68) & (t < t[0] + (cycle + 1) / 16.68)
            if mask.any():
                plot.plot(v[mask] * int(self.audi_edge_sign.currentData()), data[LOAD].to_numpy(float)[mask], pen=self.pg.mkPen("#c62828" if cycle == 0 else "#1565c0", width=1.5))
        self.refresh_audi_program()

    def export_audi_edge(self):
        if self.audi_edge_result is None:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, self._text("导出第16章结果", "Export section 16 result"), "AUDI_section_16.xlsx", "Excel (*.xlsx)")
        if path:
            with ExcelWriter(Path(path).with_suffix(".xlsx")) as writer:
                self.audi_edge_result.comparison.to_excel(writer, sheet_name="Comparison", index=False)
                self.audi_edge_result.cycles.to_excel(writer, sheet_name="Five cycles", index=False)

    def export_audi_program(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.window, self._text("导出 AUDI 试验清单", "Export Audi test program"),
            "AUDI_VR-EF-33-2_v2.5_test_program.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        self.refresh_audi_program()
        report = self.audi_program_report.copy()
        report.insert(0, "Standard", "AUDI VR-EF-33-2 v2.5 (2020-07-30)")
        report.to_excel(Path(path).with_suffix(".xlsx"), index=False)

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
        self._map_table_filling = False
        self.map_file_table.itemChanged.connect(self._on_map_check_changed)

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
        if hasattr(self, "audi_program_page"):
            self.window.tabs.setTabText(self.window.tabs.indexOf(self.audi_program_page), self._text("AUDI 试验顺序", "Audi test program"))
            self.audi_program_type_label.setText(self._text("减振器类型", "Damper type"))
            self.audi_program_type.setItemText(0, self._text("可调", "Regulated"))
            self.audi_program_type.setItemText(1, self._text("常规", "Conventional"))
            self.audi_program_refresh.setText(self._text("刷新分析状态", "Refresh analysis"))
            self.audi_program_export.setText(self._text("导出规范顺序清单", "Export ordered program"))
            self.audi_program_note.setText(self._text(
                "依据 AUDI VR-EF-33-2 v2.5 第1章适用范围和第4–22章顺序；按本项目范围排除第5、7、9–12章耐久类试验。条件项目需结合结构和项目要求核实；未录入项目限值时不判定合格。",
                "Audi VR-EF-33-2 v2.5 order, excluding durability sections 5, 7 and 9–12 for this project. Confirm conditional tests against the design and project requirements; no pass/fail without project limits.",
            ))
            self.refresh_audi_program()
        if hasattr(self, "audi_edge_page"):
            self.window.tabs.setTabText(self.window.tabs.indexOf(self.audi_edge_page), self._text("16 边缘敏感性", "16 Edge sensitivity"))
            self.audi_edge_open.setText(self._text("选择五循环数据…", "Select five-cycle data…"))
            self.audi_edge_sign_label.setText(self._text("压缩方向位移", "Compression displacement"))
            self.audi_edge_sign.setItemText(0, self._text("减小", "Decreases"))
            self.audi_edge_sign.setItemText(1, self._text("增大", "Increases"))
            self.audi_edge_export.setText(self._text("导出结果…", "Export result…"))
            if self.audi_edge_result is None:
                self.audi_edge_status.setText(self._text("导入从伸张端静止起步、首次运动为压缩的 5 个完整循环；规范条件由试验记录核实。", "Import five complete cycles starting at rest from extension, moving first in compression. Verify test conditions in the test record."))
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
        self.map_files = []
        self.map_result = None
        self._add_map_paths(paths)
        self.refresh_map_plots()

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
        headers = [self._text("计算", "Include"), self._text("文件", "File"), self._text("格式", "Format"), self._text("电流 A", "Current A"), self._text("速度段", "Speed runs"), self._text("状态", "Status"), self._text("完整路径", "Full path")]
        table = self.map_file_table
        self._map_table_filling = True
        try:
            table.setRowCount(len(self.map_files))
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            for row, item in enumerate(self.map_files):
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
            self._map_table_filling = False

    def _on_map_check_changed(self, item):
        if self._map_table_filling or item.column() != 0:
            return
        if self.map_result is not None:
            self.map_result = None
            self.refresh_map_plots()
            self.map_status.setText(self._text(
                "勾选状态已变化，之前的分析结果已清空，请重新分析。",
                "Selection changed; previous results were cleared. Run analysis again.",
            ))

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
        selected_files = [
            item for row, item in enumerate(self.map_files)
            if self.map_file_table.item(row, 0) is not None
            and self.map_file_table.item(row, 0).checkState() == QtCore.Qt.CheckState.Checked
        ]
        if not selected_files:
            QtWidgets.QMessageBox.information(self.window, self._text("全电流分析", "Full-current analysis"), self._text("请至少勾选一个文件参与计算。", "Select at least one file to include."))
            return
        skipped = len(self.map_files) - len(selected_files)
        cursor_set = False
        try:
            QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.CursorShape.WaitCursor)
            cursor_set = True
            self.map_result = analyze_map_files(
                selected_files,
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
        soft_a = float(self.map_result.settings["Soft Current A"])
        hard_a = float(self.map_result.settings["Hard Current A"])
        self.map_status.setText(self._text(
            f"分析完成：{len(selected_files)} 个文件" + (f"（{skipped} 个未勾选已跳过），" if skipped else "，") + f"{len(self.map_result.run_detail)} 个有效速度段；同工况最多 {repeats} 次重复，取最后一个重复。软/硬电流自动取最软/最硬档 {soft_a:g} A / {hard_a:g} A。",
            f"Analysis complete: {len(selected_files)} file(s)" + (f" ({skipped} unchecked skipped), " if skipped else ", ") + f"{len(self.map_result.run_detail)} valid speed runs; up to {repeats} retained repeats, the last repeat is used. Soft/hard anchors are the softest/hardest current steps {soft_a:g} A / {hard_a:g} A.",
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
        legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt", labelTextColor="#263238", verSpacing=2)
        legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.map_linearity_plot.addItem(legend, row=0, col=1)
        self.map_linearity_legend = legend
        self.map_linearity_plot.ci.layout.setColumnStretchFactor(0, 4)
        self.map_linearity_plot.ci.layout.setColumnStretchFactor(1, 1)
        raw = self.map_result.current_force_linearity
        item20_speeds = sorted(raw["Speed m/s"].unique())
        item20_colors = ("#b71c1c", "#0d47a1", "#2e7d32", "#6a1b9a", "#bf360c", "#006064", "#ad1457", "#4e342e")
        speed_colors = {speed: item20_colors[index % len(item20_colors)] for index, speed in enumerate(item20_speeds)}
        point_symbol = "o" if self.map_show_points.isChecked() else None
        for ((speed, direction), group) in raw.groupby(["Speed m/s", "Direction"], sort=True):
            group = group.sort_values("Current A")
            color = speed_colors[speed]
            pen = self.pg.mkPen(color, width=2)
            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
            curve = linearity.plot(
                group["Current A"].to_numpy(float), group["Normalized Force"].to_numpy(float),
                pen=pen, symbol=point_symbol, symbolSize=6, symbolBrush=color, symbolPen=color,
            )
            if direction == "Rebound":
                legend.addItem(curve, self._text(f"{speed:g} m/s", f"{speed:g} m/s"))
        linearity.addLine(y=0, pen=self.pg.mkPen("#888888", width=0.7))
        soft_current = float(self.map_result.settings["Soft Current A"])
        hard_current = float(self.map_result.settings["Hard Current A"])
        linearity.getAxis("left").setTicks([[(value, f"{int(value * 100)}%") for value in (-1.0, -0.5, 0.0, 0.5, 1.0)]])
        linearity.setYRange(-1.1, 1.1, padding=0)
        band_pen = self._dash_pen("#b0bec5", 1.2, (16, 12))
        linearity.addLine(y=1.0, pen=band_pen)
        linearity.addLine(y=-1.0, pen=band_pen)
        ideal_pen = self._dash_pen("#455a64", 1.8, (16, 12))
        ideal_curve = linearity.plot([soft_current, hard_current], [0.0, 1.0], pen=ideal_pen)
        legend.addItem(ideal_curve, self._text("45°理想线", "45° ideal line"))
        linearity.plot([soft_current, hard_current], [0.0, -1.0], pen=ideal_pen)
        for _sample, label in legend.items:
            legend.layout.setAlignment(label, QtCore.Qt.AlignmentFlag.AlignVCenter)
        legend.setFixedHeight(22 * len(legend.items) + 8)
        self.map_linearity_plot.ci.layout.setAlignment(legend, QtCore.Qt.AlignmentFlag.AlignTop)

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
        spread_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        spread_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.map_spread_plot.addItem(spread_legend, row=0, col=1)
        self.map_spread_legend = spread_legend
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

        amplify = self.map_spread_plot.addPlot(row=0, col=2)
        self._map_plot_style(amplify, self._text("放大倍数", "Amplification"), None, self._text("速度", "Speed"), "m/s")
        amplify.setTitle(self._text("第21项：放大倍数", "Item 21: amplification"), color="#202020", size="11pt")
        amplify.showGrid(x=True, y=True, alpha=0.15)
        amplify.getAxis("bottom").setTicks([[(speed_positions[float(speed)], f"{speed:g}") for speed in speeds]])
        amplify.setXRange(-0.6, max(0.6, len(speeds) - 0.4), padding=0)
        amplify_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        amplify_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.map_spread_plot.addItem(amplify_legend, row=0, col=3)
        self.map_amplify_legend = amplify_legend
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
        self.map_spread_plot.ci.layout.setColumnStretchFactor(0, 3)
        self.map_spread_plot.ci.layout.setColumnStretchFactor(1, 1)
        self.map_spread_plot.ci.layout.setColumnStretchFactor(2, 3)
        self.map_spread_plot.ci.layout.setColumnStretchFactor(3, 1)

        raw = self.map_result.current_force_linearity
        fv_plot = self.map_force_velocity_plot.addPlot(row=0, col=0)
        self._map_plot_style(fv_plot, self._text("压缩 ← 阻尼力 → 复原", "Compression ← damping force → rebound"), "N", self._text("速度", "Speed"), "m/s")
        fv_plot.setTitle(self._text("F-V 全电流曲线", "F-V full-current curves"), color="#202020", size="11pt")
        fv_plot.showGrid(x=True, y=True, alpha=0.15)
        fv_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        fv_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.map_force_velocity_plot.addItem(fv_legend, row=0, col=1)
        self.map_fv_legend = fv_legend
        self.map_force_velocity_plot.ci.layout.setColumnStretchFactor(0, 4)
        self.map_force_velocity_plot.ci.layout.setColumnStretchFactor(1, 1)
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
        fi_legend = self.pg.LegendItem(offset=(0, 0), labelTextSize="9pt")
        fi_legend.setBrush(self.pg.mkBrush(255, 255, 255))
        self.map_force_current_plot.addItem(fi_legend, row=0, col=1)
        self.map_fi_legend = fi_legend
        self.map_force_current_plot.ci.layout.setColumnStretchFactor(0, 4)
        self.map_force_current_plot.ci.layout.setColumnStretchFactor(1, 1)
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

    def _dash_pen(self, color, width=1.5, pattern=(16, 12)):
        pen = QtGui.QPen(QtGui.QColor(color), width)
        # Plot coordinates are scaled by the ViewBox; keep dash width in pixels.
        pen.setCosmetic(True)
        pen.setDashPattern([float(value) for value in pattern])
        return pen

    def export_map(self):
        if self.map_result is None:
            QtWidgets.QMessageBox.information(self.window, self._text("导出", "Export"), self._text("请先完成全电流分析。", "Run full-current analysis first."))
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self.window, self._text("导出全电流分析结果", "Export full-current analysis"), "Full_Current_Analysis.xlsx", "Excel (*.xlsx)")
        if path:
            output = export_map_analysis_xlsx(self.map_result, path)
            self.map_status.setText(self._text(f"已导出：{output}", f"Exported: {output}"))

