from decimal import Decimal
from services.fluxo_caixa import saldo_projetado

def test_saldo_projetado():
    assert saldo_projetado(Decimal("100"), Decimal("50"), Decimal("20")) == Decimal("130")
