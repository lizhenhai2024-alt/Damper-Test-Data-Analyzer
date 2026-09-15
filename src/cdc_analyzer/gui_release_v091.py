from __future__ import annotations

import sys

from . import gui_release_v090 as _v090_module
from .dynamic_gui_v091 import DynamicPagesController
from .gui import _qt_imports
from .gui_release_v090 import _build_release_gui_classes_v090
from .product_info import COMPANY_EN, PRODUCT_NAME


def _build_release_gui_classes_v091():
    _QtCore, QtWidgets, _pg = _qt_imports()
    previous_controller = _v090_module.DynamicPagesController
    _v090_module.DynamicPagesController = DynamicPagesController
    try:
        BaseMainWindow = _build_release_gui_classes_v090()
    finally:
        _v090_module.DynamicPagesController = previous_controller

    class MainWindow(BaseMainWindow):
        def __init__(self):
            previous = _v090_module.DynamicPagesController
            _v090_module.DynamicPagesController = DynamicPagesController
            try:
                super().__init__()
            finally:
                _v090_module.DynamicPagesController = previous

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                "Damper Test Data Analyzer\n减振器 / CDC 试验数据分析工具\nV0.9.1",
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v091()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
