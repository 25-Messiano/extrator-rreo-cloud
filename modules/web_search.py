from __future__ import annotations

from urllib.parse import quote_plus
from urllib.request import Request, urlopen
import json

from config.storage import GOOGLE_CSE_API_KEY, GOOGLE_CSE_CX


def _fallback(consulta: str, aviso: str):
    return {
        "modo": "externo",
        "google_url": f"https://www.google.com/search?q={quote_plus(consulta)}",
        "resultados": [],
        "aviso": aviso,
    }


def pesquisar_web(consulta: str, limite: int = 8):
    consulta = consulta.strip()
    if not consulta:
        raise ValueError("Informe um termo para pesquisar.")

    if not (GOOGLE_CSE_API_KEY and GOOGLE_CSE_CX):
        return _fallback(
            consulta,
            "A pesquisa integrada não está configurada. Abra a consulta diretamente no Google.",
        )

    endpoint = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={quote_plus(GOOGLE_CSE_API_KEY)}&cx={quote_plus(GOOGLE_CSE_CX)}"
        f"&q={quote_plus(consulta)}&num={max(1, min(limite, 10))}&safe=active"
    )
    req = Request(endpoint, headers={"User-Agent": "Calendario-Messiano/1.0"})
    try:
        with urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return _fallback(
            consulta,
            "A pesquisa integrada está indisponível no momento. Abra a consulta diretamente no Google.",
        )

    resultados = [
        {
            "titulo": x.get("title", ""),
            "link": x.get("link", ""),
            "resumo": x.get("snippet", ""),
            "fonte": x.get("displayLink", ""),
        }
        for x in data.get("items", [])
    ]
    return {
        "modo": "integrado",
        "google_url": f"https://www.google.com/search?q={quote_plus(consulta)}",
        "resultados": resultados,
    }
