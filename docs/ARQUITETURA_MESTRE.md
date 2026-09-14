# TESOURARIA APLB — Arquitetura Mestre

## Fonte única de verdade
Todos os relatórios derivam dos lançamentos oficiais.

## Fluxo de importação
Extrato PDF/Excel → leitura → normalização → regras/IA → arquivo de conferência Excel + JSON → revisão humana → liberação → base oficial.

## Segurança
- login e senha com hash;
- perfis de acesso;
- auditoria;
- notificação ao programador/responsável a cada login bem-sucedido;
- alertas de tentativas suspeitas;
- senha nunca é enviada em notificações.

## Códigos e grupos
- códigos APLB cadastráveis pela interface;
- grupos e subgrupos DRE cadastráveis;
- múltiplos códigos por grupo;
- grupos podem existir sem códigos;
- vínculos com vigência;
- alteração histórica controlada;
- telas com modais/janelas flutuantes para criar, editar, desativar e vincular.

## Correção e estorno
Nenhuma correção apaga o histórico. Toda mudança gera auditoria.

## Fluxo de caixa
### Realizado
Derivado dos lançamentos oficiais.

### Projetado
Cadastro de previsões futuras com data, valor, código, natureza, recorrência, probabilidade e comparação projetado x realizado.

## Patrimônio
Cadastro de bens permanentes, com vínculo opcional ao lançamento financeiro de origem.

## Cloud
- PostgreSQL Cloud para dados;
- Cloud Storage para documentos e backups;
- backup mestre automático com pasta ATUAL e HISTORICO;
- JSONs de conferência e snapshots de fechamento.
