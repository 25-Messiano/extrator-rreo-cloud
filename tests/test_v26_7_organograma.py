from pathlib import Path

def test_v267_ajudas_nos_modulos_amarelos():
    root=Path(__file__).resolve().parents[1]
    ajuda=(root/'ui/help_modulos.py').read_text(encoding='utf-8')
    for chave in ['extratos','ia','conferencia','conciliacao','pesquisa','relatorios','fechamento','config','monitor']:
        assert f'"{chave}"' in ajuda
    for page in ['06_Extratos_Bancarios.py','07_Importacao_IA.py','08_Conferencia.py','09_Conciliacao.py','15_Pesquisa_Avancada.py','16_Relatorios_DRE.py','17_Fechamento_Mensal.py','21_Configuracoes.py','22_Monitoramento.py']:
        assert 'botao_ajuda(' in (root/'pages'/page).read_text(encoding='utf-8')

def test_v267_conferencia_massa_e_divergencias():
    root=Path(__file__).resolve().parents[1]
    conf=(root/'pages/08_Conferencia.py').read_text(encoding='utf-8')
    svc=(root/'services/importacao_extrato.py').read_text(encoding='utf-8')
    conc=(root/'pages/09_Conciliacao.py').read_text(encoding='utf-8')
    assert 'Edição em massa' in conf and 'atualizar_itens_em_massa' in svc
    assert 'Relatório de divergências' in conc and 'Baixar divergências em Excel' in conc
