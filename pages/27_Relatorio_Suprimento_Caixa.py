from ui.common import require_login, topbar
from relatorios.ui_exclusivos import suprimento
require_login('RELATORIOS'); topbar('Suprimento de Caixa','Relatório exclusivo do código 0801: saída Banco × entrada Caixa.'); suprimento()
