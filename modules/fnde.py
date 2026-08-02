from __future__ import annotations

import argparse
import io
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook
from pypdf import PdfReader
import pypdfium2 as pdfium

BASE_DIR = Path(__file__).resolve().parents[1]
REFERENCIAS_FNDE_DIR = BASE_DIR / "data" / "referencias_fnde"
DEFAULT_MODEL = "gemini-3.6-flash"
FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash")

COLUNAS_FNDE = {"PNAE": 20, "PNATE": 21, "PDDE": 22, "QSE": 23}

DEFAULT_ALIASES = {
    "PNAE": [
        "PROGRAMA NACIONAL DE ALIMENTACAO ESCOLAR",
        "PROG NACIONAL DE ALIMENTACAO ESCOLAR",
        "NACIONAL DE ALIMENTACAO ESCOLAR",
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
        "QUOTA ESTADUAL MUNICIPAL",
        "COTA ESTADUAL MUNICIPAL",
        "SALARIO EDUCACAO",
        "QSE",
        "QESE",
    ],
}

DEFAULT_PDDE_EXCLUSIONS = [
    "ANTIGO PDDE ESTRUTURA",
    "AGUA E ESGOTAMENTO SANITARIO",
    "ESCOLA DO CAMPO",
    "ESCOLA ACESSIVEL",
    "PDE ESCOLA",
    "ENSINO MEDIO INOVADOR",
    "MAIS CULTURA",
    "ESCOLA DE FRONTEIRA",
    "ATLETA NA ESCOLA",
    "ESCOLA SUSTENTAVEL",
]


@dataclass
class OcorrenciaFNDE:
    programa: str
    titulo: str
    valor: float
    pagina: int | None = None
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

    def valores_planilha(self) -> dict[str, float]:
        return {
            "PNAE": round(float(self.pnae or 0.0), 2),
            "PNATE": round(float(self.pnate or 0.0), 2),
            "PDDE": round(float(self.pdde or 0.0), 2),
            "QSE": round(float(self.qse or 0.0), 2),
        }

    def como_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalizar_texto(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").strip())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9]+", " ", texto.upper())
    return re.sub(r"\s+", " ", texto).strip()


def _ler_json(nome: str) -> dict[str, Any]:
    caminho = REFERENCIAS_FNDE_DIR / nome
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
        return bruto if isinstance(bruto, dict) else {}
    except Exception:
        return {}


def _carregar_aliases() -> dict[str, list[str]]:
    configurados = _ler_json("aliases_programas.json").get("aliases", {})
    resultado: dict[str, list[str]] = {}
    for programa, padroes in DEFAULT_ALIASES.items():
        extras = configurados.get(programa, []) if isinstance(configurados, dict) else []
        resultado[programa] = sorted(
            {normalizar_texto(v) for v in [*padroes, *extras] if str(v).strip()},
            key=len,
            reverse=True,
        )
    return resultado


def _carregar_exclusoes_pdde() -> list[str]:
    extras = _ler_json("palavras_excluir.json").get("excluir_do_pdde", [])
    return sorted(
        {normalizar_texto(v) for v in [*DEFAULT_PDDE_EXCLUSIONS, *extras] if str(v).strip()},
        key=len,
        reverse=True,
    )


ALIASES = _carregar_aliases()
EXCLUSOES_PDDE = _carregar_exclusoes_pdde()


def normalizar_codigo_ibge(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float):
        valor = int(valor)
    codigo = re.sub(r"\D", "", str(valor))
    return codigo.zfill(7) if codigo else ""


def converter_valor_brasileiro(valor: Any) -> float | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return round(float(valor), 2)
    texto = re.sub(r"[^\d,.\-]", "", str(valor).strip())
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto), 2)
    except ValueError:
        return None


def extrair_identificacao_nome_pdf(caminho_pdf: str | Path) -> tuple[str, str, str]:
    nome = Path(caminho_pdf).stem
    codigo_match = re.search(r"(?<!\d)(\d{7})(?!\d)", nome)
    codigo = codigo_match.group(1) if codigo_match else ""
    uf_match = re.search(r"[-_/\s]([A-Z]{2})\s*$", nome.upper())
    uf = uf_match.group(1) if uf_match else ""
    municipio = ""
    if codigo_match:
        municipio = nome[codigo_match.end():]
        municipio = re.sub(r"[-_/\s]+[A-Za-z]{2}\s*$", "", municipio).strip(" _-/")
    return codigo, municipio, uf


def extrair_texto_pdf(caminho_pdf: str | Path) -> str:
    leitor = PdfReader(str(caminho_pdf))
    paginas: list[str] = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        try:
            texto = pagina.extract_text() or ""
        except Exception:
            texto = ""
        paginas.append(f"\n===== PÁGINA {numero} =====\n{texto.strip()}")
    return "\n".join(paginas).strip()


def renderizar_paginas_png(caminho_pdf: str | Path, escala: float = 1.7, limite_paginas: int = 20) -> list[tuple[int, bytes]]:
    documento = pdfium.PdfDocument(str(caminho_pdf))
    imagens: list[tuple[int, bytes]] = []
    try:
        for indice in range(min(len(documento), limite_paginas)):
            pagina = documento[indice]
            bitmap = pagina.render(scale=escala)
            imagem = bitmap.to_pil()
            buffer = io.BytesIO()
            imagem.save(buffer, format="PNG", optimize=True)
            imagens.append((indice + 1, buffer.getvalue()))
            imagem.close(); bitmap.close(); pagina.close()
    finally:
        documento.close()
    return imagens


def _classificar_titulo(titulo: str) -> str | None:
    texto = normalizar_texto(titulo)
    if any(exc in texto for exc in EXCLUSOES_PDDE):
        return None
    # Ordem importante: nomes específicos antes do alias curto PDDE/QSE.
    for programa in ("PNAE", "PNATE", "PDDE", "QSE"):
        if any(alias and alias in texto for alias in ALIASES[programa]):
            return programa
    return None


def _pagina_por_posicao(texto: str, posicao: int) -> int | None:
    marcas = list(re.finditer(r"===== P[ÁA]GINA\s+(\d+)\s+=====", texto[:posicao], re.I))
    return int(marcas[-1].group(1)) if marcas else None


def extrair_blocos_textuais(texto_pdf: str) -> list[OcorrenciaFNDE]:
    """Extrai blocos digitais diretamente, sem Gemini, quando o PDF possui texto."""
    ocorrencias: list[OcorrenciaFNDE] = []
    padrao = re.compile(r"-\s*Valor\s+Total\s+R\$\s*([\d.]+,\d{2})", re.I)
    vistos: set[tuple[str, str, int | None, float]] = set()

    for match in padrao.finditer(texto_pdf):
        inicio = max(0, match.start() - 500)
        trecho = texto_pdf[inicio:match.start()]
        # O título fica depois do último marcador de interface/bloco.
        partes = re.split(r"(?:Salvar\s+como\s+PDF|===== P[ÁA]GINA\s+\d+\s+=====)", trecho, flags=re.I)
        titulo_bruto = partes[-1].strip()
        linhas = [l.strip() for l in titulo_bruto.splitlines() if l.strip()]
        titulo = " ".join(linhas[-3:]).strip(" -")
        programa = _classificar_titulo(titulo)
        valor = converter_valor_brasileiro(match.group(1))
        pagina = _pagina_por_posicao(texto_pdf, match.start())
        if not programa or valor is None:
            continue
        chave = (programa, normalizar_texto(titulo), pagina, valor)
        if chave in vistos:
            continue
        vistos.add(chave)
        ocorrencias.append(OcorrenciaFNDE(
            programa=programa,
            titulo=titulo,
            valor=valor,
            pagina=pagina,
            justificativa="Valor Total extraído diretamente do bloco textual do PDF.",
        ))
    return ocorrencias


def _somar_ocorrencias(ocorrencias: list[OcorrenciaFNDE]) -> dict[str, float]:
    totais = {"PNAE": 0.0, "PNATE": 0.0, "PDDE": 0.0, "QSE": 0.0}
    for ocorrencia in ocorrencias:
        programa = _classificar_titulo(ocorrencia.titulo)
        if programa:
            ocorrencia.programa = programa
            totais[programa] += float(ocorrencia.valor)
    return {k: round(v, 2) for k, v in totais.items()}


def _api_key() -> str:
    chave = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not chave:
        raise RuntimeError("Chave do Gemini não encontrada. Configure GEMINI_API_KEY no Render.")
    return chave


def _modelos_candidatos(model: str | None = None) -> list[str]:
    candidatos = [model, os.getenv("GEMINI_MODEL"), *FALLBACK_MODELS]
    resultado: list[str] = []
    for candidato in candidatos:
        nome = str(candidato or "").strip()
        if not nome or nome.startswith("gemini-2."):
            continue
        if nome not in resultado:
            resultado.append(nome)
    return resultado or [DEFAULT_MODEL]


def _schema_gemini() -> dict[str, Any]:
    ocorrencia = {
        "type": "object",
        "properties": {
            "programa": {"type": "string", "enum": ["PNAE", "PNATE", "PDDE", "QSE"]},
            "titulo": {"type": "string"},
            "valor": {"type": "number"},
            "pagina": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "justificativa": {"type": "string"},
        },
        "required": ["programa", "titulo", "valor", "pagina", "justificativa"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "codigo_ibge": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "municipio": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "uf": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "ocorrencias": {"type": "array", "items": ocorrencia},
            "avisos": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["codigo_ibge", "municipio", "uf", "ocorrencias", "avisos"],
        "additionalProperties": False,
    }


def _prompt_fnde(nome: str, codigo: str, municipio: str, uf: str, texto: str) -> str:
    return f"""Você extrai blocos do demonstrativo FNDE/SIGEFWEB.
Arquivo: {nome}; código IBGE: {codigo}; município: {municipio}; UF: {uf}.

Retorne apenas ocorrências dos quatro programas abaixo, usando exclusivamente o Valor Total do título do próprio bloco:
- PNAE: Programa Nacional de Alimentação Escolar, inclusive PROG.NACIONAL...
- PNATE: Programa Nacional de Apoio ao Transporte do Escolar, inclusive TRANSP DO ESCOLAR.
- PDDE: somente PROGRAMA DINHEIRO DIRETO NA ESCOLA.
- QSE: QUOTA/COTA ESTADUAL/MUNICIPAL, SALÁRIO-EDUCAÇÃO, QSE ou QESE.

Nunca classifique como PDDE: {EXCLUSOES_PDDE}.
Não some linhas das esferas ao total do cabeçalho. Não inclua PNLD nem programas alheios.

Texto extraído:
{texto[:120000]}"""


def _extrair_com_gemini(caminho: Path, texto: str, identificacao: tuple[str, str, str], model: str | None) -> tuple[list[OcorrenciaFNDE], list[str], dict[str, str]]:
    from google import genai
    from google.genai import types
    conteudo: list[Any] = [_prompt_fnde(caminho.name, *identificacao, texto)]
    for pagina, png in renderizar_paginas_png(caminho):
        conteudo.append(types.Part.from_text(text=f"Imagem da página {pagina}:"))
        conteudo.append(types.Part.from_bytes(data=png, mime_type="image/png"))

    cliente = genai.Client(api_key=_api_key())
    ultimo_erro: Exception | None = None
    try:
        for modelo in _modelos_candidatos(model):
            try:
                resposta = cliente.models.generate_content(
                    model=modelo,
                    contents=conteudo,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=_schema_gemini(),
                    ),
                )
                bruto = resposta.parsed if isinstance(getattr(resposta, "parsed", None), dict) else json.loads(resposta.text or "{}")
                ocorrencias: list[OcorrenciaFNDE] = []
                for item in bruto.get("ocorrencias", []) or []:
                    valor = converter_valor_brasileiro(item.get("valor"))
                    if valor is None:
                        continue
                    titulo = str(item.get("titulo") or "").strip()
                    programa = _classificar_titulo(titulo)
                    if not programa:
                        continue
                    ocorrencias.append(OcorrenciaFNDE(programa, titulo, valor, item.get("pagina"), str(item.get("justificativa") or "")))
                return ocorrencias, [str(a) for a in bruto.get("avisos", []) or []], {
                    "codigo_ibge": normalizar_codigo_ibge(bruto.get("codigo_ibge")),
                    "municipio": str(bruto.get("municipio") or "").strip(),
                    "uf": str(bruto.get("uf") or "").strip().upper(),
                }
            except Exception as erro:
                ultimo_erro = erro
                continue
    finally:
        cliente.close()
    raise RuntimeError(f"Falha em todos os modelos Gemini: {ultimo_erro}")


def extrair_com_gemini(caminho_pdf: str | Path, model: str | None = None, enviar_imagens: bool = True) -> tuple[ResultadoFNDE, str]:
    caminho = Path(caminho_pdf)
    codigo_nome, municipio_nome, uf_nome = extrair_identificacao_nome_pdf(caminho)
    texto = extrair_texto_pdf(caminho)
    ocorrencias = extrair_blocos_textuais(texto)
    avisos: list[str] = []
    identificacao_gemini = {"codigo_ibge": "", "municipio": "", "uf": ""}

    encontrados = {o.programa for o in ocorrencias}
    # Gemini só é necessário quando o PDF não tem texto útil ou algum programa-alvo está faltando.
    if enviar_imagens and (len(normalizar_texto(texto)) < 300 or len(encontrados) < 4):
        gemini_ocorrencias, gemini_avisos, identificacao_gemini = _extrair_com_gemini(
            caminho, texto, (codigo_nome, municipio_nome, uf_nome), model
        )
        existentes = {(o.programa, normalizar_texto(o.titulo), o.pagina, round(o.valor, 2)) for o in ocorrencias}
        for ocorrencia in gemini_ocorrencias:
            chave = (ocorrencia.programa, normalizar_texto(ocorrencia.titulo), ocorrencia.pagina, round(ocorrencia.valor, 2))
            if chave not in existentes:
                ocorrencias.append(ocorrencia); existentes.add(chave)
        avisos.extend(gemini_avisos)

    totais = _somar_ocorrencias(ocorrencias)
    codigo = codigo_nome or identificacao_gemini["codigo_ibge"]
    municipio = municipio_nome or identificacao_gemini["municipio"]
    uf = uf_nome or identificacao_gemini["uf"]
    resultado = ResultadoFNDE(
        codigo_ibge=codigo,
        municipio=municipio,
        uf=uf,
        pnae=totais["PNAE"], pnate=totais["PNATE"], pdde=totais["PDDE"], qse=totais["QSE"],
        ocorrencias=ocorrencias,
        avisos=avisos,
    )
    return resultado, texto


def process(caminho_pdf: str | Path, model: str | None = None, enviar_imagens: bool = True) -> tuple[dict[str, float], str, ResultadoFNDE]:
    resultado, texto = extrair_com_gemini(caminho_pdf, model=model, enviar_imagens=enviar_imagens)
    return resultado.valores_planilha(), texto, resultado


def localizar_aba_principal(workbook: Any):
    melhor = workbook.active; pontuacao_melhor = -1
    for ws in workbook.worksheets:
        pontuacao = 0
        for linha in range(1, min(20, ws.max_row) + 1):
            for coluna in range(1, ws.max_column + 1):
                valor = normalizar_texto(ws.cell(linha, coluna).value)
                pontuacao += 10 if "CODIGO IBGE" in valor else 0
                pontuacao += 10 if "ENTE FEDERADO" in valor or "MUNICIPIO" in valor else 0
        if pontuacao > pontuacao_melhor:
            melhor, pontuacao_melhor = ws, pontuacao
    return melhor


def localizar_coluna_ibge(worksheet: Any) -> int:
    for linha in range(1, min(20, worksheet.max_row) + 1):
        for coluna in range(1, worksheet.max_column + 1):
            if "CODIGO IBGE" in normalizar_texto(worksheet.cell(linha, coluna).value):
                return coluna
    raise RuntimeError("A coluna Código IBGE não foi encontrada na planilha.")


def localizar_linha_ibge(worksheet: Any, codigo_ibge: str) -> int:
    coluna = localizar_coluna_ibge(worksheet); procurado = normalizar_codigo_ibge(codigo_ibge)
    for linha in range(1, worksheet.max_row + 1):
        if normalizar_codigo_ibge(worksheet.cell(linha, coluna).value) == procurado:
            return linha
    raise RuntimeError(f"Código IBGE {procurado} não encontrado na planilha.")


def preencher_resultado_na_planilha(caminho_planilha: str | Path, resultado: ResultadoFNDE, caminho_saida: str | Path | None = None, nome_aba: str | None = None) -> Path:
    entrada = Path(caminho_planilha); saida = Path(caminho_saida) if caminho_saida else entrada
    if entrada.resolve() != saida.resolve():
        saida.write_bytes(entrada.read_bytes())
    workbook = load_workbook(saida)
    try:
        ws = workbook[nome_aba] if nome_aba else localizar_aba_principal(workbook)
        linha = localizar_linha_ibge(ws, resultado.codigo_ibge)
        for programa, valor in resultado.valores_planilha().items():
            celula = ws.cell(linha, COLUNAS_FNDE[programa]); celula.value = valor; celula.number_format = '#,##0.00'
        workbook.save(saida)
        return saida
    finally:
        workbook.close()


def processar_pdf_e_preencher_planilha(caminho_pdf: str | Path, caminho_planilha: str | Path, caminho_saida: str | Path | None = None, nome_aba: str | None = None, model: str | None = None) -> ResultadoFNDE:
    _, _, resultado = process(caminho_pdf, model=model, enviar_imagens=True)
    preencher_resultado_na_planilha(caminho_planilha, resultado, caminho_saida, nome_aba)
    return resultado


def processar_varios_pdfs(arquivos_pdf: Iterable[str | Path], caminho_planilha: str | Path, caminho_saida: str | Path | None = None, nome_aba: str | None = None, model: str | None = None) -> tuple[Path, list[ResultadoFNDE], list[dict[str, str]]]:
    entrada = Path(caminho_planilha); saida = Path(caminho_saida) if caminho_saida else entrada
    if entrada.resolve() != saida.resolve(): saida.write_bytes(entrada.read_bytes())
    workbook = load_workbook(saida); resultados = []; erros = []
    try:
        ws = workbook[nome_aba] if nome_aba else localizar_aba_principal(workbook)
        for arquivo in arquivos_pdf:
            try:
                _, _, resultado = process(arquivo, model=model, enviar_imagens=True)
                linha = localizar_linha_ibge(ws, resultado.codigo_ibge)
                for programa, valor in resultado.valores_planilha().items():
                    celula = ws.cell(linha, COLUNAS_FNDE[programa]); celula.value = valor; celula.number_format = '#,##0.00'
                resultados.append(resultado)
            except Exception as erro:
                erros.append({"arquivo": Path(arquivo).name, "erro": str(erro)})
        workbook.save(saida); return saida, resultados, erros
    finally:
        workbook.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai PNAE, PNATE, PDDE e QSE de PDF FNDE.")
    parser.add_argument("pdf"); parser.add_argument("--planilha"); parser.add_argument("--saida"); parser.add_argument("--sem-imagens", action="store_true")
    args = parser.parse_args()
    valores, _, resultado = process(args.pdf, enviar_imagens=not args.sem_imagens)
    print(json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2))
    if args.planilha:
        print(preencher_resultado_na_planilha(args.planilha, resultado, args.saida))


if __name__ == "__main__":
    main()
