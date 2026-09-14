# TESOURARIA APLB — V15 Fechamento Mensal

A V15 homologa o fechamento por **competência contábil**, e não apenas pela data física do movimento.

## Regras
- Pré-fechamento mostra quantidade, entradas, saídas e resultado da competência.
- Importações em conferência, itens de extrato pendentes e lançamentos RASCUNHO/EM_CONFERENCIA bloqueiam o fechamento.
- Movimentos bancários não conciliados geram alerta explícito para revisão.
- Fechamento grava snapshot com totais, saldos e status anterior de cada lançamento.
- APROVADO/CONCILIADO passam para FECHADO.
- Competência fechada bloqueia novos lançamentos, correções, cancelamentos e estornos.
- Reabertura exige motivo, gera auditoria e restaura APROVADO/CONCILIADO conforme o snapshot.
- Lançamentos antigos sem competência continuam usando o mês da data como fallback.

## Segurança
Nenhum dado é apagado no fechamento ou na reabertura. O processo é auditável e reversível.
