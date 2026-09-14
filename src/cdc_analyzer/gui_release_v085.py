from __future__ import annotations

import sys

from . import gui_release_v084 as _v084_module
from .dynamic_gui_v085 import DynamicPagesController
from .gui import _qt_imports
from .gui_release_v084 import _build_release_gui_classes_v084
from .product_info import COMPANY_EN, PRODUCT_NAME


def _build_release_gui_classes_v085():
    _QtCore, QtWidgets, _pg = _qt_imports()
    BaseMainWindow = _build_release_gui_classes_v084()

    class MainWindow(BaseMainWindow):
        def __init__(self):
            previous_controller = _v084_module.DynamicPagesController
            _v084_module.DynamicPagesController = DynamicPagesController
            try:
                super().__init__()
            finally:
                _v084_module.DynamicPagesController = previous_controller
            self.dynamic_pages.configure_responsive_layout()
            screen = self.screen().availableGeometry()
            self.resize(min(1500, int(screen.width() * 0.96)), min(900, int(screen.height() * 0.92)))

        def _show_about_dialog(self):
            QtWidgets.QMessageBox.information(
                self,
                "关于软件" if self.language == "zh_CN" else "About",
                (
                    "Damper Test Data Analyzer\n"
                    "减振器 / CDC 试验数据分析工具\n"
                    "V0.8.21"
                    if self.language == "zh_CN"
                    else "Damper Test Data Analyzer\nDamper / CDC test-data analysis\nV0.8.21"
                ),
            )

    return MainWindow


def main() -> int:
    _QtCore, QtWidgets, _pg = _qt_imports()
    MainWindow = _build_release_gui_classes_v085()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(COMPANY_EN)
    window = MainWindow()
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

