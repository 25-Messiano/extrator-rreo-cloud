from ui.common import require_login, topbar
from relatorios.ui_exclusivos import resumo
require_login('RELATORIOS'); topbar('Resumo Geral Banco + Caixa','Relatório consolidado exclusivo Banco + Caixa.'); resumo(None,'RESUMO GERAL - BANCO E CAIXA','resumo_banco_caixa')
