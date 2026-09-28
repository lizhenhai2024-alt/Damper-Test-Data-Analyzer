from __future__ import annotations

import sys

from . import gui_release as _base_release
from . import gui_release_v085 as _v085_module
from .dynamic_gui_v090 import DynamicPagesController
from .gui import _qt_imports
from .gui_release_v085 import _build_release_gui_classes_v085
from .product_info import COMPANY_EN, PRODUCT_NAME


_previous_help = _base_release._release_help_html


def _help_v090(language: str) -> str:
    html = _previous_help(language)
    if language == "zh_CN":
        section = """
        <h2>13. 全电流分析：第20/21项、F-V 与 F-I</h2>
        <ol>
          <li>点击“选择全电流数据文件夹…”读取所选文件夹和全部子文件夹中的 MTS <code>.PVP</code> 与 CTW <code>.dctw</code> 文件。</li>
          <li>程序只从文件名自动识别电流（例如 <code>0.4.pvp</code> 或 <code>2#-0.3A-1.dctw</code>），不能手工修改。无法识别电流的文件不会加载。CTW 力通道按文件头标定表换算为 N。</li>
          <li>同一路径不会重复加入；重复测量会作为独立来源保留。选中列表行后点击“移除所选数据”可排除异常或重复测量，原始文件不会被删除。同电流、速度和方向的保留测量取最后一个重复文件的数据，同时记录重复次数和标准差。</li>
          <li>仅评价不高于 1.047 m/s 的速度段。每段取最后一个完整循环，在行程中心总行程 10% 窗口内分别取复原最大力和压缩最小力。</li>
          <li>软电流默认 0.3 A、硬电流默认 1.6 A，仅作参考显示；软件按 Audi VR-EF-33-2 规范自动取每个速度方向最软（最小电流档）与最硬（最大电流档）阻尼力作为归一化与范围计算的锚点，第20项计算 <code>(|Fᵢ|−|Fsoft|)/(|Fhard|−|Fsoft|)</code> 并显示正负两侧45°理想虚线。每个速度一条归一化曲线（复原正、压缩负），电流档超出默认范围（如磁流变 0～5 A）时无需修改设置即可完整显示。</li>
          <li>第21项在同一张图中用左轴柱形表示阻尼力范围、右轴折线表示放大倍数，并标注计算值。横轴按 Audi 标准等间距排列，只显示实测试验速度点。</li>
          <li>F-V 图显示各电流下阻尼力随速度的变化；F-I 图显示各速度下阻尼力随电流的变化；F-V 数据页以电流为行、速度和方向为列。</li>
        </ol>
        <p>客户项目限值需由受控项目文件给出；未设置限值时软件只报告测量和计算结果。</p>
        """
    else:
        section = """
        <h2>13. Full-current analysis: items 20/21, F-V and F-I</h2>
        <p>Select one full-current folder and scan its complete tree for MTS .PVP and CTW .dctw files. Current is read only from each filename. When several files share the same current/speed/direction, the last retained repeat is used (each run evaluates its last complete cycle); removing a row never deletes its source file.</p>
        <p>Soft and hard current fields default to 0.3 A and 1.6 A and serve as reference only; per Audi VR-EF-33-2 sections 20/21 the softest and hardest retained current steps of each speed/direction are used automatically as the anchors for the normalized force and the spread. Item 20 shows one normalized curve per speed (rebound positive, compression negative) with 45-degree ideal reference lines on both sides. Item 21 combines spread bars and amplification lines on dual Y axes with value labels. F-V and F-I plots and an F-V matrix table are also provided.</p>
        """
    return html.replace("</body></html>", section + "</body></html>", 1)


_base_release._release_help_html = _help_v090


def _build_release_gui_classes_v090():
    _QtCore, QtWidgets, _pg = _qt_imports()
    previous_controller = _v085_module.DynamicPagesController
    _v085_module.DynamicPagesController = DynamicPagesController
    try:
        BaseMainWindow = _build_release_gui_classes_v085()
    finally:
        _v085_module.DynamicPagesController = previous_controller

    class MainWindow(BaseMainWindow):
        def __init__(self):
            previous = _v085_module.DynamicPagesController
            _v085_module.DynamicPagesController = DynamicPagesController
            try:
                super().__init__()
            finally:
                _v085_module.DynamicPagesController = previous

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                "Damper Test Data Analyzer\n减振器 / CDC 试验数据分析工具\nV0.9.0",
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v090()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
