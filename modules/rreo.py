from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

from core.validacao import normalizar_texto, validar_codigos_rreo
from integrations.gemini import extract_rreo_values, identify_rreo_municipality

DEFAULT_CODES = [
    "1.1", "1.2", "1.3", "1.4", "2.1", "2.1.1", "2.1.2", "2.2",
    "2.3", "2.4", "2.5", "2.6", "6.1.1", "6.2", "6.2.1",
]
MONEY_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)")


def extract_text(pdf_path: str | Path) -> str:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {path}")
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=2, y_tolerance=3, layout=True) or ""
            pages.append(f"\n===== PÁGINA {number} =====\n{text}")
    return "\n".join(pages).strip()


def _br_to_float(value: str) -> float:
    return float(value.replace(".", "").replace(",", "."))


def _line_block(text: str, code: str, max_chars: int = 900) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(code)}\s*[-–—]", text)
    if not match:
        return ""
    limit = min(len(text), match.start() + max_chars)
    next_match = re.search(r"(?m)^\s*\d+(?:\.\d+)+\s*[-–—]", text[match.end():limit])
    end = match.end() + next_match.start() if next_match else limit
    return text[match.start():end]


def extract_codes(text: str, codes: Iterable[str] | None = None) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for code in validar_codigos_rreo(codes or DEFAULT_CODES):
        values = MONEY_PATTERN.findall(_line_block(text, code))
        result[code] = _br_to_float(values[1]) if len(values) >= 2 else None
    return result


def identify_internal_municipality(
    texto_pdf: str,
    municipios: list[dict[str, Any]],
    uf_esperada: str,
    usar_gemini: bool = False,
) -> tuple[dict[str, Any] | None, float, str, str, int]:
    """Identifica Município+UF pelo conteúdo; IBGE vem depois do cadastro oficial."""
    header = normalizar_texto((texto_pdf or "")[:12000])
    if not header:
        return None, 0.0, "CONTEUDO_VAZIO", "", 0

    def best(reference: str) -> tuple[dict[str, Any] | None, float]:
        ref = normalizar_texto(reference)
        candidate = None
        score = 0.0
        for city in municipios:
            name = normalizar_texto(city.get("nome"))
            current = 1.0 if ref == name else SequenceMatcher(None, ref, name).ratio()
            if current > score:
                candidate, score = city, current
        return candidate, score

    # Primeiro procura nomes oficiais completos no cabeçalho.
    exact = [(header.find(normalizar_texto(city.get("nome"))), city) for city in municipios]
    exact = [(position, city) for position, city in exact if position >= 0]
    if exact:
        exact.sort(key=lambda item: item[0])
        return exact[0][1], 0.99, "NOME_EXATO_NO_CONTEUDO", "", 0

    patterns = [
        r"(?:MUNICIPIO|ENTE FEDERADO|PREFEITURA MUNICIPAL DE|PREFEITURA DE)\s*[:\-]?\s*([A-Z0-9 .'-]{3,90})",
        rf"([A-Z][A-Z0-9 .'-]{{2,70}})\s*[-/]\s*{re.escape(str(uf_esperada).upper())}",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, header):
            raw = re.split(r"\s{2,}|EXERCICIO|PERIODO|CNPJ|RELATORIO|DEMONSTRATIVO", match.group(1))[0]
            city, score = best(raw)
            if city and score >= 0.88:
                return city, score, "CABECALHO_INTERNO", "", 0

    if usar_gemini:
        try:
            name, returned_uf, confidence, model, attempts = identify_rreo_municipality(
                texto_pdf, str(uf_esperada).upper(), [str(city.get("nome") or "") for city in municipios]
            )
            if name and confidence >= 0.78 and (not returned_uf or returned_uf == str(uf_esperada).upper()):
                city, score = best(name)
                if city and score >= 0.84:
                    return city, min(confidence, score), "GEMINI_CONTEUDO_INTERNO", model, attempts
        except Exception:
            pass
    return None, 0.0, "MUNICIPIO_INTERNO_NAO_IDENTIFICADO", "", 0


def process(pdf_path: str | Path, codigos: Iterable[str] | None = None) -> tuple[dict[str, float | None], str]:
    codes = validar_codigos_rreo(codigos or DEFAULT_CODES)
    text = extract_text(pdf_path)
    values = extract_codes(text, codes)
    missing = [code for code in codes if values.get(code) is None]
    if missing:
        try:
            fallback = extract_rreo_values(texto_pdf=text, codigos=missing)
            for code in missing:
                if fallback.get(code) is not None:
                    values[code] = fallback[code]
        except Exception:
            pass
    return values, text
