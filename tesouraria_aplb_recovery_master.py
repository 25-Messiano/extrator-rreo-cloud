"""TESOURARIA APLB - bootstrap mestre de recuperação.

Uso em contingência:
1) configurar DATABASE_URL (PostgreSQL Cloud preferencialmente);
2) configurar TESOURARIA_ADMIN_PASSWORD;
3) executar: python tesouraria_aplb_recovery_master.py

O script recria tabelas ausentes, garante o administrador inicial,
carrega cadastros-base e gera um snapshot estrutural JSON.
"""
from database.db import init_db, healthcheck
from services.security import ensure_admin
from services.seed import seed_initial_data
from services.backup import gerar_snapshot_config


def recover():
    init_db()
    ensure_admin()
    seed_initial_data()
    ok, backend = healthcheck()
    if not ok:
        raise RuntimeError(f"Falha de banco: {backend}")
    path = gerar_snapshot_config()
    print("TESOURARIA APLB - recuperação inicial concluída")
    print("Banco:", backend)
    print("Snapshot:", path)


if __name__ == "__main__":
    recover()
