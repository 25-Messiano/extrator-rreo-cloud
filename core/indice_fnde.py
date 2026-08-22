from __future__ import annotations

from typing import Any, Iterable

from core.identificacao_arquivos import (
    codigo_ibge_no_texto,
    identificar_municipio,
    normalizar_codigo_ibge,
)


def codigo_ibge_do_nome(name: str) -> str:
    return codigo_ibge_no_texto(name)


def build_fnde_index(
    files: Iterable[dict[str, Any]],
    uf: str = "",
    municipios: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Indexa FNDE por IBGE com fallback seguro por nome + UF.

    Quando o filename contem IBGE, ele tem prioridade absoluta. Se o codigo
    nao existir no nome, a associacao tenta municipio oficial normalizado e,
    por ultimo, similaridade alta sem aceitar ambiguidades.
    """
    por_ibge: dict[str, dict[str, Any]] = {}
    duplicados: list[dict[str, Any]] = []
    invalidos: list[dict[str, Any]] = []
    lista_municipios = list(municipios or [])
    uf_norm = str(uf or "").upper().strip()

    for item in files:
        nome = str(item.get("name") or "")
        code = codigo_ibge_do_nome(nome)
        metodo = "IBGE"
        confianca = 1.0
        municipio_nome = ""

        if not code and lista_municipios:
            resultado = identificar_municipio(nome, lista_municipios, uf_norm)
            if resultado.identificado and not resultado.ambiguo:
                code = normalizar_codigo_ibge(resultado.codigo_ibge)
                metodo = resultado.metodo
                confianca = resultado.confianca
                municipio_nome = resultado.municipio
            elif resultado.ambiguo:
                invalidos.append({
                    "arquivo": nome,
                    "motivo": "MUNICIPIO_AMBIGUO",
                    "confianca": resultado.confianca,
                })
                continue

        if not code:
            invalidos.append({"arquivo": nome, "motivo": "MUNICIPIO_NAO_IDENTIFICADO"})
            continue

        enriched = dict(item)
        enriched.update({
            "codigo_ibge": code,
            "uf": uf_norm,
            "municipio_arquivo": municipio_nome,
            "metodo_identificacao": metodo,
            "confianca_identificacao": confianca,
        })

        if code in por_ibge:
            # Mantem a versao mais recente quando ha duplicidade de upload.
            atual = por_ibge[code]
            atual_updated = atual.get("updated")
            novo_updated = item.get("updated")
            usar_novo = bool(novo_updated and (not atual_updated or novo_updated > atual_updated))
            duplicados.append({
                "codigo_ibge": code,
                "primeiro": atual.get("name"),
                "duplicado": nome,
                "mantido": nome if usar_novo else atual.get("name"),
            })
            if usar_novo:
                por_ibge[code] = enriched
            continue
        por_ibge[code] = enriched

    return {
        "por_ibge": por_ibge,
        "duplicados": duplicados,
        "invalidos": invalidos,
        "total": len(por_ibge),
    }
