from __future__ import annotations

import json
import os
import re
from typing import Any

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

DESCRICOES_RREO = {
    "1.1": "Receita Resultante do Imposto sobre a Propriedade Predial e Territorial Urbana - IPTU",
    "1.2": "Receita Resultante do Imposto sobre Transmissão Inter Vivos - ITBI",
    "1.3": "Receita Resultante do Imposto sobre Serviços de Qualquer Natureza - ISS",
    "1.4": "Receita Resultante do Imposto de Renda Retido na Fonte - IRRF",
    "2.1": "Cota-Parte FPM",
    "2.1.1": "Parcela referente à Constituição Federal, art. 159, I, alínea b",
    "2.1.2": "Parcela referente à Constituição Federal, art. 159, I, alíneas d e e",
    "2.2": "Cota-Parte ICMS",
    "2.3": "Cota-Parte IPI-Exportação",
    "2.4": "Cota-Parte ITR",
    "2.5": "Cota-Parte IPVA",
    "2.6": "Cota-Parte IOF-Ouro",
    "6.1.1": "FUNDEB - Impostos e Transferências de Impostos - Principal",
    "6.2": "FUNDEB - Complementação da União - VAAF",
    "6.2.1": "FUNDEB - Complementação da União - VAAF - Principal",
}


def _api_key() -> str:
    key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip()

    if not key:
        raise RuntimeError(
            "Chave do Gemini não encontrada. Configure GEMINI_API_KEY "
            "ou GOOGLE_API_KEY no ambiente do Render."
        )

    return key


def _schema(codigos: list[str]) -> dict[str, Any]:
    properties: dict[str, Any] = {}

    for codigo in codigos:
        properties[codigo] = {
            "anyOf": [
                {"type": "number"},
                {"type": "null"},
            ],
            "description": (
                "Valor da coluna RECEITAS REALIZADAS Até o Bimestre (b) "
                f"para a linha {codigo}."
            ),
        }

    return {
        "type": "object",
        "properties": properties,
        "required": codigos,
        "additionalProperties": False,
    }


def _montar_prompt(texto_pdf: str, codigos: list[str]) -> str:
    linhas = "\n".join(
        f"- {codigo}: {DESCRICOES_RREO.get(codigo, 'linha identificada pelo código')}"
        for codigo in codigos
    )

    return f"""
Você é um extrator especializado no Demonstrativo das Receitas e Despesas
com Manutenção e Desenvolvimento do Ensino do RREO municipal.

Leia o texto integral da tabela antes de escolher qualquer valor.

REGRAS OBRIGATÓRIAS:
1. Para cada código, localize a LINHA COMPLETA da tabela.
2. Confirme ao mesmo tempo o código e a descrição da linha.
3. A tabela normalmente possui duas colunas monetárias:
   - PREVISÃO ATUALIZADA (a)
   - RECEITAS REALIZADAS Até o Bimestre (b)
4. Retorne SOMENTE o valor da coluna \"RECEITAS REALIZADAS Até o Bimestre (b)\",
   que normalmente é o segundo valor monetário da linha.
5. Não use valores da coluna \"PREVISÃO ATUALIZADA (a)\".
6. Não use números encontrados em fórmulas, notas, cabeçalhos, totais ou outras linhas.
7. Para o código 1.1, somente aceite a linha cuja descrição seja a receita
   resultante do IPTU. Não confunda com totais, percentuais ou referências
   ao código 1.1 em fórmulas.
8. Se a linha não puder ser confirmada com segurança, retorne null.
9. Converta números brasileiros para número decimal:
   \"1.234.567,89\" deve ser 1234567.89.

LINHAS A EXTRAIR:
{linhas}

TEXTO EXTRAÍDO DO PDF:
--- INÍCIO DO TEXTO ---
{texto_pdf}
--- FIM DO TEXTO ---
""".strip()


def _normalizar_resultado(
    raw: dict[str, Any],
    codigos: list[str],
) -> dict[str, float | None]:
    resultado: dict[str, float | None] = {}

    for codigo in codigos:
        valor = raw.get(codigo)

        if valor is None or valor == "":
            resultado[codigo] = None
            continue

        if isinstance(valor, (int, float)):
            resultado[codigo] = float(valor)
            continue

        texto = str(valor).strip()
        texto = re.sub(r"[^\d,.\-]", "", texto)

        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")

        try:
            resultado[codigo] = float(texto)
        except ValueError:
            resultado[codigo] = None

    return resultado


def extract_rreo_values(
    texto_pdf: str,
    codigos: list[str],
    model: str | None = None,
) -> dict[str, float | None]:
    """Extrai os valores da coluna (b) usando leitura contextual pelo Gemini."""
    if not texto_pdf or not texto_pdf.strip():
        return {codigo: None for codigo in codigos}

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("Biblioteca google-genai não instalada.") from exc

    client = genai.Client(api_key=_api_key())

    try:
        response = client.models.generate_content(
            model=model or DEFAULT_MODEL,
            contents=_montar_prompt(texto_pdf, codigos),
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_json_schema=_schema(codigos),
            ),
        )

        parsed = getattr(response, "parsed", None)

        if isinstance(parsed, dict):
            raw = parsed
        else:
            raw = json.loads(response.text or "{}")

        return _normalizar_resultado(raw, codigos)

    finally:
        client.close()
