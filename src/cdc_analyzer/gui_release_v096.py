from __future__ import annotations

import sys

from . import gui_release as _base_release
from . import gui_release_v091 as _v091_module
from .dynamic_gui_v092 import DynamicPagesController
from .gui import _qt_imports
from .gui_release_v095 import _build_release_gui_classes_v095
from .product_info import COMPANY_EN, PRODUCT_NAME


_previous_help = _base_release._release_help_html


def _help_v096(language: str) -> str:
    html = _previous_help(language)
    if language == "zh_CN":
        section = """
        <h2>14. 阻尼力测试分析：PVP / CTW，AUDI 与 BMW 规范</h2>
        <ol>
          <li>「阻尼力测试分析」页支持三种数据加载方式：点击“添加文件…”选择一个或多个 MTS <code>.PVP</code> 或 CTW <code>.dctw</code> 文件；点击“添加数据文件夹…”扫描所选文件夹及全部子文件夹中的同类文件；也可先用“添加文件…”再追加“添加数据文件夹…”混合加载。</li>
          <li>电流 A 一律从文件名自动识别（例如 <code>0.4.pvp</code> 或 <code>2#-0.3A-1.dctw</code>），不可手工修改；无法识别电流的文件不会加载。CTW 力通道按文件头标定表换算为 N。</li>
          <li>规范下拉可选 AUDI 或 BMW：AUDI 对应 VR-EF-33-2 第20/21项；BMW 对应 BMW CDC 全电流阻尼力图谱（每速度电流扫描）。软电流默认 0.3 A、硬电流默认 1.6 A，仅作参考；软件自动取每个速度方向最软（最小电流档）与最硬（最大电流档）阻尼力作为归一化与范围计算的锚点。</li>
          <li>每个速度段取最后一个完整循环，在行程中心总行程 10% 窗口内分别取复原最大力和压缩最小力；同一电流、速度、方向的重复测量取最后一个重复文件。结果包含第20项电流—力线性、第21项力值范围与放大倍数、F-V 图、F-I 图及 F-V 数据表，可一键导出 Excel。</li>
        </ol>
        <p>客户项目限值需由受控项目文件给出；未设置限值时软件只报告测量和计算结果。</p>
        """
    else:
        section = """
        <h2>14. Damping-force analysis: PVP / CTW, AUDI and BMW profiles</h2>
        <p>The Damping-force analysis page loads MTS .PVP and CTW .dctw files three ways: “Add files…” for one or more files, “Add data folder…” to scan a folder tree, or a mix of both. Current is read only from each filename. The profile dropdown selects AUDI (VR-EF-33-2 items 20/21) or BMW (per-speed current-sweep damping-force map). Each run evaluates its last complete cycle and the center 10% full-stroke directional extrema; softest/hardest current steps are used automatically as anchors. Item 20 current–force linearity, item 21 spread and amplification, F-V / F-I plots and the F-V data table are provided, with one-click Excel export.</p>
        """
    return html.replace("</body></html>", section + "</body></html>", 1)


_base_release._release_help_html = _help_v096


def _build_release_gui_classes_v096():
    _QtCore, QtWidgets, _pg = _qt_imports()
    previous_controller = _v091_module.DynamicPagesController
    _v091_module.DynamicPagesController = DynamicPagesController
    try:
        BaseMainWindow = _build_release_gui_classes_v095()
    finally:
        _v091_module.DynamicPagesController = previous_controller

    class MainWindow(BaseMainWindow):
        def __init__(self):
            previous = _v091_module.DynamicPagesController
            _v091_module.DynamicPagesController = DynamicPagesController
            try:
                super().__init__()
            finally:
                _v091_module.DynamicPagesController = previous

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                "Damper Test Data Analyzer\n减振器 / CDC 试验数据分析工具\nV0.9.13",
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v096()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
