from __future__ import annotations
import json
from sqlalchemy import select
from database.db import session_scope
from models.entities import Auditoria
from services.tenancy import get_active_tesouraria_id, tenant_where


def _json(data):
    if data is None:
        return None
    return json.dumps(data, ensure_ascii=False, default=str)


def registrar_auditoria(usuario_id, acao, entidade, registro_id=None, anterior=None, novo=None, motivo=None):
    with session_scope() as s:
        s.add(Auditoria(
            tesouraria_id=get_active_tesouraria_id(), usuario_id=usuario_id, acao=acao, entidade=entidade, registro_id=registro_id,
            anterior_json=_json(anterior), novo_json=_json(novo), motivo=motivo
        ))


def listar_auditoria(limit=500):
    with session_scope() as s:
        rows = s.scalars(select(Auditoria).where(tenant_where(Auditoria.tesouraria_id)).order_by(Auditoria.criado_em.desc()).limit(limit)).all()
        return [
            {
                "id": r.id, "data_hora": r.criado_em, "usuario_id": r.usuario_id,
                "acao": r.acao, "entidade": r.entidade, "registro_id": r.registro_id,
                "motivo": r.motivo, "anterior": r.anterior_json, "novo": r.novo_json,
            }
            for r in rows
        ]
