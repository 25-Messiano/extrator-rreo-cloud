from pathlib import Path

from services.importacao_movimento_pdf import ler_movimento_pdf, competencia_do_lote

ROOT=Path(__file__).resolve().parents[1]

def test_parser_movimento_modelo_real_primeira_linha():
    mov=ler_movimento_pdf((ROOT/'01_2026.pdf').read_bytes())
    assert mov
    assert competencia_do_lote(mov)=='2026-01'
    primeira=mov[0]
    assert primeira['codigo']=='0001'
    assert primeira['origem_bc']=='B'
    assert primeira['natureza']=='SAIDA'
    assert float(primeira['valor'])==70.60

def test_paginas_v259_e_menu_existem():
    assert (ROOT/'pages/37_Importar_Movimento_PDF.py').exists()
    assert (ROOT/'pages/38_Importar_Extratos_PDF.py').exists()
    menu=(ROOT/'ui/common.py').read_text(encoding='utf-8')
    assert '37_Importar_Movimento_PDF.py' in menu
    assert '38_Importar_Extratos_PDF.py' in menu
    assert (ROOT/'VERSION').read_text().strip()in ('V25.9','V25.10','V25.11','V25.12','V25.13', 'V26', 'V26.1', 'V26.2', 'V26.3', 'V26.4', 'V26.5', 'V26.6', 'V26.7', 'V26.8', 'V26.9', 'V26.10')
