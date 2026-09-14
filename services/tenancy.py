from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from sqlalchemy import select, func, true
from database.db import session_scope
from models.entities import Tesouraria, UsuarioTesouraria, Usuario, ConfiguracaoSistema

_active_tesouraria: ContextVar[int | None] = ContextVar("active_tesouraria", default=None)


def app_version() -> str:
    """Versão única do código-base usada simultaneamente por Central e todas as filiais."""
    try:
        return Path(__file__).resolve().parents[1].joinpath("VERSION").read_text(encoding="utf-8").strip() or "V25"
    except Exception:
        return "V25.1"



def tenant_identity_data(tenant: dict | None = None) -> dict:
    """Identidade visual pura da unidade, sem dependência de Streamlit."""
    tenant = tenant or {}
    nome = (tenant.get("nome") or "Unidade não selecionada").strip()
    codigo = (tenant.get("codigo") or "-").strip()
    cidade = (tenant.get("cidade") or "").strip()
    uf = (tenant.get("uf") or "").strip().upper()
    ambiente = (tenant.get("ambiente") or "PRODUCAO").strip().upper()
    tipo = (tenant.get("tipo") or "FILIADA").strip().upper()
    local = "/".join(x for x in (cidade, uf) if x) or "Local não informado"
    is_test = ambiente == "TESTE"
    return {
        "nome": nome, "codigo": codigo, "cidade": cidade, "uf": uf, "local": local,
        "ambiente": ambiente, "tipo": tipo, "icone": "🧪" if is_test else "🏛️",
        "ambiente_label": "AMBIENTE DE TESTE" if is_test else "PRODUÇÃO",
        "titulo_operacional": nome.upper(),
        "linha_identificacao": f"{codigo} • {local} • {'Ambiente de Teste' if is_test else 'Unidade Filiada'}",
    }

def set_active_tesouraria(tesouraria_id: int | None):
    _active_tesouraria.set(int(tesouraria_id) if tesouraria_id else None)


def get_active_tesouraria_id() -> int | None:
    return _active_tesouraria.get()


def tenant_where(column):
    """Filtro seguro: fora da UI mantém compatibilidade legada; na UI isola por unidade ativa."""
    tid = get_active_tesouraria_id()
    return true() if tid is None else column == tid


def ensure_default_tesourarias():
    with session_scope() as s:
        central = s.scalar(select(Tesouraria).where(Tesouraria.codigo == "CENTRAL"))
        if not central:
            central = Tesouraria(
                codigo="CENTRAL", nome="CENTRAL DAS TESOURARIAS - AUDITORIA",
                tipo="CENTRAL", ambiente="PRODUCAO", ativa=True,
            )
            s.add(central); s.flush()
        else:
            central.nome = "CENTRAL DAS TESOURARIAS - AUDITORIA"
            central.tipo = "CENTRAL"
            central.ambiente = "PRODUCAO"
            central.ativa = True
        teste = s.scalar(select(Tesouraria).where(Tesouraria.codigo == "TESTE"))
        if not teste:
            teste = Tesouraria(
                codigo="TESTE", nome="AMBIENTE DE TESTE",
                tipo="FILIADA", ambiente="TESTE", ativa=True,
            )
            s.add(teste); s.flush()
        # Compatibilidade legada: antes da migração V25, registros antigos sem tenant
        # são concentrados na CENTRAL para que a rotina de migração consiga movê-los
        # de forma segura. Após a migração, a CENTRAL deixa de receber qualquer dado
        # operacional automaticamente.
        marker = s.get(ConfiguracaoSistema, "V25_MIGRACAO_CENTRAL_CONCLUIDA")
        if not marker or not str(marker.valor or "").upper().startswith("SIM"):
            for tabela in (
                "lancamentos", "contas_financeiras", "saldos_iniciais", "fluxo_projetado",
                "patrimonio", "favorecidos", "importacoes_extrato", "fechamentos_mensais", "centros_custo",
                "codigos_aplb",
            ):
                try:
                    s.execute(__import__('sqlalchemy').text(
                        f"UPDATE {tabela} SET tesouraria_id=:tid WHERE tesouraria_id IS NULL"
                    ), {"tid": central.id})
                except Exception:
                    pass
        admins = s.scalars(select(Usuario).where(Usuario.perfil == "ADMINISTRADOR", Usuario.ativo.is_(True))).all()
        for u in admins:
            # Administrador pertence à CENTRAL. Filiais usam contas operacionais próprias.
            link = s.scalar(select(UsuarioTesouraria).where(
                UsuarioTesouraria.usuario_id == u.id,
                UsuarioTesouraria.tesouraria_id == central.id,
            ))
            if link:
                link.ativo = True; link.papel = "ADMIN"
            else:
                s.add(UsuarioTesouraria(usuario_id=u.id, tesouraria_id=central.id, papel="ADMIN", ativo=True))
            # Limpa vínculos legados de administradores centrais com unidades operacionais.
            antigos = s.scalars(select(UsuarioTesouraria).join(
                Tesouraria, Tesouraria.id == UsuarioTesouraria.tesouraria_id
            ).where(UsuarioTesouraria.usuario_id == u.id, Tesouraria.tipo != "CENTRAL")).all()
            for antigo in antigos:
                antigo.ativo = False
    return True


def _to_dict(t: Tesouraria):
    return {
        "id": t.id, "codigo": t.codigo, "nome": t.nome, "tipo": t.tipo,
        "ambiente": t.ambiente, "cnpj": t.cnpj or "", "cidade": t.cidade or "",
        "uf": t.uf or "", "responsavel": getattr(t, "responsavel", None) or "",
        "telefone": getattr(t, "telefone", None) or "", "email": getattr(t, "email", None) or "",
        "observacao": getattr(t, "observacao", None) or "", "ativa": t.ativa,
        # Não é uma cópia gravada por filial: é a versão corrente do único código-base.
        "versao_sistema": app_version(),
    }


def listar_tesourarias(usuario_id: int | None = None, incluir_inativas=False):
    with session_scope() as s:
        q = select(Tesouraria).order_by(Tesouraria.ambiente, Tesouraria.nome)
        if not incluir_inativas:
            q = q.where(Tesouraria.ativa.is_(True))
        if usuario_id:
            u = s.get(Usuario, usuario_id)
            if u and u.perfil != "ADMINISTRADOR":
                q = q.join(UsuarioTesouraria, UsuarioTesouraria.tesouraria_id == Tesouraria.id).where(
                    UsuarioTesouraria.usuario_id == usuario_id,
                    UsuarioTesouraria.ativo.is_(True),
                )
        return [_to_dict(t) for t in s.scalars(q).all()]


def obter_tesouraria(tid: int):
    with session_scope() as s:
        t = s.get(Tesouraria, tid)
        return None if not t else _to_dict(t)


def criar_tesouraria(codigo, nome, tipo="FILIADA", ambiente="PRODUCAO", cnpj=None,
                     cidade=None, uf=None, responsavel=None, telefone=None, email=None,
                     observacao=None):
    """Cria somente a unidade de dados; nunca duplica/copía o código do aplicativo."""
    codigo = (codigo or "").strip().upper(); nome = (nome or "").strip()
    if not codigo or not nome:
        raise ValueError("Código e nome são obrigatórios.")
    ambiente = (ambiente or "PRODUCAO").strip().upper()
    if ambiente not in ("PRODUCAO", "TESTE"):
        raise ValueError("Ambiente inválido.")
    with session_scope() as s:
        if s.scalar(select(Tesouraria.id).where(func.lower(Tesouraria.codigo) == codigo.lower())):
            raise ValueError("Código de tesouraria já existe.")
        t = Tesouraria(
            codigo=codigo, nome=nome, tipo=tipo, ambiente=ambiente,
            cnpj=(cnpj or "").strip() or None, cidade=(cidade or "").strip() or None,
            uf=(uf or "").strip().upper() or None,
            responsavel=(responsavel or "").strip() or None,
            telefone=(telefone or "").strip() or None,
            email=(email or "").strip() or None,
            observacao=(observacao or "").strip() or None,
            ativa=True,
        )
        s.add(t); s.flush(); tid = t.id
        # Nenhum usuário da CENTRAL é transformado em operador da nova filial.
        # O bootstrap cria uma conta administrativa operacional própria da filial.
        return tid


def criar_tesouraria_com_admin(codigo, nome, admin_email, admin_senha, tipo="FILIADA", ambiente="PRODUCAO",
                                cnpj=None, cidade=None, uf=None, responsavel=None, telefone=None,
                                email=None, observacao=None):
    """Cria filial e seu administrador operacional em uma única transação.

    V26.1: novas filiais já nascem no padrão de autenticação por e-mail e não
    dependem da conta legada admin/123.
    """
    from services.security import normalizar_email, validar_senha, hash_password
    codigo = (codigo or "").strip().upper(); nome = (nome or "").strip()
    if not codigo or not nome:
        raise ValueError("Código e nome são obrigatórios.")
    ambiente = (ambiente or "PRODUCAO").strip().upper()
    if ambiente not in ("PRODUCAO", "TESTE"):
        raise ValueError("Ambiente inválido.")
    email_login = normalizar_email(admin_email or "")
    validar_senha(admin_senha or "")
    with session_scope() as s:
        if s.scalar(select(Tesouraria.id).where(func.lower(Tesouraria.codigo) == codigo.lower())):
            raise ValueError("Código de tesouraria já existe.")
        if s.scalar(select(Usuario.id).where(func.lower(Usuario.email) == email_login.lower())):
            raise ValueError("Este e-mail de login já está vinculado a outro usuário.")
        if s.scalar(select(Usuario.id).where(func.lower(Usuario.login) == email_login.lower())):
            raise ValueError("Este e-mail já está sendo usado como identificador interno de outro usuário.")
        t = Tesouraria(
            codigo=codigo, nome=nome, tipo=tipo, ambiente=ambiente,
            cnpj=(cnpj or "").strip() or None, cidade=(cidade or "").strip() or None,
            uf=(uf or "").strip().upper() or None,
            responsavel=(responsavel or "").strip() or None,
            telefone=(telefone or "").strip() or None,
            email=(email or "").strip() or None,
            observacao=(observacao or "").strip() or None,
            ativa=True,
        )
        s.add(t); s.flush()
        u = Usuario(
            nome=f"Administrador - {nome}",
            login=email_login, email=email_login,
            senha_hash=hash_password(admin_senha),
            perfil="TESOURARIA", ativo=True,
        )
        s.add(u); s.flush()
        s.add(UsuarioTesouraria(
            usuario_id=u.id, tesouraria_id=t.id, papel="ADMIN_UNIDADE", ativo=True,
        ))
        return t.id, u.id


def atualizar_tesouraria(tesouraria_id: int, **dados):
    permitidos = {"nome", "cnpj", "cidade", "uf", "responsavel", "telefone", "email", "observacao"}
    with session_scope() as s:
        t = s.get(Tesouraria, tesouraria_id)
        if not t:
            raise ValueError("Tesouraria não encontrada.")
        for campo, valor in dados.items():
            if campo not in permitidos:
                continue
            if campo == "uf":
                valor = (valor or "").strip().upper() or None
            elif isinstance(valor, str):
                valor = valor.strip() or None
            setattr(t, campo, valor)
        return True


def definir_tesouraria_ativa(tesouraria_id: int, ativa: bool):
    with session_scope() as s:
        t = s.get(Tesouraria, tesouraria_id)
        if not t:
            raise ValueError("Tesouraria não encontrada.")
        if t.codigo in ("CENTRAL", "TESTE") and not ativa:
            raise ValueError("CENTRAL e TESTE são unidades estruturais e não podem ser inativadas por esta tela.")
        t.ativa = bool(ativa)
        return True


def vincular_usuario(usuario_id: int, tesouraria_id: int, papel="OPERADOR"):
    with session_scope() as s:
        x = s.scalar(select(UsuarioTesouraria).where(
            UsuarioTesouraria.usuario_id == usuario_id,
            UsuarioTesouraria.tesouraria_id == tesouraria_id,
        ))
        if x:
            x.ativo = True; x.papel = papel
        else:
            s.add(UsuarioTesouraria(
                usuario_id=usuario_id, tesouraria_id=tesouraria_id,
                papel=papel, ativo=True,
            ))


def diagnostico_isolamento() -> dict:
    """Diagnóstico somente leitura da separação de dados entre unidades."""
    from sqlalchemy import text
    from database.db import engine
    tabelas=(
        "lancamentos","contas_financeiras","saldos_iniciais","favorecidos",
        "centros_custo","fluxo_projetado","patrimonio","importacoes_extrato",
        "fechamentos_mensais","prestacoes_contas",
    )
    unidades=listar_tesourarias(None, True)
    by={u["id"]:{"id":u["id"],"codigo":u["codigo"],"nome":u["nome"],"tipo":u["tipo"],"ambiente":u["ambiente"]} for u in unidades}
    orfaos={}
    with engine.connect() as conn:
        for tabela in tabelas:
            try:
                rows=conn.execute(text(f"SELECT tesouraria_id, COUNT(*) qtd FROM {tabela} GROUP BY tesouraria_id")).mappings().all()
            except Exception:
                continue
            for r in rows:
                tid=r["tesouraria_id"]
                qtd=int(r["qtd"] or 0)
                if tid is None:
                    orfaos[tabela]=qtd
                elif tid in by:
                    by[tid][tabela]=qtd
        for u in by.values():
            for tabela in tabelas:
                u.setdefault(tabela,0)
    central=next((u for u in by.values() if u["codigo"]=="CENTRAL"),None)
    teste=next((u for u in by.values() if u["codigo"]=="TESTE"),None)
    operacionais=("lancamentos","contas_financeiras","saldos_iniciais","favorecidos","centros_custo","fluxo_projetado","patrimonio","importacoes_extrato","fechamentos_mensais")
    problemas=[]
    if central:
        q=sum(int(central.get(k,0)) for k in operacionais)
        if q: problemas.append(f"CENTRAL possui {q} registro(s) operacional(is); deveria permanecer sem movimento próprio.")
    if teste:
        # Dados de teste são permitidos, mas nunca devem ser confundidos com produção.
        pass
    if orfaos:
        problemas.append("Existem registros sem tesouraria_id: "+", ".join(f"{k}={v}" for k,v in sorted(orfaos.items()) if v))
    return {"unidades":list(by.values()),"orfaos":orfaos,"problemas":problemas,"ok":not problemas}
