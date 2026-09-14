from datetime import date
from decimal import Decimal

from services.fluxo_caixa import (
    _fmt_data,
    _next_date,
    agregar_realizado,
    detectar_alertas_deficit,
    saldo_projetado,
)


def test_data_interface_formato_brasileiro():
    assert _fmt_data(date(2026, 9, 10)) == "10/09/2026"


def test_recorrencia_mensal_preserva_dia_quando_possivel():
    assert _next_date(date(2026, 1, 31), "MENSAL") == date(2026, 2, 28)
    assert _next_date(date(2026, 3, 15), "TRIMESTRAL") == date(2026, 6, 15)


def test_agregacao_realizado_entradas_saidas_saldo():
    rows = [
        {"data": date(2026, 1, 10), "natureza": "ENTRADA", "valor": 100.0},
        {"data": date(2026, 1, 11), "natureza": "SAIDA", "valor": 40.0},
    ]
    agg = agregar_realizado(rows, "MÊS", 50.0)
    assert len(agg) == 1
    assert agg[0]["entradas"] == 100.0
    assert agg[0]["saídas"] == 40.0
    assert agg[0]["resultado"] == 60.0
    assert agg[0]["saldo"] == 110.0


def test_alerta_deficit_e_formula_saldo():
    assert saldo_projetado(Decimal("100"), Decimal("20"), Decimal("150")) == Decimal("-30")
    alertas = detectar_alertas_deficit([{"período": "09/2026", "saldo": -30.0, "entradas": 20.0, "saídas": 150.0}])
    assert alertas[0]["tipo"] == "DÉFICIT"
