from __future__ import annotations

import csv
import hashlib
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, func

from database.db import session_scope
from models.entities import (
    CodigoAPLB,
    GrupoDRE,
    GrupoCodigoVinculo,
    ContaFinanceira,
    Lancamento,
    SaldoInicial,
    CargaInicialItem,
    Usuario, Auditoria, Tesouraria,
)


def _legacy_tenant_id():
    with session_scope() as s:
        return s.scalar(select(Tesouraria.id).where(Tesouraria.codigo=="CENTRAL"))

ROOT = Path(__file__).resolve().parents[1]

# Descrições recuperadas da relação oficial de códigos e dos demonstrativos 2026.
# Códigos novos ainda não presentes na relação de 29/07/2024 ficam explicitamente
# marcados como pendentes de consolidação, sem inventar classificação contábil.
DESCRICOES_COMPLEMENTARES = {
    "0008": "SERVIÇO DE LIMPEZA",
    "0010": "MATERIAL DE LIMPEZA",
    "0013": "ÁGUA MINERAL",
    "0014": "PREST. DE SERV. DIVER. PARA SEDE DA APLB",
    "0017": "PROD. ALIMENTÍCIOS/OUTROS PARA A COZINHA",
    "0021": "MANUT. DE EQUIP. E AP. ELETRÔNICOS DA APLB",
    "0022": "SERVIÇOS DE SISTEMAS / TESOURARIA E SECRETARIA",
    "0173": "XIII ASSEMBLEIA",
    "0174": "XIV ASSEMBLEIA",
    "0175": "XV ASSEMBLEIA",
    "0205": "V FESTA DO SERVIDOR",
    "0501": "REUNIÃO LOCAL",
    "0506": "CONSELHO SINDICAL",
    "0613": "SUPORTE / AJUDA DE CUSTO REGIONAL SISALEIRA",
    "0802": "RESSARC. DA GRATIF. DE DESLOCAMENTO",
    "0804": "DEVOLUÇÃO DE COBRANÇA INDEVIDA DE PLANO DE SAÚDE E ODONTOLÓGICO",
    "0812": "ESTORNO BANCÁRIO / CÓDIGO A CONSOLIDAR",
    "0820": "DESP. ESCRITÓRIO DE CONTABILIDADE",
    "0904": "MAT. PERMANENTE - BENS/CONSUMO DURÁVEIS PARA SEDE DA APLB",
    "0906": "PRESTAÇ. DE SERV. PARA CONSTRUÇÃO DO CTR",
    "0908": "MATERIAL DE CONSTRUÇÃO PARA A CONSTRUÇÃO DO CTR",
    "0910": "EMBASA - TERRENO - CTR",
    "0911": "INTERNET - TERRENO - CTR",
    "0914": "MATERIAIS DE LIMPEZA PARA O CTR",
    "0915": "MATERIAIS DIVERSOS PARA O CTR",
    "0916": "PRESTAÇÃO DE SERVIÇOS DIVERSOS NO TERRENO",
    "0918": "DESP. COM DOCUMENTAÇÃO TRABALHISTA",
    "0919": "DESP. TRABALHISTAS / GPS RECEITA FEDERAL - CÓDIGO A CONSOLIDAR",
}


def _seed_catalogos_basicos() -> None:
    with session_scope() as s:
        # V19: o catálogo oficial é auditável pela interface. O seed apenas
        # acrescenta códigos ausentes; nunca sobrescreve descrições/estado que
        # o administrador já tenha alterado no PostgreSQL.
        path = ROOT / "data" / "catalogo_codigos.csv"
        if path.exists():
            existentes = {c.codigo for c in s.scalars(select(CodigoAPLB).where(CodigoAPLB.tesouraria_id==_legacy_tenant_id())).all()}
            with path.open(encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    codigo=r["codigo"].strip()
                    if codigo in existentes:
                        continue
                    nat=(r.get("natureza_padrao") or "").strip().upper()
                    permite_entrada = nat in ("ENTRADA", "AMBOS") or codigo in ("0703", "0801", "0804")
                    # Regra V22: todo código de entrada pode ser usado também em saída.
                    permite_saida = nat in ("ENTRADA", "SAIDA", "AMBOS") or codigo in ("0703", "0801", "0804")
                    natureza_compat = "AMBOS" if permite_entrada and permite_saida else ("ENTRADA" if permite_entrada else "SAIDA")
                    s.add(CodigoAPLB(
                        tesouraria_id=_legacy_tenant_id(),
                        codigo=codigo,
                        descricao=r["descricao"].strip(),
                        natureza_padrao=natureza_compat,
                        permite_entrada=permite_entrada,
                        permite_saida=permite_saida,
                        ativo=str(r.get("ativo") or "1").strip().lower() not in ("0","false","nao","não"),
                    ))
                    existentes.add(codigo)

    # Grupos DRE oficiais: upsert idempotente. Isso permite ampliar a estrutura
    # em versões futuras sem apagar ou recriar vínculos existentes no PostgreSQL.
    with session_scope() as s:
        path = ROOT / "data" / "grupos_dre_oficiais.csv"
        if not path.exists():
            path = ROOT / "data" / "grupos_dre_exemplo.csv"
        if path.exists():
            existentes = {g.codigo_grupo: g for g in s.scalars(select(GrupoDRE)).all()}
            with path.open(encoding="utf-8-sig") as f:
                for idx, r in enumerate(csv.DictReader(f), start=1):
                    codigo = r["grupo"].strip()
                    nome = r["nome"].strip()
                    ordem = int(r.get("ordem") or idx)
                    g = existentes.get(codigo)
                    if g:
                        g.nome = nome
                        g.ordem = ordem
                        g.ativo = True
                    else:
                        s.add(GrupoDRE(codigo_grupo=codigo,nome=nome,ordem=ordem,ativo=True))

    # Mantém os vínculos simples já cadastrados. Regras condicionais/ambíguas
    # (código + descrição) são tratadas pelo motor relatorios/dre.py.
    with session_scope() as s:
        if not s.scalar(select(GrupoCodigoVinculo.id).limit(1)):
            groups = {g.codigo_grupo: g.id for g in s.scalars(select(GrupoDRE)).all()}
            codes = {c.codigo: c.id for c in s.scalars(select(CodigoAPLB).where(CodigoAPLB.tesouraria_id==_legacy_tenant_id())).all()}
            path = ROOT / "data" / "grupos_dre_exemplo.csv"
            if path.exists():
                with path.open(encoding="utf-8-sig") as f:
                    for r in csv.DictReader(f):
                        gid = groups.get(r["grupo"].strip())
                        for code in (r.get("codigos_exemplo") or "").split(";"):
                            cid = codes.get(code.strip())
                            if gid and cid:
                                s.add(GrupoCodigoVinculo(grupo_dre_id=gid,codigo_aplb_id=cid,ativo=True))


def _garantir_codigos_carga(path: Path) -> None:
    if not path.exists():
        return
    codigos_usados: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r.get("codigo"):
                codigos_usados.add(r["codigo"].strip())

    with session_scope() as s:
        existentes = {c.codigo for c in s.scalars(select(CodigoAPLB).where(CodigoAPLB.tesouraria_id==_legacy_tenant_id())).all()}
        for codigo in sorted(codigos_usados - existentes):
            s.add(
                CodigoAPLB(
                    tesouraria_id=_legacy_tenant_id(),
                    codigo=codigo,
                    descricao=DESCRICOES_COMPLEMENTARES.get(
                        codigo, f"CÓDIGO {codigo} - DESCRIÇÃO PENDENTE DE CONSOLIDAÇÃO"
                    ),
                    natureza_padrao="SAIDA", permite_entrada=False, permite_saida=True,
                    ativo=True,
                )
            )


def _seed_saldos_iniciais_2026() -> None:
    """Saldo de abertura de janeiro/2026, sem inflar entradas do mês."""
    with session_scope() as s:
        contas = {c.tipo: c for c in s.scalars(select(ContaFinanceira).where(ContaFinanceira.ativo.is_(True))).all()}
        valores = {"BANCO": Decimal("181.46"), "CAIXA": Decimal("13777.09")}
        for tipo, valor in valores.items():
            conta = contas.get(tipo)
            if not conta:
                continue
            existe = s.scalar(
                select(SaldoInicial.id).where(
                    SaldoInicial.conta_financeira_id == conta.id,
                    SaldoInicial.data_referencia == date(2026, 1, 1),
                )
            )
            if not existe:
                s.add(
                    SaldoInicial(
                        conta_financeira_id=conta.id,
                        data_referencia=date(2026, 1, 1),
                        valor=valor,
                        observacao="Saldo inicial consolidado do demonstrativo 01_2026.pdf",
                    )
                )


def seed_carga_inicial_2026() -> None:
    """Carrega os 281 movimentos dos PDFs 01/02/03 de 2026 uma única vez.

    A carga é atômica e idempotente. Lançamentos repetidos legítimos (por exemplo,
    tarifas bancárias iguais no mesmo dia) são preservados por um fingerprint de
    origem/linha, em vez do fingerprint heurístico usado na digitação manual.
    """
    path = ROOT / "data" / "carga_inicial_2026.csv"
    if not path.exists():
        return

    _garantir_codigos_carga(path)
    _seed_saldos_iniciais_2026()

    with session_scope() as s:
        qtd = s.scalar(
            select(func.count(Lancamento.id)).where(Lancamento.origem_lancamento == "CARGA_PDF_2026")
        ) or 0
        if qtd:
            return

        contas = {c.tipo: c.id for c in s.scalars(select(ContaFinanceira).where(ContaFinanceira.ativo.is_(True))).all()}
        codigos = {c.codigo: c.id for c in s.scalars(select(CodigoAPLB).where(CodigoAPLB.tesouraria_id==_legacy_tenant_id())).all()}
        admin_id = s.scalar(select(Usuario.id).where(Usuario.login == "admin"))

        with path.open(encoding="utf-8-sig", newline="") as f:
            linhas = list(csv.DictReader(f))

        for r in linhas:
            bc = r["origem_bc"].strip()
            conta_id = contas.get("BANCO" if bc == "B" else "CAIXA")
            codigo_id = codigos.get((r.get("codigo") or "").strip())
            seq = int(r["seq"])
            raw_fp = (
                f"CARGA_PDF_2026|{seq}|{r['arquivo_origem']}|{r['pagina']}|"
                f"{r['data_movimento']}|{r.get('codigo','')}|{bc}|{r['natureza']}|{r['valor']}"
            )
            fp = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()
            lanc = Lancamento(
                data_movimento=date.fromisoformat(r["data_movimento"]),
                competencia=r["competencia"],
                codigo_aplb_id=codigo_id,
                origem_bc=bc,
                natureza=r["natureza"],
                especificacao=r["especificacao"].strip(),
                valor=Decimal(r["valor"]),
                conta_financeira_id=conta_id,
                status="APROVADO",
                origem_lancamento="CARGA_PDF_2026",
                fingerprint=fp,
                criado_por=admin_id,
                criado_em=datetime.utcnow(),
            )
            s.add(lanc)
            s.flush()
            s.add(
                CargaInicialItem(
                    lancamento_id=lanc.id,
                    arquivo_origem=r["arquivo_origem"],
                    pagina=int(r["pagina"]),
                    seq_origem=seq,
                    saldo_apos=Decimal(r["saldo_apos"]) if r.get("saldo_apos") else None,
                )
            )



def _cancelar_lancamento_teste_35() -> None:
    """Cancela uma única carga manual de teste conhecida, sem apagar o histórico.

    Migração idempotente para o registro criado em 06/09/2026 durante a homologação.
    Só atua quando TODOS os campos de identificação conferem, evitando atingir outro
    lançamento legítimo de R$ 35,00.
    """
    with session_scope() as s:
        l=s.scalar(
            select(Lancamento).where(
                Lancamento.origem_lancamento=="MANUAL",
                Lancamento.data_movimento==date(2026,9,6),
                Lancamento.origem_bc=="C",
                Lancamento.natureza=="SAIDA",
                Lancamento.valor==Decimal("35.00"),
                func.lower(Lancamento.especificacao)=="abastecimento do uno",
                Lancamento.status.in_(("APROVADO","CONCILIADO")),
            )
        )
        if not l:
            return
        anterior={
            "status":l.status,"data":str(l.data_movimento),"valor":str(l.valor),
            "natureza":l.natureza,"origem_bc":l.origem_bc,"especificacao":l.especificacao,
        }
        l.status="CANCELADO"
        s.add(Auditoria(
            usuario_id=l.criado_por,
            acao="CANCELAR_LANCAMENTO_TESTE_HOMOLOGACAO",
            entidade="lancamentos",
            registro_id=l.id,
            anterior_json=str(anterior),
            novo_json='{"status": "CANCELADO"}',
            motivo="Lançamento de R$ 35,00 usado apenas para homologação; retirado dos resultados oficiais.",
        ))



def _legacy_seed_permitido() -> bool:
    from models.entities import ConfiguracaoSistema
    with session_scope() as s:
        marker=s.get(ConfiguracaoSistema,"V25_MIGRACAO_CENTRAL_CONCLUIDA")
        return not marker or not str(marker.valor or "").upper().startswith("SIM")

def _garantir_contas_legadas_sem_tenant():
    with session_scope() as s:
        tipos={str(t).upper() for t in s.scalars(select(ContaFinanceira.tipo).where(ContaFinanceira.ativo.is_(True))).all()}
        if "BANCO" not in tipos: s.add(ContaFinanceira(nome="Banco Principal",tipo="BANCO",ativo=True))
        if "CAIXA" not in tipos: s.add(ContaFinanceira(nome="Caixa",tipo="CAIXA",ativo=True))

def seed_initial_data():
    # V25.10: novas filiais nascem sem Plano de Codigos. O catalogo historico
    # so e semeado para instalacoes legadas ainda nao migradas.
    if _legacy_seed_permitido():
        _seed_catalogos_basicos()
        _garantir_contas_legadas_sem_tenant()
        seed_carga_inicial_2026()
        _cancelar_lancamento_teste_35()

