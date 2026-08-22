from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigError(RuntimeError):
    pass


def load_json(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        raise ConfigError(f"Arquivo de configuração não encontrado: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON inválido em {path}: {exc}") from exc


def save_json(name: str, data: dict[str, Any]) -> None:
    path = CONFIG_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value
