from pathlib import Path

from services.tenancy import app_version, tenant_identity_data


def test_identidade_filial_producao():
    x=tenant_identity_data({
        "nome":"Tesouraria APLB Araci", "codigo":"ARACI-01", "cidade":"ARACI",
        "uf":"BA", "ambiente":"PRODUCAO", "tipo":"FILIADA",
    })
    assert x["titulo_operacional"] == "TESOURARIA APLB ARACI"
    assert "ARACI-01" in x["linha_identificacao"]
    assert "ARACI/BA" in x["linha_identificacao"]
    assert x["ambiente_label"] == "PRODUÇÃO"


def test_identidade_ambiente_teste():
    x=tenant_identity_data({"nome":"AMBIENTE DE TESTE","codigo":"TESTE","ambiente":"TESTE"})
    assert x["icone"] == "🧪"
    assert x["ambiente_label"] == "AMBIENTE DE TESTE"


def test_dashboard_nao_tem_titulo_operacional_fixo():
    src=(Path(__file__).resolve().parents[1]/"pages/01_Dashboard.py").read_text(encoding="utf-8")
    assert 'dash-title\">TESOURARIA APLB<' not in src
    assert 'titulo_operacional' in src


def test_versao_v25_1():
    assert app_version() in ("V25.1","V25.2","V25.3", "V25.4", "V25.5", "V25.6", "V25.7", "V25.8", "V25.9", "V25.10", "V25.11", "V25.12", "V25.13", "V26", "V26.1", "V26.2", "V26.3", "V26.4", "V26.5", "V26.6", "V26.7", "V26.8", "V26.9", "V26.10")
