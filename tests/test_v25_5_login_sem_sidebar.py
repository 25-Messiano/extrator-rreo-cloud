from pathlib import Path

from services.tenancy import app_version


def test_v255_version():
    assert app_version() in ("V25.5", "V25.6", "V25.7", "V25.8", "V25.9", "V25.10", "V25.11", "V25.12", "V25.13", "V26", "V26.1", "V26.2", "V26.3", "V26.4", "V26.5", "V26.6", "V26.7", "V26.8", "V26.9", "V26.10")

def test_login_screen_hides_sidebar_before_authentication():
    src = Path("ui/common.py").read_text(encoding="utf-8")
    assert '[data-testid="stSidebar"]' in src
    assert 'stSidebarCollapsedControl' in src
    assert 'if st.session_state.get("user")' in src
    assert 'st.rerun()' in src
