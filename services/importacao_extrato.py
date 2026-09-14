from __future__ import annotations
import hashlib
import io
import re
import unicodedata
from datetime import datetime, date
from decimal import Decimal

import pandas as pd
from sqlalchemy import select

from database.db import session_scope
from models.entities import ImportacaoExtrato, ItemConferencia, Lancamento, CodigoAPLB, Favorecido
from services.classificacao import sugerir_codigo
from services.financeiro import fingerprint, criar_lancamento
from services.auditoria import registrar_auditoria
from services.tenancy import get_active_tesouraria_id, tenant_where
from services.ai_extrato import classificar_movimentos, disponivel as ia_disponivel


def _norm_col(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Z0-9]+", "_", s.upper()).strip("_")


def _parse_money(v) -> Decimal | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float, Decimal)):
        return Decimal(str(v)).quantize(Decimal("0.01"))
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    s = re.sub(r"[^0-9.\-]", "", s)
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except Exception:
        return None


def _pick(cols, patterns):
    for p in patterns:
        for original, norm in cols.items():
            if p in norm:
                return original
    return None


def ler_excel_extrato(file_bytes: bytes) -> list[dict]:
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=xls.sheet_names[0])
    df = df.dropna(how="all")
    cols = {c: _norm_col(c) for c in df.columns}
    c_data = _pick(cols, ["DATA", "DT_MOV", "DT_LANC"])
    c_hist = _pick(cols, ["HISTORICO", "DESCRICAO", "LANCAMENTO", "DETALHE", "MEMO"])
    c_doc = _pick(cols, ["DOCUMENTO", "DOC", "NUMERO"])
    c_val = _pick(cols, ["VALOR", "MONTANTE"])
    c_cred = _pick(cols, ["CREDITO", "ENTRADA"])
    c_deb = _pick(cols, ["DEBITO", "SAIDA"])
    if not c_data or not (c_val or c_cred or c_deb):
        raise ValueError("Não consegui identificar automaticamente as colunas de Data e Valor/Crédito/Débito do extrato.")
    out=[]
    for _,r in df.iterrows():
        dt=pd.to_datetime(r.get(c_data),dayfirst=True,errors="coerce")
        if pd.isna(dt): continue
        hist=str(r.get(c_hist) if c_hist else "").strip()
        doc=str(r.get(c_doc) if c_doc and not pd.isna(r.get(c_doc)) else "").strip()
        if c_cred or c_deb:
            cred=_parse_money(r.get(c_cred)) if c_cred else None
            deb=_parse_money(r.get(c_deb)) if c_deb else None
            if cred not in (None,Decimal("0.00")):
                val=abs(cred);nat="ENTRADA"
            elif deb not in (None,Decimal("0.00")):
                val=abs(deb);nat="SAIDA"
            else: continue
        else:
            val=_parse_money(r.get(c_val))
            if val is None or val==0: continue
            nat="ENTRADA" if val>0 else "SAIDA";val=abs(val)
        out.append({"data":dt.date(),"historico":hist,"documento":doc,"valor":val,"natureza":nat})
    return out


def ler_csv_extrato(file_bytes: bytes) -> list[dict]:
    for sep in (";", ",", "\t"):
        try:
            df=pd.read_csv(io.BytesIO(file_bytes),sep=sep,encoding="utf-8")
            if len(df.columns)>1:
                bio=io.BytesIO();
                with pd.ExcelWriter(bio,engine="openpyxl") as w: df.to_excel(w,index=False)
                return ler_excel_extrato(bio.getvalue())
        except Exception:
            pass
    raise ValueError("CSV não reconhecido.")


def extrair_texto_pdf(file_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise ValueError("Leitura PDF indisponível: instale pypdf.") from exc
    reader=PdfReader(io.BytesIO(file_bytes))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def sugerir_movimentos_pdf(file_bytes: bytes) -> list[dict]:
    """Parser conservador: cria apenas linhas com data e valor claramente identificáveis."""
    txt=extrair_texto_pdf(file_bytes)
    out=[]
    rgx=re.compile(r"(?P<data>\d{2}/\d{2}/\d{4})\s+(?P<hist>.+?)\s+(?P<valor>-?\s*R?\$?\s*[\d\.]+,\d{2})(?:\s|$)")
    for line in txt.splitlines():
        m=rgx.search(" ".join(line.split()))
        if not m: continue
        try:dt=datetime.strptime(m.group("data"),"%d/%m/%Y").date()
        except Exception:continue
        val=_parse_money(m.group("valor"))
        if val is None or val==0:continue
        out.append({"data":dt,"historico":m.group("hist").strip(),"documento":"","valor":abs(val),"natureza":"ENTRADA" if val>0 else "SAIDA"})
    return out



def _natureza_por_historico(historico: str, padrao: str) -> str:
    n = _norm_col(historico).replace("_", " ")
    saida = ("TRANSFERENCIA ENVIADA", "TRANSFERIDO PARA POUPANCA", "PAGAMENTO DE BOLETO",
             "PGTO CONTA", "IMPOSTOS", "PIX ENVIADO", "TAR ", "TARIFA ",
             "CHEQUE COMPENSADO", "CHEQUE ", "TRANSF RECURSO E I")
    entrada = ("TRANSFERENCIA RECEBIDA", "TRANSFERIDO DA POUPANCA", "PIX RECEBIDO",
               "TED CREDITO EM CONTA", "TED DEVOLVIDA")
    if any(x in n for x in saida): return "SAIDA"
    if any(x in n for x in entrada): return "ENTRADA"
    return padrao

def _normaliza_texto(v):
    return " ".join((v or "").upper().strip().split())


def diagnosticar_duplicidade(data_mov, valor, codigo_id, origem_bc, natureza, especificacao, favorecido_id=None, favorecido=None, documento=None, conta_id=None):
    """EXATO bloqueia; POSSIVEL exige conferência; DISTINTO pode seguir."""
    with session_scope() as s:
        candidatos=s.scalars(select(Lancamento).where(
            Lancamento.data_movimento==data_mov,
            Lancamento.valor==Decimal(str(valor)).quantize(Decimal("0.01")),
            Lancamento.origem_bc==origem_bc,
            Lancamento.natureza==natureza,
            Lancamento.status.in_(["APROVADO","CONCILIADO","FECHADO","RASCUNHO"]),
            tenant_where(Lancamento.tesouraria_id),
        )).all()
        for l in candidatos:
            mesmo_codigo=(l.codigo_aplb_id or None)==(codigo_id or None)
            mesma_pessoa = bool(favorecido_id and l.favorecido_id==favorecido_id) or (not favorecido_id and _normaliza_texto(l.favorecido)==_normaliza_texto(favorecido))
            mesma_esp=_normaliza_texto(l.especificacao)==_normaliza_texto(especificacao)
            mesmo_doc=(not documento and not l.documento) or (_normaliza_texto(l.documento)==_normaliza_texto(documento))
            mesma_conta=(not conta_id or not l.conta_financeira_id or l.conta_financeira_id==conta_id)
            if mesmo_codigo and mesma_pessoa and mesma_esp and mesmo_doc and mesma_conta:
                return "DUPLICADO_EXATO", l.id
        if candidatos:
            return "POSSIVEL_DUPLICIDADE", candidatos[0].id
    return "DISTINTO", None


def _movimento_tecnico(mov: dict) -> bool:
    hist = _norm_col(mov.get("historico", ""))
    compacto = hist.replace("_", "")
    return "SALDO" in compacto


def criar_importacao(nome_arquivo: str, file_bytes: bytes, movimentos: list[dict], usuario_id: int, origem_bc="B", competencia=None, conta_id=None, centro_custo_id=None) -> int:
    if not competencia or not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", competencia):
        raise ValueError("Selecione o exercício e o mês de competência antes de importar.")
    file_hash=hashlib.sha256(file_bytes).hexdigest()
    with session_scope() as s:
        existente=s.scalar(select(ImportacaoExtrato.id).where(
            ImportacaoExtrato.tesouraria_id==get_active_tesouraria_id(),
            ImportacaoExtrato.hash_arquivo==file_hash,
            ImportacaoExtrato.status!="ARQUIVADO_TECNICO",
        ))
        if existente:
            raise ValueError(f"Este arquivo já foi importado nesta unidade (lote #{existente}).")
        imp=ImportacaoExtrato(tesouraria_id=get_active_tesouraria_id(),nome_arquivo=nome_arquivo,tipo_arquivo=nome_arquivo.rsplit(".",1)[-1].upper(),hash_arquivo=file_hash,competencia=competencia,conta_financeira_id=conta_id,centro_custo_id=centro_custo_id,status="EM_CONFERENCIA",criado_por=usuario_id)
        s.add(imp);s.flush();iid=imp.id
        for mov in movimentos:
            mov = dict(mov)
            mov["natureza"] = _natureza_por_historico(mov.get("historico", ""), mov.get("natureza", "ENTRADA"))
            cid,_,conf=sugerir_codigo(mov.get("historico",""),mov.get("favorecido",""))
            if mov.get("codigo_ia_id"):
                cid=mov["codigo_ia_id"]; conf=float(mov.get("confianca_ia",conf))
            fav_id=mov.get("favorecido_id")
            diag,similar=diagnosticar_duplicidade(mov["data"],mov["valor"],cid,origem_bc,mov["natureza"],mov.get("historico","") or "Movimento importado",fav_id,mov.get("favorecido"),mov.get("documento"),conta_id)
            fp=fingerprint(conta_id,mov["data"],mov["valor"],mov.get("documento",""),mov.get("historico",""),cid,origem_bc,mov["natureza"],fav_id,mov.get("favorecido"))
            if _movimento_tecnico(mov):
                status="MOVIMENTO_TECNICO"
                diag="MOVIMENTO_TECNICO"
                similar=None
            else:
                status="DUPLICADO_BLOQUEADO" if diag=="DUPLICADO_EXATO" else ("CONFERIR_DUPLICIDADE" if diag=="POSSIVEL_DUPLICIDADE" else "PENDENTE")
            s.add(ItemConferencia(importacao_id=iid,data_movimento=mov["data"],historico_original=mov.get("historico","") or "SEM HISTÓRICO",favorecido=mov.get("favorecido"),favorecido_id=fav_id,documento=mov.get("documento"),id_bancario=mov.get("id_bancario"),valor=mov["valor"],natureza=mov["natureza"],origem_bc=origem_bc,codigo_sugerido_id=cid,especificacao_sugerida=mov.get("especificacao_ia") or mov.get("historico","") or "Movimento importado",confianca=conf,status=status,fingerprint=fp,diagnostico_duplicidade=diag,lancamento_similar_id=similar,origem_classificacao=mov.get("origem_classificacao") or "DETERMINISTICO",justificativa_ia=mov.get("justificativa_ia"),modelo_ia=mov.get("modelo_ia")))
    registrar_auditoria(usuario_id,"CRIAR_IMPORTACAO","importacoes_extrato",iid,novo={"arquivo":nome_arquivo,"itens":len(movimentos),"competencia":competencia,"conta_id":conta_id,"centro_custo_id":centro_custo_id})
    return iid


def listar_importacoes(include_arquivadas=False):
    with session_scope() as s:
        q=select(ImportacaoExtrato).where(tenant_where(ImportacaoExtrato.tesouraria_id))
        if not include_arquivadas:
            q=q.where(ImportacaoExtrato.status!="ARQUIVADO_TECNICO")
        rows=s.scalars(q.order_by(ImportacaoExtrato.criado_em.desc())).all()
        return [{"id":x.id,"arquivo":x.nome_arquivo,"tipo":x.tipo_arquivo,"status":x.status,"competencia":x.competencia,"conta_id":x.conta_financeira_id,"centro_custo_id":x.centro_custo_id,"criado_em":x.criado_em,"liberado_em":x.liberado_em} for x in rows]


def listar_itens(importacao_id):
    with session_scope() as s:
        q=select(ItemConferencia,CodigoAPLB).join(ImportacaoExtrato, ImportacaoExtrato.id==ItemConferencia.importacao_id).outerjoin(CodigoAPLB,CodigoAPLB.id==ItemConferencia.codigo_sugerido_id).where(ItemConferencia.importacao_id==importacao_id, tenant_where(ImportacaoExtrato.tesouraria_id)).order_by(ItemConferencia.data_movimento,ItemConferencia.id)
        return [{"id":i.id,"data":i.data_movimento,"historico":i.historico_original,"favorecido":i.favorecido or "","favorecido_id":i.favorecido_id,"documento":i.documento or "","id_bancario":i.id_bancario or "","valor":float(i.valor),"natureza":i.natureza,"B/C":i.origem_bc,"codigo_id":i.codigo_sugerido_id,"codigo":c.codigo if c else "","confianca":float(i.confianca or 0),"status":i.status,"duplicidade":i.diagnostico_duplicidade or "","similar_id":i.lancamento_similar_id,"observacao":i.observacao_conferencia or "","lancamento_id":i.lancamento_gerado_id,"origem_classificacao":i.origem_classificacao or "DETERMINISTICO","justificativa_ia":i.justificativa_ia or "","modelo_ia":i.modelo_ia or ""} for i,c in s.execute(q).all()]


def reprocessar_importacao_com_ia(importacao_id: int, usuario_id: int) -> dict:
    """Reclassifica apenas itens ainda não decididos por humano. Não cria lançamentos.

    Usa os dados bancários já extraídos (data, histórico, documento, valor e natureza),
    preservando-os como fonte objetiva. A IA somente sugere código, pessoa e especificação.
    """
    if not ia_disponivel():
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    elegiveis={"PENDENTE","CONFERIR_DUPLICIDADE","DUPLICADO_BLOQUEADO","CORRIGIR"}
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,importacao_id)
        if not imp or imp.tesouraria_id != get_active_tesouraria_id():
            raise ValueError("Importação não encontrada na unidade ativa.")
        if not imp.competencia or not imp.conta_financeira_id:
            raise ValueError("Lote legado sem competência/conta não pode ser reprocessado. Ele deve permanecer arquivado para auditoria.")
        itens=s.scalars(select(ItemConferencia).where(ItemConferencia.importacao_id==importacao_id).order_by(ItemConferencia.id)).all()
        dados=[]; ids=[]
        for i in itens:
            if i.status not in elegiveis:
                continue
            dados.append({
                "data":i.data_movimento,"historico":i.historico_original or "",
                "documento":i.documento or "","id_bancario":i.id_bancario or "",
                "valor":i.valor,"natureza":i.natureza,
            })
            ids.append(i.id)
    if not dados:
        return {"processados":0,"preservados":len(itens),"baixa_confianca":0,"duplicados":0,"possiveis":0}
    classificados=classificar_movimentos(dados)
    baixa=duplicados=possiveis=0
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,importacao_id)
        for item_id,mov in zip(ids,classificados):
            i=s.get(ItemConferencia,item_id)
            if not i or i.status not in elegiveis:
                continue
            i.codigo_sugerido_id=mov.get("codigo_ia_id")
            i.favorecido_id=mov.get("favorecido_id")
            i.favorecido=mov.get("favorecido") or i.favorecido
            i.especificacao_sugerida=mov.get("especificacao_ia") or i.historico_original
            i.confianca=float(mov.get("confianca_ia",0))
            i.origem_classificacao=mov.get("origem_classificacao") or "OPENAI"
            i.justificativa_ia=mov.get("justificativa_ia")
            i.modelo_ia=mov.get("modelo_ia")
            diag,similar=diagnosticar_duplicidade(i.data_movimento,i.valor,i.codigo_sugerido_id,i.origem_bc,i.natureza,i.especificacao_sugerida,i.favorecido_id,i.favorecido,i.documento,imp.conta_financeira_id)
            i.diagnostico_duplicidade=diag;i.lancamento_similar_id=similar
            i.fingerprint=fingerprint(imp.conta_financeira_id,i.data_movimento,i.valor,i.documento,i.historico_original,i.codigo_sugerido_id,i.origem_bc,i.natureza,i.favorecido_id,i.favorecido)
            if diag=="DUPLICADO_EXATO":
                i.status="DUPLICADO_BLOQUEADO";duplicados+=1
            elif diag=="POSSIVEL_DUPLICIDADE":
                i.status="CONFERIR_DUPLICIDADE";possiveis+=1
            else:
                i.status="PENDENTE"
            if i.confianca<0.80: baixa+=1
    registrar_auditoria(usuario_id,"REPROCESSAR_IMPORTACAO_IA","importacoes_extrato",importacao_id,novo={"processados":len(classificados),"baixa_confianca":baixa,"duplicados":duplicados,"possiveis":possiveis})
    return {"processados":len(classificados),"preservados":len(itens)-len(classificados),"baixa_confianca":baixa,"duplicados":duplicados,"possiveis":possiveis}


def atualizar_item(item_id,status,codigo_id=None,especificacao=None,observacao=None,usuario_id=None,favorecido_id=None):
    with session_scope() as s:
        i=s.get(ItemConferencia,item_id)
        imp=s.get(ImportacaoExtrato,i.importacao_id) if i else None
        if not i or not imp or imp.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Item não encontrado na unidade ativa.")
        if codigo_id is not None:i.codigo_sugerido_id=codigo_id
        if especificacao is not None:i.especificacao_sugerida=especificacao
        if favorecido_id is not None:
            i.favorecido_id=favorecido_id
            f=s.get(Favorecido,favorecido_id); i.favorecido=f.nome if f else i.favorecido
        i.status=status;i.observacao_conferencia=observacao
    registrar_auditoria(usuario_id,"CONFERIR_ITEM","itens_conferencia",item_id,novo={"status":status,"codigo_id":codigo_id})


def liberar_importacao(importacao_id,usuario_id):
    criados=[];duplicados=0
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,importacao_id)
        if not imp or imp.tesouraria_id != get_active_tesouraria_id():raise ValueError("Importação não encontrada na unidade ativa.")
        itens=s.scalars(select(ItemConferencia).where(ItemConferencia.importacao_id==importacao_id,ItemConferencia.status=="APROVADO")).all()
    for i in itens:
        try:
            origem_lote="IMPORTACAO_MOVIMENTO_PDF" if imp.tipo_arquivo=="PDF_MOVIMENTO" else "IMPORTACAO_EXTRATO"
            rid=criar_lancamento(i.data_movimento,i.codigo_sugerido_id,i.origem_bc,i.natureza,i.especificacao_sugerida or i.historico_original,i.valor,imp.conta_financeira_id,i.favorecido,i.documento,imp.competencia,"APROVADO",origem_lote,usuario_id,favorecido_id=i.favorecido_id,centro_custo_id=imp.centro_custo_id)
            with session_scope() as s:
                ii=s.get(ItemConferencia,i.id);ii.lancamento_gerado_id=rid;ii.status="LIBERADO"
            criados.append(rid)
        except ValueError as exc:
            if "duplicidade" in str(exc).lower():duplicados+=1
            else:raise
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,importacao_id);imp.status="LIBERADO";imp.liberado_por=usuario_id;imp.liberado_em=datetime.utcnow()
    registrar_auditoria(usuario_id,"LIBERAR_IMPORTACAO","importacoes_extrato",importacao_id,novo={"criados":len(criados),"duplicados":duplicados})
    return len(criados),duplicados


def atualizar_itens_em_massa(importacao_id, item_ids, status, usuario_id, observacao=None):
    """V26.7: decisão humana em massa, sem liberar automaticamente a base oficial."""
    permitidos={"APROVADO","CORRIGIR","IGNORADO","PENDENTE"}
    if status not in permitidos: raise ValueError("Status de conferência inválido.")
    ids={int(x) for x in (item_ids or [])}
    if not ids: return 0
    alterados=0
    with session_scope() as s:
        imp=s.get(ImportacaoExtrato,importacao_id)
        if not imp or imp.tesouraria_id != get_active_tesouraria_id(): raise ValueError("Importação não encontrada na unidade ativa.")
        itens=s.scalars(select(ItemConferencia).where(ItemConferencia.importacao_id==importacao_id,ItemConferencia.id.in_(ids))).all()
        for i in itens:
            if i.diagnostico_duplicidade=="DUPLICADO_EXATO" and status=="APROVADO":
                continue
            i.status=status
            if observacao is not None:i.observacao_conferencia=observacao
            alterados+=1
    registrar_auditoria(usuario_id,"CONFERIR_ITENS_MASSA","itens_conferencia",novo={"importacao_id":importacao_id,"status":status,"quantidade":alterados,"ids":sorted(ids)})
    return alterados
