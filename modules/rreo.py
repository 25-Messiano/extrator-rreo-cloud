from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import pdfplumber

from integrations.gemini import extract_rreo_values


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
