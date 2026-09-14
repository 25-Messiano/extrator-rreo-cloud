from ui.common import require_login, topbar
from relatorios.ui_exclusivos import resumo
require_login('RELATORIOS'); topbar('Resumo Geral Caixa','Relatório exclusivo do Caixa.'); resumo('C','RESUMO GERAL - CAIXA','resumo_caixa')
