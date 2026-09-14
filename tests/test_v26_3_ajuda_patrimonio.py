from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v26_3_ajuda_patrimonio_integrada():
    assert (ROOT / 'VERSION').read_text(encoding='utf-8').strip() in ('V26.3', 'V26.4', 'V26.5', 'V26.6', 'V26.7', 'V26.8', 'V26.9', 'V26.10')
    src = (ROOT / 'pages' / '11_Patrimonio.py').read_text(encoding='utf-8')
    assert '@st.dialog("❓ Como usar a área de Patrimônio", width="large")' in src
    assert 'Bens obsoletos não são apagados' in src
    assert 'O filtro escolhido vale igualmente para **PDF e Excel**' in src
    assert 'o patrimônio nunca desaparece da história' in src
