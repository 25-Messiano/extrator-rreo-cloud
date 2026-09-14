# V20 — Resumos oficiais em PDF e Excel

Implementação consolidada dos cinco modelos homologados pelo usuário:

1. Resumo Geral — Banco.
2. Resumo Geral — Caixa.
3. Resumo Geral — Banco e Caixa.
4. Suprimento de Caixa (código 0801).
5. Saldos Históricos Banco / Caixa / Banco + Caixa.

## Regras

- Toda apuração vem exclusivamente dos lançamentos oficiais `APROVADO`, `CONCILIADO` ou `FECHADO`.
- A competência contábil tem prioridade sobre a data física do lançamento.
- CANCELADO não participa.
- PDF e Excel usam a mesma apuração.
- Resumos por código mostram 1º e 2º semestre e conservam códigos sem movimento com zero quando pertencem à natureza correspondente do catálogo.
- Cada resumo executa uma conferência automática: soma por códigos × base oficial mês a mês.
- Suprimento de Caixa confronta `0801 / Banco / SAÍDA` com `0801 / Caixa / ENTRADA`; divergência é explicitamente sinalizada.
- Saldos históricos são recalculados pela base oficial para o intervalo de anos escolhido.

## Segurança contábil

Nenhum relatório grava ou altera lançamentos. O módulo é somente leitura.
