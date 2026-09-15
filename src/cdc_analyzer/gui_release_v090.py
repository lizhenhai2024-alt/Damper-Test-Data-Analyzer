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
        <h2>13. Audi 第20/21项：电流—力线性、力值范围和放大倍数</h2>
        <ol>
          <li>点击“添加 PVP / DCTW 文件…”可一次选择多个 MTS <code>.PVP</code> 或 CTW <code>.dctw</code> 文件；“递归扫描文件夹…”会读取所选文件夹和全部子文件夹。</li>
          <li>程序从文件名识别电流（例如 <code>0.4.pvp</code> 或 <code>2#-0.3A-1.dctw</code>）。电流可在列表中双击修改。CTW 力通道按文件头标定表换算为 N。</li>
          <li>同一路径不会重复加入；重复测量会作为独立来源保留。选中列表行后点击“移除所选数据”可排除异常或重复测量，原始文件不会被删除。同电流、速度和方向的保留测量按均值汇总，同时记录重复次数和标准差。</li>
          <li>仅评价不高于 1.047 m/s 的速度段。每段取最后一个完整循环，在行程中心总行程 10% 窗口内分别取复原最大力和压缩最小力。</li>
          <li>第20项按每个速度与方向计算 <code>(|Fᵢ|−|Fsoft|)/(|Fhard|−|Fsoft|)</code>，压缩方向在图中显示为负值，并报告线性拟合 R² 与最大偏差。</li>
          <li>第21项按速度计算阻尼力范围 <code>|Fhard|−|Fsoft|</code> 和放大倍数 <code>|Fhard|/|Fsoft|</code>；压缩范围显示为负值，放大倍数保持正值。</li>
        </ol>
        <p>客户项目限值需由受控项目文件给出；未设置限值时软件只报告测量和计算结果。</p>
        """
    else:
        section = """
        <h2>13. Audi items 20/21: current–force linearity, spread and amplification</h2>
        <p>Load multiple MTS .PVP or CTW .dctw files directly, or scan a folder tree. Current is inferred from the filename and remains editable. Retained repeat measurements at equal current, speed and direction are averaged with count and standard deviation. Removing a row never deletes its source file.</p>
        <p>Runs up to 1.047 m/s use the directional extrema in the center 10% of the last complete cycle. Item 20 reports normalized current–force linearity, R² and maximum fit deviation. Item 21 reports hard-to-soft damping-force spread and amplification by speed and direction.</p>
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
