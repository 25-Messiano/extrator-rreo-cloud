from modules.calendar_parser import parse_data_literal, parse_linha_calendario


def test_parse_ac():
    d = parse_data_literal("07/07/-4000aC")
    assert (d.dia, d.mes, d.ano_num) == (7, 7, -4000)


def test_parse_dc():
    d = parse_data_literal("08/08/2026dC")
    assert d.ano_num == 2026


def test_preserva_correspondencia():
    r = parse_linha_calendario("G.07/08/2026dC.SEX>M.27/09/2036dC|LN")
    assert r["data_g"] == "07/08/2026dC"
    assert r["data_m"] == "27/09/2036dC"
    assert r["marcacoes"] == "LN"
