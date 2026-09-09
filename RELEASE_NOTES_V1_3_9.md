# EXTRATOR RREO CLOUD V1.3.9 — SAFE INTEGRATED MAPPING

## Objetivo
Consolidar em uma unica versao a evolucao iniciada apos a deteccao do erro de associacao de linha/coluna, separando de forma rigida:
1. estrutura da planilha;
2. identidade do municipio;
3. extracao PDF;
4. validacao;
5. mapeamento de destino;
6. implantacao Excel.

## Contrato oficial de fluxo
A-D estrutural -> identificacao tolerante -> JSON identidade -> .py exclusivos dos codigos -> coluna (a) bloqueada -> coluna (b) autorizada -> JSON extracao -> SAFE -> JSON validado -> cabecalho real -> JSON destino -> Excel -> JSON implantacao.

## Evolucoes principais
- A, B, C e D viram preflight obrigatorio; falha = bloqueio de implantacao.
- Nome externo exato e unico dentro da UF tem prioridade de identidade; IBGE nao e exigido no PDF.
- Nome interno confirma/audita. Conflito forte com outro municipio bloqueia a identidade.
- IBGE e lido da coluna C apenas depois da harmonizacao nominal e passa a confirmar a linha.
- Cada codigo RREO continua com .py exclusivo de extracao.
- PREVISAO ATUALIZADA (a) permanece reconhecida e proibida.
- RECEITAS REALIZADAS Ate o Bimestre (b) e a unica coluna monetaria autorizada.
- O destino e resolvido pelo cabecalho real da planilha com fronteira numerica exata; 2.1 nao casa 2.1.1.
- 2.1 e 6.2 permanecem validadores estruturais sem destino Excel.
- O destino nao relocaliza municipio pelo IBGE: usa a linha da identidade e valida A-D antes de escrever.
- Extração nunca escreve Excel; destino nunca le PDF; JSON e o contrato entre camadas.

## Destinos oficiais
2.1.1=E; 2.1.2=F; 2.3=H; 2.4=J; 2.2=K; 2.5=L; 6.1.1=N; 6.2.1=O; 1.1=P; 1.4=Q; 1.2=R; 1.3=S; 2.6=T.

## Homologacao
- pytest: 92/92.
- Planilha modelo: PLANILHA_PRONTA; 5570 municipios; 0 erros A-D.
- Araci/BA: linha 235, IBGE 2902104, 1.3 -> S235.
- Paraiba: 223/223 PDFs identificados por nome externo exato dentro da UF na prova nominal.
- Agua Branca/PB: 1.4=1458429.92; destino Q2582; FPM 2.1.1+2.1.2=2.1.

## Politica de seguranca operacional
A versao e fail-closed: ambiguidade, conflito de identidade, mudanca de cabecalho, IBGE estrutural invalido, A/B ausentes, codigo sem destino ou tentativa de escrever em coluna proibida interrompem a implantacao daquele registro.
