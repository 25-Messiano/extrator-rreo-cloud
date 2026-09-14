# TESOURARIA APLB V25.2 - Isolamento integral entre unidades

## Objetivo
A V25.2 corrige vazamentos de leitura e operacao entre a CENTRAL, o AMBIENTE DE TESTE e as tesourarias filiadas. O codigo-base continua unico e compartilhado, mas todo dado operacional fica restrito a sua `tesouraria_id`.

## Diagnostico do banco de producao antes da correcao
A auditoria somente leitura no PostgreSQL do Render confirmou que a migracao para ARACI-01 foi concluida no banco: CENTRAL e TESTE nao possuem lancamentos, contas, saldos iniciais, importacoes, patrimonio, centros de custo ou fechamentos; ARACI-01 concentra os dados migrados. Logo, os valores que apareciam no TESTE eram causados por consultas sem filtro de tesouraria, nao por dados gravados indevidamente no TESTE.

## Correcoes principais
- Dashboard e indicadores operacionais agora filtram a unidade ativa.
- Conciliacao manual e automatica respeitam a tesouraria ativa.
- Importacoes, itens de conferencia e reprocessamento validam o proprietario do lote.
- Favorecidos e centros de custo passam a pertencer a uma tesouraria.
- Patrimonio, saldos iniciais, fechamentos, fluxo projetado, monitoramento e auditoria operam por unidade.
- Correcao, cancelamento e estorno rejeitam lancamento de outra tesouraria.
- Contas e referencias usadas em novos lancamentos sao validadas contra a unidade ativa.
- TESTE nao pode alterar Codigos/DRE ou Configuracoes globais; esses cadastros sao compartilhados pelo codigo-base.
- Nova pagina Central `Diagnostico de Isolamento` mostra a matriz de registros por unidade e alerta sobre orfaos ou movimento indevido na CENTRAL.

## Regra arquitetural
A CENTRAL nao e uma unidade financeira. Ela administra, audita e acompanha as filiadas. O AMBIENTE DE TESTE pode ter dados proprios de teste, mas nunca deve ler ou alterar dados de producao. Cada filial possui seus proprios registros operacionais. Codigos/DRE e a estrutura do aplicativo permanecem globais e compartilhados, de modo que uma nova versao do sistema vale para todas as unidades.

## Compatibilidade e migracao
A migracao V25 ja realizada permanece preservada. A V25.2 nao move novamente os registros de ARACI-01. A inicializacao legada so pode carregar dados historicos enquanto o marcador de migracao V25 nao estiver concluido.

## Testes
A suite completa foi executada em banco SQLite novo e isolado: 39 testes aprovados. Inclui teste de isolamento que cria dados em uma filial, troca para TESTE e confirma que Dashboard, lancamentos, favorecidos, centros, patrimonio, saldos, importacoes e monitoramento nao exibem os dados da filial.
