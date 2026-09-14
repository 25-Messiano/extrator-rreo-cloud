# TESOURARIA APLB V13 - Operação limpa + reprocessamento IA

## Objetivos

1. Lançamentos CANCELADOS deixam de aparecer em toda a operação normal.
2. CANCELADOS permanecem apenas na Auditoria, sem exclusão física do histórico.
3. A tela Correção/Estorno/Cancelamento não exibe JSON técnico e mostra ficha financeira limpa.
4. Importações legadas sem competência ou conta bancária são arquivadas tecnicamente e ocultadas da operação normal.
5. Lotes válidos já existentes podem ser reprocessados pela OpenAI sem reenviar o PDF.
6. O reprocessamento altera somente itens pendentes/corrigíveis e preserva decisões humanas já tomadas.
7. A IA continua sem autorização para lançar na base oficial; duplicidade continua sendo decisão determinística.
8. Classificação IA é executada em lotes menores para reduzir timeout e melhorar estabilidade.
9. APIs Streamlit antigas `use_container_width` foram migradas para `width`.

## Fluxo operacional

06 Extratos -> 07 IA/Reprocessamento -> 08 Conferência humana -> Base oficial -> 09 Conciliação.

## Segurança

- Data, valor e natureza do extrato não são alterados pela classificação IA.
- Duplicado exato é bloqueado.
- Possível duplicidade exige conferência.
- Confiança abaixo de 80% gera alerta.
- Lançamentos cancelados não compõem saldos, DRE ou relatórios e ficam somente na Auditoria.
