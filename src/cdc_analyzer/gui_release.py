from __future__ import annotations

import html
import sys
from importlib.resources import files

from .dynamic_gui import DynamicPagesController
from .gui import _qt_imports
from .gui_v05 import _build_gui_classes_v05, _help_html, _t
from .i18n import tr
from .product_info import (
    AUTHOR_DEPARTMENT_ZH,
    AUTHOR_NAME_ZH,
    COMPANY_EN,
    COMPANY_ZH,
    PRODUCT_NAME,
    RELEASE_DATE,
    RELEASE_EDITION_EN,
    RELEASE_EDITION_ZH,
)

OFFICIAL_WEBSITE = "https://www.faw-tokico.com/"


def _release_help_html(language: str) -> str:
    base = _help_html(language)
    if language == "zh_CN":
        old_title = "CDC 零位阻尼力分析器 — 专业帮助"
        new_title = f"{PRODUCT_NAME} — 专业帮助"
        release_box = f"""
        <div style="margin:8px 0 18px 0;padding:12px 14px;border:1px solid #bdbdbd;background:#f7f7f7;">
          <b>{html.escape(COMPANY_ZH)}</b><br>
          {html.escape(COMPANY_EN)}<br>
          编制：{html.escape(AUTHOR_DEPARTMENT_ZH)}　{html.escape(AUTHOR_NAME_ZH)}<br>
          发布日期：{html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_ZH)}<br>
          公司官网：{html.escape(OFFICIAL_WEBSITE)}
        </div>
        """
        updated = base.replace("用于 CDC/电控减振器", "用于电控/半主动减振器")
        dynamic_help = """
        <h2>11. 响应时间 / Switching Time</h2>
        <p>响应时间页提供 BMW、Audi、红旗、国内主机和零跑客户 Profile，选择后自动载入目标速度：红旗 0.131 / 0.262 / 0.524 / 1.047 m/s，国内主机 0.1 / 0.3 / 0.6 m/s，零跑 0.15 / 0.70 m/s。速度输入框保持可编辑，可输入任意大于 0 的客户速度点，例如 0.1、0.3、0.6、1.0 m/s；多个速度用逗号分隔。响应图可以选择三个同步时间图或双 Y 轴 I₁₀%→F₉₀% 图。</p>
        <ul>
          <li><b>计时基准：</b>电流触发比例可设置，默认 10% 时显示 I₁₀%；图中的 I 下标与设置一致并跟随实际触发交点。各响应时间均为相应力阈值交点时刻减去电流触发交点时刻，单位 ms。</li>
          <li><b>Audi：</b>计算 F₁% / F₆₃% / F₉₀% 力响应、死区时间和力梯度，并检查 4 kHz 采样要求。</li>
          <li><b>BMW：</b>支持软→硬、软→中、硬→中、硬→软设定值跳变，输出 t₆₃% 与 t₉₀%。提供可见的电流触发比例设置，因为当前导入的 BMW 摘录没有给出该触发百分比的规范定义。</li>
          <li><b>红旗 / 国内主机 / 零跑：</b>当前按所选速度预设执行通用响应时间提取，并使用界面中设置的电流与载荷阈值；未提供的客户限值不会自动推断。</li>
          <li><b>图形标注：</b>起始载荷阈值默认 1% 并可调整，F 与 t 的下标同步使用设置值。F 起始阈值和 F₆₃% 可分别勾选显示；取消后对应参考线、交点和时间文字同步隐藏。文字为透明背景、正常字重，与坐标轴标题同为 10 pt。</li>
          <li><b>双 Y 轴阻尼力响应：</b>X 轴为时间，左侧蓝色轴与曲线表示电流，右侧红色轴与曲线表示阻尼力。两条竖虚线标记电流 I₁₀% 和阻尼力 F₉₀% 的线性插值时刻。电流曲线只显示 I₁₀% 交点，不显示 F₉₀% 时刻的电流交点和文字；阻尼力曲线显示两个时刻的交点。主响应时间为 t(F₉₀%) − t(I₁₀%)，与三联图一致。</li>
          <li><b>计算电流过冲：</b>勾选项默认开启；对电流过冲（上升超过终值）或电流下冲（下降低于终值）引起的瞬态力跌落进行识别。图中在电流曲线上标注 Iₘₐₓ= / Iₘᵢₙ= 电流极值（含过冲率）与 I₁₀₀%= 电流满幅值。当响应被分类为“瞬态跌落-恢复型（Dip &amp; Recovery）”时，稳态力差不足，传统 t₆₃% / t₉₀% 不适用；图中明确标注并在计时上做门控处理，避免把瞬态跌落误判为真实响应时间。</li>
          <li>若未输入客户 t₉₀% 限值，只报告测量值，不自动判定 PASS/FAIL。</li>
        </ul>
        <p><b>显示缩放：</b>使用 Qt 自动 DPI 缩放，支持 100% / 150%。工具栏自动换行；较小屏幕可滚动查看完整响应图，字体不会被二次放大或裁切。</p>
        <h2>12. 迟滞 / Hysteresis</h2>
        <ul>
          <li><b>迟滞图：</b>首图为所有速度的电流—阻尼力图，共用纵轴“压缩&lt;--阻尼力(N)--&gt;复原”。复原绘为正值、压缩为负值，所有迟滞试验曲线统一使用连续实线段，不显示数据点符号。图形选择器新增电流—迟滞力柱状图，按速度和压缩/复原方向分组，柱顶显示整数迟滞力值；还可查看单一速度的电流—阻尼力迟滞图和单一电流的速度—阻尼力图。迟滞阻尼力按整数显示和导出，内部计算保留完整精度。点击“加载多速度迟滞数据…”可一次选择不同速度的原始文件；点击“扫描迟滞数据文件夹…”可递归导入所选文件夹及子文件夹中的全部 DAT 文件。程序隔离各文件的 Block ID 后按实测速度分组，不跨速度求均值；默认分组容差 3%。Excel 包含全部图，PNG 导出当前选中图；导出时自动恢复完整纵轴范围，避免压缩方向裁切。菜单栏【导出 → 图片分辨率】可选 150 / 300 / 600 PPI，默认 300 PPI。</li>
          <li><b>BMW：</b>自动识别升/降电流档位，在零位移处分别计算复原与压缩载荷；按运动方向把载荷归一为正阻尼幅值后计算迟滞 N 和迟滞 %。</li>
          <li><b>Audi：</b>按 ±3% 每行程采样点的滑动平均平滑载荷，切换后的第一个循环不参与均值，至少使用 4 个后续循环；在 KFM 前/后平台计算迟滞，并输出第一循环差值。</li>
          <li>Audi 的软 / KFM / 硬电流允许手动输入；留空时根据阻尼力水平自动推断，正式客户报告前应人工确认状态映射。</li>
        </ul>
        <div class="warn">客户项目 Lastenheft / 受控试验规范中的限值始终优先。本软件不会对未提供的客户限值进行猜测。</div>
        """
    else:
        old_title = "CDC Zero Position Force Analyzer — Professional Help"
        new_title = f"{PRODUCT_NAME} — Professional Help"
        release_box = f"""
        <div style="margin:8px 0 18px 0;padding:12px 14px;border:1px solid #bdbdbd;background:#f7f7f7;">
          <b>{html.escape(COMPANY_EN)}</b><br>
          {html.escape(COMPANY_ZH)}<br>
          Prepared by: {html.escape(AUTHOR_DEPARTMENT_ZH)} / {html.escape(AUTHOR_NAME_ZH)}<br>
          Release date: {html.escape(RELEASE_DATE)}　{html.escape(RELEASE_EDITION_EN)}<br>
          Official website: {html.escape(OFFICIAL_WEBSITE)}
        </div>
        """
        updated = base.replace("CDC/electronic damper", "electronically controlled / semi-active damper")
        dynamic_help = """
        <h2>10. Response Time / Switching Time</h2>
        <p>The response page provides BMW, Audi, Hongqi, Domestic OEM and Leapmotor profiles. Their speed presets include Hongqi 0.131 / 0.262 / 0.524 / 1.047 m/s, Domestic OEM 0.1 / 0.3 / 0.6 m/s and Leapmotor 0.15 / 0.70 m/s. The speed field remains editable and accepts any positive values. The response plot can show three synchronized traces or a dual-axis I₁₀%→F₉₀% view.</p>
        <ul>
          <li><b>Timing reference:</b>The current trigger percentage is configurable; the default 10% setting is shown as I₁₀%. Its subscript follows the setting and its label follows the measured trigger intersection. Each response time is its force-threshold crossing time minus the current-trigger crossing time.</li>
          <li><b>Audi:</b>F₁% / F₆₃% / F₉₀% response, dead time and force gradients are reported; 4 kHz sampling is checked.</li>
          <li><b>BMW:</b>supports soft→hard, soft→medium, hard→medium and hard→soft setpoint changes and reports t₆₃% / t₉₀%. The current trigger fraction remains visible because the supplied BMW excerpt does not define that percentage.</li>
          <li><b>Hongqi / Domestic OEM / Leapmotor:</b>use the selected speed preset with the common response extraction and operator-configured current/force thresholds. Customer limits are never inferred when they have not been supplied.</li>
          <li><b>Plot labels:</b>The initial force threshold defaults to 1% and is adjustable; the F and t subscripts follow its setting. The initial F threshold and F₆₃% can be shown independently. Clearing either option hides its guides, intersection and time label together. Labels use transparent, normal-weight 10 pt text.</li>
          <li><b>Dual-axis damping response:</b>Time is the X axis. The blue left axis and curve show current; the red right axis and curve show damping force. Two vertical dashed guides mark the linearly interpolated current I₁₀% and force F₉₀% times. The current curve shows only the I₁₀% intersection; its point and text at the F₉₀% time are hidden. The force curve retains both intersections. The primary result is t(F₉₀%) − t(I₁₀%), matching the three-panel plot.</li>
          <li><b>Current overshoot:</b> enabled by default; transient force dips caused by current overshoot (rise above target) or undershoot (fall below target) are detected. The current trace is annotated with Iₘₐₓ= / Iₘᵢₙ= extremes (with overshoot %) and the I₁₀₀%= full-scale level. If the response is classified as Dip &amp; Recovery, the steady-state force gap is insufficient and classical t₆₃% / t₉₀% do not apply. The plot annotates this and gates the response timing so a transient dip is not mistaken for the true response time.</li>
          <li>No PASS/FAIL is assigned without an entered project t₉₀% limit.</li>
        </ul>
        <p>Qt handles 100% / 150% display scaling. Controls wrap and the full response graph remains scrollable on smaller displays.</p>
        <h2>11. Hysteresis</h2>
        <ul>
          <li><b>Plots:</b>The first graph overlays all speeds on a shared current–force axis: positive rebound, negative compression. Every hysteresis curve is an antialiased, continuously connected solid polyline without point symbols. The plot selector also includes a current–hysteresis force bar chart grouped by speed and compression/rebound direction, with integer values above each bar, plus current–force views by speed and speed–force views by current. Hysteresis force values are displayed and exported as integers while calculations retain full precision. Use “Load multi-speed hysteresis data…” to select multiple raw speed files at once, or “Scan hysteresis data folder…” to import every DAT file recursively from a folder tree. Their Block IDs are isolated before grouping by measured speed. Separate speed groups are never averaged together. The default 3% grouping tolerance is adjustable. Excel includes all plots; PNG exports the selected view after restoring the full vertical range. Use Export → Image Resolution to select 150 / 300 / 600 PPI; 300 PPI is the default.</li>
          <li><b>BMW:</b>pairs increasing/decreasing current results at zero displacement and calculates absolute and percentage hysteresis using direction-normalized damping magnitude.</li>
          <li><b>Audi:</b>applies the ±3% samples-per-stroke moving average, excludes the first post-switch cycle, uses at least four retained cycles, compares KFM before/after and reports first-cycle delta.</li>
          <li>Soft / KFM / hard currents can be entered explicitly; automatic force-level inference must be verified before controlled reporting.</li>
        </ul>
        <div class="warn">Controlled project requirements remain authoritative. The software does not invent missing customer limits.</div>
        """
    updated = updated.replace(old_title, new_title)
    marker = f"<h1>{new_title}</h1>"
    updated = updated.replace(marker, marker + release_box, 1)
    return updated.replace("</body></html>", dynamic_help + "</body></html>", 1)


def _find_app_icon():
    try:
        asset_dir = files("cdc_analyzer").joinpath("assets")
        for name in (
            "damper_test_data_analyzer.ico",
            "damper_test_data_analyzer.png",
            "damper_test_data_analyzer.svg",
        ):
            candidate = asset_dir.joinpath(name)
            if candidate.is_file():
                return str(candidate)
    except Exception:
        pass
    return None


def _build_release_gui_classes():
    QtCore, QtWidgets, pg = _qt_imports()
    from PySide6 import QtGui

    BaseMainWindow = _build_gui_classes_v05()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            self.release_language_toolbar = None
            self.release_language_label = None
            self._initial_view_ranges: list[tuple[tuple[float, float], tuple[float, float]]] = []
            self.dynamic_pages = None
            super().__init__()
            self._setup_language_toolbar()
            self._configure_release_defaults()
            self._ensure_form_labels()
            self._hide_fixed_window_basis()
            self._style_plot_selectors()
            self._apply_release_identity()
            self._capture_initial_view_ranges()
            self.dynamic_pages = DynamicPagesController(self, QtCore, QtWidgets, pg)

        def _table(self):
            table = super()._table()
            table.setMouseTracking(True)
            table.viewport().setMouseTracking(True)
            table.setStyleSheet(
                table.styleSheet()
                + """
                QTableView::item:hover {
                    background-color: #e8f5e9;
                    color: #202020;
                }
                QTableView::item:selected {
                    background-color: #dff2df;
                    color: #202020;
                }
                QTableView::item:selected:hover {
                    background-color: #cfe8cf;
                    color: #202020;
                }
                """
            )
            return table

        def _setup_language_toolbar(self):
            language_layout = self.language_box.layout()
            if language_layout is not None:
                language_layout.removeWidget(self.language_combo)
                language_layout.removeWidget(self.help_button)
            self.language_box.hide()

            toolbar = QtWidgets.QToolBar()
            toolbar.setObjectName("releaseLanguageToolbar")
            toolbar.setMovable(False)
            toolbar.setFloatable(False)
            toolbar.setMinimumHeight(46)
            toolbar.setContentsMargins(8, 3, 8, 3)

            label = QtWidgets.QLabel()
            label_font = label.font()
            label_font.setBold(True)
            label_font.setPointSize(max(10, label_font.pointSize()))
            label.setFont(label_font)
            label.setMinimumWidth(86)
            toolbar.addWidget(label)

            combo_font = self.language_combo.font()
            combo_font.setPointSize(max(10, combo_font.pointSize()))
            self.language_combo.setFont(combo_font)
            self.language_combo.setMinimumWidth(160)
            self.language_combo.setMinimumHeight(32)
            toolbar.addWidget(self.language_combo)

            spacer = QtWidgets.QWidget()
            spacer.setSizePolicy(
                QtWidgets.QSizePolicy.Policy.Expanding,
                QtWidgets.QSizePolicy.Policy.Preferred,
            )
            toolbar.addWidget(spacer)
            self.help_button.setMinimumHeight(32)
            toolbar.addWidget(self.help_button)
            self.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, toolbar)

            self.release_language_toolbar = toolbar
            self.release_language_label = label

        def _configure_release_defaults(self):
            index = self.window_basis.findData("total_stroke")
            if index >= 0:
                self.window_basis.setCurrentIndex(index)
            self.window_percent.setValue(2.0)
            self.window_basis.setToolTip("默认按总行程全宽定义评价窗口 / Default: total-stroke full width")

        def _hide_fixed_window_basis(self):
            """Keep the fixed full-stroke basis in configuration without redundant UI."""
            self.window_basis.blockSignals(True)
            self.window_basis.clear()
            self.window_basis.addItem(
                tr(self.language, "basis_total"), "total_stroke"
            )
            self.window_basis.setCurrentIndex(0)
            self.window_basis.blockSignals(False)
            self.window_basis.hide()
            label = self.eval_form.labelForField(self.window_basis)
            if label is not None:
                label.hide()

        def _config(self):
            config = super()._config()
            config.window_basis = "total_stroke"
            return config

        def _ensure_label(self, form, field, text: str, minimum_width: int = 72):
            label = form.labelForField(field)
            if label is None:
                row, _role = form.getWidgetPosition(field)
                if row >= 0:
                    label = QtWidgets.QLabel(text)
                    form.setWidget(row, QtWidgets.QFormLayout.ItemRole.LabelRole, label)
            if label is None:
                return
            label.setText(text)
            label.setVisible(True)
            label.setMinimumWidth(minimum_width)
            font = label.font()
            font.setBold(True)
            label.setFont(font)

        def _ensure_form_labels(self):
            for form in (self.eval_form, self.gas_form, self.plot_form):
                form.setLabelAlignment(
                    QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
                form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

            for field, key in (
                (self.profile, "profile"),
                (self.force, "force"),
                (self.window_percent, "window"),
                (self.window_basis, "window_basis"),
                (self.zero_target, "target_x"),
            ):
                self._ensure_label(self.eval_form, field, tr(self.language, key), 88)

            for field, key in (
                (self.gas_mode, "mode"),
                (self.gas_operation, "gas_operation"),
                (self.gas_force, "gas_force"),
                (self.gas_pressure, "gauge_pressure"),
                (self.rod_dia, "rod_diameter"),
            ):
                self._ensure_label(self.gas_form, field, tr(self.language, key), 88)

            for field, text in (
                (self.x_axis, tr(self.language, "x_axis")),
                (self.y_axis, tr(self.language, "y_axis")),
                (self.current_filter, tr(self.language, "current")),
                (self.run_filter, tr(self.language, "run")),
                (self.cycle_filter, tr(self.language, "cycle")),
                (self.background_combo, _t(self.language, "background")),
            ):
                self._ensure_label(self.plot_form, field, text, 72)

        def _style_plot_selectors(self):
            selection_style = (
                "QAbstractItemView::item:selected {"
                "background-color:#dff2df; color:#202020;"
                "}"
            )
            self.x_axis.view().setStyleSheet(selection_style)
            self.y_axis.setStyleSheet(
                "QListWidget::item:selected { background-color:#dff2df; }"
            )

        def _apply_v05_language(self):
            super()._apply_v05_language()
            if hasattr(self, "help_browser"):
                self._apply_release_identity()
            if getattr(self, "release_language_label", None) is not None:
                self.release_language_label.setText("界面语言" if self.language == "zh_CN" else "UI Language")
            if hasattr(self, "plot_form"):
                self._ensure_form_labels()
                self._hide_fixed_window_basis()
            if getattr(self, "dynamic_pages", None) is not None:
                self.dynamic_pages.apply_language(self.language)

        def _apply_plot_background(self, refresh: bool = False):
            super()._apply_plot_background(refresh=refresh)
            if getattr(self, "dynamic_pages", None) is not None:
                self.dynamic_pages.refresh_response_plot()
                self.dynamic_pages.refresh_hysteresis_plot()

        def _apply_release_identity(self):
            self.setWindowTitle(PRODUCT_NAME)
            icon_path = _find_app_icon()
            if icon_path:
                icon = QtGui.QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
            if hasattr(self, "help_browser"):
                self.help_browser.setHtml(_release_help_html(self.language))
            if getattr(self, "release_language_label", None) is not None:
                self.release_language_label.setText("界面语言" if self.language == "zh_CN" else "UI Language")

        def refresh_plot(self):
            super().refresh_plot()
            if hasattr(self, "_initial_view_ranges"):
                self._capture_initial_view_ranges()

        def _capture_initial_view_ranges(self):
            plots = self._plot_items()
            if not plots:
                self._initial_view_ranges = []
                return
            for plot in plots:
                plot.enableAutoRange(x=True, y=True)
                plot.autoRange()
            self._initial_view_ranges = []
            for plot in plots:
                view_range = plot.viewRange()
                self._initial_view_ranges.append(
                    (
                        (float(view_range[0][0]), float(view_range[0][1])),
                        (float(view_range[1][0]), float(view_range[1][1])),
                    )
                )
                plot.getViewBox().disableAutoRange()

        def _reset_view(self):
            plots = self._plot_items()
            if not plots:
                return
            if len(self._initial_view_ranges) != len(plots):
                self._capture_initial_view_ranges()
            if len(self._initial_view_ranges) != len(plots):
                return
            for plot, (x_range, y_range) in zip(plots, self._initial_view_ranges):
                view_box = plot.getViewBox()
                view_box.disableAutoRange()
                view_box.setRange(xRange=x_range, yRange=y_range, padding=0)

    return MainWindow


def main() -> int:
    _, QtWidgets, _ = _qt_imports()
    MainWindow = _build_release_gui_classes()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
