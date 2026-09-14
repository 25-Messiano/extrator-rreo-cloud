# TESOURARIA APLB V25.5 - Login limpo sem menu lateral

## Objetivo
Impedir que páginas e menus operacionais sejam exibidos antes da autenticação.

## Regra visual
Enquanto `st.session_state.user` não existir, toda a sidebar do Streamlit e seu controle de recolhimento ficam ocultos por CSS. O portal de acesso permanece como única interface visível.

## Após login
A autenticação válida grava a sessão e chama `st.rerun()`. Na nova execução, o CSS de ocultação não é aplicado e os menus são renderizados conforme o perfil, a unidade e as permissões do usuário.

## Segurança e dados
A V25.5 não altera dados financeiros, migração, usuários, senhas, vínculos, saldos, extratos ou relatórios. A proteção por `require_login` continua ativa também para acesso direto por URL.
