# Deploy no Render

1. Envie o projeto para o repositório GitHub correto do Calendário Messiano.
2. No Render, confirme que o serviço usa esse repositório/branch.
3. Configure `GOOGLE_SERVICE_ACCOUNT_JSON` como secret (ou use arquivo secreto com `GOOGLE_APPLICATION_CREDENTIALS`).
4. `GCS_BUCKET` já possui valor padrão `calendario-messiano-dados` no `render.yaml`.
5. `GOOGLE_CSE_API_KEY` e `GOOGLE_CSE_CX` são opcionais; sem eles, a página Pesquisa abre a consulta no Google externamente.
6. O build executa validação e gera o SQLite a partir das fontes do Cloud.
7. O health check é `/api/saude`.

Nunca coloque o valor real das credenciais no GitHub.
