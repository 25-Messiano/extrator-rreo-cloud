from core.identificacao_arquivos import identificar_municipio, identificar_uf
from core.indice_fnde import build_fnde_index
from core.indice_rreo import build_rreo_index, localizar_por_municipio
from integrations import google_storage


MUNICIPIOS_MG = [
    {"codigo_ibge": "3153905", "nome": "Raposos", "uf": "MG"},
    {"codigo_ibge": "3154606", "nome": "Ribeirão das Neves", "uf": "MG"},
]


def test_raposos_fnde_com_ibge_e_identificado():
    nome = "FNDE_2025_3153905_Raposos - MG.pdf"
    r = identificar_municipio(nome, MUNICIPIOS_MG, "MG")
    assert r.codigo_ibge == "3153905"
    assert r.municipio == "Raposos"
    assert r.uf == "MG"
    assert r.metodo == "IBGE"


def test_fnde_sem_ibge_usa_nome_e_uf():
    files = [{"name": "FNDE_2025_Raposos - MG.pdf", "blob_name": "x", "size": 10}]
    idx = build_fnde_index(files, "MG", MUNICIPIOS_MG)
    assert "3153905" in idx["por_ibge"]
    assert idx["por_ibge"]["3153905"]["metodo_identificacao"] in {"NOME_NORMALIZADO", "SIMILARIDADE"}


def test_rreo_unificado_localiza_por_ibge_ou_nome():
    files = [{"name": "RREO_MUNICIPAL_2025_3153905_Raposos-MG.pdf", "blob_name": "r", "size": 10}]
    idx = build_rreo_index(files, "MG", MUNICIPIOS_MG)
    item = localizar_por_municipio(idx, "Raposos", "MG", "3153905")
    assert item is not None
    assert item["name"].endswith("Raposos-MG.pdf")


def test_pasta_com_ano_depois_da_uf_e_identificada():
    assert identificar_uf("31_Minas Gerais_MG_2025") == "MG"
    assert identificar_uf("FNDE_Minas_Gerais_MG_2025") == "MG"


def test_fallback_fnde_varre_ano_e_filtra_por_ibge(monkeypatch):
    raposos = {
        "name": "FNDE_2025_3153905_Raposos - MG.pdf",
        "blob_name": "01_Arquivo_dos_Estados_RREO_e_FNDE/02_FNDE/FNDE_2025/pasta_incomum/FNDE_2025_3153905_Raposos - MG.pdf",
        "size": 100,
        "updated": None,
    }
    bahia = {
        "name": "FNDE_2025_2910800_Feira de Santana - BA.pdf",
        "blob_name": "01_Arquivo_dos_Estados_RREO_e_FNDE/02_FNDE/FNDE_2025/outra/FNDE_2025_2910800_Feira de Santana - BA.pdf",
        "size": 100,
        "updated": None,
    }
    monkeypatch.setattr(google_storage, "find_fnde_folder", lambda uf, year: None)
    monkeypatch.setattr(google_storage, "_list_pdfs_under_prefix", lambda prefix: [raposos, bahia] if "FNDE_2025" in prefix else [])
    result = google_storage.list_fnde_pdfs_by_uf("MG", 2025)
    assert [x["name"] for x in result] == [raposos["name"]]


def test_fallback_rreo_usa_uf_no_caminho(monkeypatch):
    mg = {
        "name": "RREO_MUNICIPAL_2025_Raposos.pdf",
        "blob_name": "01_Arquivo_dos_Estados_RREO_e_FNDE/01_RREO/RREO_2025/31_Minas Gerais_MG_2025/RREO_MUNICIPAL_2025_Raposos.pdf",
        "size": 100,
        "updated": None,
    }
    sp = {
        "name": "RREO_MUNICIPAL_2025_Campinas.pdf",
        "blob_name": "01_Arquivo_dos_Estados_RREO_e_FNDE/01_RREO/RREO_2025/35_Sao Paulo_SP_2025/RREO_MUNICIPAL_2025_Campinas.pdf",
        "size": 100,
        "updated": None,
    }
    monkeypatch.setattr(google_storage, "find_rreo_folder", lambda uf, year: None)
    monkeypatch.setattr(google_storage, "_list_pdfs_under_prefix", lambda prefix: [mg, sp] if "RREO_2025" in prefix else [])
    result = google_storage.list_rreo_pdfs_by_uf("MG", 2025)
    assert [x["name"] for x in result] == [mg["name"]]
