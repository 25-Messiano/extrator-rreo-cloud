from __future__ import annotations
from difflib import SequenceMatcher
from sqlalchemy import select

from database.db import session_scope
from services.tenancy import get_active_tesouraria_id
from models.entities import CodigoAPLB


def _norm(s: str) -> str:
    return " ".join((s or "").upper().strip().split())


def sugerir_codigo(historico: str, favorecido: str = "") -> tuple[int | None, str, float]:
    """Classificador determinístico inicial. A camada IA poderá substituir/complementar sem gravar direto."""
    alvo = _norm(f"{historico} {favorecido}")
    with session_scope() as s:
        codigos = s.scalars(select(CodigoAPLB).where(CodigoAPLB.ativo.is_(True), CodigoAPLB.tesouraria_id==get_active_tesouraria_id())).all()
        best = (None, "", 0.0)
        for c in codigos:
            desc = _norm(c.descricao)
            tokens = [t for t in desc.split() if len(t) >= 4]
            hits = sum(1 for t in tokens if t in alvo)
            token_score = hits / max(1, len(tokens))
            seq = SequenceMatcher(None, desc, alvo).ratio()
            score = max(token_score, seq * 0.55)
            # regras fortes comuns
            if "UNIMED" in alvo and "SAUDE" in desc.replace("Ú", "U"):
                score = max(score, 0.97)
            if "COELBA" in alvo and "COELBA" in desc:
                score = max(score, 0.99)
            if "EMBASA" in alvo and "EMBASA" in desc:
                score = max(score, 0.99)
            if "TARIFA" in alvo and "TARIFA" in desc:
                score = max(score, 0.98)
            if score > best[2]:
                best = (c.id, c.codigo, float(min(score, 0.99)))
        return best
