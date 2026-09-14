from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from datetime import datetime

from sqlalchemy import select, text

from database.db import engine, session_scope
from models.entities import Tesouraria, ConfiguracaoSistema
from services.backup import gerar_backup_completo, validar_backup
from services.auditoria import registrar_auditoria

# Tabelas operacionais cuja propriedade é definida diretamente por tesouraria_id.
# Tabelas filhas (itens_conferencia, conciliacoes, carga_inicial_itens etc.) acompanham
# seus registros-pai por FK e não precisam ter o ID reescrito.
TABELAS_MIGRAVEIS = (
    "contas_financeiras",
    "saldos_iniciais",
    "centros_custo",
    "favorecidos",
    "lancamentos",
    "fluxo_projetado",
    "patrimonio",
    "importacoes_extrato",
    "fechamentos_mensais",
    "prestacoes_contas",
    "codigos_aplb",
)


def _central_e_destino(destino_id: int):
    with session_scope() as s:
        origem = s.scalar(select(Tesouraria).where(Tesouraria.codigo == "CENTRAL"))
        destino = s.get(Tesouraria, int(destino_id))
        if not origem:
            raise ValueError("Unidade estrutural CENTRAL não encontrada.")
        if not destino:
            raise ValueError("Tesouraria de destino não encontrada.")
        if destino.id == origem.id:
            raise ValueError("A CENTRAL não pode ser o destino da migração.")
        if destino.tipo != "FILIADA" or destino.ambiente != "PRODUCAO":
            raise ValueError("O destino deve ser uma Tesouraria FILIADA de PRODUÇÃO.")
        if not destino.ativa:
            raise ValueError("A tesouraria de destino está inativa.")
        return {
            "origem_id": origem.id,
            "origem_codigo": origem.codigo,
            "origem_nome": origem.nome,
            "destino_id": destino.id,
            "destino_codigo": destino.codigo,
            "destino_nome": destino.nome,
        }


def _scalar(conn, sql: str, **params):
    return conn.execute(text(sql), params).scalar()


def previsualizar_migracao(destino_id: int) -> dict:
    ctx = _central_e_destino(destino_id)
    origem_id = ctx["origem_id"]
    destino_id = ctx["destino_id"]

    contagens = {}
    destino_existente = {}
    with engine.connect() as conn:
        for tabela in TABELAS_MIGRAVEIS:
            contagens[tabela] = int(_scalar(conn, f"SELECT COUNT(*) FROM {tabela} WHERE tesouraria_id=:tid", tid=origem_id) or 0)
            destino_existente[tabela] = int(_scalar(conn, f"SELECT COUNT(*) FROM {tabela} WHERE tesouraria_id=:tid", tid=destino_id) or 0)

        linhas = conn.execute(text("""
            SELECT origem_bc, natureza, COUNT(*) AS qtd, COALESCE(SUM(valor),0) AS total
            FROM lancamentos
            WHERE tesouraria_id=:tid
            GROUP BY origem_bc, natureza
            ORDER BY origem_bc, natureza
        """), {"tid": origem_id}).mappings().all()
        totais = [
            {"origem": r["origem_bc"], "natureza": r["natureza"], "quantidade": int(r["qtd"]), "total": Decimal(str(r["total"] or 0))}
            for r in linhas
        ]

        # Conflitos que podem violar chaves únicas ao trocar apenas tesouraria_id.
        conflitos_fechamento = int(_scalar(conn, """
            SELECT COUNT(*) FROM fechamentos_mensais s
            WHERE s.tesouraria_id=:origem
              AND EXISTS (
                  SELECT 1 FROM fechamentos_mensais d
                  WHERE d.tesouraria_id=:destino AND d.ano=s.ano AND d.mes=s.mes
              )
        """, origem=origem_id, destino=destino_id) or 0)
        conflitos_prestacao = int(_scalar(conn, """
            SELECT COUNT(*) FROM prestacoes_contas s
            WHERE s.tesouraria_id=:origem
              AND EXISTS (
                  SELECT 1 FROM prestacoes_contas d
                  WHERE d.tesouraria_id=:destino
                    AND d.competencia=s.competencia AND d.versao=s.versao
              )
        """, origem=origem_id, destino=destino_id) or 0)

        itens_extrato = int(_scalar(conn, """
            SELECT COUNT(*) FROM itens_conferencia i
            JOIN importacoes_extrato e ON e.id=i.importacao_id
            WHERE e.tesouraria_id=:tid
        """, tid=origem_id) or 0)
        conciliacoes = int(_scalar(conn, """
            SELECT COUNT(*) FROM conciliacoes c
            JOIN lancamentos l ON l.id=c.lancamento_id
            WHERE l.tesouraria_id=:tid
        """, tid=origem_id) or 0)
        carga_inicial = int(_scalar(conn, """
            SELECT COUNT(*) FROM carga_inicial_itens c
            JOIN lancamentos l ON l.id=c.lancamento_id
            WHERE l.tesouraria_id=:tid
        """, tid=origem_id) or 0)

    total_diretos = sum(contagens.values())
    return {
        **ctx,
        "contagens": contagens,
        "destino_existente": destino_existente,
        "itens_conferencia_vinculados": itens_extrato,
        "conciliacoes_vinculadas": conciliacoes,
        "carga_inicial_vinculada": carga_inicial,
        "totais_lancamentos": totais,
        "total_registros_diretos": total_diretos,
        "conflitos_fechamento": conflitos_fechamento,
        "conflitos_prestacao": conflitos_prestacao,
        "pode_migrar": total_diretos > 0 and conflitos_fechamento == 0 and conflitos_prestacao == 0,
    }


def gerar_backup_pre_migracao(output_dir="data/backups") -> dict:
    path = gerar_backup_completo(output_dir=output_dir)
    validacao = validar_backup(path)
    if not validacao.get("valido"):
        raise RuntimeError("O backup pré-migração não passou na validação de integridade.")
    return {
        "path": str(path),
        "nome": Path(path).name,
        "tamanho": Path(path).stat().st_size,
        "validacao": validacao,
    }


def executar_migracao(destino_id: int, confirmacao: str, usuario_id: int, backup_path: str | None = None) -> dict:
    previa = previsualizar_migracao(destino_id)
    esperado = f"MIGRAR {previa['destino_codigo']}"
    if (confirmacao or "").strip().upper() != esperado.upper():
        raise ValueError(f"Confirmação inválida. Digite exatamente: {esperado}")
    if previa["conflitos_fechamento"] or previa["conflitos_prestacao"]:
        raise ValueError("Existem conflitos no destino. A migração foi bloqueada antes de alterar dados.")
    if previa["total_registros_diretos"] <= 0:
        raise ValueError("A CENTRAL não possui mais registros operacionais pendentes de migração.")

    # Backup obrigatório e validado. Se a tela já gerou um, valida novamente; senão cria agora.
    if backup_path:
        validacao = validar_backup(backup_path)
        if not validacao.get("valido"):
            raise RuntimeError("Backup informado é inválido.")
        backup_usado = str(backup_path)
    else:
        b = gerar_backup_pre_migracao()
        backup_usado = b["path"]

    origem_id = previa["origem_id"]
    destino_id = previa["destino_id"]
    alterados = {}

    # Uma única transação: ou todas as tabelas mudam de proprietário, ou nenhuma muda.
    with engine.begin() as conn:
        # Repete as verificações de conflito dentro da janela imediatamente anterior aos UPDATEs.
        cf = _scalar(conn, """
            SELECT COUNT(*) FROM fechamentos_mensais s
            WHERE s.tesouraria_id=:origem
              AND EXISTS (SELECT 1 FROM fechamentos_mensais d
                          WHERE d.tesouraria_id=:destino AND d.ano=s.ano AND d.mes=s.mes)
        """, origem=origem_id, destino=destino_id) or 0
        cp = _scalar(conn, """
            SELECT COUNT(*) FROM prestacoes_contas s
            WHERE s.tesouraria_id=:origem
              AND EXISTS (SELECT 1 FROM prestacoes_contas d
                          WHERE d.tesouraria_id=:destino
                            AND d.competencia=s.competencia AND d.versao=s.versao)
        """, origem=origem_id, destino=destino_id) or 0
        if cf or cp:
            raise ValueError("Conflito detectado no momento da migração. Nenhum dado foi alterado.")

        for tabela in TABELAS_MIGRAVEIS:
            r = conn.execute(text(
                f"UPDATE {tabela} SET tesouraria_id=:destino WHERE tesouraria_id=:origem"
            ), {"destino": destino_id, "origem": origem_id})
            alterados[tabela] = int(r.rowcount or 0)

    pos = previsualizar_migracao(destino_id)
    if pos["total_registros_diretos"] != 0:
        raise RuntimeError("A migração terminou, mas ainda há registros operacionais vinculados à CENTRAL. Verifique antes de continuar.")

    with session_scope() as s:
        marker = s.get(ConfiguracaoSistema, "V25_MIGRACAO_CENTRAL_CONCLUIDA")
        valor = f"SIM|DESTINO={previa['destino_codigo']}|ID={destino_id}|EM={datetime.utcnow().isoformat()}Z"
        if marker:
            marker.valor = valor
            marker.atualizado_em = datetime.utcnow()
        else:
            s.add(ConfiguracaoSistema(chave="V25_MIGRACAO_CENTRAL_CONCLUIDA", valor=valor))

    registrar_auditoria(
        usuario_id,
        "MIGRACAO_CENTRAL_PARA_FILIAL",
        "tesourarias",
        destino_id,
        anterior={"origem": previa["origem_codigo"], "contagens": previa["contagens"]},
        novo={"destino": previa["destino_codigo"], "alterados": alterados, "backup": Path(backup_usado).name},
        motivo="Separação da Central de Auditoria da operação financeira na V25.",
    )

    return {
        "sucesso": True,
        "origem": previa["origem_nome"],
        "destino": previa["destino_nome"],
        "destino_codigo": previa["destino_codigo"],
        "alterados": alterados,
        "backup": backup_usado,
        "totais_antes": previa["totais_lancamentos"],
        "executado_em": datetime.utcnow().isoformat() + "Z",
    }
