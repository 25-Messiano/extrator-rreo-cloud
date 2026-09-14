from __future__ import annotations

from decimal import Decimal
import inspect
from pathlib import Path
import streamlit as st

from database.db import healthcheck, init_db
from services.security import (
    authenticate,
    authenticate_for_tenant,
    authenticate_email,
    ativar_email_conta_legada,
    contextos_legados_sem_email,
    ensure_operational_admins,
    senha_inicial_temporaria,
    carregar_usuario_sessao,
    ensure_admin,
    permitido,
    usuario_pode_acessar_tesouraria,
    solicitar_recuperacao_senha, validar_token_recuperacao, redefinir_senha_por_token,
)
from services.seed import seed_initial_data
from services.tenancy import ensure_default_tesourarias, listar_tesourarias, set_active_tesouraria, obter_tesouraria, app_version, tenant_identity_data

# Mapa de páginas -> permissão mínima. Além de esconder visualmente, cada página
# também chama require_login(acao), portanto acesso direto por URL continua protegido.
PAGE_PERMISSIONS = {
    "Dashboard": "CONSULTAR",
    "Lançamentos": "LANCAR",
    "Correção_Estorno": "CORRIGIR",
    "Banco": "CONSULTAR",
    "Caixa": "CONSULTAR",
    "Extratos_Bancarios": "IMPORTAR",
    "Importação_IA": "IMPORTAR",
    "Conferência": "CONFERIR",
    "Conciliação": "CONCILIAR",
    "Fluxo_de_Caixa": "FLUXO",
    "Patrimônio": "PATRIMONIO",
    "Códigos_Grupos_DRE": "CADASTROS",
    "Favorecidos_Fornecedores": "CADASTROS",
    "Contas_Bancarias": "CADASTROS",
    "Centros_de_Custo": "CONFIGURAR",
    "Pesquisa_Avancada": "CONSULTAR",
    "Relatórios_DRE": "RELATORIOS",
    "Fechamento_Mensal": "FECHAR",
    "Auditoria": "AUDITORIA",
    "Usuários_Permissões": "USUARIOS",
    "Backup_Recuperacao": "BACKUP",
    "Configurações": "CONFIGURAR",
    "Monitoramento": "MONITORAR",
}

# V25.6: contextos de interface mutuamente exclusivos.
# A Central nunca carrega páginas financeiras de uma filial e uma filial/teste
# nunca carrega páginas administrativas da Central. Minha Conta e Prestações
# de Contas sao compartilhadas porque possuem comportamento conforme o perfil.
CENTRAL_ONLY_PAGES = {
    "18_Auditoria.py", "19_Usuarios_Permissoes.py", "20_Backup_Recuperacao.py",
    "21_Configuracoes.py", "22_Monitoramento.py", "30_Central_Tesourarias.py",
    "32_Ambiente_Teste.py", "33_Cadastrar_Tesouraria.py",
    "34_Migracao_Dados_Central.py", "36_Diagnostico_Isolamento.py", "39_Configuracao_DRE_Central.py",
}
OPERATIONAL_ONLY_PAGES = {
    "01_Dashboard.py", "02_Lancamentos.py", "03_Correcao_Estorno.py",
    "04_Banco.py", "05_Caixa.py", "06_Extratos_Bancarios.py",
    "07_Importacao_IA.py", "08_Conferencia.py", "09_Conciliacao.py",
    "10_Fluxo_de_Caixa.py", "11_Patrimonio.py", "12_Codigos_Grupos_DRE.py",
    "13_Favorecidos_Fornecedores.py", "14_Contas_Bancarias.py",
    "15_Centros_de_Custo.py", "15_Pesquisa_Avancada.py",
    "16_Relatorios_DRE.py", "17_Fechamento_Mensal.py",
    "23_Relatorio_Movimento_Financeiro.py", "24_Relatorio_Resumo_Banco.py",
    "25_Relatorio_Resumo_Caixa.py", "26_Relatorio_Resumo_Banco_Caixa.py",
    "27_Relatorio_Suprimento_Caixa.py", "28_Relatorio_Saldos_Historicos.py",
    "29_Central_Outros_Relatorios.py", "37_Importar_Movimento_PDF.py",
    "38_Importar_Extratos_PDF.py", "40_Folha_Pagamento.py",
}

def _session_context() -> str:
    profile = st.session_state.get("portal_profile")
    if profile == "ADMINISTRADOR":
        return "CENTRAL"
    tenant = st.session_state.get("tesouraria") or {}
    if tenant.get("ambiente") == "TESTE":
        return "TESTE"
    return "FILIADA"

def _caller_page_name() -> str:
    # require_login e chamado diretamente pelos scripts Streamlit.
    for frame in inspect.stack()[1:8]:
        name = Path(frame.filename).name
        if name == "app.py" or frame.filename.replace("\\", "/").find("/pages/") >= 0:
            return name
    return ""

def _enforce_page_context() -> None:
    """Mantem cada sessao no universo correto e corrige URLs antigas."""
    page = _caller_page_name()
    ctx = _session_context()
    if ctx == "CENTRAL" and page in OPERATIONAL_ONLY_PAGES:
        st.switch_page("app.py")
    if ctx in ("FILIADA", "TESTE") and page in CENTRAL_ONLY_PAGES:
        st.switch_page("pages/01_Dashboard.py")



def bootstrap_app():
    init_db(); ensure_admin(); ensure_default_tesourarias(); seed_initial_data(); ensure_operational_admins()
    try:
        from services.backup import backup_automatico_diario
        backup_automatico_diario()
    except Exception:
        pass


def brl(v) -> str:
    try:
        d=Decimal(str(v))
    except Exception:
        d=Decimal("0")
    s=f"{d:,.2f}".replace(",","X").replace(".",",").replace("X",".")
    return f"R$ {s}"


def _ocultar_sidebar_publica() -> None:
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        button[kind="headerNoPadding"] {display:none!important;}
        section[data-testid="stSidebar"] {display:none!important;}
        </style>
        """, unsafe_allow_html=True,
    )


def _entrar_no_contexto(user: dict, tesouraria_id: int | None = None) -> None:
    st.session_state.user = user
    if user.get("perfil") == "ADMINISTRADOR":
        st.session_state.portal_profile = "ADMINISTRADOR"
        st.session_state.pop("portal_tesouraria_id", None)
        st.session_state.pop("tesouraria_id", None)
        st.session_state.senha_temporaria = False
        st.switch_page("app.py")
    if not tesouraria_id:
        raise ValueError("Nenhuma unidade operacional autorizada foi selecionada.")
    tid=int(tesouraria_id)
    if not usuario_pode_acessar_tesouraria(user.get("id"), tid):
        raise ValueError("Seu usuário não está autorizado nesta unidade.")
    st.session_state.portal_profile = "TESOURARIA"
    st.session_state.portal_tesouraria_id = tid
    st.session_state.tesouraria_id = tid
    st.session_state.senha_temporaria = senha_inicial_temporaria(user.get("id"))
    st.switch_page("pages/01_Dashboard.py")


# Credenciais da Central não entram em perfis operacionais; o contexto é resolvido pelo vínculo do usuário.
def _resolver_contexto_pos_login(user: dict) -> None:
    if user.get("perfil") == "ADMINISTRADOR":
        _entrar_no_contexto(user)
    opcoes=[x for x in listar_tesourarias(user.get("id")) if x.get("tipo") != "CENTRAL" and x.get("ativa", True)]
    if not opcoes:
        raise ValueError("Este usuário não está vinculado a nenhuma tesouraria ativa.")
    if len(opcoes) == 1:
        _entrar_no_contexto(user, opcoes[0]["id"])
    st.session_state.pending_login_user = user
    st.rerun()


def login_screen() -> bool:
    """Portal V26: e-mail é a identidade pública; unidade é autorização, não credencial.

    Contas legadas sem e-mail usam uma migração única, validando a credencial antiga
    antes de cadastrar um e-mail exclusivo. Depois disso, o acesso é somente por e-mail.
    """
    if st.session_state.get("user"):
        return True
    _ocultar_sidebar_publica()

    reset_token = str(st.query_params.get("reset_token", "") or "")
    if reset_token:
        info = validar_token_recuperacao(reset_token)
        st.markdown("## 🔑 Redefinir senha")
        if not info:
            st.error("Este link é inválido, expirou ou já foi utilizado.")
            if st.button("Voltar ao login"):
                st.query_params.clear(); st.rerun()
            return False
        st.caption(f"Conta: {info['nome']} · link temporário de uso único")
        with st.form("reset_password_email_form"):
            nova = st.text_input("Nova senha", type="password", help="Mínimo de 10 caracteres, com letra e número.")
            conf = st.text_input("Confirmar nova senha", type="password")
            enviar = st.form_submit_button("Salvar nova senha", type="primary", width="stretch")
        if enviar:
            if nova != conf:
                st.error("A confirmação não confere.")
            else:
                try:
                    redefinir_senha_por_token(reset_token, nova)
                    st.success("Senha atualizada. Entre novamente com seu e-mail e a nova senha.")
                    st.query_params.clear(); st.session_state.clear(); st.rerun()
                except Exception as exc:
                    st.error(str(exc))
        return False

    pendente=st.session_state.get("pending_login_user")
    if pendente:
        st.markdown("## 🏛️ Escolha a unidade")
        st.caption(f"Usuário: {pendente.get('nome','')} · {pendente.get('email','')}")
        opcoes=[x for x in listar_tesourarias(pendente.get("id")) if x.get("tipo") != "CENTRAL" and x.get("ativa", True)]
        if not opcoes:
            st.session_state.pop("pending_login_user",None)
            st.error("Nenhuma unidade ativa está vinculada a este usuário.")
            return False
        mp={f"{'🧪' if x.get('ambiente')=='TESTE' else '🏛️'} {x['nome']} · {x.get('codigo','')}":x for x in opcoes}
        rotulo=st.selectbox("Unidade autorizada", list(mp))
        c1,c2=st.columns(2)
        if c1.button("Entrar nesta unidade", type="primary", width="stretch"):
            _entrar_no_contexto(pendente, mp[rotulo]["id"])
        if c2.button("Cancelar", width="stretch"):
            st.session_state.pop("pending_login_user",None); st.rerun()
        return False

    st.markdown("## 🔐 Acesso ao TESOURARIA APLB")
    st.caption("Entre com seu e-mail e senha. O sistema abrirá somente as unidades autorizadas para esse usuário.")
    with st.form("login_email_v26"):
        email=st.text_input("E-mail", placeholder="nome@exemplo.com")
        senha=st.text_input("Senha", type="password")
        ok=st.form_submit_button("Entrar", type="primary", width="stretch")
    if ok:
        user=authenticate_email(email, senha)
        if not user:
            st.error("E-mail ou senha inválidos.")
        else:
            try:
                _resolver_contexto_pos_login(user)
            except Exception as exc:
                st.error(str(exc))

    with st.expander("🔑 Esqueci minha senha"):
        st.caption("Informe somente o e-mail cadastrado. Se ele existir, enviaremos um link temporário de uso único.")
        with st.form("forgot_password_email_v26"):
            ident=st.text_input("E-mail cadastrado", key="forgot_email")
            solicitar=st.form_submit_button("Enviar link de recuperação", width="stretch")
        if solicitar:
            try:
                solicitar_recuperacao_senha(ident)
            except Exception:
                pass
            st.success("Se o e-mail estiver cadastrado, o link de recuperação será enviado.")

    # V26.1: a migração legada é transitória. Ela só aparece enquanto existir
    # ao menos uma conta ativa sem e-mail e lista somente os contextos pendentes.
    perfis=contextos_legados_sem_email()
    if perfis:
        with st.expander("🧭 Primeiro acesso / ativar e-mail de uma conta antiga"):
            st.warning("Use esta opção apenas uma vez para contas antigas ainda sem e-mail. Depois da ativação, o acesso passa a ser somente por e-mail.")
            labels={x['key']:x['label'] for x in perfis}
            with st.form("ativar_email_legado_v261"):
                escolha=st.selectbox("Conta antiga", [x['key'] for x in perfis], format_func=lambda k:labels[k])
                login_antigo=st.text_input("Login antigo", value="admin", help="Na maioria das contas antigas é admin. Usuários antigos personalizados podem informar o login que já utilizavam.")
                novo_email=st.text_input("E-mail que passará a ser seu login")
                senha_antiga=st.text_input("Senha atual desta conta", type="password")
                ativar=st.form_submit_button("Ativar login por e-mail", type="primary", width="stretch")
            if ativar:
                alvo=next(x for x in perfis if x['key']==escolha)
                try:
                    user=ativar_email_conta_legada(novo_email, senha_antiga, alvo['tid'], alvo['key']=='ADMIN', login_antigo)
                    st.success("E-mail ativado. A partir de agora, use esse e-mail para entrar e recuperar a senha.")
                    _resolver_contexto_pos_login(user)
                except Exception as exc:
                    st.error(str(exc))
    return False

def _refresh_session_user():
    user=st.session_state.get("user")
    if not user:
        return None
    fresh=carregar_usuario_sessao(user.get("id"))
    if fresh and int(user.get("senha_versao") or 1) != int(fresh.get("senha_versao") or 1):
        st.session_state.clear()
        st.warning("Sua senha foi alterada. Entre novamente para continuar.")
        st.switch_page("app.py")
    if not fresh:
        st.session_state.pop("user",None)
        st.error("Seu usuário foi desativado ou não está mais disponível. Entre novamente.")
        st.stop()
    st.session_state.user=fresh
    return fresh


def _hide_unauthorized_pages(user: dict) -> None:
    """Oculta do menu lateral as páginas às quais o usuário não tem acesso.

    A proteção real é feita no servidor por require_login; o CSS é somente uma
    melhoria de interface para não mostrar opções inúteis ao usuário.
    """
    escondidas=[]
    for slug,acao in PAGE_PERMISSIONS.items():
        if not permitido(user.get("perfil","CONSULTA"),acao,user.get("id")):
            escondidas.append(slug)
    if not escondidas:
        return
    selectors=[]
    for slug in escondidas:
        selectors.extend([
            f'[data-testid="stSidebarNav"] li:has(a[href$="/{slug}"])',
            f'[data-testid="stSidebarNav"] a[href$="/{slug}"]',
        ])
    st.markdown(
        "<style>" + ",".join(selectors) + "{display:none!important;}</style>",
        unsafe_allow_html=True,
    )



def _session_controls(user: dict) -> None:
    with st.sidebar:
        st.markdown("**Usuário ativo**")
        st.caption(f"👤 {user.get('nome','')} · {user.get('perfil','')}")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Trocar usuário", key="sidebar_switch_user", width="stretch"):
                st.session_state.clear(); st.switch_page("app.py")
        with c2:
            if st.button("🚪 Sair", key="sidebar_logout", width="stretch"):
                st.session_state.clear(); st.switch_page("app.py")
        st.page_link("pages/35_Minha_Conta.py", label="🔐 Minha conta / Alterar senha", width="stretch")
        st.markdown("**Programador:**  \nMessiano A. Sena")
        if st.session_state.get("senha_temporaria"):
            st.warning("Senha inicial temporária em uso. Altere-a em Minha conta.", icon="⚠️")


def _select_tesouraria_ativa(user: dict) -> dict | None:
    # V25.6: ADMINISTRADOR não seleciona nem opera filial nestá sessao.
    # Para operar Araci/Teste/outra unidade, deve Trocar usuário e autenticar no
    # perfil daquela unidade. Isso elimina mistura visual e de contexto.
    if st.session_state.get("portal_profile") == "ADMINISTRADOR":
        centrais = [x for x in listar_tesourarias(None) if x.get("tipo") == "CENTRAL"]
        central = centrais[0] if centrais else None
        if not central:
            st.error("Central de Auditoria não cadastrada."); st.stop()
        st.session_state.tesouraria_id = central["id"]
        st.session_state.tesouraria = central
        set_active_tesouraria(central["id"])
        with st.sidebar:
            st.markdown("### 👑 ADMINISTRADOR")
            st.caption("CENTRAL DAS TESOURARIAS · Auditoria e administração")
            st.caption(f"Código-base {app_version()}")
        _session_controls(user)
        return central

    opcoes=[x for x in listar_tesourarias(user.get("id")) if x.get("tipo") != "CENTRAL"]
    if not opcoes:
        st.error("Seu usuario não está vinculado a nenhuma tesouraria ativa."); st.stop()
    ids=[x["id"] for x in opcoes]
    locked = st.session_state.get("portal_tesouraria_id")
    if not locked or int(locked) not in ids or not usuario_pode_acessar_tesouraria(user.get("id"), int(locked)):
        st.error("A unidade destá sessao não está autorizada. Troque de usuario e entre novamente.")
        st.session_state.clear(); st.stop()
    escolhido = int(locked)
    tenant = obter_tesouraria(escolhido)
    icon = "🧪" if tenant.get("ambiente") == "TESTE" else "🏛️"
    with st.sidebar:
        st.markdown(f"### {icon} {tenant['nome']}")
        st.caption(f"{tenant.get('codigo','')} · {tenant.get('cidade','')}/{tenant.get('uf','')} · {tenant.get('ambiente','')}")
        st.caption(f"Código-base {app_version()}")
    _session_controls(user)
    st.session_state.tesouraria_id=escolhido; set_active_tesouraria(escolhido)
    return tenant



def tenant_identity(tenant: dict | None = None) -> dict:
    return tenant_identity_data(tenant or st.session_state.get("tesouraria") or {})


def unit_banner(compact: bool = False) -> None:
    ident = tenant_identity()
    if compact:
        st.caption(
            f"{ident['icone']} Unidade ativa: **{ident['nome']}** · "
            f"Código **{ident['codigo']}** · {ident['ambiente_label']} · {app_version()}"
        )
        return
    bg = "#fff7ed" if ident["ambiente"] == "TESTE" else "#eff6ff"
    border = "#fdba74" if ident["ambiente"] == "TESTE" else "#bfdbfe"
    st.markdown(
        f"""<div style="background:{bg};border:1px solid {border};border-radius:10px;padding:10px 13px;margin:.25rem 0 .9rem 0">
        <b>{ident['icone']} Unidade operacional ativa: {ident['nome']}</b><br>
        <span style="font-size:.86rem;color:#475569">Código: {ident['codigo']} &nbsp;•&nbsp; {ident['local']} &nbsp;•&nbsp; {ident['ambiente_label']} &nbsp;•&nbsp; Código-base {app_version()}</span>
        </div>""",
        unsafe_allow_html=True,
    )

def hierarchical_sidebar(user: dict) -> None:
    """V25.6: menu depende exclusivamente do contexto autenticado."""
    st.markdown("""<style>
    [data-testid="stSidebarNav"] {display:none!important;}
    div[data-testid="stSidebar"] [data-testid="stExpander"] details summary p {font-weight:700;}
    </style>""", unsafe_allow_html=True)
    ctx = _session_context()
    with st.sidebar:
        if ctx == "CENTRAL":
            st.divider()
            st.markdown("### 🏢 Central de Auditoria")
            st.page_link("app.py", label="🏠 Início da Central")
            st.page_link("pages/30_Central_Tesourarias.py", label="🏢 Tesourarias Filiadas")
            st.page_link("pages/33_Cadastrar_Tesouraria.py", label="➕ Nova Tesouraria")
            st.page_link("pages/34_Migracao_Dados_Central.py", label="🔁 Migração de Dados")
            st.page_link("pages/31_Prestacoes_Contas.py", label="📥 Prestações de Contas")
            st.page_link("pages/36_Diagnostico_Isolamento.py", label="🛡️ Diagnóstico de Isolamento")
            with st.expander("⚙️ Administração", expanded=False):
                if permitido(user.get("perfil","CONSULTA"),"AUDITORIA",user.get("id")):
                    st.page_link("pages/18_Auditoria.py", label="↳ Auditoria")
                if permitido(user.get("perfil","CONSULTA"),"USUARIOS",user.get("id")):
                    st.page_link("pages/19_Usuarios_Permissoes.py", label="↳ Usuários e Permissões")
                if permitido(user.get("perfil","CONSULTA"),"BACKUP",user.get("id")):
                    st.page_link("pages/20_Backup_Recuperacao.py", label="↳ Backup e Recuperacao")
                if permitido(user.get("perfil","CONSULTA"),"CONFIGURAR",user.get("id")):
                    st.page_link("pages/39_Configuracao_DRE_Central.py", label="↳ Configuração DRE Oficial")
                    st.page_link("pages/21_Configuracoes.py", label="↳ Configurações")
                if permitido(user.get("perfil","CONSULTA"),"MONITORAR",user.get("id")):
                    st.page_link("pages/22_Monitoramento.py", label="↳ Monitoramento")
            st.page_link("pages/32_Ambiente_Teste.py", label="🧪 Administrar Ambiente de Teste")
            return

        ident = tenant_identity()
        st.divider()
        if permitido(user.get("perfil","CONSULTA"),"CONSULTAR",user.get("id")):
            st.page_link("pages/01_Dashboard.py", label="🏠 Dashboard")
        with st.expander("📁 Cadastros", expanded=False):
            if permitido(user.get("perfil","CONSULTA"),"CADASTROS",user.get("id")):
                st.page_link("pages/13_Favorecidos_Fornecedores.py", label="↳ Pessoas / Favorecidos")
                st.page_link("pages/14_Contas_Bancarias.py", label="↳ Bancos / Contas Bancárias")
                st.page_link("pages/12_Codigos_Grupos_DRE.py", label="↳ Plano de Códigos")
            if permitido(user.get("perfil","CONSULTA"),"CONFIGURAR",user.get("id")):
                st.page_link("pages/15_Centros_de_Custo.py", label="↳ Centros de Custo")
            if permitido(user.get("perfil","CONSULTA"),"PATRIMONIO",user.get("id")):
                st.page_link("pages/11_Patrimonio.py", label="↳ Patrimônio")
        with st.expander("💰 Financeiro", expanded=False):
            links=[
                ("LANCAR","pages/02_Lancamentos.py","Lançamentos"),("CONSULTAR","pages/04_Banco.py","Banco"),
                ("CONSULTAR","pages/05_Caixa.py","Caixa"),("CORRIGIR","pages/03_Correcao_Estorno.py","Correção / Estorno"),
                ("IMPORTAR","pages/37_Importar_Movimento_PDF.py","Importar Movimento PDF"),("IMPORTAR","pages/38_Importar_Extratos_PDF.py","Importar Extratos PDF"),
                ("IMPORTAR","pages/06_Extratos_Bancarios.py","Extratos Bancarios"),("IMPORTAR","pages/07_Importacao_IA.py","Importação IA"),
                ("CONFERIR","pages/08_Conferencia.py","Conferência"),("CONCILIAR","pages/09_Conciliacao.py","Conciliação"),
                ("FLUXO","pages/10_Fluxo_de_Caixa.py","Fluxo de Caixa"),("LANCAR","pages/40_Folha_Pagamento.py","Folha de Pagamento / Recibos"),("FECHAR","pages/17_Fechamento_Mensal.py","Fechamento Mensal"),
            ]
            for ac,path,label in links:
                if permitido(user.get("perfil","CONSULTA"),ac,user.get("id")):
                    st.page_link(path,label=f"↳ {label}")
        if permitido(user.get("perfil","CONSULTA"),"RELATORIOS",user.get("id")):
            with st.expander("📊 Relatórios", expanded=False):
                st.page_link("pages/23_Relatorio_Movimento_Financeiro.py",label="↳ Movimento Financeiro")
                st.page_link("pages/24_Relatorio_Resumo_Banco.py",label="↳ Resumo Geral Banco")
                st.page_link("pages/25_Relatorio_Resumo_Caixa.py",label="↳ Resumo Geral Caixa")
                st.page_link("pages/26_Relatorio_Resumo_Banco_Caixa.py",label="↳ Banco + Caixa")
                st.page_link("pages/27_Relatorio_Suprimento_Caixa.py",label="↳ Suprimento de Caixa")
                st.page_link("pages/16_Relatorios_DRE.py",label="↳ DRE")
                st.page_link("pages/28_Relatorio_Saldos_Historicos.py",label="↳ Saldos por Ano")
                st.page_link("pages/29_Central_Outros_Relatorios.py",label="↳ Outros Relatórios")
        st.page_link("pages/31_Prestacoes_Contas.py", label="📤 Prestacao de Contas")
        if permitido(user.get("perfil","CONSULTA"),"CONSULTAR",user.get("id")):
            st.page_link("pages/15_Pesquisa_Avancada.py", label="🔎 Pesquisa Avancada")



def require_login(acao: str | None = None):
    bootstrap_app()
    if not login_screen():
        st.stop()
    user=_refresh_session_user()
    _hide_unauthorized_pages(user)
    tenant=_select_tesouraria_ativa(user)
    st.session_state.tesouraria=tenant
    _enforce_page_context()
    hierarchical_sidebar(user)
    if acao and not permitido(user.get("perfil","CONSULTA"),acao,user.get("id")):
        st.error("Acesso negado. Seu perfil não possui permissão para está página ou operação.")
        st.stop()
    return user


def require_admin(user: dict | None = None):
    user=user or st.session_state.get("user") or {}
    if user.get("perfil")!="ADMINISTRADOR":
        st.error("Operação permitida somente a Administrador.")
        st.stop()
    return user


def topbar(title: str, subtitle: str = ""):
    """Cabeçalho coerente com o contexto autenticado.

    Na CENTRAL nunca exibe linguagem de unidade operacional/saldo. Em FILIAL/TESTE
    exibe somente a identidade da unidade autenticada.
    """
    user=st.session_state.get("user") or {}
    ctx=_session_context()
    c1,c2=st.columns([5,1])
    with c1:
        st.title(title)
        if subtitle:
            st.caption(subtitle)
        if ctx == "CENTRAL":
            st.caption(f"👑 CENTRAL DAS TESOURARIAS · Administração/Auditoria · Código-base {app_version()}")
        else:
            unit_banner(compact=True)
    with c2:
        st.caption(f"👤 {user.get('nome','')}")
        st.caption(user.get("perfil",""))
        if st.button("Sair",key=f"logout_{title}"):
            st.session_state.clear(); st.switch_page("app.py")


def db_badge():
    ok,backend=healthcheck()
    if ok: st.success(f"Banco: {backend}",icon="✅")
    else: st.error(f"Falha no banco: {backend}")


def code_options(codigos):
    return {f"{x['codigo']} — {x['descricao']}":x['id'] for x in codigos}


def account_options(contas):
    return {f"{x['nome']} ({x['tipo']})":x['id'] for x in contas}
