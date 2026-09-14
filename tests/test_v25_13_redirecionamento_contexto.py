from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_login_redireciona_por_contexto():
    src=(ROOT/'ui/common.py').read_text(encoding='utf-8')
    assert 'st.switch_page("app.py")' in src
    assert 'st.switch_page("pages/01_Dashboard.py")' in src

def test_trocar_usuario_e_sair_voltam_ao_portal_raiz():
    src=(ROOT/'ui/common.py').read_text(encoding='utf-8')
    assert 'st.session_state.clear(); st.switch_page("app.py")' in src

def test_contexto_incompativel_redireciona_em_vez_de_exibir_erro():
    src=(ROOT/'ui/common.py').read_text(encoding='utf-8')
    trecho=src[src.index('def _enforce_page_context'):src.index('def bootstrap_app')]
    assert 'st.switch_page("app.py")' in trecho
    assert 'st.switch_page("pages/01_Dashboard.py")' in trecho
    assert 'st.error(' not in trecho
