from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

from core.validacao import normalizar_texto, validar_codigos_rreo
from integrations.gemini import extract_rreo_values

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
    """Confere o município interno sem decidir o destino do PDF.

    Regra vigente do RREO:
    - o município operacional vem exclusivamente do nome externo do arquivo;
    - esta função serve apenas para auditoria;
    - Gemini nunca é chamado para escolher ou trocar o município;
    - uma identificação interna só é devolvida quando o cabeçalho é inequívoco.
    """
    del usar_gemini  # Mantido somente para compatibilidade de assinatura.

    header = normalizar_texto((texto_pdf or "")[:9000])
    if not header:
        return None, 0.0, "CONTEUDO_VAZIO", "", 0

    uf = str(uf_esperada or "").upper().strip()
    oficiais = [
        city for city in municipios
        if not city.get("uf") or str(city.get("uf")).upper() == uf
    ]

    def localizar_nome(raw: str) -> tuple[dict[str, Any] | None, float]:
        referencia = normalizar_texto(raw)
        if not referencia:
            return None, 0.0
        melhor = None
        melhor_nota = 0.0
        for city in oficiais:
            nome = normalizar_texto(city.get("nome"))
            if referencia == nome:
                return city, 1.0
            nota = SequenceMatcher(None, referencia, nome).ratio()
            if nota > melhor_nota:
                melhor, melhor_nota = city, nota
        return melhor, melhor_nota

    # Só examina campos típicos do cabeçalho. Não procura qualquer nome solto
    # no documento, evitando falsos positivos em tabelas e rodapés.
    patterns = [
        r"(?:ENTE FEDERADO|MUNICIPIO|MUNICÍPIO)\s*[:\-]?\s*([A-Z0-9 .'-]{3,90})",
        r"(?:PREFEITURA MUNICIPAL DE|PREFEITURA DE)\s+([A-Z0-9 .'-]{3,90})",
        rf"([A-Z][A-Z0-9 .'-]{{2,70}})\s*[-/]\s*{re.escape(uf)}\b",
    ]
    stop_words = r"\s{2,}|EXERCICIO|PERIODO|CNPJ|RELATORIO|DEMONSTRATIVO|ORCAMENTOS|PAGINA"
    for pattern in patterns:
        for match in re.finditer(pattern, header):
            raw = re.split(stop_words, match.group(1))[0].strip(" -:/")
            city, score = localizar_nome(raw)
            if city and score >= 0.93:
                return city, score, "CONFERENCIA_CABECALHO_LOCAL", "", 0

    return None, 0.0, "MUNICIPIO_INTERNO_NAO_CONFIRMADO", "", 0


def process(pdf_path: str | Path, codigos: Iterable[str] | None = None) -> tuple[dict[str, float | None], str]:
    codes = validar_codigos_rreo(codigos or DEFAULT_CODES)
    text = extract_text(pdf_path)

    # Caminho rápido: extração local primeiro. Gemini só complementa códigos
    # ausentes; nunca participa da decisão sobre o município.
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
