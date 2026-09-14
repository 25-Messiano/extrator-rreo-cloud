# V23 — Central, Multitesourarias e Ambiente de Teste

- Central de Auditoria com cadastro ilimitado de tesourarias filiadas.
- Identificador `tesouraria_id` nos principais registros financeiros.
- Base V22 legada migrada para `CENTRAL` sem reclassificar lançamentos.
- Unidade `TESTE` criada isoladamente e vazia.
- Usuários podem ser vinculados a uma ou mais tesourarias; Administrador vê todas.
- Seletor de unidade ativa no menu.
- Prestação de contas versionada com snapshot: ENVIADA -> APROVADA / DEVOLVIDA / REJEITADA.
- Parecer obrigatório e auditoria da decisão.
- Lançamentos, contas, saldos e relatórios principais passam a respeitar a unidade ativa.

A Central não edita silenciosamente a prestação apresentada. Correções geram nova versão e preservam o histórico.
