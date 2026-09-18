from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_v079_hides_end_average_and_shows_unset_t90_limit():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release_v079 import _build_release_gui_classes_v079

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes_v079()
    window = MainWindow()
    pages = window.dynamic_pages

    assert pages.response_end_label.isHidden()
    assert pages.response_end_fraction.isHidden()
    assert pages.response_end_fraction.value() == pytest.approx(2.0)
    assert pages.response_t90_limit.value() == pytest.approx(0.0)
    assert pages.response_t90_limit.specialValueText() == "未设置"

    window.language = "en_US"
    pages.apply_language("en_US")
    assert pages.response_t90_limit.specialValueText() == "Not set"
    assert pages.response_end_label.isHidden()
    assert pages.response_end_fraction.isHidden()

    window.close()
    app.processEvents()


def test_v079_help_title_drops_professional_help_suffix():
    from cdc_analyzer import __version__
    from cdc_analyzer.gui_release_v079 import _release_help_html_v079
    from cdc_analyzer.product_info import PRODUCT_NAME

    zh = _release_help_html_v079("zh_CN")
    en = _release_help_html_v079("en_US")

    assert "Damper Test Data Analyzer — 专业帮助" not in zh
    assert "Damper Test Data Analyzer — Professional Help" not in en
    assert f"<h1>{PRODUCT_NAME} V{__version__}</h1>" in zh
    assert f"<h1>{PRODUCT_NAME} V{__version__}</h1>" in en
