from __future__ import annotations
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config.settings import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    # Importa todos os modelos antes do create_all.
    import models.entities  # noqa: F401
    Base.metadata.create_all(bind=engine)
    # Migrações aditivas V10: compatíveis com SQLite local e PostgreSQL Cloud.
    migrations = {
        "favorecidos": [
            ("tesouraria_id", "INTEGER"),
            ("codigo_cadastro", "VARCHAR(30)"), ("pix", "VARCHAR(180)"), ("banco", "VARCHAR(120)"),
            ("agencia", "VARCHAR(50)"), ("conta", "VARCHAR(50)"),
        ],
        "lancamentos": [("favorecido_id", "INTEGER"), ("centro_custo_id", "INTEGER"), ("tesouraria_id", "INTEGER")],
        "importacoes_extrato": [("competencia", "VARCHAR(7)"), ("conta_financeira_id", "INTEGER"), ("centro_custo_id", "INTEGER"), ("tesouraria_id", "INTEGER")],
        "usuarios": [("permissoes_json", "TEXT"), ("senha_versao", "INTEGER"), ("email", "VARCHAR(160)")],
        "contas_financeiras": [("tesouraria_id", "INTEGER")],
        "saldos_iniciais": [("tesouraria_id", "INTEGER")],
        "fluxo_projetado": [
            ("tesouraria_id", "INTEGER"),
            ("conta_financeira_id", "INTEGER"), ("centro_custo_id", "INTEGER"), ("favorecido_id", "INTEGER"),
            ("cenario", "VARCHAR(20)"), ("frequencia", "VARCHAR(30)"), ("recorrente", "BOOLEAN"),
            ("data_fim_recorrencia", "DATE"),
        ],
        "patrimonio": [
            ("tesouraria_id", "INTEGER"),
            ("estado_conservacao", "VARCHAR(40)"),
            ("vida_util_anos", "INTEGER"),
            ("fornecedor_id", "INTEGER"),
        ],
        # V26.6: anexos patrimoniais ficam persistidos no PostgreSQL e isolados por filial.
        "patrimonio_anexos": [
            ("tesouraria_id", "INTEGER"), ("patrimonio_id", "INTEGER"),
            ("nome_arquivo", "VARCHAR(255)"), ("mime_type", "VARCHAR(120)"),
            ("tamanho_bytes", "INTEGER"), ("conteudo", "BYTEA" if engine.dialect.name == "postgresql" else "BLOB"),
            ("descricao", "VARCHAR(255)"), ("ativo", "BOOLEAN"),
            ("criado_por", "INTEGER"), ("criado_em", "TIMESTAMP"), ("removido_em", "TIMESTAMP"),
        ],
        # V26.4: histórico patrimonial por competência preserva a transição de situação.
        "patrimonio_movimentos": [("situacao_anterior", "VARCHAR(30)"), ("situacao_nova", "VARCHAR(30)")],
        "fechamentos_mensais": [("tesouraria_id", "INTEGER")],
        "centros_custo": [("tesouraria_id", "INTEGER")],
        "auditoria": [("tesouraria_id", "INTEGER")],
        # V24: dados administrativos da filial. O código do aplicativo continua único e compartilhado.
        "tesourarias": [("responsavel", "VARCHAR(160)"), ("telefone", "VARCHAR(60)"), ("email", "VARCHAR(160)"), ("observacao", "TEXT")],
        # V22: permissões independentes por natureza no catálogo oficial.
        "codigos_aplb": [("permite_entrada", "BOOLEAN"), ("permite_saida", "BOOLEAN"), ("gera_patrimonio", "BOOLEAN"), ("tesouraria_id", "INTEGER")],
        "trabalhadores_folha": [("matricula", "VARCHAR(40)"), ("data_admissao", "DATE"), ("email", "VARCHAR(160)"),
            ("jornada", "VARCHAR(80)"), ("banco", "VARCHAR(120)"), ("agencia", "VARCHAR(40)"), ("conta", "VARCHAR(60)"),
            ("pix", "VARCHAR(180)"), ("centro_custo_id", "INTEGER"), ("dependentes", "INTEGER"), ("situacao", "VARCHAR(30)")],
        "eventos_folha": [("incidencia", "VARCHAR(180)"), ("codigo_aplb_id", "INTEGER"), ("centro_custo_obrigatorio", "BOOLEAN")],
        # V26.10: estruturas da Folha são aditivas e preservam histórico por vigência.
        "parametros_folha": [("tesouraria_id", "INTEGER")],
        "historico_salarial": [("tesouraria_id", "INTEGER")],
        "calendario_folha": [("tesouraria_id", "INTEGER")],
        "folha_snapshots": [("tesouraria_id", "INTEGER")],
        "checklist_folha": [("tesouraria_id", "INTEGER")],
        "itens_conferencia": [
            ("favorecido_id", "INTEGER"), ("id_bancario", "VARCHAR(180)"),
            ("diagnostico_duplicidade", "VARCHAR(30)"), ("lancamento_similar_id", "INTEGER"),
            ("origem_classificacao", "VARCHAR(30)"), ("justificativa_ia", "TEXT"), ("modelo_ia", "VARCHAR(80)"),
        ],
    }
    from sqlalchemy import inspect
    insp = inspect(engine)
    with engine.begin() as conn:
        for table, cols in migrations.items():
            existentes = {c["name"] for c in insp.get_columns(table)}
            for nome, tipo in cols:
                if nome not in existentes:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {nome} {tipo}"))
        conn.execute(text("UPDATE fluxo_projetado SET cenario='REALISTA' WHERE cenario IS NULL OR trim(cenario)=''"))
        conn.execute(text("UPDATE patrimonio SET situacao='ATIVO' WHERE situacao IS NULL OR trim(situacao)=''"))
        conn.execute(text("UPDATE fluxo_projetado SET frequencia=COALESCE(NULLIF(recorrencia,''),'ÚNICA') WHERE frequencia IS NULL OR trim(frequencia)=''"))
        conn.execute(text("UPDATE fluxo_projetado SET recorrente=FALSE WHERE recorrente IS NULL"))
        conn.execute(text("UPDATE usuarios SET senha_versao=1 WHERE senha_versao IS NULL"))
        # V26: e-mail é a identidade pública. Mantemos NULL para contas legadas até
        # a ativação única, mas impedimos dois usuários de compartilhar o mesmo e-mail.
        # Antes de criar o índice, abortamos de forma explícita se houver duplicidade legada.
        duplicados = conn.execute(text("""
            SELECT lower(trim(email)) AS email_norm, COUNT(*) AS qtd
            FROM usuarios
            WHERE email IS NOT NULL AND trim(email) <> ''
            GROUP BY lower(trim(email)) HAVING COUNT(*) > 1
        """)).fetchall()
        if duplicados:
            raise RuntimeError("Existem e-mails duplicados em usuários. Corrija antes de ativar o login por e-mail.")
        conn.execute(text("UPDATE usuarios SET email=lower(trim(email)) WHERE email IS NOT NULL AND trim(email)<>''"))
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_email_normalizado ON usuarios (lower(email)) WHERE email IS NOT NULL AND trim(email)<>''"))
        except Exception:
            # Bancos muito antigos podem não aceitar índice funcional; a camada de serviço
            # ainda aplica unicidade transacional antes de qualquer gravação.
            pass
        # V22: migração compatível com o catálogo já existente.
        # Todo código originalmente de ENTRADA pode operar também como SAÍDA.
        # Códigos originalmente de SAÍDA permanecem somente SAÍDA, salvo exceções
        # já reconhecidas como bidirecionais. O administrador pode alterar depois.
        conn.execute(text("UPDATE codigos_aplb SET permite_entrada = CASE WHEN UPPER(COALESCE(natureza_padrao,'')) IN ('ENTRADA','AMBOS') OR codigo IN ('0703','0801','0804') THEN TRUE ELSE FALSE END WHERE permite_entrada IS NULL"))
        conn.execute(text("UPDATE codigos_aplb SET permite_saida = CASE WHEN UPPER(COALESCE(natureza_padrao,'')) IN ('ENTRADA','SAIDA','AMBOS') OR codigo IN ('0703','0801','0804') THEN TRUE ELSE FALSE END WHERE permite_saida IS NULL"))
        conn.execute(text("UPDATE codigos_aplb SET natureza_padrao = CASE WHEN permite_entrada=TRUE AND permite_saida=TRUE THEN 'AMBOS' WHEN permite_entrada=TRUE THEN 'ENTRADA' WHEN permite_saida=TRUE THEN 'SAIDA' ELSE natureza_padrao END"))
        # V26.2: codigo patrimonial e configuravel por filial. Para bases antigas,
        # reconhece somente descricoes inequivocas; o administrador pode ajustar depois.
        conn.execute(text("UPDATE codigos_aplb SET gera_patrimonio=FALSE WHERE gera_patrimonio IS NULL"))
        conn.execute(text("UPDATE codigos_aplb SET gera_patrimonio=TRUE WHERE gera_patrimonio=FALSE AND (UPPER(COALESCE(descricao,'')) LIKE '%MAT. PERMANENTE%' OR UPPER(COALESCE(descricao,'')) LIKE '%MATERIAL PERMANENTE%' OR UPPER(COALESCE(descricao,'')) LIKE '%COMPRA DE IMÓVEL%' OR UPPER(COALESCE(descricao,'')) LIKE '%COMPRA DE IMOVEL%')"))
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_patrimonio_lancamento_origem ON patrimonio (lancamento_origem_id) WHERE lancamento_origem_id IS NOT NULL"))
        except Exception:
            pass
        # V25.10: cada filial possui seu proprio Plano de Codigos.
        # Codigos legados sao vinculados a filial que ja possui os lancamentos.
        # Em producao atual, isso aponta o catalogo historico para ARACI-01.
        try:
            conn.execute(text("""
                UPDATE codigos_aplb c SET tesouraria_id = x.tesouraria_id
                FROM (
                    SELECT codigo_aplb_id, MIN(tesouraria_id) AS tesouraria_id
                    FROM lancamentos
                    WHERE codigo_aplb_id IS NOT NULL AND tesouraria_id IS NOT NULL
                    GROUP BY codigo_aplb_id
                    HAVING COUNT(DISTINCT tesouraria_id)=1
                ) x
                WHERE c.id=x.codigo_aplb_id AND c.tesouraria_id IS NULL
            """))
        except Exception:
            # SQLite nao suporta UPDATE ... FROM em todas as versoes; fallback correlacionado.
            try:
                conn.execute(text("""
                    UPDATE codigos_aplb SET tesouraria_id=(
                        SELECT MIN(l.tesouraria_id) FROM lancamentos l
                        WHERE l.codigo_aplb_id=codigos_aplb.id AND l.tesouraria_id IS NOT NULL
                    ) WHERE tesouraria_id IS NULL AND (
                        SELECT COUNT(DISTINCT l2.tesouraria_id) FROM lancamentos l2
                        WHERE l2.codigo_aplb_id=codigos_aplb.id AND l2.tesouraria_id IS NOT NULL
                    )=1
                """))
            except Exception:
                pass
        # Codigos ainda sem dono vao para ARACI-01 quando essa filial existir.
        try:
            conn.execute(text("""
                UPDATE codigos_aplb SET tesouraria_id=(SELECT id FROM tesourarias WHERE codigo='ARACI-01' LIMIT 1)
                WHERE tesouraria_id IS NULL AND EXISTS (SELECT 1 FROM tesourarias WHERE codigo='ARACI-01')
            """))
        except Exception:
            pass
        # V25.2: chaves de unicidade operacionais passam a ser por tesouraria.
        # Filiais distintas podem usar o mesmo código de centro, número patrimonial,
        # código de favorecido e fingerprint sem interferir entre si.
        if engine.dialect.name == "postgresql":
            try:
                conn.execute(text("ALTER TABLE codigos_aplb DROP CONSTRAINT IF EXISTS codigos_aplb_codigo_key"))
                conn.execute(text("DROP INDEX IF EXISTS ix_codigos_aplb_codigo"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_codigos_aplb_codigo ON codigos_aplb (codigo)"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_codigo_tesouraria_codigo ON codigos_aplb (tesouraria_id, codigo) WHERE tesouraria_id IS NOT NULL"))
                conn.execute(text("ALTER TABLE favorecidos DROP CONSTRAINT IF EXISTS favorecidos_codigo_cadastro_key"))
                conn.execute(text("ALTER TABLE lancamentos DROP CONSTRAINT IF EXISTS lancamentos_fingerprint_key"))
                conn.execute(text("ALTER TABLE patrimonio DROP CONSTRAINT IF EXISTS patrimonio_numero_patrimonial_key"))
                conn.execute(text("ALTER TABLE centros_custo DROP CONSTRAINT IF EXISTS centros_custo_codigo_key"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_favorecido_tesouraria_codigo ON favorecidos (tesouraria_id, codigo_cadastro) WHERE codigo_cadastro IS NOT NULL"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_lancamento_tesouraria_fingerprint ON lancamentos (tesouraria_id, fingerprint) WHERE fingerprint IS NOT NULL"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_patrimonio_tesouraria_numero ON patrimonio (tesouraria_id, numero_patrimonial) WHERE numero_patrimonial IS NOT NULL"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_centro_tesouraria_codigo ON centros_custo (tesouraria_id, codigo)"))
            except Exception:
                pass

        # V23: fechamento mensal passa a ser exclusivo por tesouraria + competência.
        if engine.dialect.name == "postgresql":
            try:
                conn.execute(text("ALTER TABLE fechamentos_mensais DROP CONSTRAINT IF EXISTS uq_fechamento_periodo"))
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_fechamento_tesouraria_periodo ON fechamentos_mensais (tesouraria_id, ano, mes)"))
            except Exception:
                pass

        # V13: lotes legados sem competência/conta ficam fora da operação normal, preservados para auditoria.
        conn.execute(text("UPDATE importacoes_extrato SET status='ARQUIVADO_TECNICO' WHERE (competencia IS NULL OR conta_financeira_id IS NULL) AND status<>'LIBERADO'"))
        # V14: linhas de saldo do extrato são informação técnica, nunca receita/despesa.
        conn.execute(text("UPDATE itens_conferencia SET status='MOVIMENTO_TECNICO', diagnostico_duplicidade='MOVIMENTO_TECNICO' WHERE UPPER(COALESCE(historico_original,'')) LIKE '%SALDO ANTERIOR%' OR UPPER(COALESCE(historico_original,'')) LIKE '%SALDO INICIAL%'"))


def healthcheck() -> tuple[bool, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        backend = "PostgreSQL Cloud" if settings.database_url.startswith("postgres") else "SQLite local"
        return True, backend
    except Exception as exc:
        return False, str(exc)
