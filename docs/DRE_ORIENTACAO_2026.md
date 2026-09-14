# DRE - orientação por código e conteúdo (2026)

Esta versão introduz um motor de regras DRE com prioridade sobre vínculos simples Código -> Grupo.
O objetivo é permitir que um mesmo código seja classificado de modo diferente quando o histórico/especificação indicar naturezas distintas.

## Grupo 2.4.12 - Outros Serviços de Terceiros (Especificar)

A composição foi calibrada contra os Relatórios de Execução Financeira consolidados de janeiro, fevereiro e março de 2026.

### Janeiro/2026 - R$ 109.094,56
- 0803: R$ 108.069,56
- 0021: R$ 385,00
- 0008: R$ 410,00 (somente serviços esporádicos/manutenção identificados por regra)
- 0916: R$ 230,00 (somente serviços prestados identificados por regra)

### Fevereiro/2026 - R$ 108.120,65
- 0803: R$ 107.780,65
- 0012: R$ 340,00 (somente serviço de lavagem/estofados; seguro do veículo permanece fora desta regra)

### Março/2026 - R$ 110.121,69
- 0803: R$ 106.724,69
- 0021: R$ 100,00
- 0501: R$ 350,00 (serviço extraordinário de limpeza)
- 0014: R$ 42,00
- 0916: R$ 2.905,00 (serviços prestados identificados por regra)

## Regra operacional

O arquivo `data/dre_regras.csv` guarda regras de classificação com prioridade, código e expressão de conteúdo.
A classificação por regra ocorre antes do vínculo genérico Código -> Grupo, evitando dupla contagem.
A interface DRE permite selecionar um grupo e visualizar exatamente quais lançamentos o compõem.

Isso permite manter a orientação para meses futuros sem reescrever os lançamentos históricos.

## V7 - Relatório de Execução Financeira oficial
- O menu Relatórios / DRE passa a oferecer o modelo oficial em PDF e Excel.
- Horizonte de seleção: 2026 a 2050.
- A base de lançamentos permanece a fonte operacional única.
- Janeiro, fevereiro e março de 2026 formam a matriz de calibração oficial dos grupos contábeis.
- O motor admite que um mesmo código apareça em grupos diferentes conforme a especificação.
- O motor também deve admitir rateio de um único lançamento entre dois grupos (ex.: aquisição mista de móveis e equipamentos).
- CANCELADO não participa de DRE, saldos ou relatórios oficiais.
