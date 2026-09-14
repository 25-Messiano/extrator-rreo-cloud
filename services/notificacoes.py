from __future__ import annotations
from datetime import datetime
import json
import urllib.request

from config.settings import settings


def notificar_acesso_programador(usuario: dict) -> bool:
    """Envia webhook opcional. Sem URL configurada, apenas retorna False sem afetar o login."""
    url = settings.programador_alert_webhook_url
    if not url:
        return False
    payload = {
        "evento": "LOGIN_TESOURARIA_APLB",
        "usuario": usuario.get("nome"),
        "login": usuario.get("login"),
        "perfil": usuario.get("perfil"),
        "data_hora_utc": datetime.utcnow().isoformat() + "Z",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 300
    except Exception:
        return False
