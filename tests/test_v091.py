from pathlib import Path
import os

import numpy as np
import pytest

from cdc_analyzer import audi_items_20_21 as items


def _runs(current):
    runs = []
    for speed in (0.1, 0.3):
        phase = np.linspace(0, 8 * np.pi, 4001)
        displacement = 30 * np.sin(phase)
        velocity = speed * np.cos(phase)
        magnitude = 250 + 1000 * current + 500 * speed
        force = np.where(velocity >= 0, magnitude, -0.8 * magnitude)
        runs.append((speed, displacement, force, velocity))
    return runs


def _result(monkeypatch, tmp_path):
    files = []
    for current in (0.3, 0.95, 1.6):
        path = tmp_path / f"sample-{current:g}A-1.dctw"
        path.write_bytes(b"fixture")
        files.append(items.ImportedMapFile(path, 99.0, "DCTW", 2, (0.1, 0.3)))
    monkeypatch.setattr(items, "_parse_dctw", lambda path, current: _runs(current))
    return files, items.analyze_map_files(files)


def test_full_current_defaults_filename_source_and_fv_table(monkeypatch, tmp_path):
    _files, result = _result(monkeypatch, tmp_path)
    assert result.settings["Soft Current A"] == pytest.approx(0.3)
    assert result.settings["Hard Current A"] == pytest.approx(1.6)
    assert sorted(result.run_detail["Current A"].unique()) == pytest.approx([0.3, 0.95, 1.6])
    assert (result.current_force_linearity.query("Direction == 'Rebound'")["Force N"] > 0).all()
    assert (result.current_force_linearity.query("Direction == 'Compression'")["Force N"] < 0).all()
    assert list(result.force_velocity_table.columns) == [
        "Current A", "Rebound 0.1 m/s", "Rebound 0.3 m/s",
        "Compression 0.1 m/s", "Compression 0.3 m/s",
    ]
    assert len(result.force_velocity_table) == 3
    assert all(str(dtype) == "Int64" for dtype in result.force_velocity_table.dtypes[1:])
    for (_speed, direction), group in result.current_force_linearity.groupby(["Speed m/s", "Direction"]):
        expected = [0.0, 0.5, 1.0] if direction == "Rebound" else [0.0, -0.5, -1.0]
        assert group.sort_values("Current A")["Normalized Force"].to_numpy() == pytest.approx(expected)


def test_missing_filename_current_is_rejected(tmp_path):
    path = tmp_path / "measurement.dctw"
    path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="文件名"):
        items.current_from_filename(path)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("20260609  FR30     0.3-A-2.pvp", 0.3),
        ("20260609  FR30     0.9-A.pvp", 0.9),
        ("sample-1.6_A_2.pvp", 1.6),
        ("sample-0.4A-2.dctw", 0.4),
        ("0.5.pvp", 0.5),
    ],
)
def test_current_filename_variants(name, expected):
    assert items.current_from_filename(name) == pytest.approx(expected)


def test_file_inspection_hides_header_values_outside_test_speed_range(monkeypatch, tmp_path):
    path = tmp_path / "20260609 FR30 0.3-A-2.pvp"
    path.write_bytes(b"fixture")
    empty = np.array([], dtype=float)
    monkeypatch.setattr(items, "_parse_pvp", lambda _path, _current: [
        (40.958, empty, empty, empty),
        (0.05, empty, empty, empty),
        (0.13, empty, empty, empty),
        (1.047, empty, empty, empty),
    ])

    inspected = items.inspect_map_file(path)

    assert inspected.run_count == 3
    assert inspected.speeds_mps == pytest.approx((0.05, 0.13, 1.047))


def test_v091_gui_standard_layout(monkeypatch, tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6 import QtCore, QtWidgets
    import pyqtgraph as pg
    from cdc_analyzer.gui_release_v091 import _build_release_gui_classes_v091

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    window = _build_release_gui_classes_v091()()
    pages = window.dynamic_pages
    files, result = _result(monkeypatch, tmp_path)
    pages.map_files = files
    pages.map_result = result
    pages._refresh_map_file_table()
    pages._fill_table(pages.map_force_velocity_table, result.force_velocity_table)
    pages.refresh_map_plots()

    assert pages.map_soft_current.value() == pytest.approx(0.3)
    assert pages.map_hard_current.value() == pytest.approx(1.6)
    assert pages.map_show_points.isChecked()
    assert pages.map_file_table.editTriggers() == QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
    assert not hasattr(pages, "map_add_button")
    assert pages.map_linearity_plot.backgroundBrush().color().name() == "#ffffff"
    linearity = pages.map_linearity_plot.getItem(0, 0)
    dashed = [curve for curve in linearity.listDataItems() if curve.opts["pen"].style() == QtCore.Qt.PenStyle.DashLine]
    assert len(dashed) == 2
    assert pages.map_spread_plot.getItem(0, 0) is not None
    assert pages.map_spread_plot.getItem(1, 0) is None
    bars = [item for item in pages.map_spread_plot.getItem(0, 0).items if isinstance(item, pg.BarGraphItem)]
    assert len(bars) == 2
    assert all(np.asarray(bar.opts["x"]) == pytest.approx([0.0, 1.0]) for bar in bars)
    assert isinstance(pages._map_spread_right_view, pg.ViewBox)
    fv_curves = pages.map_force_velocity_plot.getItem(0, 0).listDataItems()
    fi_curves = pages.map_force_current_plot.getItem(0, 0).listDataItems()
    assert fv_curves and fi_curves
    assert all(curve.opts["pen"].style() == QtCore.Qt.PenStyle.SolidLine for curve in fv_curves + fi_curves)
    assert all(curve.opts["connect"] == "all" for curve in fv_curves + fi_curves)
    assert all(curve.opts["symbol"] == "o" for curve in fv_curves + fi_curves)
    pages.map_show_points.setChecked(False)
    app.processEvents()
    fv_curves = pages.map_force_velocity_plot.getItem(0, 0).listDataItems()
    fi_curves = pages.map_force_current_plot.getItem(0, 0).listDataItems()
    assert all(curve.opts["symbol"] is None for curve in fv_curves + fi_curves)
    assert pages.map_force_velocity_table.columnCount() == 5
    window.close()
    app.processEvents()


def test_current_packaged_gui_is_v091():
    root = Path(__file__).resolve().parents[1]
    assert "gui_release_v095" in (root / "launcher.py").read_text()
    assert "gui_release_v095:main" in (root / "pyproject.toml").read_text()
    assert "APP_VERSION: V0.9.5" in (root / ".github" / "workflows" / "build-windows.yml").read_text()
