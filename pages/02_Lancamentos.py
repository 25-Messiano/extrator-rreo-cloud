import streamlit as st
from datetime import date
from ui.common import require_login,topbar,code_options,account_options
from ui.help_modulos import botao_ajuda
from services.financeiro import (
    listar_codigos, listar_contas, listar_centros_custo, criar_lancamento,
    criar_transferencia_interna, listar_lancamentos, listar_favorecidos,
)

u=require_login("LANCAR");topbar("Lançamentos","Base oficial única: Data | Código | B/C | Pessoa | Centro de Custo | Especificação | Entrada/Saída")
botao_ajuda("lancamentos")
cont=account_options(listar_contas());
centros=listar_centros_custo(); cmap={f"{x['codigo']} — {x['nome']}":x['id'] for x in centros}
favs=listar_favorecidos(); fmap={f"{x['codigo']} | {x['nome']}":x for x in favs}

tab1,tab2=st.tabs(["Novo lançamento","Transferência Banco → Caixa"])
with tab1:
    nat=st.radio("Natureza do lançamento",["ENTRADA","SAIDA"],horizontal=True,key="nat_lancamento")
    catalogo=listar_codigos()
    codigos_permitidos=[x for x in catalogo if (x.get("permite_entrada") if nat=="ENTRADA" else x.get("permite_saida"))]
    cod=code_options(codigos_permitidos)
    st.caption(f"Mostrando somente códigos autorizados pelo administrador para {nat}.")
    with st.form("novo_lanc"):
        a,b,c=st.columns(3);dt=a.date_input("Data",date.today());comp=b.text_input("Competência",value=dt.strftime("%Y-%m"));bc=c.selectbox("B/C",["B","C"],format_func=lambda x:"Banco" if x=="B" else "Caixa")
        e,f=st.columns(2);ck=e.selectbox("Código",["— Sem código —"]+list(cod));acct=f.selectbox("Conta",["—"]+list(cont))
        cc=st.selectbox("Centro de Custo",["— Sem centro de custo —"]+list(cmap))
        esp=st.text_area("Especificação",height=90)
        g,h=st.columns(2);favk=g.selectbox("Pessoa/Entidade",["— Não cadastrado —"]+list(fmap));fav_livre=g.text_input("Favorecido/Origem (se não cadastrado)");doc=h.text_input("Documento / referência bancária")
        valor=st.number_input("Valor (R$)",min_value=0.01,step=0.01,format="%.2f");status=st.selectbox("Status",["APROVADO","RASCUNHO"])
        ok=st.form_submit_button("Salvar lançamento",type="primary")
    if ok:
        try:
            fx=fmap.get(favk); fav=fx["nome"] if fx else fav_livre
            rid=criar_lancamento(dt,cod.get(ck),bc,nat,esp,valor,cont.get(acct),fav,doc,comp,status,"MANUAL",u["id"],favorecido_id=fx["id"] if fx else None,centro_custo_id=cmap.get(cc))
            st.success(f"Lançamento #{rid} salvo com sucesso.")
        except Exception as exc:st.error(str(exc))
with tab2:
    bancos={k:v for k,v in cont.items() if "(BANCO)" in k};caixas={k:v for k,v in cont.items() if "(CAIXA)" in k}
    ambos=[x for x in listar_codigos() if x.get("permite_entrada") and x.get("permite_saida")]
    cod_ambos=code_options(ambos)
    labels=list(cod_ambos)
    padrao_0801=next((i for i,k in enumerate(labels) if k.startswith("0801 ")),0)
    with st.form("transf"):
        dt=st.date_input("Data da transferência",date.today(),key="td");valor=st.number_input("Valor",min_value=0.01,step=0.01,key="tv");banco=st.selectbox("Conta Banco",list(bancos) or ["Cadastre uma conta Banco"]);caixa=st.selectbox("Conta Caixa",list(caixas) or ["Cadastre uma conta Caixa"]);codigo_transf=st.selectbox("Código da transferência (precisa permitir Entrada e Saída)",labels or ["— Sem código bidirecional cadastrado —"],index=padrao_0801 if labels else 0);esp=st.text_input("Especificação","SUPRIMENTO DE CAIXA");ok=st.form_submit_button("Registrar transferência")
    if ok:
        try:
            cid=cod_ambos.get(codigo_transf)
            if not cid: raise ValueError("Cadastre ou autorize um código para Entrada e Saída antes de registrar a transferência.")
            x,y=criar_transferencia_interna(dt,valor,bancos.get(banco),caixas.get(caixa),esp,codigo_id=cid,usuario_id=u["id"]);st.success(f"Transferência registrada: saída #{x} e entrada #{y}.")
        except Exception as exc:st.error(str(exc))
st.divider();st.subheader("Últimos lançamentos");st.dataframe(listar_lancamentos(limit=100),width="stretch",hide_index=True)
