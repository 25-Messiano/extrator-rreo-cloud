# Revisao Brasil Completo - 2026-08-19

## Objetivo
Garantir que RREO + FNDE em "Todos os Estados" percorra a matriz nacional completa, preserve o Excel e nao seja bloqueado indefinidamente por um unico municipio/PDF.

## Correcoes aplicadas
- Execucao nacional baseada explicitamente nas 27 UFs oficiais, e nao apenas nas pastas encontradas no Cloud.
- Estado sem pasta RREO/FNDE continua na fila e gera registro de ausencia, em vez de desaparecer silenciosamente.
- Brasilia/DF passa a ser carregada como entrada municipal com codigo IBGE 5300108; a linha agregada Distrito Federal/DF nao entra na fila municipal.
- Timeout de lote configuravel: timeout_lote_segundos=420 (maximo configuravel 1800s).
- Timeout aplicado aos fluxos combinado, somente RREO e somente FNDE.
- Google Cloud Storage: listagem, download e upload com timeout defensivo padrao de 120s (GCS_TIMEOUT_SECONDS).
- OCR Tesseract com timeout padrao de 90s por chamada (TESSERACT_TIMEOUT_SECONDS).
- Excel parcial criado/disponibilizado logo apos preparar a planilha e salvo novamente ao final de cada lote.
- fnde_todos_estados ativado.
- Campo de configuracao do timeout de lote adicionado a tela Configuracoes.

## Validacoes executadas
- scripts/validate_project.py: OK.
- pytest: 4 testes aprovados.
- Compilacao dos modulos alterados: OK.
- Matriz da planilha: 27 UFs com pelo menos uma entrada processavel apos o tratamento de Brasilia; 5.571 entradas processaveis na fila nacional.
- Teste de timeout confirma que uma tarefa lenta e marcada como erro/timeout sem impedir o retorno do lote.

## Limite desta validacao
O ambiente de revisao nao possui GOOGLE_SERVICE_ACCOUNT_JSON/GCP_KEY nem GEMINI_API_KEY/GOOGLE_API_KEY. Por isso nao foi possivel executar uma varredura real dos PDFs do bucket nem chamadas reais ao Gemini. A validacao remota deve ser feita no Render com as credenciais ja configuradas.
