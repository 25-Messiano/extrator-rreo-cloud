from __future__ import annotations
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Date, DateTime, Boolean, Numeric, Text,
    ForeignKey, Float, UniqueConstraint, Index, LargeBinary
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class Tesouraria(Base):
    __tablename__ = "tesourarias"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), index=True)
    nome: Mapped[str] = mapped_column(String(180), index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="FILIADA")  # CENTRAL / FILIADA
    ambiente: Mapped[str] = mapped_column(String(20), default="PRODUCAO")  # PRODUCAO / TESTE
    cnpj: Mapped[str | None] = mapped_column(String(30), nullable=True)
    cidade: Mapped[str | None] = mapped_column(String(120), nullable=True)
    uf: Mapped[str | None] = mapped_column(String(2), nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(160), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(60), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    login: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    senha_hash: Mapped[str] = mapped_column(String(255))
    perfil: Mapped[str] = mapped_column(String(40), default="CONSULTA")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    permissoes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    senha_versao: Mapped[int] = mapped_column(Integer, default=1)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime, index=True)
    usado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    email_destino: Mapped[str | None] = mapped_column(String(160), nullable=True)
    enviado: Mapped[bool] = mapped_column(Boolean, default=False)
    erro_envio: Mapped[str | None] = mapped_column(Text, nullable=True)


class UsuarioTesouraria(Base):
    __tablename__ = "usuario_tesouraria"
    __table_args__ = (UniqueConstraint("usuario_id", "tesouraria_id", name="uq_usuario_tesouraria"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    papel: Mapped[str] = mapped_column(String(30), default="OPERADOR")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CodigoAPLB(Base):
    __tablename__ = "codigos_aplb"
    __table_args__ = (UniqueConstraint("tesouraria_id", "codigo", name="uq_codigo_tesouraria_codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    codigo: Mapped[str] = mapped_column(String(10), index=True)
    descricao: Mapped[str] = mapped_column(String(255))
    natureza_padrao: Mapped[str | None] = mapped_column(String(20), nullable=True)
    permite_entrada: Mapped[bool] = mapped_column(Boolean, default=False)
    permite_saida: Mapped[bool] = mapped_column(Boolean, default=True)
    gera_patrimonio: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    vigencia_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)


class GrupoDRE(Base):
    __tablename__ = "grupos_dre"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo_grupo: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    nome: Mapped[str] = mapped_column(String(255))
    grupo_pai_id: Mapped[int | None] = mapped_column(ForeignKey("grupos_dre.id"), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    pai = relationship("GrupoDRE", remote_side=[id])


class GrupoCodigoVinculo(Base):
    __tablename__ = "grupo_codigo_vinculo"
    __table_args__ = (
        UniqueConstraint("grupo_dre_id", "codigo_aplb_id", "vigencia_inicio", name="uq_grupo_codigo_vigencia"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    grupo_dre_id: Mapped[int] = mapped_column(ForeignKey("grupos_dre.id"), index=True)
    codigo_aplb_id: Mapped[int] = mapped_column(ForeignKey("codigos_aplb.id"), index=True)
    vigencia_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class ContaFinanceira(Base):
    __tablename__ = "contas_financeiras"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(20))  # BANCO / CAIXA
    banco: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    conta: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class SaldoInicial(Base):
    __tablename__ = "saldos_iniciais"
    __table_args__ = (
        UniqueConstraint("conta_financeira_id", "data_referencia", name="uq_saldo_inicial_conta_data"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    conta_financeira_id: Mapped[int] = mapped_column(ForeignKey("contas_financeiras.id"), index=True)
    data_referencia: Mapped[date] = mapped_column(Date, index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CargaInicialItem(Base):
    __tablename__ = "carga_inicial_itens"
    __table_args__ = (
        UniqueConstraint("arquivo_origem", "seq_origem", name="uq_carga_inicial_arquivo_seq"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(ForeignKey("lancamentos.id"), index=True)
    arquivo_origem: Mapped[str] = mapped_column(String(120), index=True)
    pagina: Mapped[int] = mapped_column(Integer)
    seq_origem: Mapped[int] = mapped_column(Integer)
    saldo_apos: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Favorecido(Base):
    __tablename__ = "favorecidos"
    __table_args__ = (UniqueConstraint("tesouraria_id", "codigo_cadastro", name="uq_favorecido_tesouraria_codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(255), index=True)
    documento: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="OUTRO")
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    codigo_cadastro: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    pix: Mapped[str | None] = mapped_column(String(180), nullable=True)
    banco: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    conta: Mapped[str | None] = mapped_column(String(50), nullable=True)


class Lancamento(Base):
    __tablename__ = "lancamentos"
    __table_args__ = (UniqueConstraint("tesouraria_id", "fingerprint", name="uq_lancamento_tesouraria_fingerprint"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    data_movimento: Mapped[date] = mapped_column(Date, index=True)
    competencia: Mapped[str | None] = mapped_column(String(7), nullable=True)
    codigo_aplb_id: Mapped[int | None] = mapped_column(ForeignKey("codigos_aplb.id"), nullable=True, index=True)
    origem_bc: Mapped[str] = mapped_column(String(10), index=True)  # B / C
    natureza: Mapped[str] = mapped_column(String(10), index=True)  # ENTRADA / SAIDA
    especificacao: Mapped[str] = mapped_column(Text)
    favorecido: Mapped[str | None] = mapped_column(String(255), nullable=True)
    favorecido_id: Mapped[int | None] = mapped_column(ForeignKey("favorecidos.id"), nullable=True, index=True)
    documento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    conta_financeira_id: Mapped[int | None] = mapped_column(ForeignKey("contas_financeiras.id"), nullable=True)
    centro_custo_id: Mapped[int | None] = mapped_column(ForeignKey("centros_custo.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="RASCUNHO", index=True)
    origem_lancamento: Mapped[str] = mapped_column(String(40), default="MANUAL")
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lancamento_original_id: Mapped[int | None] = mapped_column(ForeignKey("lancamentos.id"), nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


Index("ix_lancamentos_periodo_status", Lancamento.data_movimento, Lancamento.status)


class FluxoProjetado(Base):
    __tablename__ = "fluxo_projetado"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    data_prevista: Mapped[date] = mapped_column(Date, index=True)
    natureza: Mapped[str] = mapped_column(String(10))
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    codigo_aplb_id: Mapped[int | None] = mapped_column(ForeignKey("codigos_aplb.id"), nullable=True)
    descricao: Mapped[str] = mapped_column(Text)
    favorecido: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recorrencia: Mapped[str | None] = mapped_column(String(50), nullable=True)
    probabilidade: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[str] = mapped_column(String(30), default="PREVISTO")
    conta_financeira_id: Mapped[int | None] = mapped_column(ForeignKey("contas_financeiras.id"), nullable=True)
    centro_custo_id: Mapped[int | None] = mapped_column(ForeignKey("centros_custo.id"), nullable=True)
    favorecido_id: Mapped[int | None] = mapped_column(ForeignKey("favorecidos.id"), nullable=True)
    cenario: Mapped[str] = mapped_column(String(20), default="REALISTA")
    frequencia: Mapped[str] = mapped_column(String(30), default="ÚNICA")
    recorrente: Mapped[bool] = mapped_column(Boolean, default=False)
    data_fim_recorrencia: Mapped[date | None] = mapped_column(Date, nullable=True)


class Patrimonio(Base):
    __tablename__ = "patrimonio"
    __table_args__ = (UniqueConstraint("tesouraria_id", "numero_patrimonial", name="uq_patrimonio_tesouraria_numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    numero_patrimonial: Mapped[str | None] = mapped_column(String(80), nullable=True)
    descricao: Mapped[str] = mapped_column(String(255))
    categoria: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_aquisicao: Mapped[date | None] = mapped_column(Date, nullable=True)
    valor: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    fornecedor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nota_fiscal: Mapped[str | None] = mapped_column(String(120), nullable=True)
    local_uso: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsavel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    situacao: Mapped[str] = mapped_column(String(30), default="ATIVO")
    estado_conservacao: Mapped[str | None] = mapped_column(String(40), nullable=True)
    vida_util_anos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fornecedor_id: Mapped[int | None] = mapped_column(ForeignKey("favorecidos.id"), nullable=True, index=True)
    lancamento_origem_id: Mapped[int | None] = mapped_column(ForeignKey("lancamentos.id"), nullable=True)


class PatrimonioAnexo(Base):
    __tablename__ = "patrimonio_anexos"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    patrimonio_id: Mapped[int] = mapped_column(ForeignKey("patrimonio.id"), index=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tamanho_bytes: Mapped[int] = mapped_column(Integer, default=0)
    conteudo: Mapped[bytes] = mapped_column(LargeBinary)
    descricao: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    removido_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Auditoria(Base):
    __tablename__ = "auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    acao: Mapped[str] = mapped_column(String(80))
    entidade: Mapped[str] = mapped_column(String(80))
    registro_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    anterior_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    novo_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AcessoLog(Base):
    __tablename__ = "acessos_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    login_informado: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sucesso: Mapped[bool] = mapped_column(Boolean, default=False)
    detalhes: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class ImportacaoExtrato(Base):
    __tablename__ = "importacoes_extrato"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    tipo_arquivo: Mapped[str] = mapped_column(String(40))
    hash_arquivo: Mapped[str] = mapped_column(String(64), index=True)
    competencia: Mapped[str | None] = mapped_column(String(7), nullable=True, index=True)
    conta_financeira_id: Mapped[int | None] = mapped_column(ForeignKey("contas_financeiras.id"), nullable=True)
    centro_custo_id: Mapped[int | None] = mapped_column(ForeignKey("centros_custo.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="EM_CONFERENCIA", index=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    liberado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    liberado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ItemConferencia(Base):
    __tablename__ = "itens_conferencia"
    id: Mapped[int] = mapped_column(primary_key=True)
    importacao_id: Mapped[int] = mapped_column(ForeignKey("importacoes_extrato.id"), index=True)
    data_movimento: Mapped[date] = mapped_column(Date, index=True)
    historico_original: Mapped[str] = mapped_column(Text)
    favorecido: Mapped[str | None] = mapped_column(String(255), nullable=True)
    favorecido_id: Mapped[int | None] = mapped_column(ForeignKey("favorecidos.id"), nullable=True, index=True)
    documento: Mapped[str | None] = mapped_column(String(120), nullable=True)
    id_bancario: Mapped[str | None] = mapped_column(String(180), nullable=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    natureza: Mapped[str] = mapped_column(String(10))
    origem_bc: Mapped[str] = mapped_column(String(10), default="B")
    codigo_sugerido_id: Mapped[int | None] = mapped_column(ForeignKey("codigos_aplb.id"), nullable=True)
    especificacao_sugerida: Mapped[str | None] = mapped_column(Text, nullable=True)
    confianca: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="PENDENTE", index=True)
    observacao_conferencia: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    diagnostico_duplicidade: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    lancamento_similar_id: Mapped[int | None] = mapped_column(ForeignKey("lancamentos.id"), nullable=True)
    lancamento_gerado_id: Mapped[int | None] = mapped_column(ForeignKey("lancamentos.id"), nullable=True)
    origem_classificacao: Mapped[str | None] = mapped_column(String(30), nullable=True)
    justificativa_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo_ia: Mapped[str | None] = mapped_column(String(80), nullable=True)


class Conciliacao(Base):
    __tablename__ = "conciliacoes"
    __table_args__ = (UniqueConstraint("lancamento_id", name="uq_conciliacao_lancamento"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    lancamento_id: Mapped[int] = mapped_column(ForeignKey("lancamentos.id"), index=True)
    importacao_item_id: Mapped[int | None] = mapped_column(ForeignKey("itens_conferencia.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDENTE", index=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    conciliado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    conciliado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class FechamentoMensal(Base):
    __tablename__ = "fechamentos_mensais"
    __table_args__ = (UniqueConstraint("tesouraria_id", "ano", "mes", name="uq_fechamento_tesouraria_periodo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    ano: Mapped[int] = mapped_column(Integer)
    mes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ABERTO")
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    fechado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reaberto_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    reaberto_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    motivo_reabertura: Mapped[str | None] = mapped_column(Text, nullable=True)


class CentroCusto(Base):
    __tablename__ = "centros_custo"
    __table_args__ = (UniqueConstraint("tesouraria_id", "codigo", name="uq_centro_tesouraria_codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int | None] = mapped_column(ForeignKey("tesourarias.id"), nullable=True, index=True)
    codigo: Mapped[str] = mapped_column(String(30), index=True)
    nome: Mapped[str] = mapped_column(String(180), index=True)
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PatrimonioMovimento(Base):
    __tablename__ = "patrimonio_movimentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    patrimonio_id: Mapped[int] = mapped_column(ForeignKey("patrimonio.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    data_movimento: Mapped[date] = mapped_column(Date, index=True)
    local_anterior: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_novo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsavel_anterior: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsavel_novo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    situacao_anterior: Mapped[str | None] = mapped_column(String(30), nullable=True)
    situacao_nova: Mapped[str | None] = mapped_column(String(30), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PrestacaoContas(Base):
    __tablename__ = "prestacoes_contas"
    __table_args__ = (UniqueConstraint("tesouraria_id", "competencia", "versao", name="uq_prestacao_competencia_versao"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    competencia: Mapped[str] = mapped_column(String(7), index=True)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="RASCUNHO", index=True)
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    observacao_envio: Mapped[str | None] = mapped_column(Text, nullable=True)
    parecer_auditoria: Mapped[str | None] = mapped_column(Text, nullable=True)
    enviada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    analisada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    analisada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criada_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ConfiguracaoSistema(Base):
    __tablename__ = "configuracoes_sistema"
    chave: Mapped[str] = mapped_column(String(120), primary_key=True)
    valor: Mapped[str | None] = mapped_column(Text, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# V26.9 - Folha de Pagamento e Recibos Avulsos
class TrabalhadorFolha(Base):
    __tablename__ = "trabalhadores_folha"
    __table_args__ = (UniqueConstraint("tesouraria_id", "cpf", name="uq_trabalhador_tesouraria_cpf"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    nome: Mapped[str] = mapped_column(String(255), index=True)
    cpf: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    rg: Mapped[str | None] = mapped_column(String(40), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    endereco: Mapped[str | None] = mapped_column(Text, nullable=True)
    cargo: Mapped[str | None] = mapped_column(String(120), nullable=True)
    vinculo: Mapped[str] = mapped_column(String(40), default="EMPREGADO")
    salario_base: Mapped[Decimal] = mapped_column(Numeric(14,2), default=0)
    matricula: Mapped[str | None] = mapped_column(String(40), nullable=True)
    data_admissao: Mapped[date | None] = mapped_column(Date, nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    jornada: Mapped[str | None] = mapped_column(String(80), nullable=True)
    banco: Mapped[str | None] = mapped_column(String(120), nullable=True)
    agencia: Mapped[str | None] = mapped_column(String(40), nullable=True)
    conta: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pix: Mapped[str | None] = mapped_column(String(180), nullable=True)
    centro_custo_id: Mapped[int | None] = mapped_column(ForeignKey("centros_custo.id"), nullable=True, index=True)
    dependentes: Mapped[int] = mapped_column(Integer, default=0)
    situacao: Mapped[str] = mapped_column(String(30), default="ATIVO")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class EventoFolha(Base):
    __tablename__ = "eventos_folha"
    __table_args__ = (UniqueConstraint("tesouraria_id", "codigo", name="uq_evento_folha_tesouraria_codigo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(20), index=True)
    descricao: Mapped[str] = mapped_column(String(180))
    natureza: Mapped[str] = mapped_column(String(20))
    formula: Mapped[str | None] = mapped_column(Text, nullable=True)
    incidencia: Mapped[str | None] = mapped_column(String(180), nullable=True)
    codigo_aplb_id: Mapped[int | None] = mapped_column(ForeignKey("codigos_aplb.id"), nullable=True)
    centro_custo_obrigatorio: Mapped[bool] = mapped_column(Boolean, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

class FolhaCompetencia(Base):
    __tablename__ = "folhas_competencia"
    __table_args__ = (UniqueConstraint("tesouraria_id", "competencia", "tipo", name="uq_folha_comp_tipo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    competencia: Mapped[str] = mapped_column(String(7), index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="MENSAL")
    status: Mapped[str] = mapped_column(String(30), default="RASCUNHO", index=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ReciboAvulso(Base):
    __tablename__ = "recibos_avulsos"
    __table_args__ = (UniqueConstraint("tesouraria_id", "numero", name="uq_recibo_tesouraria_numero"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    numero: Mapped[int] = mapped_column(Integer, index=True)
    favorecido_id: Mapped[int | None] = mapped_column(ForeignKey("favorecidos.id"), nullable=True, index=True)
    nome: Mapped[str] = mapped_column(String(255)); cpf: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rg: Mapped[str | None] = mapped_column(String(40), nullable=True); telefone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    endereco: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_recibo: Mapped[date] = mapped_column(Date, index=True); competencia: Mapped[str] = mapped_column(String(7), index=True)
    valor: Mapped[Decimal] = mapped_column(Numeric(14,2)); servico: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="RASCUNHO", index=True)
    documento_nome: Mapped[str | None] = mapped_column(String(255), nullable=True); documento_mime: Mapped[str | None] = mapped_column(String(120), nullable=True); documento_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    comprovante_nome: Mapped[str | None] = mapped_column(String(255), nullable=True); comprovante_mime: Mapped[str | None] = mapped_column(String(120), nullable=True); comprovante_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True); criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# V26.10 - Parametrizacao, vigencias e governanca da Folha
class ParametroFolha(Base):
    __tablename__ = "parametros_folha"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    grupo: Mapped[str] = mapped_column(String(50), index=True)  # PISO, INSS, IRRF, FGTS, BENEFICIO, FERIAS, 13, RESCISAO, OUTRO
    chave: Mapped[str] = mapped_column(String(120), index=True)
    descricao: Mapped[str] = mapped_column(String(255))
    valor_decimal: Mapped[Decimal | None] = mapped_column(Numeric(16,6), nullable=True)
    valor_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    vigencia_inicio: Mapped[date] = mapped_column(Date, index=True)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    fonte_referencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class HistoricoSalarial(Base):
    __tablename__ = "historico_salarial"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    trabalhador_id: Mapped[int] = mapped_column(ForeignKey("trabalhadores_folha.id"), index=True)
    salario: Mapped[Decimal] = mapped_column(Numeric(14,2))
    vigencia_inicio: Mapped[date] = mapped_column(Date, index=True)
    vigencia_fim: Mapped[date | None] = mapped_column(Date, nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class CalendarioFolha(Base):
    __tablename__ = "calendario_folha"
    __table_args__ = (UniqueConstraint("tesouraria_id", "competencia", "tipo", name="uq_calendario_folha_comp_tipo"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    competencia: Mapped[str] = mapped_column(String(7), index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="MENSAL")
    data_abertura: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_limite_eventos: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_conferencia: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_fechamento: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_pagamento_prevista: Mapped[date | None] = mapped_column(Date, nullable=True)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)

class FolhaSnapshot(Base):
    __tablename__ = "folha_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    folha_id: Mapped[int] = mapped_column(ForeignKey("folhas_competencia.id"), index=True)
    etapa: Mapped[str] = mapped_column(String(30), index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    criado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ChecklistFolha(Base):
    __tablename__ = "checklist_folha"
    id: Mapped[int] = mapped_column(primary_key=True)
    tesouraria_id: Mapped[int] = mapped_column(ForeignKey("tesourarias.id"), index=True)
    folha_id: Mapped[int] = mapped_column(ForeignKey("folhas_competencia.id"), index=True)
    item: Mapped[str] = mapped_column(String(180))
    concluido: Mapped[bool] = mapped_column(Boolean, default=False)
    observacao: Mapped[str | None] = mapped_column(Text, nullable=True)
    atualizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
