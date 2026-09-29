"""Ordered Audi VR-EF-33-2 v2.5 test program and result coverage.

The chapter order is a reporting order. The standard defines additional
within-test sequences; it does not establish that every chapter must be run
chronologically on the same specimen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import pandas as pd


STANDARD = "AUDI VR-EF-33-2"
VERSION = "2.5 (2020-07-30)"


@dataclass(frozen=True)
class AudiTest:
    section: str
    title: str
    scope: str = "all"
    analyzer: str | None = None


# Section 1 of VR-EF-33-2 v2.5 is the source for applicability. Conditional
# tests require the actual damper design or project specification to decide.
AUDI_TESTS: tuple[AudiTest, ...] = (
    AudiTest("4", "常温特性曲线", analyzer="force_curve"),
    AudiTest("5", "里程后特性曲线"),
    AudiTest("6", "高活塞速度特性曲线"),
    AudiTest("7", "热、耐久与冷态特性曲线"),
    AudiTest("8.1", "无侧向力摩擦"),
    AudiTest("8.2", "有侧向力摩擦"),
    AudiTest("8.3", "夹持状态摩擦", scope="clamped_monotube"),
    AudiTest("8.4", "空气弹簧压力下摩擦", scope="air_spring"),
    AudiTest("8.5", "激励后重复摩擦"),
    AudiTest("9", "高速耐久（2.5 m/s）"),
    AudiTest("10", "高速强度（Ramp）"),
    AudiTest("11", "AUDI 磨损试验"),
    AudiTest("12", "设定行为"),
    AudiTest("13.1", "动态低温密封"),
    AudiTest("13.2", "静态低温密封", scope="monotube_or_project"),
    AudiTest("13.3", "近用户工况低温密封", scope="monotube_or_project"),
    AudiTest("14", "发泡试验"),
    AudiTest("15", "阻尼力迟滞与不连续性"),
    AudiTest("16", "边缘敏感性", scope="regulated", analyzer="edge_sensitivity"),
    AudiTest("17", "频率响应", analyzer="frequency_response"),
    AudiTest("18", "切换时间", scope="regulated", analyzer="response"),
    AudiTest("19", "切换迟滞", scope="regulated", analyzer="switch_hysteresis"),
    AudiTest("20", "电流—阻尼力线性", scope="regulated", analyzer="current_map"),
    AudiTest("21", "阻尼力范围与放大倍数", scope="regulated", analyzer="current_map"),
    AudiTest("22.1", "正弦 Clatter 声学试验"),
    AudiTest("22.2", "Pink Clatter 声学试验"),
)

_BY_SECTION = {test.section: test for test in AUDI_TESTS}
EXCLUDED_DURABILITY_SECTIONS = frozenset({"5", "7", "9", "10", "11", "12"})
IN_SCOPE_TESTS = tuple(test for test in AUDI_TESTS if test.section not in EXCLUDED_DURABILITY_SECTIONS)


@dataclass(frozen=True)
class AudiSpecimen:
    regulated: bool
    monotube: bool | None = None
    clamped_installation: bool | None = None
    air_spring: bool | None = None
    project_required_sections: frozenset[str] = frozenset()


def applicability(test: AudiTest, specimen: AudiSpecimen) -> bool | None:
    """Return True/False or None when a design-dependent scope is unknown."""
    if test.section in specimen.project_required_sections:
        return True
    if test.scope == "all":
        return True
    if test.scope == "regulated":
        return specimen.regulated
    if test.scope == "conventional":
        return not specimen.regulated
    if test.scope == "clamped_monotube":
        if specimen.monotube is False or specimen.clamped_installation is False:
            return False
        if specimen.monotube is None or specimen.clamped_installation is None:
            return None
        return True
    if test.scope == "air_spring":
        return specimen.air_spring
    if test.scope == "monotube_or_project":
        return specimen.monotube
    raise ValueError(f"Unknown Audi test scope: {test.scope}")


def compile_audi_test_report(
    specimen: AudiSpecimen,
    records: Sequence[Mapping[str, object]] = (),
) -> pd.DataFrame:
    """Summarize test evidence in standard order without inventing a verdict.

    A recorded Pass/Fail verdict needs an explicit project requirement reference;
    the Audi standard delegates many numerical limits to the project LAH.
    """
    by_section: dict[str, Mapping[str, object]] = {}
    for record in records:
        section = str(record.get("section", ""))
        if section not in _BY_SECTION:
            raise ValueError(f"Unknown Audi test section: {section}")
        if section in EXCLUDED_DURABILITY_SECTIONS:
            raise ValueError(f"Audi durability section is excluded: {section}")
        if section in by_section:
            raise ValueError(f"Duplicate Audi test section: {section}")
        verdict = str(record.get("verdict", "pending"))
        if verdict not in {"pending", "pass", "fail"}:
            raise ValueError(f"Invalid verdict for section {section}: {verdict}")
        if verdict != "pending" and not str(record.get("limit_reference", "")).strip():
            raise ValueError(f"Section {section} needs a project limit reference for a verdict")
        by_section[section] = record

    rows = []
    for test in IN_SCOPE_TESTS:
        applies = applicability(test, specimen)
        record = by_section.get(test.section, {})
        rows.append({
            "Section": test.section,
            "Test": test.title,
            "Applicable": applies,
            "Analyzer": test.analyzer or "manual evidence",
            "Verdict": str(record.get("verdict", "pending")) if applies is not False else "not applicable",
            "Evidence": str(record.get("evidence", "")),
            "Limit Reference": str(record.get("limit_reference", "")),
            "Notes": str(record.get("notes", "")),
        })
    return pd.DataFrame(rows)

