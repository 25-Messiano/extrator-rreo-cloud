import streamlit as st
from datetime import date
import pandas as pd

from ui.common import require_login, topbar, unit_banner
from services.financeiro import salvar_patrimonio, listar_patrimonio, listar_favorecidos
from services.administracao import atualizar_patrimonio, listar_movimentos_patrimonio
from services.patrimonio import (
    SITUACOES, ESTADOS_CONSERVACAO, listar_aquisicoes_patrimoniais_pendentes, cadastrar_de_lancamento,
    listar_para_relatorio, relatorio_excel_bytes, relatorio_pdf_bytes, listar_competencias_movimentacao,
    resumo_movimentacao_competencia, movimentacao_pdf_bytes, adicionar_anexo, listar_anexos, obter_anexo, arquivar_anexo,
)

u=require_login("PATRIMONIO")
topbar("Patrimônio", "Cadastro completo, documentos, competência, vínculo financeiro e relatórios patrimoniais")
unit_banner(compact=True)


def _df(rows):
    df=pd.DataFrame(rows)
    for col in df.columns:
        if "data" in str(col).lower() or "aquisi" in str(col).lower() or "criado" in str(col).lower():
            df[col]=df[col].apply(lambda x:x.strftime("%d/%m/%Y") if hasattr(x,"strftime") else x)
    return df


def _fmt_tamanho(n):
    n=int(n or 0)
    return f"{n/1024/1024:.2f} MB" if n>=1024*1024 else f"{n/1024:.1f} KB"


@st.dialog("❓ Como usar a área de Patrimônio", width="large")
def ajuda_patrimonio():
    st.markdown("""
### Regras de uso do Patrimônio
Cada filial mantém **seu próprio cadastro patrimonial**, sem misturar bens de outras unidades.

**1. Cadastro de bens permanentes**  
Registre **Nº patrimonial, descrição, categoria, data de aquisição, valor, fornecedor, Nota Fiscal, local de uso, responsável, estado de conservação, vida útil e situação**. O número patrimonial deve ser único dentro da filial.

**2. Entrada manual ou por lançamento**  
O bem pode ser cadastrado manualmente ou nascer de uma **SAÍDA oficial** cujo código esteja marcado no Plano de Códigos como **Gerar/identificar patrimônio**. Isso inclui lançamentos liberados da Importação de Movimento PDF. A identificação é uma sugestão; a criação do bem exige confirmação humana.

**3. Fornecedor e Nota Fiscal**  
Sempre que possível, selecione o fornecedor já cadastrado em **Pessoas / Favorecidos**. O nome e a NF permanecem gravados no cadastro do bem para consulta e relatório.

**4. Estado de conservação e vida útil**  
Use o estado de conservação para registrar a condição física/funcional do bem. A vida útil é informada em anos e serve como referência administrativa; ela não baixa o bem automaticamente.

**5. Situação patrimonial**  
- **ATIVO** — em uso normal.  
- **INATIVO** — temporariamente sem uso, mas ainda pertencente à filial.  
- **EM_MANUTENCAO** — temporariamente fora de uso para manutenção.  
- **OBSOLETO** — permanece no banco e no histórico, mas fica fora do relatório padrão.  
- **TRANSFERIDO** — mudou de destinação, mantendo rastreabilidade.  
- **BAIXADO** — retirado formalmente do patrimônio, sem apagar o histórico.

Mudanças para **OBSOLETO, TRANSFERIDO ou BAIXADO** devem ser justificadas. Nenhuma dessas situações exclui o registro histórico.

### Bens obsoletos não são apagados
Marcar um bem como **OBSOLETO** nunca exclui o registro do banco nem o lançamento de origem. Ele continua disponível para pesquisa, auditoria e histórico; apenas deixa de aparecer no relatório patrimonial padrão.

**6. Anexos de documentos**  
Na área **Documentos do bem**, podem ser anexados NF, foto, termo de responsabilidade, termo de transferência, termo de baixa ou outro comprovante. Os arquivos ficam vinculados ao bem e à filial. Cada arquivo pode ter até **10 MB**. Quando um anexo deixa de ser necessário, ele é arquivado com registro de auditoria, em vez de apagar a história sem rastreio.

**7. Movimentação por competência**  
A aquisição entra na competência da data de aquisição. Alterações posteriores entram na competência da **data da movimentação**, sempre exibida em **DD/MM/AAAA**. Assim é possível saber em que mês houve aquisição, manutenção, inativação, reativação, obsolescência, transferência ou baixa.

**8. Relatórios patrimoniais**  
Os relatórios podem mostrar bens em uso, ativos, inativos, em manutenção, obsoletos, transferidos, baixados ou todos. O filtro escolhido vale igualmente para **PDF e Excel**. O relatório padrão não mostra obsoletos nem baixados.

### Regra central
**o patrimônio nunca desaparece da história. O bem muda de situação; os relatórios decidem o que deve ser exibido.**

### Fluxo recomendado
**Lançamento/Importação PDF → Conferência → Código patrimonial → Confirmação do bem → Cadastro completo + anexos → Movimentações por competência → Relatórios PDF/Excel.**
""")

c_help1,c_help2=st.columns([12,1])
with c_help2:
    if st.button("❓",key="ajuda_patrimonio",help="Regras e instruções de uso do Patrimônio",width="stretch"):
        ajuda_patrimonio()

st.info("Bens inativos, obsoletos, transferidos ou baixados permanecem no banco e na auditoria. O relatório padrão apenas filtra o que deve ser exibido.",icon="ℹ️")

tab1,tab2,tab3,tab4,tab5=st.tabs(["📦 Cadastro patrimonial","🔗 Aquisições identificadas","📎 Documentos do bem","📅 Movimentação por competência","📊 Relatórios"])

with tab1:
    favorecidos=listar_favorecidos()
    fav_map={f"{x['codigo']} · {x['nome']}":x for x in favorecidos}

    @st.dialog("Novo bem patrimonial",width="large")
    def novo_bem():
        c1,c2=st.columns(2)
        numero=c1.text_input("Nº Patrimonial")
        categoria=c2.text_input("Categoria")
        descricao=st.text_input("Descrição do bem")
        c1,c2=st.columns(2)
        dt=c1.date_input("Data de aquisição",date.today(),format="DD/MM/YYYY")
        valor=c2.number_input("Valor de aquisição (R$)",min_value=0.0,step=0.01)
        fornecedor_id=None; fornecedor_texto=""
        if fav_map:
            op=st.selectbox("Fornecedor cadastrado",["— Não vincular —"]+list(fav_map))
            if op!="— Não vincular —": fornecedor_id=fav_map[op]["id"]; fornecedor_texto=fav_map[op]["nome"]
        fornecedor_texto=st.text_input("Fornecedor / Razão social",value=fornecedor_texto,help="Pode ser preenchido manualmente quando o fornecedor ainda não estiver no cadastro.")
        nf=st.text_input("Nota Fiscal / documento de aquisição")
        c1,c2=st.columns(2); local=c1.text_input("Local de uso"); resp=c2.text_input("Responsável")
        c1,c2,c3=st.columns(3)
        conserv=c1.selectbox("Estado de conservação",[""]+list(ESTADOS_CONSERVACAO),index=0)
        vida=c2.number_input("Vida útil (anos)",min_value=0,max_value=100,value=0,step=1)
        sit=c3.selectbox("Situação inicial",list(SITUACOES),index=0)
        if st.button("Salvar bem",type="primary",width="stretch"):
            try:
                salvar_patrimonio(descricao,numero,categoria,dt,valor,fornecedor_texto,nf,local,resp,sit,
                    usuario_id=u["id"],estado_conservacao=conserv or None,vida_util_anos=vida or None,fornecedor_id=fornecedor_id)
                st.success("Bem cadastrado com sucesso."); st.rerun()
            except Exception as e: st.error(str(e))

    if st.button("+ Novo patrimônio",type="primary"): novo_bem()
    rows=listar_patrimonio(); st.caption(f"Total cadastrado nesta unidade: {len(rows)}")
    if rows:
        st.dataframe(_df(rows),width="stretch",hide_index=True)
        mp={f"#{x['id']} | {x['numero'] or 'SEM Nº'} | {x['descricao']}":x for x in rows}
        x=mp[st.selectbox("Administrar bem",list(mp))]
        with st.form("editar_patrimonio"):
            c1,c2=st.columns(2); numero=c1.text_input("Nº Patrimonial",x["numero"]); cat=c2.text_input("Categoria",x["categoria"])
            desc=st.text_input("Descrição",x["descricao"])
            c1,c2=st.columns(2); dt=c1.date_input("Data de aquisição",x["aquisição"] or date.today(),format="DD/MM/YYYY"); valor=c2.number_input("Valor de aquisição (R$)",min_value=0.0,value=float(x["valor"]),step=0.01)
            fav_labels=["— Sem vínculo —"]+list(fav_map); current="— Sem vínculo —"
            if x.get("fornecedor_id"):
                for lab,f in fav_map.items():
                    if f["id"]==x["fornecedor_id"]: current=lab; break
            sel_fav=st.selectbox("Fornecedor cadastrado",fav_labels,index=fav_labels.index(current) if current in fav_labels else 0)
            fornecedor_id=None if sel_fav=="— Sem vínculo —" else fav_map[sel_fav]["id"]
            forn=st.text_input("Fornecedor / Razão social",x["fornecedor"])
            nf=st.text_input("Nota Fiscal / documento de aquisição",x.get("nota_fiscal", ""))
            c1,c2=st.columns(2); local=c1.text_input("Local de uso",x["local"]); resp=c2.text_input("Responsável",x["responsável"])
            c1,c2,c3=st.columns(3)
            conserv_atual=x.get("conservação",""); cons_opts=[""]+list(ESTADOS_CONSERVACAO)
            conserv=c1.selectbox("Estado de conservação",cons_opts,index=cons_opts.index(conserv_atual) if conserv_atual in cons_opts else 0)
            vida=c2.number_input("Vida útil (anos)",min_value=0,max_value=100,value=int(x.get("vida_útil_anos") or 0),step=1)
            atual=x["situação"] if x["situação"] in SITUACOES else "ATIVO"; sit=c3.selectbox("Situação",list(SITUACOES),index=list(SITUACOES).index(atual))
            data_mov=st.date_input("Data da movimentação",date.today(),format="DD/MM/YYYY",help="Define a competência em que a mudança de situação/local/responsável será registrada.")
            mot=st.text_area("Motivo/observação da alteração")
            if st.form_submit_button("Salvar alteração",type="primary"):
                try:
                    if sit in ("OBSOLETO","BAIXADO","TRANSFERIDO") and sit!=atual and not mot.strip(): raise ValueError("Informe o motivo da mudança de situação.")
                    atualizar_patrimonio(x["id"],numero_patrimonial=numero.strip() or None,descricao=desc,categoria=cat,data_aquisicao=dt,valor=valor,
                        fornecedor=forn,fornecedor_id=fornecedor_id,nota_fiscal=nf,local_uso=local,responsavel=resp,
                        estado_conservacao=conserv or None,vida_util_anos=vida or None,situacao=sit,data_movimento=data_mov,
                        observacao_movimento=mot,usuario_id=u["id"])
                    st.success("Patrimônio atualizado sem apagar o histórico."); st.rerun()
                except Exception as exc: st.error(str(exc))
        movs=listar_movimentos_patrimonio(x["id"]); st.subheader("Histórico do bem")
        if movs: st.dataframe(_df(movs),width="stretch",hide_index=True)
        else: st.caption("Ainda não há alterações registradas para este bem.")
    else: st.info("Nenhum bem cadastrado.")

with tab2:
    st.markdown("#### Lançamentos que podem virar patrimônio")
    st.caption("Saídas oficiais com código marcado como patrimonial aparecem aqui. Inclui lançamento manual e Movimento PDF já conferido/liberado; o cadastro do bem exige confirmação.")
    pend=listar_aquisicoes_patrimoniais_pendentes()
    if not pend: st.success("Nenhuma aquisição patrimonial pendente de cadastro.")
    else:
        st.dataframe(_df(pend),width="stretch",hide_index=True)
        labels={f"#{r['lancamento_id']} | {r['data'].strftime('%d/%m/%Y')} | {r['codigo']} | R$ {r['valor']:,.2f} | {r['descricao'][:60]}":r for r in pend}
        esc=labels[st.selectbox("Aquisição para cadastrar",list(labels))]
        with st.form("patrimonio_de_lancamento"):
            st.text_input("Lançamento de origem",value=f"#{esc['lancamento_id']} · código {esc['codigo']}",disabled=True)
            c1,c2=st.columns(2); numero=c1.text_input("Nº Patrimonial"); categoria=c2.text_input("Categoria",value=esc["codigo_descricao"])
            descricao=st.text_input("Descrição do bem",value=esc["descricao"])
            c1,c2=st.columns(2); local=c1.text_input("Local de uso"); resp=c2.text_input("Responsável")
            c1,c2,c3=st.columns(3); conserv=c1.selectbox("Estado de conservação",[""]+list(ESTADOS_CONSERVACAO)); vida=c2.number_input("Vida útil (anos)",0,100,0); sit=c3.selectbox("Situação inicial",list(SITUACOES))
            ok=st.form_submit_button("Cadastrar bem e vincular ao lançamento",type="primary",width="stretch")
        if ok:
            try:
                rid=cadastrar_de_lancamento(esc["lancamento_id"],numero,descricao,categoria,local,resp,sit,u["id"],conserv or None,vida or None)
                st.success(f"Bem patrimonial #{rid} criado e vinculado ao lançamento #{esc['lancamento_id']}."); st.rerun()
            except Exception as exc: st.error(str(exc))

with tab3:
    st.markdown("#### Documentos do bem")
    bens=listar_patrimonio()
    if not bens: st.info("Cadastre um bem antes de anexar documentos.")
    else:
        mp={f"#{x['id']} | {x['numero'] or 'SEM Nº'} | {x['descricao']}":x for x in bens}; x=mp[st.selectbox("Bem patrimonial",list(mp),key="anexo_bem")]
        with st.form("novo_anexo_pat",clear_on_submit=True):
            up=st.file_uploader("Anexar documento",type=["pdf","png","jpg","jpeg","webp","doc","docx","xls","xlsx","csv","txt"],help="NF, foto, termo de responsabilidade, transferência, baixa ou outro documento. Máximo 10 MB por arquivo.")
            desc_an=st.text_input("Descrição do documento",placeholder="Ex.: Nota Fiscal nº 1234")
            salvar=st.form_submit_button("Salvar anexo",type="primary")
        if salvar:
            try:
                if not up: raise ValueError("Selecione um arquivo.")
                adicionar_anexo(x["id"],up.name,up.getvalue(),up.type,desc_an,u["id"]); st.success("Documento anexado ao patrimônio."); st.rerun()
            except Exception as exc: st.error(str(exc))
        anexos=listar_anexos(x["id"])
        if not anexos: st.caption("Nenhum documento anexado a este bem.")
        else:
            st.dataframe(_df([{**a,"tamanho":_fmt_tamanho(a["tamanho"])} for a in anexos]),width="stretch",hide_index=True)
            for a in anexos:
                c1,c2,c3=st.columns([5,2,1]); c1.write(f"**{a['nome']}**  \n{a['descricao'] or 'Sem descrição'}")
                arq=obter_anexo(a["id"]); c2.download_button("⬇️ Baixar",arq["conteudo"],file_name=arq["nome"],mime=arq["tipo"],key=f"baixar_anexo_{a['id']}",width="stretch")
                if c3.button("🗃️",key=f"arquivar_anexo_{a['id']}",help="Arquivar anexo"):
                    arquivar_anexo(a["id"],u["id"]); st.rerun()

with tab4:
    st.markdown("#### Movimentação patrimonial por competência")
    competencias=listar_competencias_movimentacao(); hoje=date.today(); anos=sorted({int(c[:4]) for c in competencias}|{hoje.year},reverse=True)
    meses={1:"Janeiro",2:"Fevereiro",3:"Março",4:"Abril",5:"Maio",6:"Junho",7:"Julho",8:"Agosto",9:"Setembro",10:"Outubro",11:"Novembro",12:"Dezembro"}
    c1,c2=st.columns(2); ano=c1.selectbox("Ano",anos,key="pat_mov_ano"); mes=c2.selectbox("Mês / competência",list(meses),index=(hoje.month-1 if ano==hoje.year else 0),format_func=lambda m:f"{m:02d} · {meses[m]}",key="pat_mov_mes")
    resumo=resumo_movimentacao_competencia(ano,mes); movs=resumo["rows"]
    m1,m2,m3,m4,m5=st.columns(5); m1.metric("Movimentações",resumo["total"]); m2.metric("Aquisições",resumo["tipos"].get("AQUISICAO",0)); m3.metric("Inativações",resumo["tipos"].get("INATIVACAO",0)); m4.metric("Obsolescências",resumo["tipos"].get("OBSOLESCENCIA",0)); m5.metric("Baixas",resumo["tipos"].get("BAIXA",0))
    if movs: st.dataframe(_df(movs),width="stretch",hide_index=True)
    else: st.info(f"Não houve movimentação patrimonial em {meses[mes]}/{ano}.")
    titulo=f"MOVIMENTAÇÃO PATRIMONIAL · {meses[mes].upper()}/{ano}"; e1,e2=st.columns(2)
    e1.download_button("📄 Baixar movimentação em PDF",movimentacao_pdf_bytes(movs,titulo),file_name=f"movimentacao_patrimonio_{ano}_{mes:02d}.pdf",mime="application/pdf",width="stretch")
    e2.download_button("📊 Baixar movimentação em Excel",relatorio_excel_bytes(movs),file_name=f"movimentacao_patrimonio_{ano}_{mes:02d}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")

with tab5:
    st.markdown("#### Relatórios patrimoniais")
    opcoes={
        "Bens em uso (padrão — ativos + manutenção)":"EM_USO","Somente ativos":"ATIVOS","Somente inativos":"INATIVOS",
        "Somente em manutenção":"MANUTENCAO","Somente obsoletos":"OBSOLETOS","Somente transferidos":"TRANSFERIDOS",
        "Somente baixados":"BAIXADOS","Todos — posição patrimonial completa":"TODOS",
    }
    rot=st.selectbox("Conteúdo do relatório",list(opcoes)); modo=opcoes[rot]; rel=listar_para_relatorio(modo)
    total=sum(float(r.get("Valor (R$)") or 0) for r in rel); a,b,c=st.columns(3); a.metric("Itens",len(rel)); b.metric("Valor total",f"R$ {total:,.2f}".replace(",","X").replace(".",",").replace("X",".")); c.metric("Documentos anexos",sum(int(r.get("Anexos") or 0) for r in rel))
    if rel: st.dataframe(_df(rel),width="stretch",hide_index=True)
    else: st.info("Nenhum item encontrado para este filtro.")
    titulos={"EM_USO":"RELATÓRIO DE PATRIMÔNIO EM USO","ATIVOS":"RELATÓRIO DE BENS ATIVOS","INATIVOS":"RELATÓRIO DE BENS INATIVOS","MANUTENCAO":"RELATÓRIO DE BENS EM MANUTENÇÃO","OBSOLETOS":"RELATÓRIO DE BENS OBSOLETOS","TRANSFERIDOS":"RELATÓRIO DE BENS TRANSFERIDOS","BAIXADOS":"RELATÓRIO DE BENS BAIXADOS","TODOS":"RELATÓRIO PATRIMONIAL COMPLETO"}
    c1,c2=st.columns(2); c1.download_button("📄 Baixar PDF",relatorio_pdf_bytes(rel,titulos[modo]),file_name=f"patrimonio_{modo.lower()}.pdf",mime="application/pdf",width="stretch"); c2.download_button("📊 Baixar Excel",relatorio_excel_bytes(rel),file_name=f"patrimonio_{modo.lower()}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",width="stretch")
