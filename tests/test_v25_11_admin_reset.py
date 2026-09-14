import os
from pathlib import Path


def test_v2511_version():
    assert (Path(__file__).resolve().parents[1]/"VERSION").read_text().strip() in ("V25.11", "V25.12", "V25.13", "V26", "V26.1", "V26.2", "V26.3", "V26.4", "V26.5", "V26.6", "V26.7", "V26.8", "V26.9", "V26.10")

def test_reset_config_declared():
    txt=(Path(__file__).resolve().parents[1]/"config/settings.py").read_text()
    assert "TESOURARIA_ADMIN_RESET_TOKEN" in txt
    assert "TESOURARIA_ADMIN_RESET_PASSWORD" in txt

def test_reset_is_one_time_marker():
    txt=(Path(__file__).resolve().parents[1]/"services/security.py").read_text()
    assert "ADMIN_RESET_TOKEN_APLICADO" in txt
    assert "sha256" in txt
