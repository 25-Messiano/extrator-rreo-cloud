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


def test_rreo_exclusivo_appdowelever_sem_fallback(monkeypatch):
    monkeypatch.setattr(google_storage, "list_appdowelever_rreo_pdfs_by_uf", lambda uf, year, bimestre=None: [])
    result = google_storage.list_rreo_pdfs_by_uf("MG", 2025, 6)
    assert result == []

MUNICIPIOS_AL = [
    {"codigo_ibge": "2700102", "nome": "Água Branca", "uf": "AL"},
    {"codigo_ibge": "2708907", "nome": "Satuba", "uf": "AL"},
]


def test_fnde_nome_oficial_vence_ibge_errado_do_arquivo():
    files = [{
        "name": "FNDE_2025_2700102_Satuba - AL.pdf",  # codigo de Agua Branca, nome Satuba
        "blob_name": "x",
        "size": 10,
    }]
    idx = build_fnde_index(files, "AL", MUNICIPIOS_AL)
    assert "2708907" in idx["por_ibge"]
    assert "2700102" not in idx["por_ibge"]
    item = idx["por_ibge"]["2708907"]
    assert item["municipio_oficial"] == "Satuba"
    assert item["codigo_ibge"] == "2708907"
    assert item["codigo_ibge_arquivo"] == "2700102"
    assert item["ibge_arquivo_divergente"] is True
    assert item["metodo_identificacao"] == "NOME_OFICIAL_IBGE_ARQUIVO_DIVERGENTE"


def test_fnde_nome_oficial_localiza_mesmo_com_codigo_de_oito_digitos():
    files = [{
        "name": "FNDE_2025_22708907_Satuba - AL.pdf",
        "blob_name": "x",
        "size": 10,
    }]
    idx = build_fnde_index(files, "AL", MUNICIPIOS_AL)
    item = idx["por_ibge"]["2708907"]
    assert item["municipio_oficial"] == "Satuba"
    assert item["codigo_ibge_arquivo"] == "22708907"
    assert item["ibge_arquivo_divergente"] is True


def test_fnde_duplicado_identico_fica_fora_da_fila_e_auditado():
    files = [
        {"name": "FNDE_2025_2708907_Satuba - AL.pdf", "blob_name": "a", "size": 10, "md5_hash": "abc"},
        {"name": "FNDE_2025_2708907_Satuba - AL (copia).pdf", "blob_name": "b", "size": 10, "md5_hash": "abc"},
    ]
    idx = build_fnde_index(files, "AL", MUNICIPIOS_AL)
    assert list(idx["por_ibge"]) == ["2708907"]
    assert len(idx["duplicados"]) == 1
    assert idx["duplicados"][0]["status"] == "DUPLICADO_IDENTICO"
    assert idx["por_ibge"]["2708907"]["quantidade_candidatos"] == 2


def test_fnde_duplicado_diferente_nao_duplica_processamento_e_marca_conflito():
    files = [
        {"name": "FNDE_2025_2708907_Satuba - AL.pdf", "blob_name": "a", "size": 10, "md5_hash": "abc"},
        {"name": "FNDE_2025_2708907_Satuba - AL versao2.pdf", "blob_name": "b", "size": 12, "md5_hash": "xyz"},
    ]
    idx = build_fnde_index(files, "AL", MUNICIPIOS_AL)
    assert len(idx["por_ibge"]) == 1
    assert idx["por_ibge"]["2708907"]["duplicado_conflitante"] is True
    assert idx["duplicados"][0]["status"] == "DUPLICADO_CONFLITANTE"


def test_fallback_cloud_usa_pasta_uf_mesmo_se_codigo_filename_aponta_outro_estado(monkeypatch):
    item = {
        "name": "FNDE_2025_3153905_Satuba - AL.pdf",  # codigo MG errado
        "blob_name": "01_Arquivo_dos_Estados_RREO_e_FNDE/02_FNDE/FNDE_2025/27_Alagoas_AL/FNDE_2025_3153905_Satuba - AL.pdf",
        "size": 100,
        "updated": None,
    }
    monkeypatch.setattr(google_storage, "find_fnde_folder", lambda uf, year: None)
    monkeypatch.setattr(google_storage, "_list_year_pdfs_cached", lambda module, year: [item])
    result = google_storage.list_fnde_pdfs_by_uf("AL", 2025)
    assert [x["name"] for x in result] == [item["name"]]


def test_rreo_nome_oficial_vence_ibge_errado_sem_trocar_destino():
    files = [{
        "name": "RREO_MUNICIPAL_2025_2700102_Satuba-AL.pdf",
        "blob_name": "r",
        "size": 10,
    }]
    idx = build_rreo_index(files, "AL", MUNICIPIOS_AL)
    item = localizar_por_municipio(idx, "Satuba", "AL", "2708907")
    assert item is not None
    assert item["codigo_ibge"] == "2708907"
    assert item["municipio_oficial"] == "Satuba"
    assert item["codigo_ibge_arquivo"] == "2700102"
    assert item["ibge_arquivo_divergente"] is True
