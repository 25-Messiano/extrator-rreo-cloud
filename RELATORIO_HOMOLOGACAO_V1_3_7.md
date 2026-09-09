# Homologacao tecnica — v1.3.7 RREO SAFE

Data: 2026-09-08

## Objetivo

Endurecer a identidade municipal sem alterar o motor financeiro que vinha apresentando concordancia integral entre os dois leitores independentes.

## Correcoes aplicadas

1. Removida a identificacao por substring em todo o texto.
2. Identidade agora vem de cabecalho explicito com UF.
3. Contracoes como d'Oeste/DOESTE, d'Agua/DAGUA e d'Arca/DARCA sao canonicalizadas de forma deterministica.
4. Variantes e nomes historicos so sao aceitos por tabela de aliases controlados.
5. IA nao pode liberar nome apenas por similaridade; precisa resolver para nome canonico/alias controlado.
6. Adicionada verificacao de cobertura de lote estadual: municipios esperados x PDFs encontrados.
7. Mantidas dupla leitura pdfplumber + PyMuPDF, hash, fingerprint, rollback e verificacao pos-XLSX da v1.3.6.

## Testes automatizados

- 74 testes pytest aprovados.
- `scripts/validate_project.py`: aprovado.
- `compileall`: aprovado.

## Smoke test com PDFs reais problemáticos

10/10 casos reais aprovados, incluindo:
- Itapejara d'Oeste/PR sem confundir com Tapejara.
- Perola d'Oeste/PR sem confundir com Perola.
- Rancho Alegre d'Oeste/PR sem confundir com Rancho Alegre.
- Boa Saude/RN reconhecida a partir de Januario Cicco.
- Campo Grande/RN reconhecida a partir de Augusto Severo.
- Arez/RN a partir de Ares.
- Assu/RN a partir de Acu.
- Chiapeta/RS a partir de Chiapetta.
- Itatiba do Sul/RS sem confundir com Itati.
- Itajai/SC sem confundir com Ita.

## Regra fail-closed

Se o cabecalho nao resolver de forma inequivoca por nome canonico ou alias controlado, o municipio permanece bloqueado para conferencia. Nenhum fuzzy solto autoriza gravacao.
