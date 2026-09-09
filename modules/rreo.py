from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

import pdfplumber

from core.validacao import normalizar_texto, validar_codigos_rreo
from integrations.gemini import extract_rreo_values, identify_rreo_municipality
from modules.rreo_safe import (
    compare_values, extract_codes_geometry, sha256_file,
    extract_municipality_header_candidates, resolve_municipality_candidate,
)
from modules.rreo_fields.registry import extract_many as extract_exclusive_fields

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
    """V1.3.7.3: cada codigo e extraido por seu proprio modulo exclusivo.

    Codigo de LINHA e papel de COLUNA sao tipos diferentes; a coluna (a) e
    registrada como proibida e somente RECEITAS REALIZADAS (b) e retornada.
    """
    selected = validar_codigos_rreo(codes or DEFAULT_CODES)
    result, _evidence = extract_exclusive_fields(text, selected)
    return result




def _extract_total_value(text: str, total_code: str) -> float | None:
    """Extrai a coluna (b) de uma linha total inteira, ex.: ``1- RECEITA DE IMPOSTOS``.

    Esta leitura existe apenas como prova estrutural independente dos 15 campos.
    Ela nao substitui nenhum valor individual; serve para bloquear aprovacao quando
    a soma dos filhos nao fecha com o total oficial do proprio PDF.
    """
    match = re.search(rf"(?m)^\s*{re.escape(total_code)}\s*[-–—]", text)
    if not match:
        return None
    limit = min(len(text), match.start() + 1200)
    next_match = re.search(r"(?m)^\s*\d+(?:\.\d+)+\s*[-–—]", text[match.end():limit])
    end = match.end() + next_match.start() if next_match else limit
    block = text[match.start():end]
    values = MONEY_PATTERN.findall(block)
    return _br_to_float(values[1]) if len(values) >= 2 else None


def validate_structural_relations(
    text: str,
    values: dict[str, float | None],
    tolerance: float = 0.02,
) -> dict[str, dict[str, float | None]]:
    """Valida identidades contabeis que pegam deslocamento de linha.

    Regras fail-closed:
    - 1.1 + 1.2 + 1.3 + 1.4 deve fechar com 1- RECEITA DE IMPOSTOS;
    - 2.1.1 + 2.1.2 deve fechar com 2.1- Cota-Parte FPM.

    So cria divergencia quando todos os valores necessarios existem no PDF.
    """
    divergences: dict[str, dict[str, float | None]] = {}

    total_1 = _extract_total_value(text, "1")
    filhos_1 = [values.get(c) for c in ("1.1", "1.2", "1.3", "1.4")]
    if total_1 is not None and all(v is not None for v in filhos_1):
        soma_1 = round(sum(float(v) for v in filhos_1 if v is not None), 2)
        if abs(soma_1 - float(total_1)) > tolerance:
            divergences["TOTAL_1"] = {
                "total_pdf": round(float(total_1), 2),
                "soma_1_1_a_1_4": soma_1,
            }

    v21 = values.get("2.1")
    v211 = values.get("2.1.1")
    v212 = values.get("2.1.2")
    if v21 is not None and v211 is not None and v212 is not None:
        soma_21 = round(float(v211) + float(v212), 2)
        if abs(soma_21 - float(v21)) > tolerance:
            divergences["TOTAL_2.1"] = {
                "2.1_pdf": round(float(v21), 2),
                "soma_2.1.1_2.1.2": soma_21,
            }

    return divergences


def validate_semantic_labels(text: str) -> dict[str, str]:
    """Confirma que codigos sensiveis continuam ligados ao rotulo correto."""
    expected = {
        "1.1": ("IPTU", "PROPRIEDADE PREDIAL"),
        "1.2": ("ITBI", "TRANSMISSAO INTER VIVOS"),
        "1.3": ("ISS", "SERVICOS DE QUALQUER NATUREZA"),
        "1.4": ("IRRF", "RENDA RETIDO"),
        "2.1": ("FPM",),
        "2.2": ("ICMS",),
        "2.3": ("IPI",),
        "2.4": ("ITR",),
        "2.5": ("IPVA",),
        "2.6": ("IOF",),
    }
    problems: dict[str, str] = {}
    for code, keywords in expected.items():
        block = _line_block(text, code, max_chars=1000)
        if not block:
            continue
        normalized = normalizar_texto(block)
        if not any(normalizar_texto(k) in normalized for k in keywords):
            problems[code] = f"Rotulo da linha {code} nao confirmou {keywords}"
    return problems


def identify_internal_municipality(
    texto_pdf: str,
    municipios: list[dict[str, Any]],
    uf_esperada: str,
    usar_gemini: bool = False,
) -> tuple[dict[str, Any] | None, float, str, str, int]:
    """Identifica Municipio+UF pelo cabecalho explicito do PDF.

    V3.7 SAFE: nao procura mais nomes municipais como substring em todo o texto.
    A liberacao automatica ocorre apenas por igualdade canonica ou alias
    controlado. Fuzzy/IA pode ajudar na arbitragem, mas nao substitui essa trava.
    """
    raw_header = (texto_pdf or '')[:18000]
    if not normalizar_texto(raw_header):
        return None, 0.0, "CONTEUDO_VAZIO", "", 0

    resolved: list[dict[str, Any]] = []
    candidates = extract_municipality_header_candidates(raw_header, uf_esperada)
    for candidate in candidates:
        city = resolve_municipality_candidate(candidate, municipios, uf_esperada)
        if city:
            resolved.append(city)

    unique = {str(city.get('codigo_ibge') or city.get('nome')): city for city in resolved}
    if len(unique) == 1:
        city = next(iter(unique.values()))
        return city, 1.0, "CABECALHO_EXATO_OU_ALIAS_CONTROLADO", "", 0
    if len(unique) > 1:
        return None, 0.0, "CABECALHO_AMBIGUO", "", 0

    if usar_gemini:
        try:
            name, returned_uf, confidence, model, attempts = identify_rreo_municipality(
                texto_pdf, str(uf_esperada).upper(), [str(city.get("nome") or "") for city in municipios]
            )
            # A IA nao libera por similaridade. Sua resposta precisa resolver por
            # nome canonico ou alias controlado, preservando a natureza fail-closed.
            if name and confidence >= 0.90 and (not returned_uf or returned_uf == str(uf_esperada).upper()):
                city = resolve_municipality_candidate(name, municipios, uf_esperada)
                if city:
                    return city, min(float(confidence), 0.95), "GEMINI_RESOLVIDO_POR_ALIAS_CONTROLADO", model, attempts
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


def extract_text_verification(pdf_path: str | Path) -> str:
    """Segunda leitura do PDF com parametros ligeiramente diferentes.

    O objetivo e reduzir o risco de aceitar silenciosamente um valor deslocado
    por uma unica parametrizacao de extracao de texto.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF nao encontrado: {path}")
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(x_tolerance=1, y_tolerance=2, layout=True) or ""
            pages.append(f"\n===== PAGINA {number} =====\n{text}")
    return "\n".join(pages).strip()


def verify_values(
    pdf_path: str | Path,
    expected: dict[str, float | None],
    codigos: Iterable[str] | None = None,
    tolerance: float = 0.01,
) -> dict[str, Any]:
    """Validação RREO independente e determinística.

    Leitor A: pdfplumber textual.
    Leitor B: PyMuPDF por coordenadas, ancorado semanticamente na coluna
    "Bimestre (b)". A IA é usada apenas como árbitro das divergências.
    """
    codes = validar_codigos_rreo(codigos or DEFAULT_CODES)
    secondary = extract_codes_geometry(pdf_path, codes)
    compared = compare_values(expected, secondary, codes, tolerance=tolerance)
    confirmed = dict(compared["confirmed"])
    divergences = dict(compared["divergences"])
    verification_text = ""

    # V1.3.7.2: uma concordancia entre dois leitores nao basta se ambos
    # puderem ter escorregado para a mesma linha. As relacoes estruturais e
    # os rotulos do proprio PDF funcionam como terceira prova independente.
    structural_divergences = validate_structural_relations(
        extract_text(pdf_path), expected, tolerance=max(tolerance, 0.02)
    )
    semantic_divergences = validate_semantic_labels(extract_text(pdf_path))

    if divergences:
        verification_text = extract_text_verification(pdf_path)
        try:
            adjudicated = extract_rreo_values(texto_pdf=verification_text, codigos=list(divergences))
        except Exception:
            adjudicated = {}
        for code in list(divergences):
            first_value = expected.get(code)
            second_value = secondary.get(code)
            third_value = adjudicated.get(code)
            # O árbitro só libera quando concorda com um dos leitores e não há
            # indício de dois valores plausíveis distintos para a mesma célula.
            if third_value is None:
                continue
            matches_first = first_value is not None and abs(float(first_value) - float(third_value)) <= tolerance
            matches_second = second_value is not None and abs(float(second_value) - float(third_value)) <= tolerance
            if matches_first and not matches_second:
                confirmed[code] = round(float(first_value), 2)
                divergences.pop(code, None)
            elif matches_second and not matches_first:
                confirmed[code] = round(float(second_value), 2)
                divergences.pop(code, None)
            elif matches_first and matches_second:
                confirmed[code] = round(float(first_value), 2)
                divergences.pop(code, None)

    return {
        "ok": not divergences and not structural_divergences and not semantic_divergences,
        "confirmed": confirmed,
        "divergences": divergences,
        "structural_divergences": structural_divergences,
        "semantic_divergences": semantic_divergences,
        "method": "PDFPLUMBER_TEXT + PYMUPDF_GEOMETRY_COLUNA_B + RELACOES_ESTRUTURAIS + ROTULO_SEMANTICO + GEMINI_ARBITRO_SOMENTE_DIVERGENCIAS",
        "verification_text": verification_text,
        "secondary_values": secondary,
        "pdf_sha256": sha256_file(pdf_path),
        "column_semantic": not semantic_divergences,
        "structural_ok": not structural_divergences,
    }

