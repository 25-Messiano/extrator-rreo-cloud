from pathlib import Path
from services.tenancy import app_version


def test_v254_version():
    assert app_version() in ("V25.4", "V25.5", "V25.6", "V25.7", "V25.8", "V25.9", "V25.10", "V25.11", "V25.12", "V25.13", "V26", "V26.1", "V26.2", "V26.3", "V26.4", "V26.5", "V26.6", "V26.7", "V26.8", "V26.9", "V26.10")


def test_v254_sidebar_has_secure_user_switch():
    txt = Path("ui/common.py").read_text(encoding="utf-8")
    assert "Usuário ativo" in txt
    assert "Trocar usuário" in txt
    assert "sidebar_switch_user" in txt
    assert "st.session_state.clear()" in txt
    assert "Minha conta / Alterar senha" in txt


def test_v254_dashboard_logout_clears_entire_session():
    txt = Path("pages/01_Dashboard.py").read_text(encoding="utf-8")
    trecho = txt.split('if st.button("Sair", width="stretch"):', 1)[1][:120]
    assert "st.session_state.clear()" in trecho
