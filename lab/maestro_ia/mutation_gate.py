from __future__ import annotations

"""Mutation smoke gate: prova que uma inversão perigosa no consenso é detectada.
Não modifica os arquivos do projeto; executa um mutante em memória.
"""

import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from core.maestro_ia.validators import compare_values


def original_gate() -> bool:
    return compare_values({"1.1": 10.0}, {"1.1": 11.0})["ok"] is False


def dangerous_mutant(primary, secondary):
    result = compare_values(primary, secondary)
    # Mutação proposital: inverte a decisão de validação.
    result["ok"] = not result["ok"]
    return result


def main() -> int:
    assert original_gate(), "Baseline inválida"
    mutant_survived = dangerous_mutant({"1.1": 10.0}, {"1.1": 11.0})["ok"] is False
    if mutant_survived:
        print("MUTATION_GATE=FAIL: mutante sobreviveu")
        return 2
    print("MUTATION_GATE=PASS: mutante perigoso foi morto pelo contrato de teste")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
