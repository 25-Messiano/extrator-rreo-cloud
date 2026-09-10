from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.maestro_ia.memory import OperationalMemory
from core.maestro_ia.models import ExtractionCase
from core.maestro_ia.orchestrator import MaestroOrchestrator
CASES=Path(__file__).with_name("cases.jsonl")
RESULT=Path(__file__).with_name("results") / "latest.json"


def main():
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    memory=OperationalMemory(str(RESULT.parent/"eval_memory.sqlite3"))
    agent=MaestroOrchestrator(memory=memory)
    results=[]; failures=0
    for line in CASES.read_text(encoding="utf-8").splitlines():
        spec=json.loads(line)
        case=ExtractionCase(case_id=spec["id"],source="RREO",year=2025,uf="BA",ibge="2900001",
                            municipality="Teste",operation="EVAL",status=spec["status"],
                            verification_ok=spec["verification_ok"],values={"1.1":100.0})
        out=agent.handle(case)
        ok=out.supervisor.decision==spec["expect"]
        failures += 0 if ok else 1
        results.append({"id":spec["id"],"decision":out.supervisor.decision,"expect":spec["expect"],"ok":ok})
    RESULT.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"cases":len(results),"failures":failures,"result":str(RESULT)},ensure_ascii=False))
    return 1 if failures else 0
if __name__=="__main__": raise SystemExit(main())
