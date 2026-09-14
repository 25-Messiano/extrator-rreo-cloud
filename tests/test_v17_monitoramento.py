from database.db import init_db
from services.administracao import monitoramento_resumo

def test_monitoramento_v17_shape():
    init_db()
    r=monitoramento_resumo()
    assert "saude" in r and "alertas" in r and "historico_7d" in r
    assert set(["Sistema","PostgreSQL","Backup","IA / OpenAI","Backup externo"]).issubset(r["saude"])
    assert r["lancamentos_oficiais"] >= 0
    assert r["acessos_24h"] >= 0
