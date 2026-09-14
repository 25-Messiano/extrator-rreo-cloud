from ui.common import require_login, topbar
from relatorios.ui_exclusivos import saldos
require_login('RELATORIOS'); topbar('Saldos Históricos','Relatório exclusivo de saldos mensais por ano: Banco, Caixa e consolidado.'); saldos()
