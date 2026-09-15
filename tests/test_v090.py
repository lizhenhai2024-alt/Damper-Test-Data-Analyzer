from pathlib import Path
import os
import struct

import numpy as np
import pytest

from cdc_analyzer import audi_items_20_21 as items


def _synthetic_runs(current):
    runs = []
    for speed in (0.1, 0.3):
        phase = np.linspace(0, 8 * np.pi, 4001)
        displacement = 30 * np.sin(phase)
        velocity = np.cos(phase) * speed
        magnitude = 200 + 800 * current + 500 * speed
        force = np.where(velocity >= 0, magnitude, -0.8 * magnitude)
        runs.append((speed, displacement, force, velocity))
    return runs


def test_current_names_and_recursive_discovery(tmp_path):
    nested = tmp_path / "repeat" / "run"
    nested.mkdir(parents=True)
    pvp = tmp_path / "0.4.pvp"
    dctw = nested / "2#-0.3A-1.dctw"
    ignored = nested / "readme.txt"
    for path in (pvp, dctw, ignored):
        path.write_bytes(b"x")
    assert items.current_from_filename(pvp) == pytest.approx(0.4)
    assert items.current_from_filename(dctw) == pytest.approx(0.3)
    assert items.discover_map_files(tmp_path) == [pvp, dctw]


def test_pvp_channel_record_decoder():
    name = b"Force"
    values = np.asarray([-12.5, 4.25, 99.0], dtype="<f4")
    data = b"prefix" + struct.pack("<I", len(name)) + name + struct.pack("<IIII", 95, 10, 0, len(values)) + values.tobytes()
    records = items._pvp_channel_records(data, name)
    assert len(records) == 1
    assert records[0][1] == pytest.approx(values)


def test_items_20_21_calculation_and_repeat_handling(monkeypatch, tmp_path):
    files = []
    for current in (0.0, 0.5, 1.0):
        for repeat in (1, 2):
            path = tmp_path / f"{current:g}A-{repeat}.dctw"
            path.write_bytes(b"fixture")
            files.append(items.ImportedMapFile(path, current, "DCTW", 2, (0.1, 0.3)))
    monkeypatch.setattr(items, "_parse_dctw", lambda path, current: _synthetic_runs(current))
    result = items.analyze_map_files(files, soft_current_a=0.0, hard_current_a=1.0)
    assert len(result.run_detail) == 12
    assert set(result.current_force_linearity["Repeat Count"]) == {2}
    for (_speed, direction), group in result.current_force_linearity.groupby(["Speed m/s", "Direction"]):
        ordered = group.sort_values("Current A")
        expected = [0.0, 0.5, 1.0] if direction == "Rebound" else [0.0, -0.5, -1.0]
        assert ordered["Normalized Force"].to_numpy() == pytest.approx(expected, abs=1e-9)
        assert ordered["Linearity R²"].iloc[0] == pytest.approx(1.0)
    assert len(result.spread_amplification) == 4
    assert (result.spread_amplification.query("Direction == 'Rebound'")["Damping Force Spread N"] > 0).all()
    assert (result.spread_amplification.query("Direction == 'Compression'")["Damping Force Spread N"] < 0).all()


def test_v090_gui_has_batch_list_and_safe_remove(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets
    from cdc_analyzer.gui_release_v090 import _build_release_gui_classes_v090

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = _build_release_gui_classes_v090()()
    pages = window.dynamic_pages
    source = tmp_path / "0.4.pvp"
    source.write_bytes(b"do not delete")
    pages.map_files = [items.ImportedMapFile(source, 0.4, "PVP", 5, (0.05, 0.1, 0.3, 0.6, 1.0))]
    pages._refresh_map_file_table()
    pages.map_file_table.selectRow(0)
    pages.remove_selected_map_files()
    assert pages.map_files == []
    assert source.read_bytes() == b"do not delete"
    assert window.tabs.indexOf(pages.map_page) >= 0
    assert pages.map_file_table.selectionMode() == QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
    assert "第20/21项" in window.help_browser.toPlainText()
    window.close()
    app.processEvents()


def test_current_packaged_gui_is_v090():
    root = Path(__file__).resolve().parents[1]
    assert "gui_release_v091" in (root / "launcher.py").read_text()
    assert "gui_release_v091:main" in (root / "pyproject.toml").read_text()
    assert "olefile>=0.47" in (root / "pyproject.toml").read_text()
    assert "APP_VERSION: V0.9.1" in (root / ".github" / "workflows" / "build-windows.yml").read_text()
