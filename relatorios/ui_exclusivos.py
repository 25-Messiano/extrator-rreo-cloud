from datetime import date
import pandas as pd
import streamlit as st
from relatorios.movimento_financeiro import movimento_mes, gerar_pdf_movimento, gerar_excel_movimento, MESES
from relatorios.dre import dre_detalhe_periodo
from relatorios.dre_oficial import dre_oficial_mes, gerar_pdf_dre_oficial, gerar_excel_dre_oficial, SECOES
from relatorios.resumos_oficiais import resumo_codigo_ano, suprimento_caixa_ano, saldos_historicos, gerar_pdf_resumo, gerar_excel_resumo, gerar_pdf_suprimento, gerar_excel_suprimento, gerar_pdf_saldos, gerar_excel_saldos

def _ano(key):
    return int(st.number_input('Exercício',2026,2050,max(2026,date.today().year),1,key=key))

def _downloads(pdf,xlsx,fn):
    c1,c2=st.columns(2)
    c1.download_button('📄 Baixar PDF',pdf,file_name=fn+'.pdf',mime='application/pdf',width='stretch')
    c2.download_button('📊 Baixar Excel',xlsx,file_name=fn+'.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',width='stretch')

def movimento():
    c1,c2=st.columns(2); ano=int(c1.number_input('Exercício',2026,2050,max(2026,date.today().year),1)); mes=c2.selectbox('Mês',range(1,13),index=date.today().month-1,format_func=lambda m:MESES[m])
    fmt=st.selectbox('Formato',[('modelo','Modelo principal — A4 paisagem'),('oficio','Ofício paisagem')],format_func=lambda x:x[1])[0]
    d=movimento_mes(ano,mes); rows=[{'Dia':r['data'],'Código':r['codigo'],'C/B':r['bc'],'Especificação':r['especificacao'],'Entrada/Banco':r['entrada_banco'],'Saída/Banco':r['saida_banco'],'Entrada/Caixa':r['entrada_caixa'],'Saída/Caixa':r['saida_caixa'],'Saldo C/B':r['saldo']} for r in d['rows']]
    st.dataframe(pd.DataFrame(rows),width='stretch',hide_index=True)
    _downloads(gerar_pdf_movimento(d,fmt),gerar_excel_movimento(d,fmt),f'MOVIMENTO_FINANCEIRO_{mes:02d}_{ano}')

def dre():
    c1,c2=st.columns(2); ano=int(c1.number_input('Exercício',2026,2050,max(2026,date.today().year),1)); mes=c2.selectbox('Mês',range(1,13),index=date.today().month-1,format_func=lambda m:MESES[m])
    d=dre_oficial_mes(ano,mes); rows=[]
    for sec,nome,itens in SECOES:
        for cod,desc in itens: rows.append({'Grupo':cod,'Descrição':desc,'Valor':float(d['valores'].get(cod,0))})
    st.dataframe(pd.DataFrame(rows),width='stretch',hide_index=True)
    if rows:
        grupo=st.selectbox('Conferir composição do grupo',[f"{x['Grupo']} - {x['Descrição']}" for x in rows]); cod=grupo.split(' - ',1)[0]; det=dre_detalhe_periodo(d['inicio'],d['fim'],cod)
        if det: st.dataframe(pd.DataFrame(det),width='stretch',hide_index=True)
    _downloads(gerar_pdf_dre_oficial(d),gerar_excel_dre_oficial(d),f'DRE_EXECUCAO_FINANCEIRA_{mes:02d}_{ano}')

def resumo(bc,titulo,slug):
    ano=_ano('ano_'+slug); d=resumo_codigo_ano(ano,bc)
    c1,c2,c3=st.columns(3); c1.metric('Entradas no ano',f"R$ {sum(d['totais_entrada'].values()):,.2f}".replace(',','X').replace('.',',').replace('X','.')); c2.metric('Saídas no ano',f"R$ {sum(d['totais_saida'].values()):,.2f}".replace(',','X').replace('.',',').replace('X','.')); c3.metric('Conferência','OK' if d['ok'] else 'DIVERGÊNCIA')
    prev=[]
    for nat,items in [('ENTRADA',d['entradas']),('SAÍDA',d['saidas'])]:
        for x in items: prev.append({'Natureza':nat,'Código':x['codigo'],'Referência':x['descricao'],**{MESES[m]:float(x['meses'][m]) for m in range(1,13)},'TOTAL':float(x['total'])})
    st.dataframe(pd.DataFrame(prev),width='stretch',hide_index=True)
    _downloads(gerar_pdf_resumo(ano,bc,titulo),gerar_excel_resumo(ano,bc,titulo),f'{slug.upper()}_{ano}')

def suprimento():
    ano=_ano('ano_sup'); d=suprimento_caixa_ano(ano)
    prev=[{'Origem':'BANCO - SAÍDA','Código':'0801',**{MESES[m]:float(d['banco'][m]) for m in range(1,13)}},{'Origem':'CAIXA - ENTRADA','Código':'0801',**{MESES[m]:float(d['caixa'][m]) for m in range(1,13)}},{'Origem':'DIFERENÇA','Código':'',**{MESES[m]:float(d['diferenca'][m]) for m in range(1,13)}}]
    st.dataframe(pd.DataFrame(prev),width='stretch',hide_index=True); st.success('Banco = Caixa em todos os meses.') if d['ok'] else st.error('Há divergência Banco × Caixa.')
    _downloads(gerar_pdf_suprimento(ano),gerar_excel_suprimento(ano),f'SUPRIMENTO_CAIXA_{ano}')

def saldos():
    c1,c2=st.columns(2); ai=int(c1.number_input('Ano inicial',2015,2050,2015,1)); af=int(c2.number_input('Ano final',2015,2050,max(2026,date.today().year),1));
    if af<ai: st.error('Ano final deve ser maior ou igual ao inicial.'); st.stop()
    rows=saldos_historicos(ai,af); prev=[]
    for x in rows:
        for chave,nome in [('B','BANCO'),('C','CAIXA'),('T','BANCO + CAIXA')]: prev.append({'Tipo':nome,'Ano':x['ano'],**{MESES[m]:float(x[chave][m]) for m in range(1,13)}})
    st.dataframe(pd.DataFrame(prev),width='stretch',hide_index=True)
    _downloads(gerar_pdf_saldos(ai,af),gerar_excel_saldos(ai,af),f'SALDOS_{ai}_A_{af}')
