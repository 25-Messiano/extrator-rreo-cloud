# V25.7 — Links internos e acessos operacionais

- Corrige todos os `st.page_link` que apontavam para nomes de arquivos inexistentes por diferença de acentuação.
- Mantém o ADMINISTRADOR da Central como contexto exclusivo.
- Cria contas operacionais internas separadas para ARACI-01 e TESTE.
- No portal, ambas aceitam o alias visual `admin`; internamente os logins são únicos.
- Senha inicial temporária: `123`, criada somente se a conta ainda não existir. Deploys futuros não redefinem a senha.
- Depois de alterar a senha em Minha Conta, a senha nova permanece.
