from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from database.db import session_scope
from models.entities import ImportacaoExtrato, ItemConferencia, Lancamento, Conciliacao
from services.financeiro import STATUS_OFICIAIS
from services.auditoria import registrar_auditoria
from services.tenancy import tenant_where

STATUS_TECNICOS = {"MOVIMENTO_TECNICO", "IGNORADO_TECNICO", "ARQUIVADO_TECNICO"}


def _historico_tecnico(texto: str) -> bool:
    n = _norm(texto)
    compacto = n.replace(" ", "")
    return "SALDO" in compacto


def _natureza_extrato(item) -> str:
    """Corrige a direção de movimentos bancários legados usando palavras inequívocas do histórico.

    Isso não altera a base oficial nem depende da IA; serve para extratos antigos que foram
    importados antes de o parser distinguir débito/crédito corretamente.
    """
    n = _norm(getattr(item, "historico_original", ""))
    saida = (
        "TRANSFERENCIA ENVIADA", "TRANSFERIDO PARA POUPANCA", "PAGAMENTO DE BOLETO",
        "PGTO CONTA", "IMPOSTOS", "PIX ENVIADO", "TAR ", "TARIFA ",
        "CHEQUE COMPENSADO", "CHEQUE ", "TRANSF RECURSO E I"
    )
    entrada = (
        "TRANSFERENCIA RECEBIDA", "TRANSFERIDO DA POUPANCA", "PIX RECEBIDO",
        "TED CREDITO EM CONTA", "TED DEVOLVIDA"
    )
    if any(x in n for x in saida):
        return "SAIDA"
    if any(x in n for x in entrada):
        return "ENTRADA"
    return getattr(item, "natureza", None) or "ENTRADA"


def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def _tokens(s):
    return {x for x in _norm(s).split() if len(x) >= 4}


def _desempatar(item, candidatos):
    """Usa descrição/favorecido/documento somente se data+natureza+valor encontrou vários."""
    if len(candidatos) <= 1:
        return candidatos[0] if candidatos else None
    doc = _norm(item.documento)
    fav = _norm(item.favorecido)
    hist_tokens = _tokens(item.historico_original)
    scores = []
    for l in candidatos:
        score = 0.0
        if doc and doc == _norm(l.documento):
            score += 5.0
        if fav and fav == _norm(l.favorecido):
            score += 4.0
        lt = _tokens(l.especificacao)
        if hist_tokens and lt:
            score += len(hist_tokens & lt) / max(1, len(hist_tokens | lt))
        scores.append((score, l))
    scores.sort(key=lambda x: x[0], reverse=True)
    if not scores or scores[0][0] <= 0:
        return None
    if len(scores) == 1 or scores[0][0] >= scores[1][0] + 1.0:
        return scores[0][1]
    return None


def diagnostico_periodo(competencia: str, conta_id: int | None = None) -> dict:
    """Compara extrato x base por Data + Entrada/Saída + Valor e confere totais."""
    with session_scope() as s:
        qi = select(ItemConferencia, ImportacaoExtrato).join(
            ImportacaoExtrato, ImportacaoExtrato.id == ItemConferencia.importacao_id
        ).where(
            ImportacaoExtrato.competencia == competencia,
            tenant_where(ImportacaoExtrato.tesouraria_id),
            ImportacaoExtrato.status != "ARQUIVADO_TECNICO",
            ItemConferencia.origem_bc == "B",
            ~ItemConferencia.status.in_(list(STATUS_TECNICOS)),
        )
        if conta_id:
            qi = qi.where(ImportacaoExtrato.conta_financeira_id == conta_id)
        itens = [(i, imp) for i, imp in s.execute(qi).all() if not _historico_tecnico(i.historico_original)]

        ql = select(Lancamento).where(
            Lancamento.competencia == competencia,
            Lancamento.origem_bc == "B",
            Lancamento.status.in_(STATUS_OFICIAIS),
            tenant_where(Lancamento.tesouraria_id),
        )
        if conta_id:
            ql = ql.where(Lancamento.conta_financeira_id == conta_id)
        lancs = s.scalars(ql).all()

    extrato_tot = {"ENTRADA": Decimal("0"), "SAIDA": Decimal("0")}
    base_tot = {"ENTRADA": Decimal("0"), "SAIDA": Decimal("0")}
    for i, _ in itens:
        nat = _natureza_extrato(i)
        extrato_tot[nat] = extrato_tot.get(nat, Decimal("0")) + Decimal(i.valor)
    for l in lancs:
        base_tot[l.natureza] = base_tot.get(l.natureza, Decimal("0")) + Decimal(l.valor)

    base_index = defaultdict(list)
    for l in lancs:
        base_index[(l.data_movimento, l.natureza, Decimal(l.valor))].append(l)

    matches = []
    conciliaveis = ambiguos = sem_match = 0
    usados = set()
    for i, imp in itens:
        nat = _natureza_extrato(i)
        cand = [x for x in base_index[(i.data_movimento, nat, Decimal(i.valor))] if x.id not in usados]
        escolhido = cand[0] if len(cand) == 1 else _desempatar(i, cand)
        if escolhido:
            usados.add(escolhido.id)
            situacao = "CONCILIAVEL"
            conciliaveis += 1
        elif len(cand) > 1:
            situacao = "AMBIGUO"
            ambiguos += 1
        else:
            situacao = "SEM_CORRESPONDENCIA"
            sem_match += 1
        matches.append({
            "item_id": i.id,
            "data": i.data_movimento,
            "natureza": nat,
            "valor": float(i.valor),
            "historico": i.historico_original,
            "lancamento_id": escolhido.id if escolhido else None,
            "situacao": situacao,
            "candidatos": len(cand),
        })

    diario = defaultdict(lambda: {"extrato_entrada": Decimal("0"), "extrato_saida": Decimal("0"), "base_entrada": Decimal("0"), "base_saida": Decimal("0")})
    for i, _ in itens:
        nat = _natureza_extrato(i)
        diario[i.data_movimento]["extrato_entrada" if nat == "ENTRADA" else "extrato_saida"] += Decimal(i.valor)
    for l in lancs:
        diario[l.data_movimento]["base_entrada" if l.natureza == "ENTRADA" else "base_saida"] += Decimal(l.valor)
    linhas_diarias = []
    for d in sorted(diario):
        x = diario[d]
        linhas_diarias.append({
            "data": d,
            "entrada_extrato": float(x["extrato_entrada"]),
            "entrada_base": float(x["base_entrada"]),
            "dif_entrada": float(x["extrato_entrada"] - x["base_entrada"]),
            "saida_extrato": float(x["extrato_saida"]),
            "saida_base": float(x["base_saida"]),
            "dif_saida": float(x["extrato_saida"] - x["base_saida"]),
        })

    return {
        "competencia": competencia,
        "conta_id": conta_id,
        "totais": {
            "entrada_extrato": float(extrato_tot.get("ENTRADA", 0)),
            "entrada_base": float(base_tot.get("ENTRADA", 0)),
            "dif_entrada": float(extrato_tot.get("ENTRADA", 0) - base_tot.get("ENTRADA", 0)),
            "saida_extrato": float(extrato_tot.get("SAIDA", 0)),
            "saida_base": float(base_tot.get("SAIDA", 0)),
            "dif_saida": float(extrato_tot.get("SAIDA", 0) - base_tot.get("SAIDA", 0)),
        },
        "conciliaveis": conciliaveis,
        "ambiguos": ambiguos,
        "sem_correspondencia": sem_match,
        "matches": matches,
        "diario": linhas_diarias,
    }


def executar_conciliacao(competencia: str, usuario_id: int, conta_id: int | None = None):
    """Registra somente correspondências únicas/claras. Não cria lançamentos nem aprova itens."""
    diag = diagnostico_periodo(competencia, conta_id)
    gravadas = 0
    with session_scope() as s:
        for m in diag["matches"]:
            if m["situacao"] != "CONCILIAVEL" or not m["lancamento_id"]:
                continue
            c = s.scalar(select(Conciliacao).where(Conciliacao.lancamento_id == m["lancamento_id"]))
            if not c:
                c = Conciliacao(lancamento_id=m["lancamento_id"])
                s.add(c)
            c.importacao_item_id = m["item_id"]
            c.status = "CONCILIADO"
            c.conciliado_por = usuario_id
            c.conciliado_em = datetime.utcnow()
            c.observacao = "V14: data + entrada/saída + valor; descrição/favorecido/documento apenas para desempate."
            l = s.get(Lancamento, m["lancamento_id"])
            if l and l.status == "APROVADO":
                l.status = "CONCILIADO"
            gravadas += 1
    registrar_auditoria(usuario_id, "CONCILIACAO_V14", "conciliacoes", novo={
        "competencia": competencia,
        "conta_id": conta_id,
        "conciliadas": gravadas,
        "ambiguas": diag["ambiguos"],
        "sem_correspondencia": diag["sem_correspondencia"],
        "totais": diag["totais"],
    })
    return gravadas, diag
