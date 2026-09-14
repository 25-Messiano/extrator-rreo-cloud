# V25.9 — Importação em lote por PDF

## Objetivo
Permitir atualização de meses posteriores sem digitação linha a linha, preservando a conferência humana e o isolamento por tesouraria.

## Novas entradas
- `37 Importar Movimento PDF`: aceita vários demonstrativos mensais Banco/Caixa em PDF.
- `38 Importar Extratos PDF`: aceita vários extratos bancários em PDF para uma mesma competência/conta.

## Segurança
Nenhum PDF grava diretamente na base oficial. O fluxo é PDF -> prévia -> lote -> Conferência -> liberação -> base oficial. Hash de arquivo impede reimportação acidental do mesmo arquivo e o motor existente marca duplicado exato/possível duplicidade por lançamento.

## Parser de movimento
O parser é conservador e foi desenhado para o modelo mensal APLB com Data, Código, B/C, Especificação, Entrada Banco, Saída Banco, Entrada Caixa, Saída Caixa e Saldo. Linhas ambíguas não são inventadas. A prévia deve ser comparada ao PDF antes da criação do lote.

## Extratos
A leitura reaproveita o motor já existente, com IA quando configurada e regras locais como fallback. Depois da Conferência, os extratos seguem para Conciliação.
