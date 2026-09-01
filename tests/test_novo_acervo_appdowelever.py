from core import checkpoint_json_nacional as checkpoint
from integrations import google_storage


def test_prefixo_appdowelever_monta_ano_estado_bimestre(monkeypatch):
    monkeypatch.setattr(google_storage, "RREO_SOURCE_ENABLED", True)
    monkeypatch.setattr(google_storage, "RREO_SOURCE_BUCKET", "appdowelever-arquivos")
    monkeypatch.setattr(google_storage, "RREO_SOURCE_BASE_PREFIX", "01_Arquivo_dos_Estados_RREO_e_FNDE/4_APPDOWELEVER/")
    monkeypatch.setattr(google_storage, "find_appdowelever_rreo_folder", lambda uf, year: "17_Tocantins_TO")
    captured = {}

    def fake_list(bucket, prefix):
        captured["bucket"] = bucket
        captured["prefix"] = prefix
        return [{"name": "RREO_Municipal_2025_Abreulandia-TO.pdf", "blob_name": prefix + "RREO_Municipal_2025_Abreulandia-TO.pdf", "size": 1, "updated": None}]

    monkeypatch.setattr(google_storage, "_list_pdfs_under_prefix_from_bucket", fake_list)
    result = google_storage.list_appdowelever_rreo_pdfs_by_uf("TO", 2025, 6)
    assert result
    assert captured["bucket"] == "appdowelever-arquivos"
    assert captured["prefix"] == "01_Arquivo_dos_Estados_RREO_e_FNDE/4_APPDOWELEVER/2025/17_Tocantins_TO/B6/"


def test_checkpoint_estado_tem_nome_estavel():
    name = checkpoint.state_blob_name(2025, "job:brasil/B6", "BA")
    assert name.endswith("/2025/job_brasil_B6/estados/BA.json")
