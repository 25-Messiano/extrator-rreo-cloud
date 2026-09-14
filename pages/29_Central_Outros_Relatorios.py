import streamlit as st
from ui.common import require_login, topbar
require_login('RELATORIOS')
topbar('Central de outros relatórios','Modelos complementares ainda não separados em páginas próprias.')
st.info('Os relatórios oficiais principais agora possuem páginas exclusivas no menu Relatórios. Esta área fica reservada para os demais modelos em homologação.')
st.markdown('''**Relatórios já separados:** Movimento Financeiro, DRE, Resumo Banco, Resumo Caixa, Banco + Caixa, Suprimento de Caixa e Saldos Históricos.''')
