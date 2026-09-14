# V25.13 — Redirecionamento de contexto

- ADMINISTRADOR sempre entra no Início da Central (`app.py`).
- FILIAL/TESTE sempre entra no Dashboard operacional.
- Trocar usuário e Sair limpam a sessão e voltam ao portal raiz.
- URL operacional em sessão CENTRAL redireciona para a Central.
- URL Central em sessão FILIAL/TESTE redireciona para o Dashboard da unidade.
- Nenhum dado financeiro foi alterado.
