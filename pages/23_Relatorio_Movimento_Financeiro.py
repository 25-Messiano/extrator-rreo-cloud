from ui.common import require_login, topbar
from relatorios.ui_exclusivos import movimento
require_login('RELATORIOS'); topbar('Movimento Financeiro Banco/Caixa','Relatório exclusivo do movimento financeiro.'); movimento()
