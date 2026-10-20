from pathlib import Path
import os

import numpy as np
import pytest

from cdc_analyzer import audi_items_20_21 as items


def _synthetic_runs(current, repeat=1):
    runs = []
    for speed in (0.1, 0.3):
        phase = np.linspace(0, 8 * np.pi, 4001)
        displacement = 30 * np.sin(phase)
        velocity = np.cos(phase) * speed
        magnitude = 200 + 800 * current + 500 * speed + 10 * repeat
        force = np.where(velocity >= 0, magnitude, -0.8 * magnitude)
        runs.append((speed, displacement, force, velocity))
    return runs


def _make_files(tmp_path, currents=(0.0, 0.5, 1.0)):
    files = []
    for current in currents:
        path = tmp_path / f"{current:g}A-1.dctw"
        path.write_bytes(b"fixture")
        files.append(items.ImportedMapFile(path, current, "DCTW", 2, (0.1, 0.3)))
    return files


def test_v092_profile_changes_settings_standard(monkeypatch, tmp_path):
    files = _make_files(tmp_path)
    monkeypatch.setattr(items, "_parse_dctw", lambda path, current: _synthetic_runs(current))
    audi = items.analyze_map_files(files, profile="AUDI")
    bmw = items.analyze_map_files(files, profile="BMW")
    assert "Audi" in audi.settings["Standard"]
    assert "BMW" in bmw.settings["Standard"]
    with pytest.raises(ValueError):
        items.analyze_map_files(files, profile="UNKNOWN")
    # Calculation results are identical; only the standard label differs.
    assert audi.current_force_linearity.equals(bmw.current_force_linearity)


def test_v092_gui_damper_page_and_analyze(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets
    from cdc_analyzer.gui_release_v096 import _build_release_gui_classes_v096

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = _build_release_gui_classes_v096()()
    pages = window.dynamic_pages
    assert window.tabs.indexOf(pages.damper_page) >= 0
    assert pages.damper_profile_combo.count() == 2
    assert pages.damper_profile_combo.itemData(0) == "AUDI"
    assert pages.damper_profile_combo.itemData(1) == "BMW"
    assert pages.damper_file_button is not None
    assert pages.damper_folder_button is not None

    files = _make_files(tmp_path)
    monkeypatch.setattr(items, "_parse_dctw", lambda path, current: _synthetic_runs(current))
    pages.damper_files = files
    pages._refresh_damper_file_table()
    pages.damper_profile_combo.setCurrentIndex(1)  # BMW
    app.processEvents()
    pages.analyze_damper()
    assert pages.damper_result is not None
    assert "BMW" in pages.damper_result.settings["Standard"]
    assert pages.damper_result.run_detail["Current A"].nunique() == 3
    window.close()
    app.processEvents()


def test_v092_gui_switch_language_text(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets
    from cdc_analyzer.gui_release_v096 import _build_release_gui_classes_v096

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = _build_release_gui_classes_v096()()
    pages = window.dynamic_pages
    assert "阻尼力测试分析" in window.help_browser.toPlainText()
    pages.window.language = "en_US"
    pages.apply_language("en_US")
    app.processEvents()
    assert pages.damper_profile_label.text() == "Profile"
    assert pages.damper_file_button.text() == "Add files…"
    window.close()
    app.processEvents()
