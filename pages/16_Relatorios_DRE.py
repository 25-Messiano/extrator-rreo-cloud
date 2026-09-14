from ui.common import require_login, topbar
from ui.help_modulos import botao_ajuda
from relatorios.ui_exclusivos import dre
require_login('RELATORIOS')
topbar('DRE','Página exclusiva da Demonstração do Resultado / Execução Financeira. Nenhum outro relatório é gerado aqui.')
botao_ajuda("relatorios")
dre()
