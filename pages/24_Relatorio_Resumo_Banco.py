from ui.common import require_login, topbar
from relatorios.ui_exclusivos import resumo
require_login('RELATORIOS'); topbar('Resumo Geral Banco','Relatório exclusivo do Banco.'); resumo('B','RESUMO GERAL - BANCO','resumo_banco')
