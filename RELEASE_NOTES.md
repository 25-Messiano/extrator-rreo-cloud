# Entrega inicial

- Novo nome: `extrator-rreo-cloud`.
- Armazenamento exclusivo no Google Cloud Storage.
- Entrada principal na raiz: `app.py`.
- Página `4_Arquivos_Cloud.py` para listar PDFs e planilhas processadas.
- Extração RREO com Gemini e fallback local corrigido para ler o segundo valor monetário da linha.
- Planilha-base incluída em `data/`.
- Dockerfile e `render.yaml` prontos para novo serviço no Render.
- Script de validação em `scripts/validate_project.py`.
## Extração visual FNDE + logs separados

- Gemini Vision passa a ser a leitura principal dos PDFs FNDE em imagem.
- OCR local Tesseract (por+eng) atua como fallback.
- Repetição automática e troca de modelo Gemini.
- Progresso incremental e checkpoints configuráveis.
- Abas LOG_FNDE e LOG_RREO separadas.
- Abas AUDITORIA e MUNICIPIOS_NAO_ENCONTRADOS preservadas.
- Modelo padrão atualizado para gemini-3.6-flash.

