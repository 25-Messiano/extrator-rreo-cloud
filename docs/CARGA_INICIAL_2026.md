# Carga Inicial Consolidada 2026

Esta versão do TESOURARIA APLB incorpora automaticamente, uma única vez, os lançamentos consolidados dos arquivos:

- `01_2026.pdf` - Janeiro/2026
- `02_2026.pdf` - Fevereiro/2026
- `03_2026.pdf` - Março/2026

## Regra de implantação

No primeiro bootstrap da aplicação em um banco que ainda não possua a carga `CARGA_PDF_2026`, o sistema cria os saldos de abertura de janeiro e grava todos os movimentos como lançamentos oficiais `APROVADO`, com origem `CARGA_PDF_2026`.

A carga é atômica e idempotente: abrir ou reiniciar o aplicativo não duplica os dados.

Cada lançamento recebe um registro técnico em `carga_inicial_itens`, preservando arquivo de origem, página, sequência e saldo exibido após o movimento. Isso permite auditoria e reconstrução sem poluir os campos visíveis do lançamento.

## Saldos de abertura

- Banco em 01/01/2026: R$ 181,46
- Caixa em 01/01/2026: R$ 13.777,09
- Total inicial: R$ 13.958,55

Os saldos de abertura ficam na tabela `saldos_iniciais`. Eles compõem o saldo acumulado, mas não são tratados como receita do mês.

## Validação contra os PDFs

| Competência | Movimentos | Entrada Banco | Saída Banco | Entrada Caixa | Saída Caixa | Saldo final |
|---|---:|---:|---:|---:|---:|---:|
| 01/2026 | 87 | 157.286,59 | 145.878,71 | 19.859,14 | 16.809,27 | 28.416,30 |
| 02/2026 | 90 | 159.401,33 | 146.970,40 | 15.700,00 | 15.715,67 | 40.831,56 |
| 03/2026 | 104 | 165.027,98 | 160.261,00 | 19.800,00 | 19.953,80 | 45.444,74 |

Total de movimentos carregados: **281**.

Os números de linhas exibidos nos PDFs (88, 91 e 105) correspondem aos movimentos mais a linha de saldo de abertura apresentada no demonstrativo.

## Competência x data

Os lançamentos preservam a data escrita no PDF. A competência mensal vem do arquivo consolidado (`2026-01`, `2026-02`, `2026-03`) e é usada pelos indicadores mensais.

Foram preservadas duas linhas do arquivo de fevereiro que trazem data de janeiro no próprio documento. Elas continuam com a data original, mas pertencem à competência `2026-02`, evitando alterar silenciosamente o documento-fonte e mantendo os totais mensais consolidados.

## Códigos

Os códigos já existentes no catálogo são reutilizados. Códigos usados nos PDFs que ainda não existiam na estrutura inicial são criados automaticamente. Quando a descrição não estava consolidada na relação oficial disponível, ela foi marcada explicitamente como pendente de consolidação, sem inventar classificação DRE.

O vínculo Código APLB -> Grupo DRE continua administrável pela interface e poderá ser refinado depois, como previsto na arquitetura do projeto.
