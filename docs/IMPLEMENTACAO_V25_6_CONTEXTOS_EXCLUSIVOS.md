# TESOURARIA APLB V25.6 — CONTEXTOS EXCLUSIVOS

## Objetivo
Eliminar a mistura visual e funcional entre Central, filiais e Ambiente de Teste.

## Regra de sessão
Cada autenticação cria um único contexto:
- ADMINISTRADOR -> CENTRAL DAS TESOURARIAS.
- Usuário vinculado a filial -> somente aquela filial.
- Usuário vinculado ao TESTE -> somente Ambiente de Teste.

Trocar usuário limpa integralmente a sessão. O próximo acesso exige nova autenticação e não herda identidade, unidade, menus ou permissões do usuário anterior.

## Central
O Administrador vê somente gestão central: filiais, nova tesouraria, migração, prestações, auditoria, usuários, backup, configurações, monitoramento e diagnóstico. A Central não exibe saldos, lançamentos ou dashboard financeiro de filial.

## Filiais e Teste
O usuário operacional vê somente a unidade em que autenticou: dashboard, cadastros autorizados, financeiro, relatórios, prestação e conta pessoal. Não vê páginas da Central nem outras unidades.

## Segurança
Credenciais de ADMINISTRADOR/AUDITORIA não são aceitas para entrar como perfil operacional de filial. Para operar uma filial é necessário usuário próprio vinculado à unidade.

Acesso direto por URL a uma página de outro contexto é bloqueado pelo servidor.
