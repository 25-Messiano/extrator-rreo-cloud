# Extrator RREO Cloud

Aplicativo Streamlit para processar PDFs municipais do RREO armazenados no Google Cloud Storage, extrair a coluna **Receitas Realizadas Até o Bimestre (b)**, preencher a planilha-base e salvar o resultado no próprio Cloud Storage.

## Arquitetura

- `app.py`: página inicial.
- `pages/1_Painel.py`: processamento por município ou estado.
- `pages/4_Arquivos_Cloud.py`: consulta de PDFs e resultados no bucket.
- `integrations/google_storage.py`: única integração de armazenamento.
- `integrations/gemini.py`: interpretação contextual das linhas da tabela.
- `modules/rreo.py`: extração do texto e fallback local.
- `data/RREO-TCM+FNDE PLANILHA BASE.xlsx`: planilha-base.

## Variáveis obrigatórias

- `GOOGLE_SERVICE_ACCOUNT_JSON`: JSON completo da conta de serviço. `GCP_KEY` também é aceito como nome alternativo.
- `GOOGLE_STORAGE_BUCKET`: nome do bucket. Padrão: `maestro-rreo-arquivos`.
- `GEMINI_API_KEY`: chave da Gemini API.
- `GEMINI_MODEL`: padrão `gemini-2.5-flash`.

A conta de serviço precisa de permissão para listar, ler, criar e atualizar objetos no bucket.

## Estrutura esperada no bucket

```text
ARQUIVO_DE_ESTADOS_RREO/
├── PDF - DOS MUNICIPIOS/
│   ├── AC/
│   ├── BA/
│   └── ...
└── PLANILHAS_PROCESSADAS/
    ├── AC/
    ├── BA/
    └── ...
```

## Execução local

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Validação antes do deploy

```bash
python -m compileall .
python scripts/validate_project.py
```

## Deploy no Render

1. Crie um repositório chamado `extrator-rreo-cloud`.
2. Envie todo o conteúdo deste pacote para a raiz do repositório.
3. Crie um novo Blueprint no Render usando `render.yaml`.
4. Cadastre `GOOGLE_SERVICE_ACCOUNT_JSON` e `GEMINI_API_KEY` como secrets.
5. Aguarde o health check `/_stcore/health`.

O projeto não usa Google Drive, OAuth ou Refresh Token.
