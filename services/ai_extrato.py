from __future__ import annotations
import base64, json, os, re
from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher
from sqlalchemy import select

from config.settings import settings
from database.db import session_scope
from models.entities import CodigoAPLB, Favorecido
from services.tenancy import tenant_where, get_active_tesouraria_id

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"

MOV_SCHEMA = {
  "type":"object","additionalProperties":False,
  "properties":{"movimentos":{"type":"array","items":{"type":"object","additionalProperties":False,
    "properties":{
      "data":{"type":"string"},"historico":{"type":"string"},"documento":{"type":"string"},
      "id_bancario":{"type":"string"},"valor":{"type":"number"},"natureza":{"type":"string","enum":["ENTRADA","SAIDA"]}
    },"required":["data","historico","documento","id_bancario","valor","natureza"]}}},
  "required":["movimentos"]
}
CLASS_SCHEMA = {
  "type":"object","additionalProperties":False,
  "properties":{"classificacoes":{"type":"array","items":{"type":"object","additionalProperties":False,
    "properties":{
      "indice":{"type":"integer"},"codigo_aplb":{"type":"string"},"favorecido_codigo":{"type":"string"},
      "favorecido_nome":{"type":"string"},"especificacao":{"type":"string"},"confianca":{"type":"number"},
      "justificativa":{"type":"string"}
    },"required":["indice","codigo_aplb","favorecido_codigo","favorecido_nome","especificacao","confianca","justificativa"]}}},
  "required":["classificacoes"]
}

def disponivel():
    return bool(settings.openai_api_key)

def _client():
    if not disponivel(): raise RuntimeError("OPENAI_API_KEY não configurada.")
    from openai import OpenAI
    return OpenAI(api_key=settings.openai_api_key, timeout=90.0, max_retries=2)

def _response_json(input_content, schema, name, instructions):
    r=_client().responses.create(model=MODEL, store=False, instructions=instructions, input=input_content,
        text={"format":{"type":"json_schema","name":name,"strict":True,"schema":schema}})
    if not getattr(r,"output_text",None): raise RuntimeError("A IA não retornou conteúdo estruturado.")
    return json.loads(r.output_text)

def extrair_pdf_com_ia(file_bytes: bytes, filename="extrato.pdf") -> list[dict]:
    data=base64.b64encode(file_bytes).decode("ascii")
    content=[{"role":"user","content":[
      {"type":"input_text","text":"Extraia SOMENTE lançamentos bancários reais deste extrato. Ignore saldo anterior/final, cabeçalhos e totais. Valor sempre positivo; natureza ENTRADA ou SAIDA. Data em DD/MM/AAAA. Preserve histórico, documento e identificador bancário/NSU/EndToEndId quando existirem."},
      {"type":"input_file","filename":filename,"file_data":f"data:application/pdf;base64,{data}"}
    ]}]
    obj=_response_json(content,MOV_SCHEMA,"extrato_bancario","Você é um extrator contábil conservador. Não invente lançamentos nem dados ausentes; use string vazia para campos ausentes.")
    out=[]
    for m in obj["movimentos"]:
        try: dt=datetime.strptime(m["data"],"%d/%m/%Y").date(); val=Decimal(str(m["valor"])).quantize(Decimal("0.01"))
        except Exception: continue
        if val<=0: continue
        out.append({"data":dt,"historico":m["historico"].strip(),"documento":m["documento"].strip(),"id_bancario":m["id_bancario"].strip(),"valor":val,"natureza":m["natureza"],"origem_extracao":"IA_PDF"})
    return out

def _catalogos():
    with session_scope() as s:
        cod=s.scalars(select(CodigoAPLB).where(CodigoAPLB.ativo.is_(True), CodigoAPLB.tesouraria_id==get_active_tesouraria_id()).order_by(CodigoAPLB.codigo)).all()
        fav=s.scalars(select(Favorecido).where(Favorecido.ativo.is_(True), tenant_where(Favorecido.tesouraria_id)).order_by(Favorecido.nome)).all()
        return ([{"id":x.id,"codigo":x.codigo,"descricao":x.descricao} for x in cod],
                [{"id":x.id,"codigo":x.codigo_cadastro or "","nome":x.nome,"tipo":x.tipo} for x in fav])

def _classificar_lote(movimentos: list[dict], offset: int = 0) -> list[dict]:
    codigos,favs=_catalogos()
    payload=[{"indice":i,"data":str(m["data"]),"historico":m.get("historico","")[:600],"documento":m.get("documento","")[:120],"valor":float(m["valor"]),"natureza":m["natureza"]} for i,m in enumerate(movimentos)]
    prompt=json.dumps({"movimentos":payload,"codigos_aplb":codigos,"pessoas_entidades":favs},ensure_ascii=False)
    obj=_response_json(prompt,CLASS_SCHEMA,"classificacao_aplb",
      "Classifique movimentos bancários da Tesouraria APLB usando APENAS códigos e pessoas fornecidos no catálogo. Se não houver correspondência segura, codigo_aplb/favorecido_codigo/favorecido_nome devem ser vazios e confiança baixa. Nunca altere data, valor ou natureza. A justificativa deve ser curta e verificável. Confiança entre 0 e 1.")
    by_idx={x["indice"]:x for x in obj["classificacoes"]}
    cod_by={x["codigo"]:x for x in codigos}; fav_by_code={x["codigo"]:x for x in favs if x["codigo"]}
    fav_by_name={x["nome"].upper():x for x in favs}
    out=[]
    for i,m in enumerate(movimentos):
        z=by_idx.get(i,{})
        c=cod_by.get(z.get("codigo_aplb","")); f=fav_by_code.get(z.get("favorecido_codigo","")) or fav_by_name.get(z.get("favorecido_nome","").upper())
        conf=max(0.0,min(1.0,float(z.get("confianca",0))))
        n=dict(m); n.update({"codigo_ia_id":c["id"] if c else None,"codigo_ia":c["codigo"] if c else "","favorecido_id":f["id"] if f else None,"favorecido":f["nome"] if f else (z.get("favorecido_nome","") or ""),"especificacao_ia":z.get("especificacao","") or m.get("historico","") or "Movimento importado","confianca_ia":conf,"justificativa_ia":z.get("justificativa","")[:1000],"modelo_ia":MODEL,"origem_classificacao":"OPENAI"})
        out.append(n)
    return out

def classificar_movimentos(movimentos: list[dict]) -> list[dict]:
    if not movimentos: return []
    # Lotes pequenos reduzem risco de timeout e tornam reprocessamentos grandes mais estáveis.
    TAM_LOTE=30
    out=[]
    for ini in range(0,len(movimentos),TAM_LOTE):
        out.extend(_classificar_lote(movimentos[ini:ini+TAM_LOTE],ini))
    return out

def enriquecer_com_ia(movimentos: list[dict]) -> list[dict]:
    """IA sugere; dados bancários objetivos continuam sendo os do parser."""
    return classificar_movimentos(movimentos)
