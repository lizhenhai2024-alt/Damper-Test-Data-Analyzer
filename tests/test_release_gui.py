from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")


def test_release_ui_defaults_and_professional_controls():
    from PySide6 import QtWidgets
    from cdc_analyzer import __version__
    from cdc_analyzer.gui_release import _build_release_gui_classes
    from cdc_analyzer.product_info import COMPANY_EN, COMPANY_ZH, PRODUCT_NAME

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes()
    window = MainWindow()

    assert window.windowTitle() == f"{PRODUCT_NAME} V{__version__}"
    assert PRODUCT_NAME == "Damper Test Data Analyzer"
    assert window.language == "zh_CN"
    assert window.language_combo.currentData() == "zh_CN"
    assert window.language_box.isHidden()
    assert window.release_language_toolbar is not None
    assert window.release_language_label.text() == "界面语言"
    assert window.language_combo.minimumWidth() >= 160

    assert window.help_button.text() == "帮助 / 使用说明"
    assert window.tabs.tabText(window.tabs.indexOf(window.help_page)) == "专业帮助"
    assert "Audi" in window.help_browser.toPlainText()
    assert "窗口基准固定为总行程全宽" in window.help_browser.toPlainText()
    assert COMPANY_ZH in window.help_browser.toPlainText()
    assert COMPANY_EN in window.help_browser.toPlainText()

    assert window.window_basis.currentData() == "total_stroke"
    assert window.window_percent.value() == pytest.approx(2.0)

    assert window.background_combo.currentData() == "white"
    assert window.zoom_in_button.text() == "放大"
    assert window.zoom_out_button.text() == "缩小"
    assert window.box_zoom_button.text() == "框选放大"
    assert window.pan_button.text() == "平移"
    assert window.reset_view_button.text() == "恢复"

    for field in (
        window.x_axis,
        window.y_axis,
        window.current_filter,
        window.run_filter,
        window.cycle_filter,
        window.background_combo,
    ):
        label = window.plot_form.labelForField(field)
        assert label is not None
        assert label.text().strip()
        assert label.isVisible() or not window.isVisible()

    assert "#dff2df" in window.x_axis.view().styleSheet().lower()
    assert "#dff2df" in window.y_axis.styleSheet().lower()
    assert not window.windowIcon().isNull()

    analysis_tables = (
        window.summary_table,
        window.run_table,
        window.cycle_table,
        window.sweep_table,
        window.quality_table,
    )
    for table in analysis_tables:
        style = table.styleSheet().lower()
        assert table.hasMouseTracking()
        assert table.viewport().hasMouseTracking()
        assert "qtableview::item:hover" in style
        assert "#e8f5e9" in style
        assert "color: #202020" in style
        assert "qtableview::item:selected" in style

    window.language_combo.setCurrentIndex(window.language_combo.findData("en_US"))
    app.processEvents()
    assert window.windowTitle() == f"{PRODUCT_NAME} V{__version__}"
    assert window.release_language_label.text() == "UI Language"
    assert window.help_button.text() == "Help / User Guide"
    assert window.tabs.tabText(window.tabs.indexOf(window.help_page)) == "Professional Help"
    assert window.background_combo.itemText(window.background_combo.findData("black")) == "Black"

    window.close()
    app.processEvents()


def test_reset_restores_initial_plot_range_in_one_click():
    from PySide6 import QtWidgets
    from cdc_analyzer.gui_release import _build_release_gui_classes

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    MainWindow = _build_release_gui_classes()
    window = MainWindow()

    window.plot_area.clear()
    plot = window.plot_area.addPlot(row=0, col=0)
    plot.plot([0.0, 1.0, 2.0, 3.0], [0.0, 2.0, -1.0, 1.0])
    window._capture_initial_view_ranges()
    initial = plot.viewRange()

    window._zoom_view(0.70)
    zoomed = plot.viewRange()
    assert zoomed[0][1] - zoomed[0][0] < initial[0][1] - initial[0][0]

    window._reset_view()
    restored = plot.viewRange()
    assert restored[0] == pytest.approx(initial[0], rel=1e-6, abs=1e-6)
    assert restored[1] == pytest.approx(initial[1], rel=1e-6, abs=1e-6)

    window.close()
    app.processEvents()
