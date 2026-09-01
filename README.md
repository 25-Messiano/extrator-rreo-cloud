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
- `GEMINI_MODEL`: padrão `gemini-3.6-flash`, com fallback para `gemini-3.5-flash`.

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

## Fonte oficial RREO (v1.3.1)

O RREO é lido **exclusivamente** do bucket `appdowelever-arquivos`, sem fallback para acervos antigos.

Estrutura esperada:

```text
01_Arquivo_dos_Estados_RREO_e_FNDE/
└── 4_APPDOWELEVER/
    └── RREO/
        └── 2025/
            └── 11_Rondonia_RO/
                └── B6/
                    └── RREO_Municipal_2025_....pdf
```

Variáveis: `RREO_SOURCE_BUCKET`, `RREO_SOURCE_BASE_PREFIX` e `RREO_SOURCE_ENABLED`.
Se um PDF não existir nessa fonte, o sistema registra `PDF NÃO ENCONTRADO NA FONTE APPDOWELEVER` e não procura em bucket antigo.
