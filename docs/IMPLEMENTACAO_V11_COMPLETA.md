# TESOURARIA APLB — V11 Implantação Completa

V11 consolida V10 e fecha os módulos administrativos/operacionais: contas e saldos iniciais, centros de custo, patrimônio com histórico, fechamento com diagnóstico, permissões individuais, auditoria exportável, backup completo diário e Cloud opcional, monitoramento e conciliação automática/revisão manual.

## Regra estrutural
A tabela `lancamentos` permanece como base financeira oficial. Relatórios, saldos, DRE, fluxo, conciliação e fechamento derivam dela. Nenhum relatório possui base contábil paralela.

## Segurança
Extratos nunca gravam diretamente na base oficial: importação -> conferência -> liberação. Cancelamentos permanecem auditados e fora dos resultados oficiais.
