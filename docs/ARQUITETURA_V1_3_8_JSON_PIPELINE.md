# Arquitetura V1.3.8 — JSON Pipeline + Tolerant Identity

## 1. Identidade
A identificação inicial NÃO exige IBGE no PDF.

Fontes combinadas, nesta ordem lógica:
1. UF restringe o universo de candidatos.
2. Nome externo do arquivo.
3. Nome interno/cabeçalho do PDF.
4. Ente Federado da planilha.
5. Alias/tolerância nominal.
6. Após o match, captura-se o IBGE e a linha da planilha como confirmação.

Status possíveis: EXATO, ALTA_CONFIANCA, TOLERANCIA_VALIDADA, AMBIGUO, PENDENTE_CONFERENCIA.

## 2. Extração
Cada código RREO tem seu próprio módulo .py. O módulo de PREVISÃO (a) é diagnóstico/proibido; o módulo RECEITAS REALIZADAS (b) é a única fonte monetária autorizada.

## 3. JSONs oficiais
- *.identidade.json — evidência de harmonização municipal.
- *.extracao.json — valores + bloco de evidência por código.
- *.validacao.json — travas semânticas/estruturais.
- *.destino.json — células e cabeçalhos exatos onde os valores podem ser implantados.

## 4. Excel
Extrator não importa/escreve Excel. Executor de destino não lê PDF. A gravação só ocorre com VALIDADO_SAFE_JSON e confere novamente aba/cabeçalho/célula.

## 5. IA
Gemini e OpenAI são revisores consultivos opcionais. Mesmo quando concordam, não substituem as travas determinísticas e não têm permissão para escrever no Excel.
