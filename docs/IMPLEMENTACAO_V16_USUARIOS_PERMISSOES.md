# V16 — Usuários e Permissões

## Objetivo
Fechar a administração de acesso do TESOURARIA APLB com defesa em duas camadas: interface + servidor.

## Perfis oficiais
- ADMINISTRADOR: acesso total e exclusivo a usuários, configurações estruturais, backup/restauração e reabertura mensal.
- TESOURARIA: operação financeira, extratos, conferência, conciliação, relatórios, patrimônio, fluxo, fechamento e cadastro de pessoas/entidades.
- CONFERENTE: conferência, conciliação, consultas, relatórios e fluxo.
- CONSULTA: consultas e relatórios sem alteração.
- AUDITORIA: consultas, relatórios, auditoria e monitoramento, sem alteração financeira.

## Proteções implementadas
1. Toda página possui permissão mínima no servidor; URL direta não contorna o bloqueio.
2. Páginas sem acesso são ocultadas do menu lateral como melhoria visual.
3. Perfil/estado/permissões são recarregados do banco em cada navegação; desativação e alterações entram em vigor imediatamente.
4. O último Administrador ativo não pode ser desativado nem rebaixado.
5. Administrador sempre possui acesso total; não existe Administrador parcial.
6. Criação de usuário, redefinição de senha e alteração de perfil/permissões exigem Administrador ativo no serviço, não apenas na tela.
7. Senhas novas exigem mínimo de 10 caracteres, com letra e número.
8. Senhas nunca são exibidas; somente redefinidas.
9. Criação, redefinição de senha e alterações de usuário são registradas na Auditoria.
10. Reabertura de competência fechada é exclusiva de Administrador e continua exigindo motivo.
11. Fechamento mensal continua disponível somente para quem possuir FECHAR.
12. Cadastro de pessoas/entidades passa a exigir CADASTROS; cadastros estruturais continuam protegidos por CONFIGURAR.
13. Monitoramento passa a exigir MONITORAR.

## Permissões individuais
Quando usadas por um perfil que não seja Administrador, substituem o perfil padrão daquele usuário. Se não forem usadas, vale a matriz oficial do perfil.

## Segurança de sessão
O sistema não confia somente no perfil armazenado na sessão Streamlit. Em cada página, recarrega o usuário no PostgreSQL e recalcula a autorização.
