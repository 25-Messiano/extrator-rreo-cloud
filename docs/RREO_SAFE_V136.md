# RREO SAFE v1.3.6

Objetivo: impedir que um valor RREO textual correto seja gravado em município, código ou célula errados.

## Cadeia de confiança

1. Leitor A: `pdfplumber` textual.
2. Leitor B independente: `PyMuPDF` por coordenadas, ancorado no cabeçalho `Bimestre (b)`.
3. Divergência A/B bloqueia a planilha; Gemini entra apenas como árbitro da divergência.
4. Município interno do PDF deve coincidir com o município oficial esperado.
5. SHA-256 do PDF identifica exatamente a fonte usada.
6. Fingerprint do resultado identifica IBGE + ano + bimestre + valores.
7. Gravação é transacional por município: snapshot -> gravação -> conferência -> rollback se falhar.
8. Após `workbook.save`, o XLSX é reaberto e as células do lote são conferidas novamente.
9. Se a reconferência do XLSX falhar, o upload da planilha oficial ao Cloud é bloqueado.
10. O LOG_RREO registra SHA-256, fingerprint, leitor secundário, confiança SAFE e pós-gravação.

## Regra operacional

**Se o sistema não consegue provar de onde veio o valor e que o mesmo valor chegou à célula correta, ele não publica a planilha oficial.**

## Render

Não exige variável de ambiente nova. `PyMuPDF` foi adicionado ao `requirements.txt` e será instalado no build Docker. OCR permanece fora do caminho normal do RREO.
