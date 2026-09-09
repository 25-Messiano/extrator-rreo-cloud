from __future__ import annotations
import re
import unicodedata

COLUNA = "D"
PAPEL = "NOME_OFICIAL_UF"


def normalizar_nome(valor) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).upper()
    texto = re.sub(r"[^A-Z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def separar_uf(valor) -> tuple[str, str]:
    s = str(valor or "").strip()
    m = re.search(r"/([A-Za-z]{2})\s*$", s)
    uf = m.group(1).upper() if m else ""
    nome = re.sub(r"/[A-Za-z]{2}\s*$", "", s).strip()
    return nome, uf


def validar(valor) -> dict:
    nome, uf = separar_uf(valor)
    ok = bool(nome) and len(uf) == 2
    return {
        "coluna": COLUNA,
        "papel": PAPEL,
        "valor": valor,
        "nome": nome,
        "uf": uf,
        "nome_normalizado": normalizar_nome(nome),
        "ok": ok,
    }
