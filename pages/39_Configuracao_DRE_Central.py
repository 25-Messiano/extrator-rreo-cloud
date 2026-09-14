import streamlit as st
from ui.common import require_login, require_admin, topbar
from services.tenancy import listar_tesourarias
from services.financeiro import listar_codigos,listar_grupos,salvar_grupo,listar_vinculos,configurar_codigos_grupo,mover_codigo_grupo,desvincular_codigo_grupo,auditoria_configuracao_dre

u=require_admin(require_login())
topbar("Configuracao Central da DRE","A estrutura oficial da DRE e o vinculo dos codigos de cada filial sao administrados exclusivamente pela Central.")
filiais=[t for t in listar_tesourarias(None) if t.get("tipo")!="CENTRAL"]
if not filiais:
    st.info("Nenhuma filial de producao cadastrada.");st.stop()
labels={f"{t['codigo']} - {t['nome']}":t for t in filiais}
sel=st.selectbox("Filial para enquadrar na DRE",list(labels));ten=labels[sel];tid=ten["id"]
st.caption(f"Plano de Codigos selecionado: {ten['nome']} ({ten['codigo']}). A filial pode editar seus codigos, mas nao pode alterar a DRE.")

@st.dialog("Novo grupo DRE oficial")
def novo_grupo():
    grupos=listar_grupos();pais={f"{g['codigo_grupo']} - {g['nome']}":g['id'] for g in grupos}
    cg=st.text_input("Codigo do grupo");nome=st.text_input("Nome");pai=st.selectbox("Grupo pai (opcional)",["-"]+list(pais));ordem=st.number_input("Ordem",0,9999,0)
    if st.button("Salvar grupo",type="primary"):
        salvar_grupo(cg,nome,pais.get(pai),ordem,usuario_id=u["id"]);st.rerun()
if st.button("+ Novo grupo DRE oficial"):novo_grupo()

res=auditoria_configuracao_dre(tid)
a,b,c,d=st.columns(4);a.metric("Codigos da filial",res["total"]);b.metric("Ativos",res["ativos"]);c.metric("Sem grupo DRE",len(res["sem_grupo"]));d.metric("Duplicidades",len(res["duplicados"]))
if res["duplicados"]:st.error("Ha codigos duplicados na configuracao DRE: "+", ".join(res["duplicados"]))

t1,t2,t3=st.tabs(["Enquadrar por grupo","Mover / remover vinculo","Mapa da filial"])
with t1:
    grupos=[g for g in listar_grupos() if g.get("ativo")]
    if not grupos:st.info("Nenhum grupo DRE oficial cadastrado.")
    else:
        gm={f"{g['codigo_grupo']} - {g['nome']}":g for g in grupos};gl=st.selectbox("Grupo DRE oficial",list(gm));g=gm[gl]
        cods=listar_codigos(True,tid);vincs=listar_vinculos(False,tid);vp={v['codigo_id']:v for v in vincs};atuais={v['codigo_id'] for v in vincs if v['grupo_id']==g['id']}
        opts=[];ids={}
        for c0 in cods:
            v=vp.get(c0['id']);suf=f" [ja em {v['grupo']}]" if v and v['grupo_id']!=g['id'] else "";rot=f"{c0['codigo']} - {c0['descricao']}{suf}";opts.append(rot);ids[rot]=c0['id']
        pad=[r for r,cid in ids.items() if cid in atuais];esc=st.multiselect("Codigos desta filial neste grupo",opts,default=pad)
        if st.button("Salvar enquadramento",type="primary"):
            try:
                configurar_codigos_grupo(g['id'],[ids[x] for x in esc],u['id'],tid);st.success("Enquadramento salvo pela Central.");st.rerun()
            except Exception as exc:st.error(str(exc))
with t2:
    vincs=listar_vinculos(False,tid);grupos=[g for g in listar_grupos() if g.get("ativo")]
    if not vincs:st.info("Ainda nao ha vinculos DRE para esta filial.")
    else:
        vm={f"{v['codigo']} - {v['codigo_descricao']} | {v['grupo']} - {v['grupo_nome']}":v for v in vincs};lab=st.selectbox("Vinculo",list(vm));v=vm[lab]
        gm={f"{g['codigo_grupo']} - {g['nome']}":g['id'] for g in grupos};dest=st.selectbox("Novo grupo",list(gm))
        c1,c2=st.columns(2)
        if c1.button("Mover",type="primary"):mover_codigo_grupo(v['codigo_id'],gm[dest],u['id']);st.rerun()
        conf=c2.checkbox("Confirmo remover o vinculo")
        if c2.button("Remover vinculo",disabled=not conf):desvincular_codigo_grupo(v['codigo_id'],u['id']);st.rerun()
with t3:
    st.dataframe(res["codigos"],width="stretch",hide_index=True)
    if res["sem_grupo"]:st.warning("Codigos ativos ainda sem enquadramento: "+", ".join(res["sem_grupo"]))
