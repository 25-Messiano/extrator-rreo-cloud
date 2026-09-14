# TESOURARIA APLB V14 — Conciliação objetiva + Backup/Recuperação

## Conciliação Bancária

Regra principal aprovada: **Data + Entrada/Saída + Valor**.

- A conta bancária também é aplicada quando selecionada.
- Se existir um único lançamento oficial com a mesma data, natureza e valor, ele é conciliável.
- Se houver mais de um candidato, descrição, favorecido e documento são usados somente para desempate.
- Caso permaneça ambíguo, fica para conferência humana.
- A conciliação nunca cria lançamento automaticamente.
- A IA permanece auxiliar e não é autoridade para conciliação.
- Linhas “Saldo Anterior/Saldo Inicial” são `MOVIMENTO_TECNICO` e não participam de entradas/saídas.
- O painel compara também os totais mensais e diários de Entradas Banco e Saídas Banco entre extrato e base oficial.

## Backup e Recuperação

O pacote V14 inclui todas as tabelas operacionais: lançamentos, extratos, itens de conferência, conciliações, auditoria, usuários, códigos, DRE, favorecidos, contas, centros de custo, patrimônio, fechamentos, configurações e logs.

Cada backup é um ZIP com:
- `backup.json`;
- `manifest.json`;
- SHA-256 interno;
- contagem por tabela;
- total de registros;
- instrução de recuperação quando disponível.

A tela permite:
- gerar backup manual;
- baixar pacote;
- validar integridade;
- simular restauração em SQLite isolado sem tocar na produção;
- restauração real protegida pela frase `RESTAURAR PRODUCAO`.

O backup automático diário continua ativo. O envio externo automático é suportado para S3/R2/objeto compatível quando as variáveis `CLOUD_BACKUP_*` forem configuradas. O disco efêmero do serviço Render não deve ser tratado como cofre permanente.
