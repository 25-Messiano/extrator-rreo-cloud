from pathlib import Path

def test_menu_hierarquico_e_paginas_exclusivas():
    common=Path('ui/common.py').read_text(encoding='utf-8')
    for label in ['Cadastros','Financeiro','Relatórios','Administração']:
        assert label in common
    pages={
      'pages/16_Relatorios_DRE.py':'DRE',
      'pages/23_Relatorio_Movimento_Financeiro.py':'movimento',
      'pages/24_Relatorio_Resumo_Banco.py':'resumo',
      'pages/25_Relatorio_Resumo_Caixa.py':'resumo',
      'pages/26_Relatorio_Resumo_Banco_Caixa.py':'resumo',
      'pages/27_Relatorio_Suprimento_Caixa.py':'suprimento',
      'pages/28_Relatorio_Saldos_Historicos.py':'saldos',
    }
    for f,token in pages.items():
        txt=Path(f).read_text(encoding='utf-8')
        assert token.lower() in txt.lower()
    dre=Path('pages/16_Relatorios_DRE.py').read_text(encoding='utf-8')
    assert 'movimento_financeiro' not in dre.lower()
