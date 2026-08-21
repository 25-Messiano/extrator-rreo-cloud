from __future__ import annotations

import io
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from core.validacao import validar_programas_fnde
from integrations.gemini import generate_structured

BASE_DIR = Path(__file__).resolve().parents[1]
REFERENCIAS_DIR = BASE_DIR / "data" / "referencias_fnde"

COLUNAS_FNDE = {"PNAE": 20, "PNATE": 21, "PDDE": 22, "QSE": 23}

ALIASES_PADRAO = {
    "PNAE": [
        "PROGRAMA NACIONAL DE ALIMENTAÇÃO ESCOLAR",
        "PROG.NACIONAL DE ALIMENTAÇÃO ESCOLAR",
        "NACIONAL DE ALIMENTAÇÃO ESCOLAR",
        "PNAE",
    ],
    "PNATE": [
        "PROGRAMA NACIONAL DE APOIO AO TRANSPORTE DO ESCOLAR",
        "PROGRAMA NACIONAL DE APOIO AO TRANSP DO ESCOLAR",
        "NACIONAL DE APOIO AO TRANSPORTE DO ESCOLAR",
        "NACIONAL DE APOIO AO TRANSP DO ESCOLAR",
        "PNATE",
    ],
    "PDDE": ["PROGRAMA DINHEIRO DIRETO NA ESCOLA", "PDDE"],
    "QSE": [
        "QUOTA ESTADUAL/MUNICIPAL",
        "COTA ESTADUAL/MUNICIPAL",
        "SALÁRIO-EDUCAÇÃO",
        "QSE",
        "QESE",
    ],
}
EXCLUSOES_PADRAO = [
    "ANTIGO PDDE ESTRUTURA",
    "ÁGUA E ESGOTAMENTO SANITÁRIO",
    "ESCOLA DO CAMPO",
    "ESCOLA ACESSÍVEL",
    "PDE ESCOLA",
    "ENSINO MÉDIO INOVADOR",
    "MAIS CULTURA",
    "ESCOLA DE FRONTEIRA",
    "ATLETA NA ESCOLA",
    "ESCOLA SUSTENTÁVEL",
]


@dataclass
class OcorrenciaFNDE:
    programa: str
    titulo: str
    valor: float
    pagina: int | None = None
    esfera: str = ""
    quantidade_entidades: int | None = None
    justificativa: str = ""


@dataclass
class ResultadoFNDE:
    codigo_ibge: str
    municipio: str
    uf: str
    pnae: float = 0.0
    pnate: float = 0.0
    pdde: float = 0.0
    qse: float = 0.0
    ocorrencias: list[OcorrenciaFNDE] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    metodo: str = ""
    modelo: str = ""
    tentativas: int = 0

    def valores_planilha(self) -> dict[str, float]:
        return {
            "PNAE": round(float(self.pnae), 2),
            "PNATE": round(float(self.pnate), 2),
            "PDDE": round(float(self.pdde), 2),
            "QSE": round(float(self.qse), 2),
        }

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalizar_texto(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Z0-9]+", " ", text.upper())
    return re.sub(r"\s+", " ", text).strip()


def normalizar_codigo_ibge(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        value = int(value)
    digits = re.sub(r"\D", "", str(value))
    return digits.zfill(7) if digits else ""


def converter_valor_brasileiro(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = re.sub(r"[^\d,.\-]", "", str(value))
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _read_json(name: str) -> dict[str, Any]:
    path = REFERENCIAS_DIR / name
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except Exception:
        return {}


def _load_rules() -> tuple[dict[str, list[str]], list[str]]:
    aliases_data = _read_json("aliases_programas.json").get("aliases", {})
    exclusions_data = _read_json("palavras_excluir.json").get("excluir_do_pdde", [])
    aliases: dict[str, list[str]] = {}
    for program in COLUNAS_FNDE:
        values = [*ALIASES_PADRAO.get(program, []), *aliases_data.get(program, [])]
        aliases[program] = sorted({normalizar_texto(v) for v in values if str(v).strip()}, key=len, reverse=True)
    exclusions = sorted(
        {normalizar_texto(v) for v in [*EXCLUSOES_PADRAO, *exclusions_data] if str(v).strip()},
        key=len,
        reverse=True,
    )
    return aliases, exclusions


ALIASES, EXCLUSOES_PDDE = _load_rules()


def extrair_identificacao_nome_pdf(path: str | Path) -> tuple[str, str, str]:
    name = Path(path).stem
    match = re.search(r"(?<!\d)(\d{7})(?!\d)", name)
    code = match.group(1) if match else ""
    uf_match = re.search(r"[-_/\s]([A-Z]{2})(?:\s*\(\d+\))?\s*$", name.upper())
    uf = uf_match.group(1) if uf_match else ""
    municipality = ""
    if match:
        municipality = name[match.end():]
        municipality = re.sub(r"[-_/\s]+[A-Za-z]{2}(?:\s*\(\d+\))?\s*$", "", municipality).strip(" _-/")
    return code, municipality, uf


def renderizar_paginas_png(
    path: str | Path,
    scale: float | None = None,
    max_pages: int = 20,
) -> list[tuple[int, bytes]]:
    render_scale = scale or float(os.getenv("FNDE_RENDER_SCALE", "2.2"))
    document = pdfium.PdfDocument(str(path))
    images: list[tuple[int, bytes]] = []
    try:
        for index in range(min(len(document), max_pages)):
            page = document[index]
            bitmap = page.render(scale=render_scale)
            image = bitmap.to_pil().convert("RGB")
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
            images.append((index + 1, buffer.getvalue()))
            image.close(); bitmap.close(); page.close()
    finally:
        document.close()
    return images


def _schema() -> dict[str, Any]:
    occurrence = {
        "type": "object",
        "properties": {
            "programa": {"type": "string", "enum": ["PNAE", "PNATE", "PDDE", "QSE"]},
            "titulo": {"type": "string"},
            "valor": {"type": "number"},
            "pagina": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "esfera": {"type": "string"},
            "quantidade_entidades": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "justificativa": {"type": "string"},
        },
        "required": ["programa", "titulo", "valor", "pagina", "esfera", "quantidade_entidades", "justificativa"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "codigo_ibge": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "municipio": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "uf": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "ocorrencias": {"type": "array", "items": occurrence},
            "avisos": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["codigo_ibge", "municipio", "uf", "ocorrencias", "avisos"],
        "additionalProperties": False,
    }


def _prompt(name: str, code: str, municipality: str, uf: str) -> str:
    return f"""
Você está lendo IMAGENS de um demonstrativo FNDE/SIGEFWEB. Faça OCR visual e extração estruturada.
Arquivo: {name}; IBGE no nome: {code}; Município: {municipality}; UF: {uf}.

Extraia apenas o Valor Total do cabeçalho de cada bloco-alvo:
- PNAE: Programa/Prog. Nacional de Alimentação Escolar.
- PNATE: Programa Nacional de Apoio ao Transporte do Escolar, inclusive abreviação TRANSP.
- PDDE: SOMENTE "PROGRAMA DINHEIRO DIRETO NA ESCOLA".
- QSE: Quota/Cota Estadual/Municipal, Salário-Educação, QSE ou QESE.

Regras críticas:
1. Não some as linhas de esfera ao Valor Total do cabeçalho; use as linhas apenas para conferir.
2. Não inclua ANTIGO PDDE ESTRUTURA, Ensino Médio Inovador, Mais Cultura, Escola Sustentável,
   Água/Esgotamento, Escola do Campo, Escola Acessível, PDE Escola ou qualquer bloco diferente.
3. Registre uma ocorrência por bloco válido, com título literal, valor, página e esfera.
4. Se o mesmo bloco aparecer duplicado por repetição visual, registre uma única vez.
5. Não invente valor. Se ilegível, registre aviso e não crie ocorrência.
6. Retorne JSON estrito conforme o schema.
""".strip()


def _classify_title(title: str) -> str | None:
    text = normalizar_texto(title)
    if any(term in text for term in EXCLUSOES_PDDE):
        return None
    for program in ("PNAE", "PNATE", "PDDE", "QSE"):
        if any(alias in text for alias in ALIASES[program]):
            return program
    return None


def _validate_occurrences(raw_items: list[dict[str, Any]]) -> tuple[list[OcorrenciaFNDE], list[str]]:
    occurrences: list[OcorrenciaFNDE] = []
    warnings: list[str] = []
    seen: set[tuple[str, str, int | None, float]] = set()
    for item in raw_items:
        title = str(item.get("titulo") or "").strip()
        program = _classify_title(title)
        value = converter_valor_brasileiro(item.get("valor"))
        if program is None or value is None:
            warnings.append(f"Bloco descartado: {title or 'sem título'}")
            continue
        key = (program, normalizar_texto(title), item.get("pagina"), value)
        if key in seen:
            continue
        seen.add(key)
        occurrences.append(OcorrenciaFNDE(
            programa=program,
            titulo=title,
            valor=value,
            pagina=int(item["pagina"]) if item.get("pagina") is not None else None,
            esfera=str(item.get("esfera") or ""),
            quantidade_entidades=int(item["quantidade_entidades"]) if item.get("quantidade_entidades") is not None else None,
            justificativa=str(item.get("justificativa") or ""),
        ))
    return occurrences, warnings


def _totals(occurrences: list[OcorrenciaFNDE]) -> dict[str, float]:
    result = {program: 0.0 for program in COLUNAS_FNDE}
    for item in occurrences:
        result[item.programa] += item.valor
    return {k: round(v, 2) for k, v in result.items()}


def _ocr_text(images: list[tuple[int, bytes]]) -> str:
    try:
        import pytesseract
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise RuntimeError("Fallback OCR indisponível: pytesseract/Pillow não instalados.") from exc

    pages: list[str] = []
    for page_number, data in images:
        image = Image.open(io.BytesIO(data)).convert("L")
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.5)
        text = pytesseract.image_to_string(
            image,
            lang=os.getenv("TESSERACT_LANG", "por+eng"),
            config="--psm 6",
            timeout=float(os.getenv("TESSERACT_TIMEOUT_SECONDS", "90")),
        )
        pages.append(f"\n===== PÁGINA {page_number} =====\n{text}")
        image.close()
    return "\n".join(pages)


def _extract_from_ocr(text: str) -> tuple[list[OcorrenciaFNDE], list[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    occurrences: list[OcorrenciaFNDE] = []
    warnings: list[str] = []
    money = re.compile(r"(?:R\$\s*)?((?:\d{1,3}(?:\.\d{3})*|\d+),\d{2})")
    for index, line in enumerate(lines):
        program = _classify_title(line)
        if not program:
            continue
        window = " ".join(lines[index:index + 4])
        match = re.search(r"VALOR\s+TOTAL", normalizar_texto(window))
        values = money.findall(window)
        if not match or not values:
            warnings.append(f"OCR encontrou título, mas não o total: {line}")
            continue
        value = converter_valor_brasileiro(values[0])
        if value is not None:
            occurrences.append(OcorrenciaFNDE(program, line, value, justificativa="OCR_LOCAL_FALLBACK"))
    validated, more = _validate_occurrences([asdict(o) for o in occurrences])
    return validated, [*warnings, *more]


def extrair_com_gemini(
    caminho_pdf: str | Path,
    model: str | None = None,
    enviar_imagens: bool = True,
) -> tuple[ResultadoFNDE, str]:
    path = Path(caminho_pdf)
    code_name, municipality_name, uf_name = extrair_identificacao_nome_pdf(path)
    images = renderizar_paginas_png(path)
    if not images:
        raise RuntimeError("O PDF não possui páginas renderizáveis.")

    warnings: list[str] = []
    occurrences: list[OcorrenciaFNDE] = []
    method = ""
    model_used = ""
    attempts = 0

    ocr_first = os.getenv("FNDE_OCR_PRIMEIRO", "true").lower() in ("1", "true", "sim", "yes")
    if ocr_first:
        try:
            ocr_text = _ocr_text(images)
            occurrences, ocr_warnings = _extract_from_ocr(ocr_text)
            warnings.extend(ocr_warnings)
            found = {item.programa for item in occurrences}
            expected = {"PNAE", "PNATE", "PDDE", "QSE"}
            if occurrences and found == expected:
                method = "OCR_LOCAL_PRINCIPAL_OK"
            else:
                warnings.append(
                    "OCR local incompleto; Gemini Vision acionado para os blocos restantes. "
                    f"Encontrados: {', '.join(sorted(found)) or 'nenhum'}."
                )
                occurrences = []
        except Exception as ocr_error:
            warnings.append(f"OCR local falhou: {type(ocr_error).__name__}: {ocr_error}")
            occurrences = []

    if not occurrences:
        try:
            from google.genai import types
            content: list[Any] = [_prompt(path.name, code_name, municipality_name, uf_name)]
            for page_number, data in images:
                content.append(types.Part.from_text(text=f"Página {page_number}:"))
                content.append(types.Part.from_bytes(data=data, mime_type="image/jpeg"))

            raw, model_used, attempts = generate_structured(
                contents=content,
                schema=_schema(),
                model=model,
                max_attempts=int(os.getenv("FNDE_GEMINI_MAX_TENTATIVAS", "3")),
            )
            occurrences, validation_warnings = _validate_occurrences(raw.get("ocorrencias", []) or [])
            warnings.extend(str(v) for v in raw.get("avisos", []) or [] if str(v).strip())
            warnings.extend(validation_warnings)
            if not occurrences:
                raise RuntimeError("Gemini Vision não retornou nenhum bloco FNDE válido.")
            method = "GEMINI_VISION_FALLBACK_OK" if ocr_first else "GEMINI_VISION_OK"
            code_response = normalizar_codigo_ibge(raw.get("codigo_ibge"))
            code = code_name or code_response
            municipality = str(raw.get("municipio") or municipality_name or "").strip()
            uf = str(raw.get("uf") or uf_name or "").strip().upper()
        except Exception as vision_error:
            if not ocr_first and os.getenv("FNDE_USAR_OCR_FALLBACK", "true").lower() in ("1", "true", "sim", "yes"):
                ocr_text = _ocr_text(images)
                occurrences, ocr_warnings = _extract_from_ocr(ocr_text)
                warnings.extend(ocr_warnings)
                if occurrences:
                    method = "OCR_LOCAL_FALLBACK_OK"
                    code, municipality, uf = code_name, municipality_name, uf_name
                else:
                    raise RuntimeError("Gemini Vision e OCR local não localizaram blocos válidos.") from vision_error
            else:
                raise RuntimeError("OCR local e Gemini Vision não localizaram blocos válidos.") from vision_error
    else:
        code, municipality, uf = code_name, municipality_name, uf_name

    totals = _totals(occurrences)
    result = ResultadoFNDE(
        codigo_ibge=code,
        municipio=municipality,
        uf=uf,
        pnae=totals["PNAE"],
        pnate=totals["PNATE"],
        pdde=totals["PDDE"],
        qse=totals["QSE"],
        ocorrencias=occurrences,
        avisos=warnings,
        metodo=method,
        modelo=model_used,
        tentativas=attempts,
    )
    return result, ""


def process(
    caminho_pdf: str | Path,
    model: str | None = None,
    enviar_imagens: bool = True,
) -> tuple[dict[str, float], str, ResultadoFNDE]:
    result, text = extrair_com_gemini(caminho_pdf, model=model, enviar_imagens=enviar_imagens)
    return result.valores_planilha(), text, result
