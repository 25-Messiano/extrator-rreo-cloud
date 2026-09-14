import pandas as pd
import streamlit as st

from ui.common import require_login, topbar
from ui.help_modulos import botao_ajuda
from services.security import (
    DESCRICOES_PERMISSOES,
    PERFIS_VALIDOS,
    PERMISSOES,
    alterar_senha,
    criar_usuario,
    permissoes_efetivas,
    atualizar_email_usuario,
    solicitar_recuperacao_senha,
)
from services.administracao import listar_usuarios, atualizar_usuario, TODAS_ACOES

u=require_login("USUARIOS")
topbar("Usuários e Permissões","Perfis oficiais, permissões individuais, proteção do Administrador e auditoria")
botao_ajuda("usuarios")

if u["perfil"]!="ADMINISTRADOR":
    st.error("Somente Administrador pode administrar usuários.")
    st.stop()

st.info(
    "As permissões entram em vigor imediatamente. O menu oculta páginas sem acesso e o servidor também bloqueia acesso direto por URL. "
    "O sistema nunca permite remover o último Administrador ativo."
)

@st.dialog("Novo usuário")
def novo():
    with st.form("form_novo_usuario"):
        nome=st.text_input("Nome *")
        email=st.text_input("E-mail de login *", help="O e-mail é a identidade de acesso e deve ser exclusivo para este usuário.")
        perfil=st.selectbox("Perfil",list(PERFIS_VALIDOS))
        senha=st.text_input("Senha inicial *",type="password",help="Mínimo de 10 caracteres, contendo letra e número.")
        confirmar=st.text_input("Confirmar senha *",type="password")
        ok=st.form_submit_button("Criar usuário",type="primary",width="stretch")
    if ok:
        if senha!=confirmar:
            st.error("A confirmação da senha não confere.")
            return
        try:
            uid=criar_usuario(nome,email,senha,perfil,email,usuario_id=u["id"])
            st.success(f"Usuário #{uid} criado com sucesso.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

c1,c2=st.columns([1,4])
if c1.button("+ Novo usuário",type="primary",width="stretch"):
    novo()
with c2:
    st.caption("Para acesso comum, prefira os perfis padrão. Use permissões individuais somente quando houver necessidade específica.")

rows=listar_usuarios()
if rows:
    tabela=[]
    for r in rows:
        tabela.append({
            "ID":r["id"],"Nome":r["nome"],"E-mail (login)":r["email"],
            "Perfil":r["perfil"],"Ativo":r["ativo"],"Último acesso":r["ultimo_acesso"],
            "Regra":("Individual" if r["permissoes"] else "Perfil padrão"),
        })
    st.dataframe(pd.DataFrame(tabela),width="stretch",hide_index=True)
else:
    st.warning("Nenhum usuário cadastrado.")

st.subheader("Matriz oficial de perfis")
mat=[]
for perfil in PERFIS_VALIDOS:
    acoes=PERMISSOES.get(perfil,set())
    if "*" in acoes:
        texto="Acesso total"
    else:
        texto="; ".join(DESCRICOES_PERMISSOES.get(a,a) for a in sorted(acoes))
    mat.append({"Perfil":perfil,"Acesso padrão":texto})
st.dataframe(pd.DataFrame(mat),width="stretch",hide_index=True)

if rows:
    st.divider()
    st.subheader("Administrar usuário")
    mp={f"#{x['id']} | {x['nome']} | {x.get('email') or 'SEM E-MAIL'}":x for x in rows}
    rotulo=st.selectbox("Usuário",list(mp),key="adm_usuario_sel")
    x=mp[rotulo]

    a,b=st.columns(2)
    perfil=a.selectbox("Perfil",list(PERFIS_VALIDOS),index=list(PERFIS_VALIDOS).index(x["perfil"]),key=f"perfil_{x['id']}")
    ativo=b.checkbox("Usuário ativo",bool(x["ativo"]),key=f"ativo_{x['id']}")

    st.markdown("#### Permissões")
    if perfil=="ADMINISTRADOR":
        modo="Usar perfil padrão"
        st.success("Administrador possui acesso total por definição; permissões individuais não se aplicam a este perfil.")
    else:
        modo=st.radio(
            "Modo de acesso",
            ["Usar perfil padrão","Usar permissões individuais"],
            index=1 if x["permissoes"] else 0,
            horizontal=True,
            key=f"modo_perm_{x['id']}",
        )
    labels={p:f"{p} — {DESCRICOES_PERMISSOES.get(p,p)}" for p in TODAS_ACOES}
    default=[labels[p] for p in x["permissoes"] if p in labels]
    selecionadas=st.multiselect(
        "Permissões individuais",
        [labels[p] for p in TODAS_ACOES],
        default=default,
        disabled=(modo=="Usar perfil padrão"),
        key=f"perm_{x['id']}",
        help="Quando ativadas, estas permissões substituem o perfil padrão para este usuário.",
    )
    custom=[v.split(" — ",1)[0] for v in selecionadas]

    efetivas=permissoes_efetivas(x["id"])
    st.caption("Permissões efetivas atuais: " + (", ".join(efetivas) if efetivas else "nenhuma"))

    if st.button("Salvar perfil e permissões",type="primary",key=f"salvar_usuario_{x['id']}"):
        try:
            atualizar_usuario(
                x["id"],perfil,ativo,
                [] if modo=="Usar perfil padrão" else custom,
                u["id"],
            )
            st.success("Usuário atualizado. A alteração passa a valer imediatamente.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    st.markdown("#### E-mail de login e recuperação")
    with st.form(f"form_email_{x['id']}"):
        email_novo=st.text_input("E-mail de login", value=x.get("email", ""), key=f"email_usuario_{x['id']}")
        salvar_mail=st.form_submit_button("Salvar e-mail")
    if salvar_mail:
        try:
            atualizar_email_usuario(x["id"], email_novo, u["id"])
            st.success("E-mail de login atualizado. Sessões antigas desse usuário serão invalidadas.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    if x.get("email"):
        if st.button("📧 Enviar link de recuperação de senha", key=f"enviar_reset_{x['id']}"):
            try:
                resultado=solicitar_recuperacao_senha(x["email"])
                if resultado.get("enviado"):
                    st.success("Link de recuperação enviado para o e-mail cadastrado.")
                else:
                    st.warning("O pedido foi registrado, mas o e-mail não pôde ser enviado. Confira a configuração SMTP da Central.")
            except Exception as e:
                st.error(str(e))

    st.markdown("#### Redefinição administrativa de emergência")
    st.caption("Prefira o link por e-mail. Use a redefinição manual apenas em emergência; a senha antiga nunca é exibida.")
    with st.form(f"form_senha_{x['id']}",clear_on_submit=True):
        nova=st.text_input("Nova senha",type="password",help="Mínimo de 10 caracteres, contendo letra e número.")
        confirma=st.text_input("Confirmar nova senha",type="password")
        mudar=st.form_submit_button("Redefinir senha")
    if mudar:
        if nova!=confirma:
            st.error("A confirmação da senha não confere.")
        else:
            try:
                alterar_senha(x["id"],nova,usuario_id_executor=u["id"])
                st.success("Senha redefinida e operação registrada na Auditoria.")
            except Exception as e:
                st.error(str(e))
