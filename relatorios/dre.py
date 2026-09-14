from __future__ import annotations

import csv
import re
import unicodedata
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select, and_, or_

from database.db import session_scope
from models.entities import Lancamento, CodigoAPLB, GrupoDRE, GrupoCodigoVinculo
from services.tenancy import get_active_tesouraria_id, tenant_where
from services.financeiro import STATUS_OFICIAIS

ROOT = Path(__file__).resolve().parents[1]
REGRAS_PATH = ROOT / "data" / "dre_regras.csv"


def _norm(txt: str | None) -> str:
    if txt is None:
        raw = ""
    else:
        raw = str(txt)
        if raw.lower() == "nan":
            raw = ""
    txt2 = unicodedata.normalize("NFKD", raw)
    return "".join(ch for ch in txt2 if not unicodedata.combining(ch)).lower()


@lru_cache(maxsize=1)
def carregar_regras_dre() -> list[dict]:
    regras: list[dict] = []
    if not REGRAS_PATH.exists():
        return regras
    with REGRAS_PATH.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            regras.append({
                "prioridade": int(r.get("prioridade") or 9999),
                "grupo": (r.get("grupo") or "").strip(),
                "natureza": (r.get("natureza") or "").strip().upper(),
                "codigo": (r.get("codigo") or "").strip().zfill(4),
                "regex": _norm(r.get("regex") or ""),
                "observacao": (r.get("observacao") or "").strip(),
            })
    return sorted(regras, key=lambda x: x["prioridade"])


def grupo_por_regra(*, codigo: str | None, natureza: str, especificacao: str | None) -> str | None:
    cod = (codigo or "").strip().zfill(4)
    nat = (natureza or "").upper()
    texto = _norm(especificacao)
    for r in carregar_regras_dre():
        if r["natureza"] and r["natureza"] != nat:
            continue
        if r["codigo"] and r["codigo"] != cod:
            continue
        if r["regex"] and not re.search(r["regex"], texto, flags=re.IGNORECASE):
            continue
        return r["grupo"]
    return None


def _period_filter(inicio: date, fim: date):
    comp_ini = f"{inicio.year:04d}-{inicio.month:02d}"
    comp_fim = f"{fim.year:04d}-{fim.month:02d}"
    return or_(
        and_(Lancamento.competencia.is_not(None), Lancamento.competencia >= comp_ini, Lancamento.competencia <= comp_fim),
        and_(Lancamento.competencia.is_(None), Lancamento.data_movimento >= inicio, Lancamento.data_movimento <= fim),
    )


def _classificar_lancamentos(inicio: date, fim: date):
    filtro_periodo = _period_filter(inicio, fim)
    with session_scope() as s:
        lancs = s.execute(
            select(Lancamento, CodigoAPLB)
            .outerjoin(CodigoAPLB, CodigoAPLB.id == Lancamento.codigo_aplb_id)
            .where(filtro_periodo, Lancamento.status.in_(STATUS_OFICIAIS), tenant_where(Lancamento.tesouraria_id))
        ).all()
        grupos = s.scalars(
            select(GrupoDRE).where(GrupoDRE.ativo.is_(True)).order_by(GrupoDRE.ordem, GrupoDRE.codigo_grupo)
        ).all()
        vinc = s.scalars(select(GrupoCodigoVinculo).where(GrupoCodigoVinculo.ativo.is_(True))).all()

        mapa_vinc: dict[int, list[GrupoCodigoVinculo]] = {}
        for v in vinc:
            mapa_vinc.setdefault(v.codigo_aplb_id, []).append(v)

        grupo_por_codigo = {g.codigo_grupo: g for g in grupos}
        classificados = []
        for l, c in lancs:
            codigo = c.codigo if c else ""
            grupo = None

            # V19: a configuração feita na interface é a fonte principal.
            # Um código pode ter no máximo um vínculo DRE ativo; regras CSV antigas
            # ficam apenas como fallback temporário para códigos ainda não configurados.
            if c:
                candidatos=[]
                for v in mapa_vinc.get(c.id, []):
                    if v.vigencia_inicio and l.data_movimento < v.vigencia_inicio:
                        continue
                    if v.vigencia_fim and l.data_movimento > v.vigencia_fim:
                        continue
                    candidatos.append(v)
                if len(candidatos) > 1:
                    # Proteção de leitura: não soma um mesmo lançamento duas vezes.
                    # A tela de auditoria sinaliza a duplicidade para correção.
                    candidatos = sorted(candidatos, key=lambda v: v.id, reverse=True)[:1]
                if candidatos:
                    grupo = next((g for g in grupos if g.id == candidatos[0].grupo_dre_id), None)

            # V25.10: nao existe enquadramento automatico por numero de codigo.
            # Cada filial possui seu proprio Plano de Codigos e somente a Central
            # pode vincula-los a estrutura oficial da DRE. Codigo sem vinculo
            # permanece sem classificacao ate a Central decidir.
            classificados.append((l, c, grupo))
        return grupos, classificados


def dre_periodo(inicio: date, fim: date) -> list[dict]:
    grupos, classificados = _classificar_lancamentos(inicio, fim)
    totais = {g.id: Decimal("0") for g in grupos}
    for l, _c, grupo in classificados:
        if not grupo:
            continue
        # Mantém a convenção histórica do motor: receitas positivas e despesas negativas.
        sinal = Decimal("1") if l.natureza == "ENTRADA" else Decimal("-1")
        totais[grupo.id] += Decimal(l.valor) * sinal
    return [
        {"grupo": g.codigo_grupo, "descricao": g.nome, "valor": float(totais[g.id])}
        for g in grupos
    ]


def dre_detalhe_periodo(inicio: date, fim: date, grupo_codigo: str) -> list[dict]:
    _grupos, classificados = _classificar_lancamentos(inicio, fim)
    rows = []
    for l, c, grupo in classificados:
        if not grupo or grupo.codigo_grupo != grupo_codigo:
            continue
        rows.append({
            "data": l.data_movimento,
            "competencia": l.competencia,
            "codigo": c.codigo if c else "",
            "codigo_descricao": c.descricao if c else "",
            "B/C": l.origem_bc,
            "especificacao": l.especificacao,
            "valor": float(l.valor),
            "status": l.status,
        })
    return rows
