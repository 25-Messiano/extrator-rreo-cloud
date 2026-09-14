from __future__ import annotations

import smtplib
from email.message import EmailMessage

from config.settings import settings


def email_configurado() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


def enviar_email(destino: str, assunto: str, corpo_texto: str) -> tuple[bool, str | None]:
    if not email_configurado():
        return False, "Serviço de e-mail não configurado."
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    msg["To"] = destino
    msg.set_content(corpo_texto)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=12) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
        return True, None
    except Exception as exc:
        return False, str(exc)[:500]
