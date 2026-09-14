# TESOURARIA APLB — V1 Operacional

## Entregue nesta versão
- PostgreSQL Cloud por `DATABASE_URL`, com SQLite apenas como fallback local.
- Login com senha hash PBKDF2 e perfis de acesso.
- Registro de acessos e webhook opcional para aviso ao programador.
- Lançamentos manuais, Banco/Caixa, Entrada/Saída e transferência Banco → Caixa.
- Correção com motivo obrigatório, estorno e trilha de auditoria.
- Códigos APLB, grupos/subgrupos DRE e vínculos com vigência.
- Cadastros em janelas flutuantes para códigos, grupos, favorecidos, contas e patrimônio.
- Importação de extratos XLSX/XLS/CSV; PDF textual com parser conservador.
- Classificação automática inicial por regras/similaridade.
- Conferência humana com exportação Excel e JSON antes da liberação.
- Bloqueio de duplicidade por fingerprint.
- Conciliação manual assistida.
- Fluxo de caixa realizado e projetado.
- Pesquisa avançada combinando período, B/C, natureza, código, status, texto e valor.
- DRE calculado a partir de vínculos Código APLB → Grupo DRE.
- Fechamento mensal, bloqueio de período e reabertura auditada.
- Snapshot de recuperação estrutural em JSON.

## Ainda depende de configuração externa ou refinamento
- Cloud Storage para documentos, comprovantes, backups e anexos.
- IA externa avançada para interpretar extratos PDF complexos/escaneados.
- Reprodução visual exata dos 19 modelos históricos; o motor de dados está pronto, mas o mapeamento oficial de códigos ainda será refinado.
- Canal definitivo de notificação do programador: configurar `PROGRAMADOR_ALERT_WEBHOOK_URL`.

## Variáveis do Render
Obrigatórias para produção:
- `APP_ENV=production`
- `DATABASE_URL=<Internal Database URL do PostgreSQL>`
- `TESOURARIA_ADMIN_PASSWORD=<segredo>`
- `SECRET_KEY=<segredo>`

Opcionais:
- `PROGRAMADOR_ALERT_WEBHOOK_URL=<webhook>`
- `CLOUD_BACKUP_BUCKET=<destino cloud>`
- `OPENAI_API_KEY=<quando a IA externa for ativada>`

## Dashboard V2
- Cards de Saldo Banco, Caixa, Total, Entradas, Saídas e Resultado do mês.
- Seletor de exercício/mês.
- Ações rápidas para lançamento, extrato, conferência, fluxo e relatórios.
- Indicadores de conferência, conciliação, rascunhos e importações.
- Série gráfica dos últimos seis meses.
- Fluxo projetado e alerta de saldo negativo.
- Lançamentos recentes.
- Saúde do PostgreSQL/SQLite, fechamento do período e cadastros ativos.

## V4 - cancelamento lógico
- Status `CANCELADO` exclui o lançamento de saldos, Dashboard, DRE e relatórios oficiais.
- O registro continua visível na pesquisa e permanece integralmente na auditoria.
- A tela Correção / Estorno agora possui a aba Cancelar, com motivo obrigatório e confirmação.
- A migração V4 cancela automaticamente o lançamento de homologação de R$ 35,00 de 06/09/2026, apenas quando todos os campos conhecidos conferem.

## V5 - Relatório Movimento Financeiro Mensal Oficial
- Exportação PDF e Excel no padrão visual dos demonstrativos consolidados APLB.
- Campos: Dia, Código, C/B, Especificação, Entrada/Banco, Saída/Banco, Entrada/Caixa, Saída/Caixa e Saldo C/B.
- Saldos Banco/Caixa inicial e final, saldo geral e totais por coluna.
- CANCELADO não entra no relatório nem nos saldos.
- Para 01/02/03 de 2026, se a base continuar exatamente igual à carga consolidada, o PDF original é devolvido diretamente, garantindo fidelidade integral do documento de referência.
- Excel é editável e reproduz cores, estrutura, quebras e formatação do modelo.
