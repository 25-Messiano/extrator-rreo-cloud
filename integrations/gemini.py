from __future__ import annotations

import json
import os
import re
import time
import threading
from typing import Any, Iterable

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
FALLBACK_MODELS = tuple(
    model.strip()
    for model in os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.5-flash,gemini-flash-latest",
    ).split(",")
    if model.strip()
)


_GEMINI_MAX_CONCURRENCY = max(1, min(int(os.getenv("GEMINI_MAX_CONCURRENCY", "1")), 2))
_GEMINI_SEMAPHORE = threading.BoundedSemaphore(_GEMINI_MAX_CONCURRENCY)
_GEMINI_CONFIG_LOCK = threading.Lock()


def configure_max_concurrency(value: int) -> int:
    """Ajusta a concorrência do Gemini antes de iniciar um processamento."""
    global _GEMINI_MAX_CONCURRENCY, _GEMINI_SEMAPHORE
    safe_value = max(1, min(int(value), 2))
    with _GEMINI_CONFIG_LOCK:
        if safe_value != _GEMINI_MAX_CONCURRENCY:
            _GEMINI_MAX_CONCURRENCY = safe_value
            _GEMINI_SEMAPHORE = threading.BoundedSemaphore(safe_value)
    return _GEMINI_MAX_CONCURRENCY


def current_max_concurrency() -> int:
    return _GEMINI_MAX_CONCURRENCY

DESCRICOES_RREO = {
    "1.1": "Receita Resultante do IPTU",
    "1.2": "Receita Resultante do ITBI",
    "1.3": "Receita Resultante do ISS",
    "1.4": "Receita Resultante do IRRF",
    "2.1": "Cota-Parte FPM",
    "2.1.1": "CF, art. 159, I, alínea b",
    "2.1.2": "CF, art. 159, I, alíneas d e e",
    "2.2": "Cota-Parte ICMS",
    "2.3": "Cota-Parte IPI-Exportação",
    "2.4": "Cota-Parte ITR",
    "2.5": "Cota-Parte IPVA",
    "2.6": "Cota-Parte IOF-Ouro",
    "6.1.1": "FUNDEB - Impostos e Transferências - Principal",
    "6.2": "FUNDEB - Complementação da União - VAAF",
    "6.2.1": "FUNDEB - VAAF - Principal",
}


def api_key() -> str:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not key:
        raise RuntimeError(
            "Chave do Gemini não encontrada. Configure GEMINI_API_KEY no Render."
        )
    return key


def model_candidates(preferred: str | None = None) -> list[str]:
    ordered = [preferred or DEFAULT_MODEL, *FALLBACK_MODELS]
    result: list[str] = []
    for model in ordered:
        if model and model not in result:
            result.append(model)
    return result


def _is_retryable(error: Exception) -> bool:
    message = str(error).upper()
    return any(token in message for token in ("429", "RESOURCE_EXHAUSTED", "500", "502", "503", "504", "UNAVAILABLE", "DEADLINE"))


def generate_structured(
    *,
    contents: Any,
    schema: dict[str, Any],
    model: str | None = None,
    max_attempts: int = 3,
) -> tuple[dict[str, Any], str, int]:
    """Executa Gemini com troca automática de modelo e repetição exponencial."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Biblioteca google-genai não instalada.") from exc

    errors: list[str] = []
    total_attempts = 0
    client = genai.Client(api_key=api_key())
    try:
        for candidate in model_candidates(model):
            for attempt in range(1, max_attempts + 1):
                total_attempts += 1
                try:
                    with _GEMINI_SEMAPHORE:
                        response = client.models.generate_content(
                            model=candidate,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_json_schema=schema,
                            ),
                        )
                    parsed = getattr(response, "parsed", None)
                    raw = parsed if isinstance(parsed, dict) else json.loads(response.text or "{}")
                    return raw, candidate, total_attempts
                except Exception as exc:  # API errors vary by SDK version
                    errors.append(f"{candidate} tentativa {attempt}: {type(exc).__name__}: {exc}")
                    message = str(exc).upper()
                    if "404" in message or "NOT_FOUND" in message:
                        break
                    if not _is_retryable(exc) or attempt >= max_attempts:
                        break
                    time.sleep(min(2 ** (attempt - 1), 8))
    finally:
        client.close()

    raise RuntimeError("Falha em todos os modelos Gemini. " + " | ".join(errors[-6:]))


def _schema_rreo(codigos: list[str]) -> dict[str, Any]:
    properties = {
        codigo: {
            "anyOf": [{"type": "number"}, {"type": "null"}],
            "description": "Valor de RECEITAS REALIZADAS Até o Bimestre (b).",
        }
        for codigo in codigos
    }
    return {
        "type": "object",
        "properties": properties,
        "required": codigos,
        "additionalProperties": False,
    }


def _prompt_rreo(texto_pdf: str, codigos: list[str]) -> str:
    linhas = "\n".join(
        f"- {codigo}: {DESCRICOES_RREO.get(codigo, 'linha identificada pelo código')}"
        for codigo in codigos
    )
    return f"""
Extraia do RREO municipal somente a coluna RECEITAS REALIZADAS Até o Bimestre (b).
Confirme código e descrição da mesma linha lógica. Não use previsão, totais, subtotais,
linhas vizinhas nem a linha agregada 2. Se não houver segurança, retorne null.
Converta 1.234.567,89 para 1234567.89.

CÓDIGOS:
{linhas}

TEXTO:
{texto_pdf}
""".strip()


def _normalizar_resultado(raw: dict[str, Any], codigos: Iterable[str]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for code in codigos:
        value = raw.get(code)
        if value in (None, ""):
            result[code] = None
        elif isinstance(value, (int, float)):
            result[code] = float(value)
        else:
            cleaned = re.sub(r"[^\d,.\-]", "", str(value))
            if "," in cleaned:
                cleaned = cleaned.replace(".", "").replace(",", ".")
            try:
                result[code] = float(cleaned)
            except ValueError:
                result[code] = None
    return result


def extract_rreo_values(
    texto_pdf: str,
    codigos: list[str],
    model: str | None = None,
) -> dict[str, float | None]:
    if not texto_pdf.strip():
        return {codigo: None for codigo in codigos}
    raw, _, _ = generate_structured(
        contents=_prompt_rreo(texto_pdf, codigos),
        schema=_schema_rreo(codigos),
        model=model,
    )
    return _normalizar_resultado(raw, codigos)


def identify_rreo_municipality(
    texto_pdf: str,
    uf_esperada: str,
    municipios_oficiais: list[str],
    model: str | None = None,
) -> tuple[str | None, str, float, str, int]:
    """Identifica município e UF no conteúdo interno do RREO.

    Retorna (municipio, uf, confianca, modelo, tentativas). Não usa o nome do
    arquivo e nunca inventa código IBGE.
    """
    if not texto_pdf.strip() or not municipios_oficiais:
        return None, "", 0.0, "", 0
    schema = {
        "type": "object",
        "properties": {
            "municipio": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "uf": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "confianca": {"type": "number"},
        },
        "required": ["municipio", "uf", "confianca"],
        "additionalProperties": False,
    }
    official = "\n".join(f"- {name}" for name in municipios_oficiais)
    prompt = f"""
Leia somente o conteúdo interno deste RREO municipal. Identifique o ente
federado responsável pelo demonstrativo. Ignore qualquer nome externo de
arquivo. A UF esperada é {uf_esperada}. Retorne exatamente um município da
lista oficial. Se não houver segurança, retorne municipio=null. Não invente
código IBGE.

MUNICÍPIOS OFICIAIS:
{official}

CONTEÚDO INTERNO:
{texto_pdf[:45000]}
""".strip()
    raw, used_model, attempts = generate_structured(contents=prompt, schema=schema, model=model, max_attempts=2)
    name = str(raw.get("municipio") or "").strip()
    returned_uf = str(raw.get("uf") or "").strip().upper()
    confidence = float(raw.get("confianca") or 0.0)
    if not name or (returned_uf and returned_uf != str(uf_esperada).upper()) or confidence < 0.70:
        return None, returned_uf, confidence, used_model, attempts
    return name, returned_uf or str(uf_esperada).upper(), confidence, used_model, attempts
