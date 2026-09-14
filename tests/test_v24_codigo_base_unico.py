from services.tenancy import (
    app_version, criar_tesouraria, listar_tesourarias, obter_tesouraria,
    atualizar_tesouraria, definir_tesouraria_ativa, ensure_default_tesourarias,
)
from database.db import init_db
from services.seed import seed_initial_data


def _setup():
    init_db(); seed_initial_data(); ensure_default_tesourarias()


def test_v24_todas_unidades_expoem_mesma_versao_do_codigo_base():
    _setup()
    assert app_version() in ("V24", "V25", "V25.1", "V25.2", "V25.3", "V25.4", "V25.5", "V25.6", "V25.7", "V25.8", "V25.9", "V25.10", "V25.11", "V25.12", "V25.13", "V26", "V26.1", "V26.2", "V26.3", "V26.4", "V26.5", "V26.6", "V26.7", "V26.8", "V26.9", "V26.10")
    rows = listar_tesourarias(None, True)
    assert rows
    assert {x["versao_sistema"] for x in rows} == {app_version()}


def test_v24_nova_filial_nasce_na_mesma_versao_sem_copia_de_app():
    _setup()
    codigo = "V24-FILIAL-UNICA"
    existentes = {x["codigo"] for x in listar_tesourarias(None, True)}
    if codigo not in existentes:
        tid = criar_tesouraria(
            codigo, "Filial V24", "FILIADA", "PRODUCAO", "", "Araci", "BA",
            "Responsável Teste", "75999999999", "teste@example.com", "Teste V24",
        )
    else:
        tid = next(x["id"] for x in listar_tesourarias(None, True) if x["codigo"] == codigo)
    t = obter_tesouraria(tid)
    assert t["versao_sistema"] == app_version()
    assert t["responsavel"] == "Responsável Teste"


def test_v24_cadastro_filial_pode_ser_editado_e_inativado():
    _setup()
    codigo = "V24-EDITAVEL"
    rows = listar_tesourarias(None, True)
    x = next((r for r in rows if r["codigo"] == codigo), None)
    tid = x["id"] if x else criar_tesouraria(codigo, "Filial Editável V24")
    atualizar_tesouraria(tid, cidade="Salvador", uf="ba", responsavel="Gestor V24")
    t = obter_tesouraria(tid)
    assert t["cidade"] == "Salvador" and t["uf"] == "BA" and t["responsavel"] == "Gestor V24"
    definir_tesouraria_ativa(tid, False)
    assert obter_tesouraria(tid)["ativa"] is False
    definir_tesouraria_ativa(tid, True)
    assert obter_tesouraria(tid)["ativa"] is True
