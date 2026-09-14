from __future__ import annotations

import hashlib
import io
import re
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select

from database.db import session_scope
from models.entities import ImportacaoExtrato, ItemConferencia, CodigoAPLB
from services.auditoria import registrar_auditoria
from services.financeiro import fingerprint
from services.importacao_extrato import diagnosticar_duplicidade
from services.tenancy import get_active_tesouraria_id

_DATE = re.compile(r"^(\d{2}/\d{2}/\d{4})\s*(\d{1,4})\s+([BC])\s+(.*)$", re.I)
_MONEY = re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)")
_SKIP = (
    "APLB - SINDICATO", "DELEGACIA SINDICAL", "DEMONSTRATIVO DO MOVIMENTO",
    "EXERCICIO:", "SALDOS BANCO/CAIXA", "PAGINA ", "TESOURARIA - APLB",
    "MES:", "SALDO INICIO", "SALDO FIM", "DIA CODIGO", "CAIXABANCO",
)


def _money(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", ".")).quantize(Decimal("0.01"))


def _texto_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("Leitura de PDF indisponível. Verifique a dependência pypdf.") from exc
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def _registros_textuais(data: bytes) -> list[str]:
    raw_lines = [" ".join(x.split()) for x in _texto_pdf(data).splitlines() if x.strip()]
    linhas=[]
    marker=re.compile(r"(?=\d{2}/\d{2}/\d{4}\s*\d{1,4}\s+[BC]\s+)", re.I)
    for linha in raw_lines:
        partes=[x.strip() for x in marker.split(linha) if x.strip()]
        linhas.extend(partes)
    out=[]; atual=""
    for linha in linhas:
        up=linha.upper()
        if _DATE.match(linha):
            if atual: out.append(atual)
            atual=linha; continue
        if not atual: continue
        if any(x in up for x in _SKIP): continue
        if re.search(r"\b(?:JANEIRO|FEVEREIRO|MARCO|MARÇO|ABRIL|MAIO|JUNHO|JULHO|AGOSTO|SETEMBRO|OUTUBRO|NOVEMBRO|DEZEMBRO)\b", up) and "R$" in up:
            continue
        atual += " " + linha
    if atual: out.append(atual)
    return out


def _normalizar_tail(s: str) -> str:
    # PDFs do modelo frequentemente colam o hífen da próxima coluna ao valor anterior.
    s = re.sub(r"(,\d{2})-(?=\s|$)", r"\1", s)
    s = re.sub(r"(?<=\s)-(?=\d)", "- ", s)
    return " ".join(s.split())


def _parse_colunas(resto: str):
    """Retorna descricao, EB, SB, EC, SC, saldo.

    O layout oficial tem quatro colunas financeiras + saldo. Célula vazia aparece como '-'.
    Trabalhamos de trás para frente para não confundir números da descrição (ex. 12/2025, 803.2).
    """
    s = _normalizar_tail(resto)
    token = re.compile(r"(?:^|\s)(-|(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})(?=\s|$)")
    matches = list(token.finditer(s))
    if len(matches) < 5:
        return None
    # Alguns PDFs repetem o saldo na linha seguinte; remove repetições finais idênticas.
    while len(matches) >= 6 and matches[-1].group(1) == matches[-2].group(1) and matches[-1].group(1) != "-":
        cut = matches[-1].start()
        s = s[:cut].rstrip()
        matches = list(token.finditer(s))
    tail = matches[-5:]
    # Só aceitamos se esses cinco tokens constituírem efetivamente o final do registro.
    if s[tail[-1].end():].strip():
        return None
    desc = s[:tail[0].start()].strip(" -")
    vals = [None if m.group(1) == "-" else _money(m.group(1)) for m in tail]
    return desc, vals[0], vals[1], vals[2], vals[3], vals[4]


def ler_movimento_pdf(data: bytes) -> list[dict]:
    """Lê o demonstrativo mensal Banco/Caixa usado historicamente pela APLB.

    Nunca grava nada. Linhas ambíguas são simplesmente omitidas e a UI informa a quantidade
    reconhecida para conferência humana antes da criação do lote.
    """
    movimentos: list[dict] = []
    for raw in _registros_textuais(data):
        m = _DATE.match(raw)
        if not m:
            continue
        try:
            dt = datetime.strptime(m.group(1), "%d/%m/%Y").date()
        except Exception:
            continue
        code = m.group(2).zfill(4)
        bc_decl = m.group(3).upper()
        parsed = _parse_colunas(m.group(4))
        if not parsed:
            continue
        desc, eb, sb, ec, sc, saldo = parsed
        cols = [("B", "ENTRADA", eb), ("B", "SAIDA", sb), ("C", "ENTRADA", ec), ("C", "SAIDA", sc)]
        for origem, natureza, valor in cols:
            if valor is None or valor == 0:
                continue
            movimentos.append({
                "data": dt, "codigo": code, "origem_bc": origem, "natureza": natureza,
                "historico": desc or f"Código {code}", "documento": "", "valor": abs(valor),
                "saldo_linha": saldo, "bc_declarado": bc_decl,
            })
    return movimentos


def competencia_do_lote(movimentos: list[dict]) -> str:
    if not movimentos:
        raise ValueError("Nenhum lançamento reconhecido no PDF.")
    from collections import Counter
    c=Counter(m["data"].strftime("%Y-%m") for m in movimentos)
    return c.most_common(1)[0][0]


def criar_importacao_movimento(nome_arquivo: str, file_bytes: bytes, movimentos: list[dict], usuario_id: int) -> int:
    if not movimentos:
        raise ValueError("Nenhum lançamento reconhecido no PDF.")
    competencia = competencia_do_lote(movimentos)
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    tid = get_active_tesouraria_id()
    with session_scope() as s:
        # mesmo arquivo na mesma unidade: não cria lote duplicado silenciosamente
        existente = s.scalar(select(ImportacaoExtrato.id).where(
            ImportacaoExtrato.tesouraria_id == tid,
            ImportacaoExtrato.hash_arquivo == file_hash,
            ImportacaoExtrato.status != "ARQUIVADO_TECNICO",
        ))
        if existente:
            raise ValueError(f"Este PDF já foi importado nesta unidade (lote #{existente}).")
        imp = ImportacaoExtrato(
            tesouraria_id=tid, nome_arquivo=nome_arquivo, tipo_arquivo="PDF_MOVIMENTO",
            hash_arquivo=file_hash, competencia=competencia, status="EM_CONFERENCIA",
            criado_por=usuario_id,
        )
        s.add(imp); s.flush(); iid = imp.id
        codigos = {c.codigo.zfill(4): c.id for c in s.scalars(select(CodigoAPLB).where(CodigoAPLB.tesouraria_id==get_active_tesouraria_id())).all()}
        for mov in movimentos:
            cid = codigos.get(str(mov.get("codigo", "")).zfill(4))
            diag, similar = diagnosticar_duplicidade(
                mov["data"], mov["valor"], cid, mov["origem_bc"], mov["natureza"],
                mov.get("historico") or "Movimento importado", documento=mov.get("documento"), conta_id=None,
            )
            status = "DUPLICADO_BLOQUEADO" if diag == "DUPLICADO_EXATO" else ("CONFERIR_DUPLICIDADE" if diag == "POSSIVEL_DUPLICIDADE" else "PENDENTE")
            fp = fingerprint(None, mov["data"], mov["valor"], mov.get("documento", ""), mov.get("historico", ""), cid, mov["origem_bc"], mov["natureza"])
            s.add(ItemConferencia(
                importacao_id=iid, data_movimento=mov["data"], historico_original=mov.get("historico") or "SEM HISTÓRICO",
                documento=mov.get("documento"), valor=mov["valor"], natureza=mov["natureza"], origem_bc=mov["origem_bc"],
                codigo_sugerido_id=cid, especificacao_sugerida=mov.get("historico") or "Movimento importado",
                confianca=1.0 if cid else 0.5, status=status, fingerprint=fp,
                diagnostico_duplicidade=diag, lancamento_similar_id=similar,
                origem_classificacao="PDF_MOVIMENTO",
            ))
    registrar_auditoria(usuario_id, "CRIAR_IMPORTACAO_MOVIMENTO_PDF", "importacoes_extrato", iid,
                        novo={"arquivo": nome_arquivo, "itens": len(movimentos), "competencia": competencia})
    return iid
