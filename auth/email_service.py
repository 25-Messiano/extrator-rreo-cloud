from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def email_configured() -> bool:
    return all(
        (os.getenv(name) or "").strip()
        for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM")
    )


def _send(to_email: str, subject: str, body: str) -> None:
    if not email_configured():
        raise RuntimeError("O envio de e-mail ainda não foi configurado no Render.")
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    host = os.environ["SMTP_HOST"]
    port = int(os.environ["SMTP_PORT"])
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    use_ssl = (os.getenv("SMTP_USE_SSL", "false").lower() == "true")

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=20) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)


def send_recovery_code(user_name: str, user_email: str, code: str) -> None:
    _send(
        user_email,
        "Código de recuperação - Extrator RREO Cloud",
        f"Olá, {user_name}.\n\nSeu código de recuperação é: {code}\n\n"
        "Ele expira em 15 minutos. Se você não solicitou a recuperação, ignore esta mensagem.",
    )


def notify_admin(admin_email: str, user_name: str, user_email: str) -> None:
    _send(
        admin_email,
        "Solicitação de recuperação de senha",
        f"O usuário {user_name} ({user_email}) solicitou recuperação de senha no Extrator RREO Cloud.",
    )
