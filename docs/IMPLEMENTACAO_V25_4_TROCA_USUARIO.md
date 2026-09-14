# TESOURARIA APLB V25.4 - Troca segura de usuário

## Objetivo
Colocar os controles de identidade da sessão junto de **Unidade em análise/operação**, tornando evidente quem está operando a unidade e permitindo trocar de usuário sem herdar a sessão anterior.

## Interface lateral
Após a unidade ativa, o sistema exibe:
- **Usuário ativo**: nome e perfil autenticado;
- **Trocar usuário**: encerra integralmente a sessão e retorna ao portal de perfis/login;
- **Sair**: encerra integralmente a sessão;
- **Minha conta / Alterar senha**: abre a página pessoal de segurança.

## Segurança
`Trocar usuário` não troca silenciosamente a identidade. O `session_state` é limpo por completo, incluindo usuário, perfil de portal, tesouraria travada, unidade ativa e demais estados de sessão. O próximo operador precisa escolher um perfil e informar login e senha novamente.

## Compatibilidade
Nenhuma tabela financeira ou dado de produção é migrado/alterado pela V25.4. O isolamento integral da V25.2 e o portal autenticado da V25.3 são preservados.
