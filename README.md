# Calendário Messiano

Aplicativo Flask para navegação sincronizada do Calendário Gregoriano (G) e Messiano (M), usando a correspondência oficial armazenada no Google Cloud Storage.

## Princípio central

A correspondência G ↔ M é lida da fonte oficial. A interface não recalcula nem corrige datas. Marcadores adicionais são carregados de fontes fixas e indexados no SQLite durante o build.

## Funcionalidades

- G + M, somente G ou somente M;
- fases da Lua com marcadores pequenos;
- estações do ano;
- Páscoa — 15 de Rúben;
- Festas Bíblicas somente com status `ATIVO`;
- navegação por mês, ano, década, século e grandes intervalos;
- “Ir para o ano” e “Hoje”;
- página separada de Pesquisa;
- preferências salvas no navegador;
- estrutura do Cloud oculta do usuário final.

## Cloud

O app usa por padrão o bucket `calendario-messiano-dados`. Os caminhos dos objetos ficam centralizados em `config/storage.py` e não aparecem na interface.

## Credenciais

Configure uma das opções:

- `GOOGLE_SERVICE_ACCOUNT_JSON` com o JSON completo da conta de serviço; ou
- `GOOGLE_APPLICATION_CREDENTIALS` apontando para um arquivo secreto.

Nunca versione credenciais.

## Pesquisa Web/Google

A página Pesquisa sempre oferece abertura da consulta no Google. A pesquisa integrada via JSON só é ativada quando `GOOGLE_CSE_API_KEY` e `GOOGLE_CSE_CX` existem. Em 2026, a Custom Search JSON API não está disponível para novos clientes; por isso o app mantém o modo externo como fallback seguro.

## Validação local

```bash
pip install -r requirements.txt
python -m scripts.validate_project
python -m scripts.importar_calendario
python app.py
```

## Render

O `render.yaml` instala dependências, valida o projeto, importa as fontes oficiais para SQLite e inicia Gunicorn. O health check usa `/api/saude`.

## Segurança

- nenhuma credencial na interface;
- nenhuma estrutura técnica do Cloud nas Configurações;
- Pesquisa externa nunca altera os registros oficiais;
- fontes opcionais podem falhar sem expor caminhos internos ao usuário.

## Relatórios em PDF

O app possui uma página separada **Relatórios**, com geração e download direto de PDFs. Os relatórios usam a mesma base oficial do calendário e podem incluir Lua, Estações, Páscoa e Festas Bíblicas conforme o tipo escolhido. A geração é feita no servidor com ReportLab e possui limites para evitar documentos gigantes e sobrecarga no Render.

Tipos disponíveis: Mensal, Anual, Correspondência G <-> M, Fases da Lua, Estações do Ano, Festas Bíblicas, Data Específica, Intervalo Personalizado e Auditoria das Fontes.
