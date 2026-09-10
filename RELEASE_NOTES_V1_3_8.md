# V1.3.8 — JSON PIPELINE + TOLERANT IDENTITY

## Arquitetura oficial
PDF -> harmonizacao nominal -> JSON identidade -> modulos exclusivos por codigo -> JSON extracao -> validacao deterministica -> JSON validacao -> JSON destino -> executor Excel.

## Identificacao municipal
- Nome externo + nome interno + Ente Federado da planilha + UF.
- IBGE NAO e requisito para reconhecer o PDF.
- O IBGE e capturado da planilha somente depois da harmonizacao e fica registrado como confirmacao da linha.
- Similaridade minima e margem de ambiguidade continuam configuraveis.

## Separacao de responsabilidades
- Extratores de PDF nao gravam Excel.
- Modulos de destino nao leem PDF.
- JSON e a fronteira oficial entre leitura, validacao e implantacao.
- PREVISAO ATUALIZADA (a) continua registrada e proibida para gravacao.
- RECEITAS REALIZADAS Ate o Bimestre (b) e a unica coluna monetaria autorizada.

## Destinos do modelo oficial
2.1.1=E; 2.1.2=F; 2.3=H; 2.4=J; 2.2=K; 2.5=L; 6.1.1=N; 6.2.1=O; 1.1=P; 1.4=Q; 1.2=R; 1.3=S; 2.6=T.
2.1 e 6.2 sao validacao somente.

## IA
- Gemini permanece integrado.
- OpenAI foi preparada como revisora opcional via OPENAI_API_KEY e Responses API.
- IA e consultiva: nao escreve Excel e nao substitui a validacao deterministica.
