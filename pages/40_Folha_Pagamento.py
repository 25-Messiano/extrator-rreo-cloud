import streamlit as st
from datetime import date
import pandas as pd
from ui.common import require_login, topbar, unit_banner
from services.folha_pagamento import *

u = require_login('LANCAR')
topbar('Folha de Pagamento', 'Gestão por competência, vigências, conferência, fechamento e recibos avulsos')
unit_banner(compact=True)

AJUDA = {
 'geral': '''### Como funciona a Folha
A Folha é separada dos lançamentos comuns. O fluxo recomendado é **RASCUNHO → EM CONFERÊNCIA → APROVADA → FECHADA → PAGA**. Uma competência fechada não deve ser sobrescrita: diferenças posteriores devem ser tratadas por folha **COMPLEMENTAR** ou ajuste auditável.

Os valores legais e internos não ficam fixos no código. Use **Parâmetros e Vigências** para cadastrar pisos, INSS, IRRF, FGTS quando aplicável, benefícios, férias, 13º, rescisões e demais regras com data de início/fim. Cada fechamento guarda uma fotografia dos parâmetros usados.

Use **Recibos Avulsos** para prestadores esporádicos; isso não os transforma em trabalhadores permanentes.''',
 'trabalhadores': '''### Trabalhadores
Cadastre pessoas recorrentes da folha. Mantenha CPF, vínculo, função, salário-base e dados cadastrais. Alterações de salário devem ser feitas em **Nova vigência salarial**, para que o valor anterior permaneça no histórico.

Tipos de vínculo podem ser usados conforme a realidade da entidade. Regras legais devem ser validadas pelo responsável/contador.''',
 'eventos': '''### Eventos da Folha
Eventos representam **PROVENTOS** ou **DESCONTOS**: salário, gratificação, adicional, benefício, falta, consignação, pensão, horas extras etc. A fórmula/regra é descritiva/configurável e não substitui a conferência humana.

Evite excluir eventos já usados; desative-os e mantenha o histórico.''',
 'parametros': '''### Parâmetros e Vigências
Nunca sobrescreva um parâmetro antigo para um novo ano. Cadastre uma **nova vigência**, por exemplo: piso até 31/12/2026 e novo piso a partir de 01/01/2027.

Grupos previstos: PISO, INSS, IRRF, FGTS, BENEFÍCIO, FÉRIAS, 13º, RESCISÃO e OUTRO. Informe fonte/referência quando possível. O sistema alerta se faltarem parâmetros essenciais para uma competência.''',
 'calendario': '''### Calendário da Folha
Organize abertura, limite para eventos, conferência, fechamento e pagamento previsto por competência. Essas datas ajudam o controle operacional e não alteram automaticamente cálculos.''',
 'fechamento': '''### Conferência e Fechamento
Antes de fechar, conclua o checklist: parâmetros, trabalhadores, eventos, dados bancários, centro de custo, encargos, comparação com mês anterior e aprovação. O fechamento cria um **snapshot** (fotografia) dos parâmetros e do checklist usados naquela competência.

Folha fechada só avança para PAGA; correções posteriores devem usar folha complementar.''',
 'recibos': '''### Recibos Avulsos
Cadastre/reutilize o prestador e gere um novo recibo a cada serviço. Dados permanentes são reaproveitados; data, competência, valor, serviço e comprovante pertencem a cada emissão. O recibo anterior nunca é sobrescrito.

O PDF contém identificação do prestador, documento, comprovante e quadro de assinaturas.'''
}

@st.dialog('❓ Orientação — Folha de Pagamento', width='large')
def ajuda(sec):
    st.markdown(AJUDA.get(sec, AJUDA['geral']))

c1,c2=st.columns([8,1])
with c1: st.caption('Vigências preservam o passado; fechamento preserva a fotografia da competência.')
with c2:
    if st.button('❓ Ajuda', key='ajuda_folha_geral'): ajuda('geral')

tabs=st.tabs(['👥 Trabalhadores','🧮 Eventos','⚙️ Parâmetros e Vigências','🗓️ Calendário','📅 Competências','✅ Conferência/Fechamento','🧾 Recibos Avulsos'])

with tabs[0]:
    a,b=st.columns([8,1]); a.subheader('Trabalhadores');
    if b.button('❓',key='aj_trab'): ajuda('trabalhadores')
    @st.dialog('Novo trabalhador',width='large')
    def nt():
        nome=st.text_input('Nome *'); c1,c2=st.columns(2); cpf=c1.text_input('CPF'); rg=c2.text_input('RG')
        tel=st.text_input('Telefone'); end=st.text_area('Endereço'); c1,c2=st.columns(2); cargo=c1.text_input('Cargo/Função'); v=c2.selectbox('Vínculo',['EMPREGADO','COLABORADOR','TEMPORARIO','DIRIGENTE','ESTAGIARIO','OUTRO'])
        sal=st.number_input('Salário-base atual',min_value=0.0,step=0.01)
        if st.button('Salvar',type='primary'):
            if not nome.strip(): st.error('Informe o nome.'); return
            wid=salvar_trabalhador(nome,cpf,rg,tel,end,cargo,v,sal)
            if sal>0: nova_vigencia_salarial(wid,sal,date.today(),'Cadastro inicial',u['id'])
            st.success('Trabalhador salvo.'); st.rerun()
    if st.button('+ Novo trabalhador',type='primary'): nt()
    rows=trabalhadores(); st.dataframe(rows,width='stretch',hide_index=True)
    if rows:
        mp={f"{x['nome']} · {x.get('cpf') or 'sem CPF'}":x['id'] for x in rows}
        sel=st.selectbox('Histórico/Vigência salarial',list(mp))
        hist=historico_salarial(mp[sel]); st.dataframe(hist,width='stretch',hide_index=True)
        with st.expander('➕ Nova vigência salarial'):
            c1,c2=st.columns(2); novo=c1.number_input('Novo salário',min_value=0.0,step=0.01,key='novo_sal'); ini=c2.date_input('Início da vigência',date.today(),format='DD/MM/YYYY',key='ini_sal'); motivo=st.text_input('Motivo da alteração')
            if st.button('Registrar nova vigência',type='primary'):
                nova_vigencia_salarial(mp[sel],novo,ini,motivo,u['id']); st.success('Nova vigência registrada sem apagar o histórico.'); st.rerun()

with tabs[1]:
    a,b=st.columns([8,1]); a.subheader('Eventos');
    if b.button('❓',key='aj_event'): ajuda('eventos')
    @st.dialog('Novo evento')
    def ne():
        c=st.text_input('Código'); d=st.text_input('Descrição'); n=st.selectbox('Natureza',['PROVENTO','DESCONTO']); f=st.text_area('Fórmula/regra (opcional)')
        if st.button('Salvar evento',type='primary'):
            if not c.strip() or not d.strip(): st.error('Informe código e descrição.'); return
            salvar_evento(c,d,n,f); st.rerun()
    if st.button('+ Novo evento'): ne()
    st.dataframe(eventos(),width='stretch',hide_index=True)

with tabs[2]:
    a,b=st.columns([8,1]); a.subheader('Parâmetros e Vigências');
    if b.button('❓',key='aj_param'): ajuda('parametros')
    grupos=['PISO','INSS','IRRF','FGTS','BENEFICIO','FERIAS','13_SALARIO','RESCISAO','CONSIGNACAO','OUTRO']
    filtro=st.selectbox('Grupo', ['TODOS']+grupos)
    st.dataframe(parametros_folha(filtro),width='stretch',hide_index=True)
    with st.expander('➕ Nova vigência de parâmetro',expanded=False):
        c1,c2=st.columns(2); g=c1.selectbox('Grupo *',grupos); chave=c2.text_input('Chave *',placeholder='Ex.: PISO_GERAL, FAIXA_1')
        desc=st.text_input('Descrição *'); c1,c2=st.columns(2); vd=c1.number_input('Valor numérico (se aplicável)',min_value=0.0,step=0.0001,format='%.4f'); vt=c2.text_input('Valor/texto (se aplicável)')
        c1,c2=st.columns(2); ini=c1.date_input('Início da vigência *',date.today(),format='DD/MM/YYYY'); tem_fim=c2.checkbox('Possui fim de vigência')
        fim=st.date_input('Fim da vigência',date.today(),format='DD/MM/YYYY') if tem_fim else None
        fonte=st.text_input('Fonte / referência'); obs=st.text_area('Observação')
        if st.button('Salvar nova vigência',type='primary'):
            if not chave.strip() or not desc.strip(): st.error('Informe chave e descrição.')
            elif fim and fim<ini: st.error('Fim da vigência não pode ser anterior ao início.')
            else: salvar_parametro(g,chave,desc,vd if vd!=0 else None,vt,ini,fim,fonte,obs,u['id']); st.success('Vigência salva.'); st.rerun()
    comp_alert=st.text_input('Verificar parâmetros da competência (MM/AAAA)',date.today().strftime('%m/%Y'))
    als=alertas_parametros(comp_alert)
    if als:
        for x in als: st.warning(x)
    else: st.success('Parâmetros essenciais encontrados para a competência informada.')

with tabs[3]:
    a,b=st.columns([8,1]); a.subheader('Calendário da Folha');
    if b.button('❓',key='aj_cal'): ajuda('calendario')
    st.dataframe(calendario_folha(),width='stretch',hide_index=True)
    with st.expander('➕ Configurar competência'):
        comp=st.text_input('Competência (MM/AAAA)',date.today().strftime('%m/%Y'),key='cal_comp'); tipo=st.selectbox('Tipo',['MENSAL','13_SALARIO','FERIAS','RESCISAO','COMPLEMENTAR'],key='cal_tipo')
        c1,c2,c3=st.columns(3); ab=c1.date_input('Abertura',date.today(),format='DD/MM/YYYY'); lim=c2.date_input('Limite eventos',date.today(),format='DD/MM/YYYY'); conf=c3.date_input('Conferência',date.today(),format='DD/MM/YYYY')
        c1,c2=st.columns(2); fec=c1.date_input('Fechamento',date.today(),format='DD/MM/YYYY'); pag=c2.date_input('Pagamento previsto',date.today(),format='DD/MM/YYYY'); obs=st.text_area('Observação',key='cal_obs')
        if st.button('Salvar calendário'): salvar_calendario(comp,tipo,ab,lim,conf,fec,pag,obs); st.success('Calendário salvo.'); st.rerun()

with tabs[4]:
    a,b=st.columns([8,1]); a.subheader('Competências');
    if b.button('❓',key='aj_comp'): ajuda('geral')
    @st.dialog('Nova competência')
    def nf():
        comp=st.text_input('Competência (MM/AAAA)',date.today().strftime('%m/%Y')); tipo=st.selectbox('Tipo',['MENSAL','13_SALARIO','FERIAS','RESCISAO','COMPLEMENTAR']); obs=st.text_area('Observação')
        if st.button('Criar folha',type='primary'): criar_folha(comp,tipo,obs,u['id']); st.rerun()
    if st.button('+ Abrir competência'): nf()
    fs=folhas(); st.dataframe(fs,width='stretch',hide_index=True)
    st.info('Folhas fechadas não devem ser editadas. Diferenças posteriores devem usar folha COMPLEMENTAR.')

with tabs[5]:
    a,b=st.columns([8,1]); a.subheader('Conferência e Fechamento');
    if b.button('❓',key='aj_fech'): ajuda('fechamento')
    fs=folhas()
    if not fs: st.info('Abra uma competência primeiro.')
    else:
        mp={f"#{x['id']} · {x['competencia']} · {x['tipo']} · {x['status']}":x for x in fs}; rot=st.selectbox('Folha',list(mp)); f=mp[rot]
        als=alertas_parametros(f['competencia'])
        for x in als: st.warning(x)
        ck=checklist_folha(f['id'])
        st.markdown('#### Checklist de fechamento')
        for item in ck:
            c1,c2=st.columns([4,2]); marcado=c1.checkbox(item['item'],value=item['concluído'],key=f"ck_{item['id']}"); obs=c2.text_input('Observação',value=item['observação'],key=f"obs_{item['id']}",label_visibility='collapsed')
            if marcado!=item['concluído'] or obs!=item['observação']: atualizar_checklist(item['id'],marcado,obs,u['id'])
        st.markdown('#### Avançar etapa')
        prox={'RASCUNHO':['EM_CONFERENCIA'],'EM_CONFERENCIA':['APROVADA','RASCUNHO'],'APROVADA':['FECHADA','EM_CONFERENCIA'],'FECHADA':['PAGA'],'PAGA':[]}.get(f['status'],[])
        if prox:
            destino=st.selectbox('Próximo status',prox)
            if st.button('Confirmar transição',type='primary'):
                try: transicionar_folha(f['id'],destino,u['id']); st.success('Status atualizado.'); st.rerun()
                except Exception as e: st.error(str(e))
        else: st.success('Folha PAGA. Histórico preservado.')
        snaps=snapshots_folha(f['id'])
        if snaps: st.dataframe(snaps,width='stretch',hide_index=True)

with tabs[6]:
    a,b=st.columns([8,1]); a.subheader('Recibos Avulsos');
    if b.button('❓',key='aj_rec'): ajuda('recibos')
    ps=prestadores(); mp={f"{x['nome']} · {x['documento']}":x for x in ps}
    @st.dialog('Novo recibo avulso',width='large')
    def nr():
        op=st.selectbox('Prestador já cadastrado', ['— preencher manualmente —']+list(mp.keys())); p=mp.get(op); ant=ultimo(p['id']) if p else None
        nome=st.text_input('Nome',value=(ant or {}).get('nome',(p or {}).get('nome','')));c1,c2=st.columns(2);cpf=c1.text_input('CPF',value=(ant or {}).get('cpf',(p or {}).get('documento','')));rg=c2.text_input('RG',value=(ant or {}).get('rg',''));tel=st.text_input('Telefone',value=(ant or {}).get('telefone',(p or {}).get('telefone','')));end=st.text_area('Endereço',value=(ant or {}).get('endereco',''))
        c1,c2=st.columns(2);dt=c1.date_input('Data',date.today(),format='DD/MM/YYYY');comp=c2.text_input('Competência (MM/AAAA)',date.today().strftime('%m/%Y'));valor=st.number_input('Valor R$',min_value=0.0,step=0.01);serv=st.text_area('Serviço prestado',value=(ant or {}).get('servico',''))
        doc=st.file_uploader('Documento do prestador (imagem)',type=['png','jpg','jpeg']);pag=st.file_uploader('Comprovante de pagamento (imagem)',type=['png','jpg','jpeg'])
        st.caption('Dados permanentes podem ser reaproveitados; o comprovante pertence a esta emissão.')
        if st.button('Emitir e armazenar recibo',type='primary'):
            rid=salvar_recibo((p or {}).get('id'),nome,cpf,rg,tel,end,dt,comp,valor,serv,doc,pag,u['id']);st.session_state['recibo_novo']=rid;st.success(f'Recibo #{rid} armazenado.');st.rerun()
    if st.button('+ Novo recibo avulso',type='primary'):nr()
    rows=recibos();st.dataframe(rows,width='stretch',hide_index=True)
    if rows:
        ids={f"{x['nº']} · {x['nome']}":x['id'] for x in rows};sel=st.selectbox('Gerar PDF de recibo',list(ids));pdf=pdf_recibo(ids[sel]);st.download_button('📄 Baixar recibo PDF',pdf,file_name=f"RECIBO_{sel.split(' · ')[0]}.pdf",mime='application/pdf')
