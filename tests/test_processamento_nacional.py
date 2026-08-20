from pathlib import Path
from time import sleep

from openpyxl import load_workbook

from core.processamento_lotes import BatchSettings, execute_parallel
from modules.mapeamento_nova_planilha import ABA_DESTINO, carregar_municipios_da_planilha

CODIGOS_UF = {
    "AC": "12", "AL": "27", "AP": "16", "AM": "13", "BA": "29", "CE": "23",
    "DF": "53", "ES": "32", "GO": "52", "MA": "21", "MT": "51", "MS": "50",
    "MG": "31", "PA": "15", "PB": "25", "PR": "41", "PE": "26", "PI": "22",
    "RJ": "33", "RN": "24", "RS": "43", "RO": "11", "RR": "14", "SC": "42",
    "SP": "35", "SE": "28", "TO": "17",
}


def test_planilha_cobre_as_27_ufs_e_brasilia():
    base = Path(__file__).resolve().parents[1] / "data" / "RREO-TCM+FNDE PLANILHA BASE.xlsx"
    wb = load_workbook(base, read_only=False, data_only=True)
    try:
        ws = wb[ABA_DESTINO]
        counts = {
            uf: len(carregar_municipios_da_planilha(ws, uf, prefixo))
            for uf, prefixo in CODIGOS_UF.items()
        }
    finally:
        wb.close()
    assert len(counts) == 27
    assert all(value > 0 for value in counts.values())
    assert sum(counts.values()) == 5571


def test_timeout_de_lote_nao_bloqueia_indefinidamente():
    def worker(value):
        if value == "lento":
            sleep(2)
        return value

    results = execute_parallel(["ok", "lento"], worker, max_workers=2, timeout_seconds=1)
    assert results[0] == ("ok", None)
    assert results[1][0] is None
    assert results[1][1] is not None


def test_configuracao_nacional_tem_timeout():
    settings = BatchSettings.from_mapping({"timeout_lote_segundos": 420})
    assert settings.batch_timeout_seconds == 420


def test_perfil_automatico_4_cpus():
    from core.recursos_execucao import recommended_profile

    profile = recommended_profile(4)
    assert profile.batch_size == 12
    assert profile.rreo_workers == 6
    assert profile.fnde_workers == 3
    assert profile.gemini_concurrency == 2


def test_batch_settings_automatico_usa_perfil_detectado(monkeypatch):
    import core.processamento_lotes as lotes

    monkeypatch.setattr(lotes, "detect_cpu_capacity", lambda: 4)
    settings = lotes.BatchSettings.from_mapping({"otimizacao_automatica": True})
    assert settings.detected_cpus == 4
    assert settings.profile_name == "Desempenho 4 CPUs"
    assert (settings.batch_size, settings.rreo_workers, settings.fnde_workers, settings.gemini_concurrency) == (12, 6, 3, 2)


def test_batch_settings_manual_preserva_configuracao(monkeypatch):
    import core.processamento_lotes as lotes

    monkeypatch.setattr(lotes, "detect_cpu_capacity", lambda: 4)
    settings = lotes.BatchSettings.from_mapping({
        "otimizacao_automatica": False,
        "tamanho_lote": 9,
        "workers_rreo": 3,
        "workers_fnde": 2,
        "gemini_concorrencia": 1,
    })
    assert settings.profile_name == "Manual"
    assert (settings.batch_size, settings.rreo_workers, settings.fnde_workers, settings.gemini_concurrency) == (9, 3, 2, 1)
