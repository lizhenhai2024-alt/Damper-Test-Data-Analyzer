from __future__ import annotations

import sys

from .gui import _qt_imports
from .gui_release_v094 import _build_release_gui_classes_v094
from .product_info import COMPANY_EN, PRODUCT_NAME


def _build_release_gui_classes_v095():
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _build_release_gui_classes_v094()

    class MainWindow(BaseMainWindow):
        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                "Damper Test Data Analyzer\n减振器 / CDC 试验数据分析工具\nV0.9.7",
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v095()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
