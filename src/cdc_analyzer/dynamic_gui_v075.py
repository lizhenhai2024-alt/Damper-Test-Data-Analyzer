from __future__ import annotations

import pandas as pd

from . import dynamic_gui_v074 as _v074_module
from .dynamic_gui_v074 import DynamicPagesController as _V074DynamicPagesController
from .response_v075 import analyze_response_time_v075

# The V0.7.4 controller resolves this symbol from its own module globals.
# Redirect it once so the inherited analyze_response() uses V0.7.5 logic.
_v074_module.analyze_response_time_v074 = analyze_response_time_v075


class DynamicPagesController(_V074DynamicPagesController):
    """V0.7.5 dynamic pages.

    Response plots and response results use separate sub-tabs so the three
    synchronized plots can consume the full available page height.
    """

    RESPONSE_HEADERS_ZH = {
        "Event ID": "事件编号",
        "Detected Event ID": "原始事件编号",
        "OEM": "规范",
        "Stage": "切换阶段",
        "Current Transition": "电流切换",
        "Current Start A": "起始电流 / A",
        "Current End A": "终止电流 / A",
        "Current Delta A": "电流变化 / A",
        "Trigger Fraction": "触发比例",
        "Trigger Current A": "I₁₀% / A",
        "Current 100% A": "I₁₀₀% / A",
        "t0 s": "t₀ / s",
        "Displacement at t0 mm": "t0位移 / mm",
        "Velocity at t0 m/s": "t0速度 / m/s",
        "Target Velocity m/s": "目标速度 / m/s",
        "Target Speed Error %": "速度误差 / %",
        "Direction": "方向",
        "Force Change": "载荷变化",
        "Response Type": "响应类型",
        "Force Separation Limit N": "稳态力差门槛 / N",
        "Force Noise Before N": "前稳态噪声 / N",
        "Force Noise After N": "后稳态噪声 / N",
        "Force Dip N": "阻尼力跌落 / N",
        "Force Minimum N": "阻尼力最小值 / N",
        "Dip Delay ms": "跌落延迟 / ms",
        "Time to Force Minimum ms": "到最小值时间 / ms",
        "Force Recovery Time ms": "恢复时间 / ms",
        "Force Dip Area N s": "跌落面积 / N·s",
        "Current Minimum A": "电流最小值 / A",
        "Current Undershoot A": "电流下冲 / A",
        "Current Undershoot %": "电流下冲率 / %",
        "Current Settling Time ms": "电流稳定时间 / ms",
        "F0 N": "F0 / N",
        "F1 N": "F₁% / N",
        "F63 N": "F₆₃% / N",
        "F90 N": "F₉₀% / N",
        "F100 N": "F₁₀₀% / N",
        "Delta F N": "ΔF / N",
        "Dead Time t1 ms": "t₁% / ms",
        "Switch Time t63 ms": "t₆₃% / ms",
        "Switch Time t90 ms": "t₉₀% / ms",
        "Gradient 63 N/s": "梯度63 / N/s",
        "Gradient 90 N/s": "梯度90 / N/s",
        "Sample Rate Hz": "采样率 / Hz",
        "Status": "状态",
        "Issues": "数据提示",
    }

    def _build_response_page(self):
        super()._build_response_page()

        root = self.response_page.layout()
        splitter = self.response_plot_area.parentWidget()
        if splitter is not None:
            root.removeWidget(splitter)
            self.response_plot_area.setParent(None)
            self.response_table.setParent(None)
            splitter.setParent(None)

        self.response_view_tabs = self.QtWidgets.QTabWidget()
        self.response_view_tabs.setDocumentMode(False)

        self.response_graph_page = self.QtWidgets.QWidget()
        graph_layout = self.QtWidgets.QVBoxLayout(self.response_graph_page)
        graph_layout.setContentsMargins(0, 0, 0, 0)
        graph_layout.setSpacing(4)
        graph_layout.addWidget(self.response_plot_area, 1)

        self.response_data_page = self.QtWidgets.QWidget()
        data_layout = self.QtWidgets.QVBoxLayout(self.response_data_page)
        data_layout.setContentsMargins(0, 0, 0, 0)
        data_layout.setSpacing(6)

        data_tools = self.QtWidgets.QHBoxLayout()
        self.response_data_hint = self.QtWidgets.QLabel()
        self.response_data_hint.setWordWrap(True)
        data_tools.addWidget(self.response_data_hint, 1)
        self.response_show_plot_button = self.QtWidgets.QPushButton()
        self.response_show_plot_button.clicked.connect(self._show_selected_response_plot)
        data_tools.addWidget(self.response_show_plot_button)
        data_layout.addLayout(data_tools)
        data_layout.addWidget(self.response_table, 1)

        self.response_view_tabs.addTab(self.response_graph_page, "")
        self.response_view_tabs.addTab(self.response_data_page, "")
        root.addWidget(self.response_view_tabs, 1)

        self.response_table.cellDoubleClicked.connect(
            lambda _row, _column: self._show_selected_response_plot()
        )

    def _show_selected_response_plot(self):
        if hasattr(self, "response_view_tabs"):
            self.response_view_tabs.setCurrentWidget(self.response_graph_page)
        self.refresh_response_plot()

    def _fill_table(self, table, frame):
        super()._fill_table(table, frame)
        if hasattr(self, "response_table") and table is self.response_table:
            if "Response Type" in frame and self.window.language == "zh_CN":
                column_index = frame.columns.get_loc("Response Type")
                labels = {
                    "Dip & Recovery": "瞬态跌落-恢复型响应",
                    "No Response": "无可识别响应",
                    "Normal Response": "常规阶跃响应",
                }
                for row_index, value in enumerate(frame["Response Type"]):
                    table.item(row_index, column_index).setText(labels.get(str(value), str(value)))
            for column in ("Switch Time t63 ms", "Switch Time t90 ms"):
                if column in frame:
                    column_index = frame.columns.get_loc(column)
                    for row_index, value in enumerate(frame[column]):
                        if pd.isna(value):
                            table.item(row_index, column_index).setText("N/A")
        if (
            hasattr(self, "response_table")
            and table is self.response_table
            and self.window.language == "zh_CN"
        ):
            labels = [
                self.RESPONSE_HEADERS_ZH.get(str(column), str(column))
                for column in frame.columns
            ]
            table.setHorizontalHeaderLabels(labels)

    def apply_language(self, language: str):
        super().apply_language(language)
        if hasattr(self, "response_view_tabs"):
            self.response_view_tabs.setTabText(
                self.response_view_tabs.indexOf(self.response_graph_page),
                self._text("图形分析", "Plot Analysis"),
            )
            self.response_view_tabs.setTabText(
                self.response_view_tabs.indexOf(self.response_data_page),
                self._text("结果数据", "Result Data"),
            )
            self.response_data_hint.setText(
                self._text(
                    "选择任一结果行后，可点击“查看图形”或双击该行查看对应响应阶段。",
                    "Select a result row, then click View Plot or double-click the row to inspect that response event.",
                )
            )
            self.response_show_plot_button.setText(
                self._text("查看图形", "View Plot")
            )

        if hasattr(self, "response_table") and self.response_result is not None:
            self._fill_table(self.response_table, self.response_result.events)
