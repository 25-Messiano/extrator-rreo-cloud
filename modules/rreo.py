from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pdfplumber

from integrations.gemini import extract_rreo_values, identify_rreo_municipality


DEFAULT_CODES = [
    "1.1",
    "1.2",
    "1.3",
    "1.4",
    "2.1",
    "2.1.1",
    "2.1.2",
    "2.2",
    "2.3",
    "2.4",
    "2.5",
    "2.6",
    "6.1.1",
    "6.2",
    "6.2.1",
]

MONEY_PATTERN = re.compile(
    r"(?<!\d)(?:\d{1,3}(?:\.\d{3})*|\d+),\d{2}(?!\d)"
)


def extract_text(pdf_path: str | Path) -> str:
    """Extrai o texto de todas as páginas, preservando quebras de linha."""
    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"PDF não encontrado: {path}")

    paginas: list[str] = []

    with pdfplumber.open(path) as pdf:
        for numero, pagina in enumerate(pdf.pages, start=1):
            texto = pagina.extract_text(
                x_tolerance=2,
                y_tolerance=3,
                layout=True,
            ) or ""

            paginas.append(
                f"\n===== PÁGINA {numero} =====\n{texto}"
            )

    return "\n".join(paginas).strip()


def _br_to_float(valor: str) -> float:
    return float(valor.replace(".", "").replace(",", "."))


def _codigo_regex(codigo: str) -> re.Pattern[str]:
    """Evita confundir 1.1 com 1.1.1, 2.1 com 2.1.1 etc."""
    return re.compile(rf"(?m)^\s*{re.escape(codigo)}\s*[-–—]")


def _bloco_da_linha(
    texto: str,
    codigo: str,
    max_chars: int = 900,
) -> str:
    """Captura a linha-alvo e suas continuações até o próximo código."""
    match = _codigo_regex(codigo).search(texto)
    if not match:
        return ""

    inicio = match.start()
    limite = min(len(texto), inicio + max_chars)
    proximo_padrao = re.compile(
        r"(?m)^\s*\d+(?:\.\d+)+\s*[-–—]"
    )
    proximo = proximo_padrao.search(texto, match.end(), limite)
    fim = proximo.start() if proximo else limite
    return texto[inicio:fim]


def extract_codes(
    texto: str,
    codigos: Iterable[str] | None = None,
) -> dict[str, float | None]:
    """
    Fallback local: lê a linha completa e escolhe o segundo valor monetário,
    correspondente à coluna 'RECEITAS REALIZADAS Até o Bimestre (b)'.
    """
    lista_codigos = list(codigos or DEFAULT_CODES)
    resultado: dict[str, float | None] = {}

    for codigo in lista_codigos:
        bloco = _bloco_da_linha(texto, codigo)
        valores = MONEY_PATTERN.findall(bloco)

        if len(valores) >= 2:
            resultado[codigo] = _br_to_float(valores[1])
        else:
            resultado[codigo] = None

    return resultado



def _normalize_name(value: str) -> str:
    import unicodedata
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text).upper()
    return re.sub(r"\s+", " ", text).strip()


def identify_internal_municipality(
    texto_pdf: str,
    municipios: list[dict],
    uf_esperada: str,
    usar_gemini: bool = True,
) -> tuple[dict | None, float, str, str, int]:
    """Identifica município exclusivamente pelo conteúdo interno do RREO.

    Retorna: município, confiança, método, modelo Gemini e tentativas.
    O nome externo do arquivo nunca participa da decisão.
    """
    texto = _normalize_name((texto_pdf or "")[:30000])
    if not texto:
        return None, 0.0, "CONTEUDO_VAZIO", "", 0

    uf_norm = _normalize_name(uf_esperada)
    cabecalho = texto[:8000]

    # Prioridade 1: padrões explícitos no cabeçalho.
    patterns = [
        r"(?:MUNICIPIO|ENTE FEDERADO|PREFEITURA MUNICIPAL DE|PREFEITURA DE)\s*[:\-]?\s*([A-Z0-9 .'-]{3,90})",
        r"([A-Z][A-Z0-9 .'-]{2,70})\s*[-/]\s*" + re.escape(uf_norm),
    ]
    candidates: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, cabecalho, flags=re.S):
            candidate = match.group(1).strip(" -/|:")
            candidate = re.split(
                r"\s{2,}|EXERCICIO|PERIODO|CNPJ|RELATORIO|ORCAMENTOS|DEMONSTRATIVO",
                candidate,
            )[0].strip()
            if candidate:
                candidates.append(candidate)

    def best_match(reference: str) -> tuple[dict | None, float]:
        from difflib import SequenceMatcher
        ref = _normalize_name(reference)
        best = None
        score = 0.0
        for city in municipios:
            name = _normalize_name(city.get("nome", ""))
            if not name:
                continue
            current = 1.0 if ref == name else SequenceMatcher(None, ref, name).ratio()
            if current > score:
                best, score = city, current
        return best, score

    for candidate in candidates:
        city, score = best_match(candidate)
        if city and score >= 0.88:
            return city, score, "CABECALHO_INTERNO", "", 0

    # Prioridade 2: nome oficial completo nas primeiras linhas.
    exact: list[tuple[int, dict]] = []
    for city in municipios:
        name = _normalize_name(city.get("nome", ""))
        if not name:
            continue
        position = cabecalho.find(name)
        if position >= 0:
            exact.append((position, city))
    if exact:
        exact.sort(key=lambda item: item[0])
        return exact[0][1], 0.97, "NOME_EXATO_NO_CABECALHO", "", 0

    # Prioridade 3: Gemini, ainda usando somente o conteúdo interno.
    if usar_gemini:
        try:
            name, returned_uf, confidence, model, attempts = identify_rreo_municipality(
                texto_pdf=texto_pdf,
                municipios=[str(city.get("nome", "")) for city in municipios],
                uf=uf_esperada,
            )
            if name and confidence >= 0.78 and (not returned_uf or returned_uf == uf_esperada.upper()):
                city, score = best_match(name)
                if city and score >= 0.84:
                    return city, min(confidence, score), "GEMINI_CONTEUDO_INTERNO", model, attempts
        except Exception:
            pass

    return None, 0.0, "MUNICIPIO_INTERNO_NAO_IDENTIFICADO", "", 0

def process(
    pdf_path: str | Path,
    codigos: Iterable[str] | None = None,
) -> tuple[dict[str, float | None], str]:
    """
    Mantém a assinatura usada pelo painel:
        resultados, texto = process(caminho_pdf, CODIGOS_RREO)
    """
    lista_codigos = list(codigos or DEFAULT_CODES)
    texto = extract_text(pdf_path)

    try:
        resultados = extract_rreo_values(
            texto_pdf=texto,
            codigos=lista_codigos,
        )
    except Exception:
        resultados = extract_codes(
            texto=texto,
            codigos=lista_codigos,
        )

    return resultados, texto
