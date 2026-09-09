from pathlib import Path

from core.database import Database


def test_registro_municipio_e_resumo(tmp_path: Path):
    db = Database(tmp_path / "atividade.db")
    db.upsert_municipio_activity(
        ano=2025, codigo_ibge="2900108", uf="BA", municipio="Abaíra",
        status_rreo="OK", status_fnde="SEM_PDF", status_geral="PROCESSADO",
        ultimo_erro="",
    )
    activity = db.get_activity_map(2025, ["2900108"])
    assert activity["2900108"]["status_geral"] == "PROCESSADO"
    assert activity["2900108"]["status_fnde"] == "SEM_PDF"
    summary = db.state_activity_summary(2025, "BA")
    assert summary["PROCESSADO"] == 1


def test_job_persistente(tmp_path: Path):
    db = Database(tmp_path / "jobs.db")
    db.upsert_job(
        job_id="teste", ano=2025, escopo="BRASIL", operacao="RREO e FNDE",
        status="EM_ANDAMENTO", total=5571, concluidos=12, erros=2, lote_atual=1,
        uf_atual="AC", municipio_atual="Acrelândia", master_blob="MASTER/teste.xlsx",
        mensagem="lote salvo",
    )
    row = db.get_job("teste")
    assert row is not None
    assert row["status"] == "EM_ANDAMENTO"
    assert row["concluidos"] == 12
    db.upsert_job(
        job_id="teste", ano=2025, escopo="BRASIL", operacao="RREO e FNDE",
        status="PAUSADO", total=5571, concluidos=24, erros=2, lote_atual=2,
        master_blob="MASTER/teste.xlsx", mensagem="pausado",
    )
    assert db.get_job("teste")["status"] == "PAUSADO"
