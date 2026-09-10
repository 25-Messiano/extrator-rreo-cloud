# V1.3.7.3 — RREO Exclusive Field Engine

## Princípio
Cada um dos 15 códigos RREO possui um arquivo Python exclusivo. O código da linha e o papel da coluna são representados por tipos diferentes (`RowCode` e `ColumnRole`).

## Colunas monetárias
- `PREVISAO_ATUALIZADA_A`: reconhecida apenas para diagnóstico. `COLLECT=False`, `WRITE_TO_EXCEL=False`.
- `RECEITAS_REALIZADAS_B`: única coluna coletável e gravável.

## Isolamento da linha
O bloco de cada código termina no próximo código numérico, inclusive totais inteiros (`2-`, `3-`, etc.). Assim `1.4` não consegue alcançar a linha `2-`.

## Excel oficial
IBGE = coluna C. Ente Federado = D. O IBGE determina a linha municipal. O nome externo do PDF + UF continua sendo chave operacional; o conteúdo interno serve à auditoria.

Destinos existentes: 1.1=P, 1.4=Q, 1.2=R, 1.3=S, 2.1.1=E, 2.1.2=F, 2.3=H, 2.4=J, 2.2=K, 2.5=L, 2.6=T, 6.1.1=N, 6.2.1=O.

`2.1` e `6.2` são extraídos e preservados como prova estrutural, mas a planilha-base não tem coluna oficial para eles. Portanto não é inventada nenhuma célula de destino.
