from pathlib import Path
import os


def test_version_v26():
    assert (Path(__file__).resolve().parents[1]/"VERSION").read_text().strip() in ("V26.1", "V26.2", "V26.3", "V26.4", "V26.5", "V26.6", "V26.7", "V26.8", "V26.9", "V26.10")


def test_login_tem_esqueci_senha_e_token():
    txt=(Path(__file__).resolve().parents[1]/"ui/common.py").read_text(encoding="utf-8")
    assert "Esqueci minha senha" in txt
    assert "reset_token" in txt
    assert "redefinir_senha_por_token" in txt


def test_token_model_seguro():
    txt=(Path(__file__).resolve().parents[1]/"models/entities.py").read_text(encoding="utf-8")
    assert "class PasswordResetToken" in txt
    assert "token_hash" in txt
    assert "usado_em" in txt and "expira_em" in txt


def test_smtp_configuravel():
    txt=(Path(__file__).resolve().parents[1]/"config/settings.py").read_text(encoding="utf-8")
    for k in ["TESOURARIA_SMTP_HOST","TESOURARIA_SMTP_PASSWORD","TESOURARIA_PUBLIC_URL","TESOURARIA_ADMIN_EMAIL"]:
        assert k in txt


def test_senha_versao_invalida_sessao():
    sec=(Path(__file__).resolve().parents[1]/"services/security.py").read_text(encoding="utf-8")
    common=(Path(__file__).resolve().parents[1]/"ui/common.py").read_text(encoding="utf-8")
    assert "senha_versao" in sec
    assert "senha_versao" in common
