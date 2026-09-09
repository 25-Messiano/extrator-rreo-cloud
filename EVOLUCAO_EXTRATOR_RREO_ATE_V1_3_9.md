# Evolucao do EXTRATOR RREO CLOUD ate a V1.3.9

## 1. O problema que revelou a necessidade de mudar a arquitetura
A verificacao manual de Agua Branca/PB mostrou que uma auditoria auxiliar havia associado ao codigo 1.4 o valor da linha seguinte. O numero era valido, mas pertencia a outro item. Isso demonstrou que concordancia entre dois leitores nao basta quando ambos compartilham a mesma regra de associacao.

## 2. V1.3.7.2 — validacao estrutural
Foi acrescentada verificacao independente de relacoes contabeis, como 2.1.1 + 2.1.2 = 2.1, para impedir que uma concordancia equivocada entre leitores seja tratada como validacao suficiente.

## 3. V1.3.7.3 — um .py por codigo
A extracao foi dividida em 15 modulos exclusivos. Cada modulo reconhece somente o seu codigo e isola o bloco ate o proximo codigo numerico. Isso impede, por exemplo, que 1.4 invada a linha 2-. Tambem foram separados os papeis de coluna: PREVISAO ATUALIZADA (a) e reconhecida mas bloqueada; RECEITAS REALIZADAS (b) e a unica autorizada.

## 4. V1.3.7.4 — destino separado da extracao
O Excel deixou de ser responsabilidade dos extratores. Foram criados modulos de destino independentes, orientados pelo cabecalho real da planilha. O mapa homologado ficou: E=2.1.1, F=2.1.2, H=2.3, J=2.4, K=2.2, L=2.5, N=6.1.1, O=6.2.1, P=1.1, Q=1.4, R=1.2, S=1.3, T=2.6. 2.1 e 6.2 nao ganham coluna inventada.

## 5. V1.3.8 — JSON como contrato entre camadas
A comunicacao deixou de depender de passagem informal de dicionarios. O fluxo passou a registrar JSON de identidade, extracao, validacao e destino. Isso permite auditoria, reexecucao de destino sem reler PDF e separacao clara de responsabilidades.

## 6. Identificacao tolerante
A identificacao do municipio passou a harmonizar nome externo do PDF, nome interno, Ente Federado da planilha e UF. O IBGE nao e exigido no PDF. Ele e recuperado da planilha depois que a linha candidata e identificada e passa a confirmar o vinculo.

## 7. V1.3.8.1 — colunas estruturais A-D
A=Nº/sequencial geral; B=sequencial de municipios dentro da UF; C=Codigo IBGE; D=Ente Federado. Essas quatro colunas passam a ser a fundacao estrutural. Se falharem, nenhuma implantacao financeira e permitida.

## 8. Mapeamento central .py + JSON
Foi criado um contrato central de configuracao para relacionar estrutura A-D, coluna (a), coluna (b), codigos RREO e destinos Excel. Exemplo homologado: Araci/BA, linha 235, codigo 1.3 -> coluna S -> celula S235.

## 9. V1.3.9 — integracao final
A V1.3.9 une tudo e remove uma fragilidade restante: o destino nao tenta identificar novamente o municipio por IBGE. A identidade resolve a linha nominalmente; A-D confirmam a linha; o cabecalho confirma a coluna; o codigo confirma o destino. Assim ha uma unica identidade e multiplas verificacoes independentes.

Outra evolucao: quando o nome externo do PDF coincide exatamente e de forma unica com o Ente Federado dentro da mesma UF, essa correspondencia e aceita como primaria. O nome interno continua sendo auditado, mas uma abreviacao interna nao reduz artificialmente a confianca. Se o nome interno apontar fortemente para outro municipio, o registro e bloqueado por conflito.

## 10. Principio final
Nenhuma camada faz duas funcoes criticas ao mesmo tempo:
- identidade nao extrai valor;
- extrator nao escolhe celula;
- validador nao grava;
- destino nao le PDF;
- gravador nao decide identidade.

O sistema trabalha em modo fail-closed: diante de duvida, nao grava.
