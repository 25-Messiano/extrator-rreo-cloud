import streamlit as st
import pandas as pd
from ui.common import require_login,topbar,code_options
from ui.help_modulos import botao_ajuda
from services.importacao_extrato import listar_importacoes,listar_itens,atualizar_item,liberar_importacao,atualizar_itens_em_massa
from services.financeiro import listar_codigos,listar_favorecidos
from services.exportacao import dataframe_excel_bytes,json_bytes

u=require_login("CONFERIR");topbar("Conferência","Revisão humana antes da liberação para a base oficial")
botao_ajuda("conferencia")
imps=listar_importacoes();opts={f"#{x['id']} | {x.get('competencia') or 'sem competência'} | {x['arquivo']} | {x['status']}":x['id'] for x in imps}
if not opts:st.info("Nenhuma importação aguardando conferência.");st.stop()
iid=opts[st.selectbox("Importação",list(opts))];itens=listar_itens(iid);df=pd.DataFrame(itens);st.dataframe(df,width="stretch",hide_index=True)
c1,c2=st.columns(2);c1.download_button("Baixar Excel de conferência",dataframe_excel_bytes(df,"Conferencia"),file_name=f"conferencia_{iid}.xlsx");c2.download_button("Baixar JSON de conferência",json_bytes({"importacao_id":iid,"itens":itens}),file_name=f"conferencia_{iid}.json",mime="application/json")

with st.expander("✏️ Edição em massa", expanded=False):
    st.caption("Selecione itens e aplique uma decisão humana comum. Duplicados exatos nunca são aprovados em massa.")
    elegiveis=[x for x in itens if x["status"] not in ("LIBERADO",)]
    emap={f"#{x['id']} | {x['data']} | {x['historico'][:55]} | R$ {x['valor']:.2f}":x["id"] for x in elegiveis}
    selecionados=st.multiselect("Itens",list(emap),key="conf_massa_itens")
    cm1,cm2=st.columns(2); decisao=cm1.selectbox("Decisão",["APROVADO","CORRIGIR","IGNORADO","PENDENTE"],key="conf_massa_status"); obs_massa=cm2.text_input("Observação comum",key="conf_massa_obs")
    ciencia=st.checkbox("Confirmo que revisei os itens selecionados",key="conf_massa_ciencia")
    if st.button("Aplicar decisão aos selecionados",disabled=(not selecionados or not ciencia)):
        n=atualizar_itens_em_massa(iid,[emap[x] for x in selecionados],decisao,u["id"],obs_massa); st.success(f"{n} item(ns) atualizado(s)."); st.rerun()
if itens:
    item_map={f"#{x['id']} | {x['data']} | {x['historico'][:60]} | R$ {x['valor']:.2f}":x for x in itens};sel=st.selectbox("Revisar item",list(item_map));r=item_map[sel];cod=code_options(listar_codigos());opts_code=["—"]+list(cod); current=next((k for k in cod if k.startswith((r["codigo"] or "")+" ")),"—"); ck=st.selectbox("Código",opts_code,index=opts_code.index(current) if current in opts_code else 0);esp=st.text_area("Especificação",r["historico"]);obs=st.text_input("Observação")
    favs=listar_favorecidos(); fmap={f"{x['codigo']} | {x['nome']} | {x['tipo']}":x['id'] for x in favs}; fopts=["— Não identificado —"]+list(fmap); favsel=st.selectbox("Pessoa / Entidade",fopts)
    st.caption(f"Classificação: {r.get('origem_classificacao','')} | Modelo: {r.get('modelo_ia','') or 'local'} | Confiança: {r.get('confianca',0):.0%}")
    if r.get("justificativa_ia"): st.info("Justificativa da IA: "+r["justificativa_ia"])
    if r.get("origem_classificacao")=="OPENAI" and r.get("confianca",0)<0.80: st.warning("Confiança da IA abaixo de 80%. Revise pessoa, código e especificação com atenção.")
    if r.get("duplicidade")=="DUPLICADO_EXATO": st.error(f"DUPLICADO EXATO: lançamento #{r.get('similar_id')} já existe. Este item está bloqueado e não deve ser lançado novamente.")
    elif r.get("duplicidade")=="POSSIVEL_DUPLICIDADE": st.warning(f"POSSÍVEL DUPLICIDADE: existe lançamento #{r.get('similar_id')} com mesma data/valor/B-C/natureza. Confira pessoa, código, especificação e documento antes de aprovar.")
    a,b,c=st.columns(3)
    if a.button("Aprovar"):
        atualizar_item(r["id"],"APROVADO",cod.get(ck),esp,obs,u["id"],fmap.get(favsel));st.success("Item aprovado.");st.rerun()
    if b.button("Marcar para correção"):
        atualizar_item(r["id"],"CORRIGIR",cod.get(ck),esp,obs,u["id"],fmap.get(favsel));st.warning("Item marcado para correção.");st.rerun()
    if c.button("Ignorar"):
        atualizar_item(r["id"],"IGNORADO",cod.get(ck),esp,obs,u["id"],fmap.get(favsel));st.success("Item ignorado.");st.rerun()
    pend=sum(1 for x in itens if x["status"] in ("PENDENTE","CONFERIR_DUPLICIDADE","CORRIGIR"))
    st.caption(f"Pendentes: {pend}")
    if st.button("LIBERAR APROVADOS PARA A BASE OFICIAL",type="primary",disabled=pend>0):
        try:n,d=liberar_importacao(iid,u["id"]);st.success(f"Liberação concluída: {n} lançamento(s) criado(s); {d} duplicidade(s) bloqueada(s).")
        except Exception as exc:st.error(str(exc))
