from __future__ import annotations

import hashlib
import json
import math
import re
from functools import lru_cache
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import fitz

from core.validacao import normalizar_texto, validar_codigos_rreo

MONEY_PATTERN = re.compile(r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)")


_ALIAS_PATH = Path(__file__).resolve().parents[1] / 'config' / 'rreo_municipality_aliases.json'


def canonical_municipality_name(value: Any) -> str:
    """Normalizacao municipal segura, preservando equivalencia de contracoes.

    Exemplos equivalentes: d'Oeste/DOESTE, d'Agua/DAGUA, d'Arca/DARCA.
    Nao faz fuzzy e nao remove palavras inteiras do nome.
    """
    raw = str(value or '').strip()
    raw = re.sub(r"\b([Dd])['’`´]\s*([A-Za-zÀ-ÿ])", r"\1\2", raw)
    return normalizar_texto(raw)


@lru_cache(maxsize=1)
def load_municipality_aliases() -> dict[tuple[str, str], str]:
    aliases: dict[tuple[str, str], str] = {}
    if not _ALIAS_PATH.exists():
        return aliases
    try:
        payload = json.loads(_ALIAS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return aliases
    for item in payload.get('aliases', []):
        uf = str(item.get('uf') or '').upper().strip()
        alias = canonical_municipality_name(item.get('alias'))
        official = canonical_municipality_name(item.get('official'))
        if len(uf) == 2 and alias and official:
            aliases[(uf, alias)] = official
    return aliases


def resolve_municipality_candidate(
    raw_candidate: str,
    municipios: Iterable[Mapping[str, Any]],
    uf: str,
) -> dict[str, Any] | None:
    """Resolve somente por igualdade canonica ou alias explicitamente cadastrado."""
    uf = str(uf or '').upper().strip()
    key = canonical_municipality_name(raw_candidate)
    if not key:
        return None
    by_key = {
        canonical_municipality_name(city.get('nome')): city
        for city in municipios
        if str(city.get('uf') or uf).upper().strip() == uf
    }
    if key in by_key:
        return dict(by_key[key])
    official_key = load_municipality_aliases().get((uf, key))
    if official_key and official_key in by_key:
        return dict(by_key[official_key])
    return None


def extract_municipality_header_candidates(text: str, uf: str, *, max_lines: int = 140) -> list[str]:
    """Extrai candidatos apenas de linhas que parecem cabecalho municipal.

    Evita a antiga busca por substring em todo o texto, que confundia Itá com
    palavras/municipios maiores e Tapejara com Itapejara d'Oeste.
    """
    uf = str(uf or '').upper().strip()
    candidates: list[str] = []
    for raw_line in (text or '').splitlines()[:max_lines]:
        line = raw_line.strip()
        if not line or len(line) > 150:
            continue
        # Formato dominante dos PDFs: MUNICIPIO - UF / MUNICIPIO / UF.
        # Faz o parse antes de normalizar, pois normalizar_texto remove o hifen.
        m = re.match(rf"^(.+?)\s*[-/]\s*{re.escape(uf)}\s*$", line, flags=re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if 2 <= len(candidate) <= 100:
                candidates.append(candidate)
                continue
        # Rotulos explicitos, sem procurar nomes soltos no restante do relatorio.
        normalized = normalizar_texto(line)
        m = re.match(r"^(?:MUNICIPIO|ENTE FEDERADO|PREFEITURA MUNICIPAL DE|PREFEITURA DE)\s*[:\-]?\s*(.+)$", normalized)
        if m:
            candidate = re.split(r"\s{2,}|EXERCICIO|PERIODO|CNPJ|RELATORIO|DEMONSTRATIVO", m.group(1))[0].strip()
            if candidate:
                candidates.append(candidate)
    # ordem estavel, sem duplicatas
    return list(dict.fromkeys(candidates))


def validate_state_completeness(expected_names: Iterable[str], found_names: Iterable[str]) -> dict[str, Any]:
    expected = {canonical_municipality_name(x): str(x) for x in expected_names if canonical_municipality_name(x)}
    found = {canonical_municipality_name(x): str(x) for x in found_names if canonical_municipality_name(x)}
    missing_keys = sorted(set(expected) - set(found))
    extra_keys = sorted(set(found) - set(expected))
    return {
        'ok': not missing_keys and not extra_keys,
        'expected': len(expected),
        'found': len(found),
        'missing': [expected[k] for k in missing_keys],
        'extra': [found[k] for k in extra_keys],
    }


def br_to_float(value: str) -> float:
    return float(value.replace('.', '').replace(',', '.'))


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def result_fingerprint(ibge: str, ano: int | str, bimestre: int | str, values: Mapping[str, Any]) -> str:
    payload = {
        'ibge': str(ibge or ''),
        'ano': str(ano or ''),
        'bimestre': str(bimestre or ''),
        'values': {str(k): None if v is None else round(float(v), 2) for k, v in sorted(values.items())},
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _page_target_x(page: fitz.Page) -> float | None:
    words = page.get_text('words')
    # Procura o cabeçalho semântico da coluna (b). Em caso de repetição, usa o primeiro.
    for i, w in enumerate(words):
        txt = str(w[4]).strip().lower()
        if txt == 'bimestre':
            same_line = [x for x in words if abs(float(x[1]) - float(w[1])) <= 2.5]
            if any(str(x[4]).strip().lower() == '(b)' for x in same_line):
                right = max(float(x[2]) for x in same_line if str(x[4]).strip().lower() in {'bimestre', '(b)'})
                left = min(float(x[0]) for x in same_line if str(x[4]).strip().lower() in {'bimestre', '(b)'})
                return (left + right) / 2.0
    # fallback: procura 'REALIZADAS' e toma a zona numérica mais à direita.
    for w in words:
        if normalizar_texto(w[4]) == 'realizadas':
            return page.rect.width * 0.88
    return None


def _code_word_indexes(words: list[tuple], code: str) -> list[int]:
    expected = f'{code}-'
    out: list[int] = []
    for i, w in enumerate(words):
        txt = str(w[4]).strip().replace('–', '-').replace('—', '-')
        if txt == expected or txt == code:
            out.append(i)
    return out


def extract_codes_geometry(pdf_path: str | Path, codes: Iterable[str], *, max_y_span: float = 55.0) -> dict[str, float | None]:
    """Extrator independente baseado em coordenadas PyMuPDF.

    Em vez de assumir 'segundo número da linha', localiza semanticamente a coluna
    Bimestre (b) e escolhe o valor monetário geometricamente alinhado a ela.
    """
    path = Path(pdf_path)
    result = {code: None for code in validar_codigos_rreo(codes)}
    with fitz.open(path) as doc:
        last_target_x: float | None = None
        for page in doc:
            detected_x = _page_target_x(page)
            if detected_x is not None:
                last_target_x = detected_x
            target_x = detected_x if detected_x is not None else last_target_x
            if target_x is None:
                continue
            words = page.get_text('words')
            # Ordenação física estável: bloco/linha/palavra já vem preservada pelo fitz.
            for code in list(result):
                if result[code] is not None:
                    continue
                candidates: list[tuple[float, float, str]] = []
                for idx in _code_word_indexes(words, code):
                    code_word = words[idx]
                    y0 = float(code_word[1]) - 3.0
                    y1 = float(code_word[3]) + max_y_span
                    # limita até o próximo código hierárquico visível quando houver
                    next_y: float | None = None
                    for other in words[idx + 1:]:
                        otxt = str(other[4]).strip().replace('–', '-').replace('—', '-')
                        if re.fullmatch(r'\d+(?:\.\d+)+-', otxt):
                            next_y = float(other[1]) - 1.5
                            break
                    if next_y is not None:
                        y1 = min(y1, next_y)
                    for w in words:
                        txt = str(w[4]).strip()
                        if not MONEY_PATTERN.fullmatch(txt):
                            continue
                        cy = (float(w[1]) + float(w[3])) / 2.0
                        if not (y0 <= cy <= y1):
                            continue
                        cx = (float(w[0]) + float(w[2])) / 2.0
                        code_cy = (float(code_word[1]) + float(code_word[3])) / 2.0
                        dy = abs(cy - code_cy)
                        # A coluna semântica decide X; a proximidade vertical ao código
                        # impede capturar a linha seguinte quando ela está mais alinhada em X.
                        dist = abs(cx - target_x) + (dy * 3.0)
                        # coluna (b) é a coluna monetária à direita; penaliza números à esquerda.
                        if cx < target_x - 95:
                            dist += 250
                        candidates.append((dist, -cx, txt))
                if candidates:
                    candidates.sort()
                    result[code] = round(br_to_float(candidates[0][2]), 2)
    return result


def compare_values(primary: Mapping[str, Any], secondary: Mapping[str, Any], codes: Iterable[str], tolerance: float = 0.01) -> dict[str, Any]:
    confirmed: dict[str, float | None] = {}
    divergences: dict[str, dict[str, float | None]] = {}
    for code in validar_codigos_rreo(codes):
        a = primary.get(code)
        b = secondary.get(code)
        if a is None and b is None:
            confirmed[code] = None
        elif a is not None and b is not None and abs(float(a) - float(b)) <= tolerance:
            confirmed[code] = round(float(a), 2)
        else:
            divergences[code] = {
                'pdfplumber': None if a is None else round(float(a), 2),
                'pymupdf_geometry': None if b is None else round(float(b), 2),
            }
    return {'confirmed': confirmed, 'divergences': divergences, 'ok': not divergences}


def identity_guard(expected_name: str, internal_name: str | None, *, require_internal: bool = True) -> dict[str, Any]:
    exp = canonical_municipality_name(expected_name)
    internal = canonical_municipality_name(internal_name or '')
    if not internal:
        return {
            'ok': not require_internal,
            'status': 'INTERNO_NAO_IDENTIFICADO',
            'message': 'Município interno não identificado no PDF.' if require_internal else '',
        }
    ok = exp == internal
    return {
        'ok': ok,
        'status': 'OK' if ok else 'DIVERGENCIA_MUNICIPIO',
        'message': '' if ok else f'Município esperado={expected_name}; conteúdo={internal_name}',
    }


def confidence_score(*, identity_ok: bool, dual_ok: bool, column_semantic: bool, hash_ok: bool, post_write_ok: bool | None = None) -> int:
    score = 0
    score += 20 if identity_ok else 0
    score += 35 if dual_ok else 0
    score += 20 if column_semantic else 0
    score += 10 if hash_ok else 0
    if post_write_ok is True:
        score += 15
    return min(score, 100)


def evidence_record(**kwargs: Any) -> dict[str, Any]:
    return {k: v for k, v in kwargs.items() if v is not None}
