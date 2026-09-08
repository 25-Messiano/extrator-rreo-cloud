# v1.3.6 — RREO SAFE

Versão de segurança do motor RREO textual.

- Segundo leitor realmente independente: PyMuPDF por geometria.
- Âncora semântica na coluna `Bimestre (b)`; não depende apenas de "segundo número".
- Bloqueio de município externo x conteúdo divergente.
- SHA-256 do PDF e fingerprint do resultado.
- Transação por município com rollback.
- Conferência imediata PDF -> célula.
- Reabertura do XLSX após salvar e conferência antes de upload ao Cloud.
- Upload oficial bloqueado quando a persistência não confere.
- LOG_RREO ampliado com evidências SAFE.
- IA somente como árbitro de divergências.
- OCR não participa do fluxo normal RREO.

Base: v1.3.5.2. As rotinas FNDE, Central de Correções, Download em Lote e MAESTRO IA permanecem preservadas.
