from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 310_000


def password_requirements(password: str) -> dict[str, bool]:
    return {
        "Mínimo de 8 caracteres": len(password) >= 8,
        "Pelo menos uma letra maiúscula": any(char.isupper() for char in password),
        "Pelo menos um número": any(char.isdigit() for char in password),
    }


def validate_password(password: str) -> None:
    checks = password_requirements(password)
    missing = [label for label, passed in checks.items() if not passed]
    if missing:
        raise ValueError("A senha deve ter no mínimo 8 caracteres, uma letra maiúscula e um número.")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(candidate.hex(), digest_hex)
    except (TypeError, ValueError):
        return False


def generate_recovery_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
