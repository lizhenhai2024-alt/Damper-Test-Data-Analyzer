import pytest

from cdc_analyzer.audi_test_program import IN_SCOPE_TESTS, AudiSpecimen, compile_audi_test_report


def test_report_follows_vref33_2_v25_sections_even_for_unordered_evidence():
    report = compile_audi_test_report(
        AudiSpecimen(regulated=True),
        [
            {"section": "21", "evidence": "spread.xlsx"},
            {"section": "4", "evidence": "normal.pvp"},
        ],
    )
    assert report["Section"].tolist() == [step.section for step in IN_SCOPE_TESTS]
    assert not {"5", "7", "9", "10", "11", "12"} & set(report["Section"])
    assert report.loc[report["Section"] == "4", "Evidence"].item() == "normal.pvp"
    assert report.loc[report["Section"] == "21", "Evidence"].item() == "spread.xlsx"
    assert report.loc[report["Section"] == "20", "Verdict"].item() == "pending"


def test_scope_and_project_limit_provenance():
    report = compile_audi_test_report(AudiSpecimen(regulated=False, monotube=False, air_spring=False))
    assert not report.loc[report["Section"] == "16", "Applicable"].item()
    assert not report.loc[report["Section"] == "18", "Applicable"].item()
    assert not report.loc[report["Section"] == "8.4", "Applicable"].item()
    assert report.loc[report["Section"] == "18", "Verdict"].item() == "not applicable"
    with pytest.raises(ValueError, match="project limit reference"):
        compile_audi_test_report(AudiSpecimen(regulated=True), [{"section": "20", "verdict": "pass"}])


def test_conditional_scope_stays_unknown_without_design_information():
    report = compile_audi_test_report(AudiSpecimen(regulated=True))
    assert report.loc[report["Section"] == "8.3", "Applicable"].item() is None
    assert report.loc[report["Section"] == "13.2", "Applicable"].item() is None
