import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    app_name: str = "TESOURARIA APLB"
    app_env: str = _env("APP_ENV", "development")
    database_url: str = _env("DATABASE_URL", "sqlite:///tesouraria_aplb.db")
    admin_password: str = _env("TESOURARIA_ADMIN_PASSWORD", "")
    admin_reset_token: str = _env("TESOURARIA_ADMIN_RESET_TOKEN", "")
    admin_reset_password: str = _env("TESOURARIA_ADMIN_RESET_PASSWORD", "")
    admin_email: str = _env("TESOURARIA_ADMIN_EMAIL", "")
    public_url: str = _env("TESOURARIA_PUBLIC_URL", "https://app-tesouraria-aplb.onrender.com")
    smtp_host: str = _env("TESOURARIA_SMTP_HOST", "")
    smtp_port: int = int(_env("TESOURARIA_SMTP_PORT", "587") or "587")
    smtp_user: str = _env("TESOURARIA_SMTP_USER", "")
    smtp_password: str = _env("TESOURARIA_SMTP_PASSWORD", "")
    smtp_from_email: str = _env("TESOURARIA_SMTP_FROM_EMAIL", "")
    smtp_from_name: str = _env("TESOURARIA_SMTP_FROM_NAME", "TESOURARIA APLB")
    smtp_use_tls: bool = _env("TESOURARIA_SMTP_USE_TLS", "1").lower() not in ("0", "false", "nao", "não")
    password_reset_minutes: int = int(_env("TESOURARIA_PASSWORD_RESET_MINUTES", "30") or "30")
    secret_key: str = _env("SECRET_KEY", "")
    cloud_backup_bucket: str = _env("CLOUD_BACKUP_BUCKET", "")
    programador_alert_destino: str = _env("PROGRAMADOR_ALERT_DESTINO", "")
    programador_alert_webhook_url: str = _env("PROGRAMADOR_ALERT_WEBHOOK_URL", "")
    openai_api_key: str = _env("OPENAI_API_KEY", "")
    openai_model: str = _env("OPENAI_MODEL", "gpt-5.6-luna")


settings = Settings()
