from modules.reports import REPORT_TYPES, ReportRequest


def test_report_types_are_registered():
    expected = {"mensal", "anual", "correspondencia", "lua", "estacoes", "festas", "data", "intervalo", "auditoria"}
    assert expected == set(REPORT_TYPES)


def test_report_request_defaults():
    req = ReportRequest(tipo="mensal")
    assert req.calendario == "both"
    assert req.referencia == "g"
    assert req.lua is True
    assert req.festas is True
