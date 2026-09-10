# Auditoria técnica — EXTRATOR RREO CLOUD v1.3.7.2

## Diagnóstico

O caso Água Branca/PB foi reproduzido com o pacote v1.3.7.1 real e o motor LIVE extrai corretamente:
- 1.4 = 1.458.429,92
- 2.1 = 25.889.148,95

Portanto, o valor 30.087.736,26 atribuído ao código 1.4 na planilha anterior não foi produzido pelo motor v1.3.7.1 real; entrou em uma extração/auditoria auxiliar externa ao fluxo LIVE.

## Risco identificado

Mesmo com dois leitores independentes, uma arquitetura baseada apenas em concordância numérica pode aceitar erro correlacionado se ambos associarem a mesma linha errada.

## Correções v1.3.7.2

1. Prova estrutural: 1.1 + 1.2 + 1.3 + 1.4 deve fechar com a linha total 1.
2. Prova estrutural: 2.1.1 + 2.1.2 deve fechar com 2.1.
3. Validação de rótulo semântico para 1.1–1.4 e 2.1–2.6.
4. Falha estrutural/semântica bloqueia a gravação oficial.
5. Registro SAFE grava divergências estruturais e semânticas.
6. Checkpoint schema elevado para impedir retomada de resultados antigos após mudança do motor.
7. PDF real de Água Branca/PB adicionado como regressão permanente.
8. Teste sintético garante bloqueio quando dois leitores concordam no mesmo valor errado.

## Validação

- scripts/validate_project.py: OK
- pytest: 78 passed
- Água Branca/PB 1.4: 1.458.429,92
- Água Branca/PB 2.1: 25.889.148,95
