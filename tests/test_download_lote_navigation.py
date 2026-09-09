from pathlib import Path


def test_download_lote_is_registered_in_custom_sidebar():
    theme = Path("ui/theme.py").read_text(encoding="utf-8")
    assert 'st.page_link("pages/7_Download_Lote.py", label="Download em Lote", icon="📦")' in theme


def test_download_lote_has_redundant_home_entry():
    home = Path("app.py").read_text(encoding="utf-8")
    assert 'st.page_link("pages/7_Download_Lote.py", label="Abrir Download em Lote", icon="📦"' in home


def test_download_lote_page_and_core_exist():
    assert Path("pages/7_Download_Lote.py").is_file()
    assert Path("core/download_lote.py").is_file()


def test_release_marker_is_visible_in_sidebar():
    theme = Path("ui/theme.py").read_text(encoding="utf-8")
    assert "v1.3.7 RREO SAFE" in theme


def test_download_lote_page_exposes_processed_spreadsheets():
    page = Path("pages/7_Download_Lote.py").read_text(encoding="utf-8")
    assert "Planilhas processadas" in page
    assert "Estaduais mais recentes" in page
    assert "MASTER nacional" in page
    assert "Preparar ZIP das planilhas" in page
