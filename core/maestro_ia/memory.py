from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from core.maestro_ia.models import ExtractionCase, MaestroOutcome


class OperationalMemory:
    """Memória operacional auditável. Não altera código e não publica resultados."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with closing(self._connect()) as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    uf TEXT NOT NULL,
                    ibge TEXT NOT NULL,
                    municipality TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    memory_action TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS strategies (
                    signature TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    successes INTEGER NOT NULL DEFAULT 0,
                    failures INTEGER NOT NULL DEFAULT 0,
                    avg_confidence REAL NOT NULL DEFAULT 0,
                    last_payload_json TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            conn.commit()

    @staticmethod
    def signature(case: ExtractionCase) -> str:
        tokens = [case.source, case.uf, case.operation, case.status]
        if case.error:
            normalized = " ".join(case.error.upper().split())[:180]
            tokens.append(normalized)
        return "|".join(tokens)

    def remember_case(self, case: ExtractionCase) -> None:
        safe = case.to_dict()
        metadata = dict(safe.get("metadata") or {})
        evidence = str(metadata.pop("document_text", "") or "")
        if evidence:
            metadata["evidence_excerpt"] = evidence[:2000]
            metadata["evidence_chars"] = len(evidence)
        safe["metadata"] = metadata
        payload = json.dumps(safe, ensure_ascii=False, sort_keys=True)
        with closing(self._connect()) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO cases
                (case_id, created_at, source, year, uf, ibge, municipality, status, error, payload_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (case.case_id, case.created_at, case.source, case.year, case.uf, case.ibge,
                 case.municipality, case.status, case.error, payload),
            )
            conn.commit()

    def remember_outcome(self, outcome: MaestroOutcome) -> None:
        payload = json.dumps(outcome.to_dict(), ensure_ascii=False, sort_keys=True)
        with closing(self._connect()) as conn:
            conn.execute(
                """INSERT INTO outcomes(case_id, decision, confidence, memory_action, payload_json)
                VALUES (?, ?, ?, ?, ?)""",
                (outcome.case.case_id, outcome.supervisor.decision,
                 outcome.supervisor.confidence, outcome.memory_action, payload),
            )
            conn.commit()

    def recommend_strategy(self, case: ExtractionCase) -> dict[str, Any] | None:
        signature = self.signature(case)
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM strategies WHERE signature=?", (signature,)).fetchone()
        return dict(row) if row else None

    def learn_strategy(self, case: ExtractionCase, strategy: str, confidence: float, success: bool, payload: dict[str, Any]) -> None:
        if not strategy:
            return
        signature = self.signature(case)
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM strategies WHERE signature=?", (signature,)).fetchone()
            if row:
                successes = int(row["successes"]) + (1 if success else 0)
                failures = int(row["failures"]) + (0 if success else 1)
                total = successes + failures
                previous_avg = float(row["avg_confidence"])
                new_avg = ((previous_avg * (total - 1)) + confidence) / max(total, 1)
                conn.execute(
                    """UPDATE strategies SET strategy=?, successes=?, failures=?, avg_confidence=?,
                    last_payload_json=?, updated_at=CURRENT_TIMESTAMP WHERE signature=?""",
                    (strategy, successes, failures, new_avg,
                     json.dumps(payload, ensure_ascii=False, sort_keys=True), signature),
                )
            else:
                conn.execute(
                    """INSERT INTO strategies(signature, source, strategy, successes, failures, avg_confidence, last_payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (signature, case.source, strategy, 1 if success else 0, 0 if success else 1,
                     confidence, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
                )
            conn.commit()

    def summary(self) -> dict[str, int]:
        with closing(self._connect()) as conn:
            cases = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0])
            outcomes = int(conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0])
            strategies = int(conn.execute("SELECT COUNT(*) FROM strategies").fetchone()[0])
        return {"cases": cases, "outcomes": outcomes, "strategies": strategies}
