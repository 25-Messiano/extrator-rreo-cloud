from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.maestro_ia.models import ExtractionCase, SupervisorDecision


def create_patch_candidate(base_dir: str, case: ExtractionCase, decision: SupervisorDecision, *, diagnosis: str) -> Path:
    """Cria somente uma PROPOSTA. Nunca aplica patch e nunca toca no Git/produção."""
    root = Path(base_dir)
    root.mkdir(parents=True, exist_ok=True)
    patch_id = f"PATCH_CANDIDATO_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
    path = root / f"{patch_id}.json"
    payload = {
        "patch_id": patch_id,
        "status": "AGUARDANDO_HOMOLOGACAO_E_APROVACAO_HUMANA",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case": case.to_dict(),
        "decision": decision.to_dict(),
        "diagnosis": diagnosis,
        "code_change": None,
        "can_apply_automatically": False,
        "requires_user_approval": True,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
