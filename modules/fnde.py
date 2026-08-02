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

from google import genai
from google.genai import types
from openpyxl import load_workbook
from pypdf import PdfReader
import pypdfium2 as pdfium

# Modelo principal e alternativas. A lista evita nova parada caso um modelo
# seja descontinuado pelo provedor.
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
FALLBACK_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash", "gemini-flash-latest")

BASE_DIR = Path(__file__).resolve().parents[1]
REFERENCIAS_DIR = BASE_DIR / "data" / "referencias_fnde"

COLUNAS_FNDE = {
    "PNAE": 20,   # T
    "PNATE": 21,  # U
    "PDDE": 22,   # V
    "QSE": 23,    # W
}

ALIASES_PADRAO = {
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
    "PDDE": [
        "PROGRAMA DINHEIRO DIRETO NA ESCOLA",
        "PDDE",
    ],
    "QSE": [
        "QUOTA ESTADUAL MUNICIPAL",
        "COTA ESTADUAL MUNICIPAL",
        "SALARIO EDUCACAO",
        "QSE",
        "QESE",
    ],
}

EXCLUSOES_PDDE_PADRAO = [
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


def _api_key() -> str:
    chave = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not chave:
        raise RuntimeError(
            "Chave do Gemini não encontrada. Configure GEMINI_API_KEY "
            "ou GOOGLE_API_KEY no Render."
        )
    return chave


def normalizar_texto(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").strip())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9]+", " ", texto.upper())
    return re.sub(r"\s+", " ", texto).strip()


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


def _ler_json(nome: str) -> dict[str, Any]:
    caminho = REFERENCIAS_DIR / nome
    try:
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
        return conteudo if isinstance(conteudo, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _carregar_regras() -> tuple[dict[str, list[str]], list[str]]:
    aliases = {k: list(v) for k, v in ALIASES_PADRAO.items()}
    aliases_json = _ler_json("aliases_programas.json").get("aliases", {})
    for programa in aliases:
        extras = aliases_json.get(programa, []) if isinstance(aliases_json, dict) else []
        aliases[programa].extend(str(x) for x in extras)
        aliases[programa] = sorted(
            {normalizar_texto(x) for x in aliases[programa] if str(x).strip()},
            key=len,
            reverse=True,
        )

    exclusoes = list(EXCLUSOES_PDDE_PADRAO)
    exclusoes_json = _ler_json("palavras_excluir.json").get("excluir_do_pdde", [])
    if isinstance(exclusoes_json, list):
        exclusoes.extend(str(x) for x in exclusoes_json)
    exclusoes_norm = sorted(
        {normalizar_texto(x) for x in exclusoes if str(x).strip()},
        key=len,
        reverse=True,
    )
    return aliases, exclusoes_norm


ALIASES_FNDE, EXCLUSOES_PDDE = _carregar_regras()


def classificar_titulo_programa(titulo: str) -> str | None:
    texto = normalizar_texto(titulo)
    if not texto:
        return None

    # Exclusões prevalecem sobre o alias genérico "PDDE".
    if any(expr in texto for expr in EXCLUSOES_PDDE):
        return None

    # Ordem deliberada: títulos longos antes de siglas.
    for programa in ("PNAE", "PNATE", "PDDE", "QSE"):
        if any(alias in texto for alias in ALIASES_FNDE[programa]):
            return programa
    return None


def extrair_identificacao_nome_pdf(caminho_pdf: str | Path) -> tuple[str, str, str]:
    nome = Path(caminho_pdf).stem
    codigo_match = re.search(r"(?<!\d)(\d{7})(?!\d)", nome)
    codigo = codigo_match.group(1) if codigo_match else ""
    uf_match = re.search(r"[-_/\s]+([A-Z]{2})\s*$", nome.upper())
    uf = uf_match.group(1) if uf_match else ""
    municipio = ""
    if codigo_match:
        municipio = nome[codigo_match.end():]
        municipio = re.sub(r"[-_/\s]+[A-Za-z]{2}\s*$", "", municipio)
        municipio = municipio.strip(" _-/")
    return codigo, municipio, uf


def extrair_texto_paginas(caminho_pdf: str | Path) -> list[str]:
    leitor = PdfReader(str(caminho_pdf))
    paginas: list[str] = []
    for pagina in leitor.pages:
        try:
            paginas.append(pagina.extract_text() or "")
        except Exception:
            paginas.append("")
    return paginas


def extrair_texto_pdf(caminho_pdf: str | Path) -> str:
    return "\n".join(
        f"\n===== PÁGINA {numero} =====\n{texto.strip()}"
        for numero, texto in enumerate(extrair_texto_paginas(caminho_pdf), start=1)
    ).strip()


def _extrair_ocorrencias_texto(paginas: list[str]) -> list[OcorrenciaFNDE]:
    ocorrencias: list[OcorrenciaFNDE] = []
    vistos: set[tuple[str, int, float]] = set()

    # Captura o título imediatamente anterior a "Valor Total R$". A faixa
    # limitada evita atravessar vários blocos quando o texto do PDF é irregular.
    padrao = re.compile(
        r"(?P<titulo>.{5,260}?)\s*-\s*Valor\s+Total\s+R\$\s*"
        r"(?P<valor>\d{1,3}(?:\.\d{3})*,\d{2})",
        re.IGNORECASE | re.DOTALL,
    )

    for numero, pagina in enumerate(paginas, start=1):
        texto = re.sub(r"\r", "", pagina or "")
        for match in padrao.finditer(texto):
            titulo_bruto = match.group("titulo")
            # Mantém somente o trecho depois do último marcador comum de interface.
            titulo_bruto = re.split(
                r"(?:Salvar\s+como\s+PDF|Exibindo\s+de\s+\d+.*?|https?://\S+)",
                titulo_bruto,
                flags=re.IGNORECASE | re.DOTALL,
            )[-1]
            titulo = re.sub(r"\s+", " ", titulo_bruto).strip(" -\n\t")
            programa = classificar_titulo_programa(titulo)
            valor = converter_valor_brasileiro(match.group("valor"))
            if programa is None or valor is None:
                continue
            chave = (programa, numero, valor)
            if chave in vistos:
                continue
            vistos.add(chave)
            ocorrencias.append(
                OcorrenciaFNDE(
                    programa=programa,
                    titulo=titulo,
                    valor=valor,
                    pagina=numero,
                    justificativa="Valor Total extraído diretamente do bloco textual do PDF.",
                )
            )
    return ocorrencias


def renderizar_paginas_png(
    caminho_pdf: str | Path,
    escala: float = 1.6,
    limite_paginas: int = 20,
) -> list[tuple[int, bytes]]:
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
            imagem.close()
            bitmap.close()
            pagina.close()
    finally:
        documento.close()
    return imagens


def _schema_gemini() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "codigo_ibge": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "municipio": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "uf": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "ocorrencias": {
                "type": "array",
                "items": {
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
                },
            },
            "avisos": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["codigo_ibge", "municipio", "uf", "ocorrencias", "avisos"],
        "additionalProperties": False,
    }


def _resumo_aliases() -> str:
    return "\n".join(f"- {p}: {', '.join(v)}" for p, v in ALIASES_FNDE.items())


def _prompt_fnde(nome: str, codigo: str, municipio: str, uf: str, texto: str) -> str:
    return f"""
Você extrai valores de demonstrativos FNDE/SIGEFWEB.

ARQUIVO: {nome}
CÓDIGO IBGE DO NOME: {codigo or 'não identificado'}
MUNICÍPIO DO NOME: {municipio or 'não identificado'}
UF DO NOME: {uf or 'não identificada'}

Retorne uma ocorrência para cada bloco válido de PNAE, PNATE, PDDE e QSE.
Use EXCLUSIVAMENTE o número mostrado em "Valor Total R$" no título do bloco.
Não some as linhas de esfera ao total do título.

REGRAS CRÍTICAS:
- PNAE: somente Alimentação Escolar.
- PNATE: somente Apoio ao Transporte do Escolar.
- PDDE: somente "PROGRAMA DINHEIRO DIRETO NA ESCOLA".
- Nunca classifique como PDDE: {', '.join(EXCLUSOES_PDDE)}.
- QSE: somente QUOTA/COTA ESTADUAL MUNICIPAL, SALÁRIO-EDUCAÇÃO, QSE ou QESE.
- Não inclua PNLD nem programas alheios.
- Preserve o título real do bloco em cada ocorrência.
- Se não houver programa, não crie ocorrência.

ALIASES ACEITOS:
{_resumo_aliases()}

TEXTO EXTRAÍDO (pode estar vazio ou imperfeito):
---
{texto[:120000]}
---
""".strip()


def _modelos_candidatos(model: str | None) -> list[str]:
    candidatos = [model or DEFAULT_MODEL, *FALLBACK_MODELS]
    return list(dict.fromkeys(m.strip() for m in candidatos if m and m.strip()))


def _chamar_gemini(caminho_pdf: Path, texto_pdf: str, model: str | None) -> dict[str, Any]:
    codigo, municipio, uf = extrair_identificacao_nome_pdf(caminho_pdf)
    conteudo: list[Any] = [_prompt_fnde(caminho_pdf.name, codigo, municipio, uf, texto_pdf)]
    for pagina, png in renderizar_paginas_png(caminho_pdf):
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
                analisado = getattr(resposta, "parsed", None)
                return analisado if isinstance(analisado, dict) else json.loads(resposta.text or "{}")
            except Exception as erro:
                ultimo_erro = erro
                mensagem = str(erro).upper()
                # Tenta o próximo modelo apenas em erro de modelo indisponível.
                if "404" in mensagem or "NOT_FOUND" in mensagem or "MODEL" in mensagem:
                    continue
                raise
    finally:
        cliente.close()
    raise RuntimeError(f"Nenhum modelo Gemini disponível. Último erro: {ultimo_erro}")


def _validar_ocorrencias(itens: Iterable[dict[str, Any] | OcorrenciaFNDE]) -> tuple[list[OcorrenciaFNDE], list[str]]:
    validas: list[OcorrenciaFNDE] = []
    avisos: list[str] = []
    vistos: set[tuple[str, str, int | None, float]] = set()

    for item in itens:
        if isinstance(item, OcorrenciaFNDE):
            ocorrencia = item
        else:
            valor = converter_valor_brasileiro(item.get("valor"))
            if valor is None:
                continue
            ocorrencia = OcorrenciaFNDE(
                programa=str(item.get("programa") or "").upper(),
                titulo=str(item.get("titulo") or "").strip(),
                valor=valor,
                pagina=int(item["pagina"]) if item.get("pagina") is not None else None,
                justificativa=str(item.get("justificativa") or "").strip(),
            )

        programa_real = classificar_titulo_programa(ocorrencia.titulo)
        if programa_real is None:
            avisos.append(f"Bloco descartado: {ocorrencia.titulo or 'sem título'}.")
            continue
        if ocorrencia.programa and ocorrencia.programa != programa_real:
            avisos.append(
                f"Classificação corrigida de {ocorrencia.programa} para {programa_real}: "
                f"{ocorrencia.titulo}."
            )
        ocorrencia.programa = programa_real
        chave = (
            programa_real,
            normalizar_texto(ocorrencia.titulo),
            ocorrencia.pagina,
            round(ocorrencia.valor, 2),
        )
        if chave in vistos:
            continue
        vistos.add(chave)
        validas.append(ocorrencia)
    return validas, avisos


def _resultado_de_ocorrencias(
    identificacao: tuple[str, str, str],
    ocorrencias: list[OcorrenciaFNDE],
    avisos: list[str] | None = None,
) -> ResultadoFNDE:
    totais = {"PNAE": 0.0, "PNATE": 0.0, "PDDE": 0.0, "QSE": 0.0}
    for item in ocorrencias:
        totais[item.programa] += item.valor
    codigo, municipio, uf = identificacao
    return ResultadoFNDE(
        codigo_ibge=codigo,
        municipio=municipio,
        uf=uf,
        pnae=round(totais["PNAE"], 2),
        pnate=round(totais["PNATE"], 2),
        pdde=round(totais["PDDE"], 2),
        qse=round(totais["QSE"], 2),
        ocorrencias=ocorrencias,
        avisos=list(avisos or []),
    )


def extrair_com_gemini(
    caminho_pdf: str | Path,
    model: str | None = None,
    enviar_imagens: bool = True,
) -> tuple[ResultadoFNDE, str]:
    caminho = Path(caminho_pdf)
    identificacao = extrair_identificacao_nome_pdf(caminho)
    paginas = extrair_texto_paginas(caminho)
    texto_pdf = "\n".join(paginas)

    # Primeira escolha: extração determinística do PDF digital.
    ocorrencias_texto = _extrair_ocorrencias_texto(paginas)
    validas_texto, avisos_texto = _validar_ocorrencias(ocorrencias_texto)
    programas_texto = {x.programa for x in validas_texto}

    # Se todos os quatro programas foram encontrados no texto, não há motivo
    # para chamar IA. Isto reduz custo e aumenta a precisão.
    if programas_texto == {"PNAE", "PNATE", "PDDE", "QSE"}:
        return _resultado_de_ocorrencias(identificacao, validas_texto, avisos_texto), texto_pdf

    # PDFs de imagem ou texto incompleto seguem para o Gemini multimodal.
    bruto = _chamar_gemini(caminho, texto_pdf, model)
    validas_gemini, avisos_gemini = _validar_ocorrencias(bruto.get("ocorrencias", []) or [])

    # Combina resultados sem duplicar. O texto digital tem precedência por ser
    # uma leitura determinística do próprio documento.
    combinadas, avisos_combinacao = _validar_ocorrencias([*validas_texto, *validas_gemini])
    avisos = [*avisos_texto, *avisos_gemini, *avisos_combinacao]
    avisos.extend(str(x) for x in (bruto.get("avisos") or []) if str(x).strip())

    resultado = _resultado_de_ocorrencias(identificacao, combinadas, avisos)
    if not resultado.ocorrencias:
        raise RuntimeError("Nenhum bloco FNDE válido foi identificado no PDF.")
    return resultado, texto_pdf


def process(
    caminho_pdf: str | Path,
    model: str | None = None,
    enviar_imagens: bool = True,
) -> tuple[dict[str, float], str, ResultadoFNDE]:
    resultado, texto = extrair_com_gemini(caminho_pdf, model=model, enviar_imagens=enviar_imagens)
    return resultado.valores_planilha(), texto, resultado


def localizar_aba_principal(workbook: Any):
    melhor = workbook.active
    melhor_pontuacao = -1
    for worksheet in workbook.worksheets:
        pontuacao = 0
        for linha in range(1, min(20, worksheet.max_row) + 1):
            for coluna in range(1, worksheet.max_column + 1):
                valor = normalizar_texto(worksheet.cell(linha, coluna).value)
                if "CODIGO IBGE" in valor:
                    pontuacao += 10
                if "ENTE FEDERADO" in valor or "MUNICIPIO" in valor:
                    pontuacao += 10
                if any(x in valor for x in ("PNAE", "PNATE", "PDDE", "QSE", "QESE")):
                    pontuacao += 2
        if pontuacao > melhor_pontuacao:
            melhor, melhor_pontuacao = worksheet, pontuacao
    return melhor


def localizar_coluna_ibge(worksheet: Any) -> int:
    for linha in range(1, min(20, worksheet.max_row) + 1):
        for coluna in range(1, worksheet.max_column + 1):
            if "CODIGO IBGE" in normalizar_texto(worksheet.cell(linha, coluna).value):
                return coluna
    raise RuntimeError("A coluna 'Código IBGE' não foi encontrada na planilha.")


def localizar_linha_ibge(worksheet: Any, codigo_ibge: str) -> int:
    coluna = localizar_coluna_ibge(worksheet)
    procurado = normalizar_codigo_ibge(codigo_ibge)
    for linha in range(1, worksheet.max_row + 1):
        if normalizar_codigo_ibge(worksheet.cell(linha, coluna).value) == procurado:
            return linha
    raise RuntimeError(f"Código IBGE {procurado} não encontrado na planilha.")


def preencher_resultado_na_planilha(
    caminho_planilha: str | Path,
    resultado: ResultadoFNDE,
    caminho_saida: str | Path | None = None,
    nome_aba: str | None = None,
) -> Path:
    entrada = Path(caminho_planilha)
    saida = Path(caminho_saida) if caminho_saida else entrada
    if entrada.resolve() != saida.resolve():
        saida.write_bytes(entrada.read_bytes())
    workbook = load_workbook(saida)
    try:
        worksheet = workbook[nome_aba] if nome_aba else localizar_aba_principal(workbook)
        linha = localizar_linha_ibge(worksheet, resultado.codigo_ibge)
        for programa, valor in resultado.valores_planilha().items():
            celula = worksheet.cell(linha, COLUNAS_FNDE[programa])
            celula.value = valor
            celula.number_format = '#,##0.00'
        workbook.save(saida)
        return saida
    finally:
        workbook.close()


def processar_pdf_e_preencher_planilha(
    caminho_pdf: str | Path,
    caminho_planilha: str | Path,
    caminho_saida: str | Path | None = None,
    nome_aba: str | None = None,
    model: str | None = None,
) -> ResultadoFNDE:
    _, _, resultado = process(caminho_pdf, model=model, enviar_imagens=True)
    preencher_resultado_na_planilha(caminho_planilha, resultado, caminho_saida, nome_aba)
    return resultado


def processar_varios_pdfs(
    arquivos_pdf: Iterable[str | Path],
    caminho_planilha: str | Path,
    caminho_saida: str | Path | None = None,
    nome_aba: str | None = None,
    model: str | None = None,
) -> tuple[Path, list[ResultadoFNDE], list[dict[str, str]]]:
    entrada = Path(caminho_planilha)
    saida = Path(caminho_saida) if caminho_saida else entrada
    if entrada.resolve() != saida.resolve():
        saida.write_bytes(entrada.read_bytes())
    workbook = load_workbook(saida)
    resultados: list[ResultadoFNDE] = []
    erros: list[dict[str, str]] = []
    try:
        worksheet = workbook[nome_aba] if nome_aba else localizar_aba_principal(workbook)
        for arquivo in arquivos_pdf:
            try:
                _, _, resultado = process(arquivo, model=model, enviar_imagens=True)
                linha = localizar_linha_ibge(worksheet, resultado.codigo_ibge)
                for programa, valor in resultado.valores_planilha().items():
                    worksheet.cell(linha, COLUNAS_FNDE[programa]).value = valor
                resultados.append(resultado)
            except Exception as erro:
                erros.append({"arquivo": Path(arquivo).name, "erro": str(erro)})
        workbook.save(saida)
        return saida, resultados, erros
    finally:
        workbook.close()


def _formatar_brl(valor: float) -> str:
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrai PNAE, PNATE, PDDE e QSE do FNDE.")
    parser.add_argument("pdf")
    parser.add_argument("--planilha")
    parser.add_argument("--saida")
    args = parser.parse_args()
    valores, _, resultado = process(args.pdf)
    print(json.dumps(resultado.como_dict(), ensure_ascii=False, indent=2))
    for programa in ("PNAE", "PNATE", "PDDE", "QSE"):
        print(f"{programa}: R$ {_formatar_brl(valores[programa])}")
    if args.planilha:
        print(preencher_resultado_na_planilha(args.planilha, resultado, args.saida))


if __name__ == "__main__":
    main()
