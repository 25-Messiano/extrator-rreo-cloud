from pathlib import Path


def test_v268_objetivo_no_dashboard():
    root=Path(__file__).resolve().parents[1]
    dash=(root/'pages/01_Dashboard.py').read_text(encoding='utf-8')
    assert 'OBJETIVO' in dash
    assert 'Sistema completo para gestão financeira, contábil, patrimonial' in dash


def test_v268_ajuda_todos_modulos_principais():
    root=Path(__file__).resolve().parents[1]
    shared={
        '01_Dashboard.py':'dashboard','02_Lancamentos.py':'lancamentos','03_Correcao_Estorno.py':'correcao',
        '04_Banco.py':'banco','05_Caixa.py':'caixa','06_Extratos_Bancarios.py':'extratos','07_Importacao_IA.py':'ia',
        '08_Conferencia.py':'conferencia','09_Conciliacao.py':'conciliacao','12_Codigos_Grupos_DRE.py':'codigos',
        '13_Favorecidos_Fornecedores.py':'favorecidos','14_Contas_Bancarias.py':'contas','15_Centros_de_Custo.py':'centros',
        '15_Pesquisa_Avancada.py':'pesquisa','16_Relatorios_DRE.py':'relatorios','17_Fechamento_Mensal.py':'fechamento',
        '18_Auditoria.py':'auditoria','19_Usuarios_Permissoes.py':'usuarios','20_Backup_Recuperacao.py':'backup',
        '21_Configuracoes.py':'config','22_Monitoramento.py':'monitor',
    }
    ajuda=(root/'ui/help_modulos.py').read_text(encoding='utf-8')
    for page,key in shared.items():
        text=(root/'pages'/page).read_text(encoding='utf-8')
        assert f'botao_ajuda("{key}")' in text
        assert f'"{key}"' in ajuda
    # Fluxo e Patrimônio já possuem modais próprios e devem ser preservados.
    assert 'Como usar o Fluxo de Caixa' in (root/'pages/10_Fluxo_de_Caixa.py').read_text(encoding='utf-8')
    assert 'Como usar a área de Patrimônio' in (root/'pages/11_Patrimonio.py').read_text(encoding='utf-8')
