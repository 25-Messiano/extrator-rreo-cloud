# TESOURARIA APLB — V26.8

Versão acumulativa baseada na V26.7, com varredura do organograma, objetivo institucional no topo do Dashboard e ajuda ❓ nos 23 módulos principais.

## V25.1 — identificação visual da unidade ativa

O cabeçalho, Dashboard e menu lateral agora mostram claramente a filial operacional ativa, seu código, local, ambiente e a versão única do código-base. A Central permanece identificada apenas como área administrativa/auditoria. Esta versão não altera dados financeiros.

# TESOURARIA APLB — V25

**Central de Auditoria + Multitesourarias + Ambiente de Teste**

# TESOURARIA APLB

Sistema web de tesouraria da APLB, estruturado para funcionar com **PostgreSQL Cloud no Render** e uma única base oficial de lançamentos.

## Princípio do sistema

`Lançamento único → Código APLB → Banco/Caixa → Classificação → Conciliação → Relatórios/DRE → Fluxo de Caixa → Patrimônio → Auditoria`

Dados importados de extratos **não entram diretamente** na base oficial. O fluxo é:

`PDF/Excel/CSV → extração → sugestão de código → conferência Excel/JSON → aprovação humana → liberação → base oficial`.

## Módulos operacionais

- Dashboard com saldos Banco, Caixa e consolidado.
- Login/senha e perfis de acesso.
- Lançamentos manuais e transferência Banco → Caixa.
- Correção, estorno e auditoria.
- Banco e Caixa.
- Extratos bancários XLSX/XLS/CSV e PDF textual.
- Importação inteligente com classificação determinística inicial.
- Conferência e liberação humana.
- Conciliação.
- Fluxo de Caixa Realizado e Projetado.
- Patrimônio.
- Códigos APLB, grupos/subgrupos DRE e vínculos com vigência.
- Favorecidos/fornecedores.
- Contas financeiras.
- Pesquisa avançada.
- Relatórios, DRE, Excel e JSON.
- Fechamento mensal e reabertura auditada.
- Backup/snapshot estrutural.

## Banco de dados

Em produção, o app usa efetivamente a variável `DATABASE_URL` para conectar ao PostgreSQL. SQLite é usado somente como fallback local quando `DATABASE_URL` não estiver definida.

## Variáveis de ambiente no Render

Obrigatórias:

- `APP_ENV=production`
- `DATABASE_URL=<Internal Database URL do PostgreSQL>`
- `TESOURARIA_ADMIN_PASSWORD=<senha inicial do admin>`
- `SECRET_KEY=<chave aleatória>`

Opcionais:

- `PROGRAMADOR_ALERT_WEBHOOK_URL=<webhook para aviso de login>`
- `CLOUD_BACKUP_BUCKET=<destino futuro do Cloud Storage>`
- `OPENAI_API_KEY=<quando a camada IA externa for ativada>`

Nunca grave senhas ou URLs privadas no GitHub.

## Primeiro acesso

Quando `TESOURARIA_ADMIN_PASSWORD` estiver definida e ainda não existir usuário `admin`, o sistema cria automaticamente:

- Login: `admin`
- Senha: valor da variável `TESOURARIA_ADMIN_PASSWORD`
- Perfil: `ADMINISTRADOR`

Depois, crie usuários próprios pela tela **Usuários e Permissões**.

## Deploy Render

Build:

```bash
pip install -r requirements.txt
```

Start:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

## Recuperação

Arquivos principais:

- `docs/RECOVERY_MASTER.txt`
- `tesouraria_aplb_recovery_master.py`
- `docs/IMPLEMENTACAO_V1_OPERACIONAL.md`

Em contingência, configure as variáveis de ambiente e execute:

```bash
python tesouraria_aplb_recovery_master.py
```

## Estado atual

A V1 operacional já possui fundação funcional. Ainda serão refinados:

1. Cloud Storage definitivo para documentos e backups.
2. IA externa avançada para PDFs complexos/escaneados.
3. Reprodução visual exata dos 19 modelos históricos, conforme o mapeamento oficial de códigos for fechado.
## Carga inicial 2026

Esta versão inclui carga automática e idempotente dos 281 movimentos consolidados de janeiro, fevereiro e março de 2026 (`01_2026.pdf`, `02_2026.pdf`, `03_2026.pdf`). O saldo final validado em março é R$ 45.444,74. Consulte `docs/CARGA_INICIAL_2026.md`.


## V4 - Cancelamento lógico e auditoria

A V4 adiciona cancelamento lógico de lançamentos na tela Correção / Estorno / Cancelamento. Lançamentos CANCELADO permanecem auditáveis, mas deixam de compor saldos, Dashboard, DRE e relatórios oficiais. A migração também cancela de forma idempotente o lançamento de homologação de R$ 35,00 de 06/09/2026 quando todos os campos conhecidos conferem.

## V6 - Motor DRE orientado por regras
A V6 amplia a estrutura completa de grupos DRE e adiciona regras condicionais por código + especificação. O grupo 2.4.12 foi calibrado contra os relatórios oficiais consolidados de janeiro, fevereiro e março de 2026, reproduzindo exatamente R$ 109.094,56, R$ 108.120,65 e R$ 110.121,69. A tela DRE também permite detalhar os lançamentos que compõem cada grupo.

## V8 - Central de Relatórios
A Central de Relatórios concentra os modelos históricos APLB. Regra absoluta: os relatórios não possuem base contábil própria; todos os valores são apurados exclusivamente da base oficial de lançamentos, excluindo CANCELADOS. PDF e Excel compartilham a mesma apuração.

## V9 - Impressao em papel Oficio
Central de Relatorios ajustada para papel Oficio/Folio 8,5 x 13 pol., em retrato ou paisagem conforme o modelo, com PDF e Excel em uma pagina de largura.

## V10 — Importação segura por competência
Inclui Ano/Mês + conta na importação de extratos, Cadastro de Pessoas e Entidades com código individual e diagnóstico de duplicidade exata/possível antes da liberação.


## V11 — Implantação completa
Ver `docs/IMPLEMENTACAO_V11_COMPLETA.md`.

## V12 — IA real de extratos
OpenAI Responses API integrada ao fluxo 06→07→08→09, com leitura de PDF/scan, Structured Outputs, classificação por catálogo fechado, score de confiança, justificativa, conferência humana obrigatória e antiduplicidade determinística. Consulte `docs/IA_EXTRATOS_V12.md`.

## V13 - Operação limpa e reprocessamento de IA

A V13 oculta lançamentos cancelados de toda a operação normal (mantendo-os somente na Auditoria), arquiva lotes legados sem competência/conta, permite reprocessar com IA os extratos válidos já existentes sem novo upload e preserva toda decisão humana já tomada na Conferência. A IA continua sem permissão para gravar diretamente na base oficial.

## V14 — Conciliação objetiva + Backup/Recuperação

- Conciliação por Data + Entrada/Saída + Valor, com descrição/favorecido/documento apenas para desempate.
- Comparação global e diária de totais de Entradas Banco e Saídas Banco entre extrato e base oficial.
- Saldo Anterior/Saldo Inicial tratado como movimento técnico e excluído da conciliação financeira.
- Backup integral de todas as tabelas operacionais em pacote ZIP com manifesto e SHA-256.
- Validação de integridade e simulação de restauração em banco temporário isolado.
- Restauração de desastre protegida por confirmação explícita.
- Upload Cloud opcional S3/R2 compatível via `CLOUD_BACKUP_*`.

## V15 — Fechamento Mensal
Fechamento por competência, pré-validação, snapshot reversível, bloqueio do período e reabertura auditada. Consulte `docs/IMPLEMENTACAO_V15_FECHAMENTO_MENSAL.md`.

## V16 — Usuários e Permissões
A V16 consolida perfis oficiais, permissões individuais, bloqueio por URL, ocultação de menu sem acesso, proteção do último Administrador, redefinição segura de senha, auditoria das ações administrativas e reabertura mensal exclusiva do Administrador. Consulte `docs/IMPLEMENTACAO_V16_USUARIOS_PERMISSOES.md`.

## V18.1 — Modelo principal consolidado de Movimento Financeiro
O relatório principal Banco/Caixa reproduz o modelo consolidado homologado, mantendo todas as nove colunas na mesma folha, com saída em PDF e Excel e opção A4 fiel ao modelo ou Ofício paisagem. Janeiro/2026 gera 5 páginas. Ver `docs/IMPLEMENTACAO_V18_FIDELIDADE_MODELO_PRINCIPAL.md`.

## V19 — Configuração auditável de Códigos / Grupos DRE
A V19 torna a vinculação Código → Grupo DRE administrável pela interface, com regra rígida de um único grupo ativo por código, auditoria, movimentação entre grupos e catálogo oficial ampliado. Também consolida Banco antes de Caixa no relatório principal e corrige a legibilidade dos status do Monitoramento.

## V20 — Resumos oficiais consolidados
A V20 implementa, em PDF e Excel, os modelos de Resumo Geral de Banco, Resumo Geral de Caixa, Resumo Geral Banco + Caixa, Suprimento de Caixa e Saldos Históricos. Todos usam a base oficial por competência, fazem conferência automática dos totais e não mantêm valores paralelos. Ver `docs/IMPLEMENTACAO_V20_RESUMOS_OFICIAIS.md`.


## V21 — Menu hierárquico e relatórios exclusivos
Menu agrupado por módulos e páginas exclusivas para os relatórios oficiais. DRE gera somente DRE.

## V22 — Permissões de Entrada/Saída por código

A partir da V22, o administrador pode definir independentemente se cada Código APLB é permitido em **Entrada**, **Saída** ou **Ambos**. Os relatórios de Resumo Banco, Resumo Caixa e Banco + Caixa usam essas permissões para exibir os códigos em cada quadro, mas continuam somando cada lançamento exclusivamente pela sua natureza real. Lançamentos históricos não são reclassificados.

Detalhes: `docs/IMPLEMENTACAO_V22_PERMISSOES_ENTRADA_SAIDA.md`.

## V24 — Código-base único para Central e filiais
A partir da V24, nenhuma filial recebe uma cópia separada do aplicativo. Todas operam no mesmo código-base e na mesma versão implantada no Render/GitHub. Uma atualização estrutural da Central passa automaticamente a valer para todas as filiais, enquanto os dados financeiros continuam isolados por `tesouraria_id`.

A Central possui uma página visível **Nova Tesouraria** para cadastrar filiais e outra área para editar cadastro, vincular usuários e ativar/inativar unidades.

## V25 — Migração segura da Central + Minha Conta / Senha

A Central de Auditoria deixa de aparecer como unidade financeira operacional. A V25 acrescenta a página **Migração de Dados da Central**, com prévia de contagens/totais, backup obrigatório, validação de conflitos, confirmação textual e transferência transacional dos dados legados para uma filial de produção. Também acrescenta **Minha Conta / Senha**, permitindo a cada usuário trocar a própria senha mediante confirmação da senha atual.

Detalhes: `docs/IMPLEMENTACAO_V25_MIGRACAO_SENHA.md`.

## V25.2 - Isolamento integral entre Central, Teste e Filiais

A V25.2 fecha consultas operacionais que ainda nao respeitavam a `tesouraria_id`. CENTRAL e TESTE nao herdam dados financeiros de ARACI-01 ou de qualquer outra filial. Foi adicionada a pagina **Diagnostico de Isolamento** para administradores da Central. Codigos/DRE e configuracoes estruturais continuam compartilhados pelo unico codigo-base; no Ambiente de Teste esses cadastros globais ficam protegidos contra alteracao.

## V25.3 - Portal de perfis com senha

A entrada passa a exibir explicitamente o perfil ADMINISTRADOR e cada tesouraria ativa, incluindo o AMBIENTE DE TESTE. O usuário escolhe o perfil/unidade e autentica com login e senha. Senhas permanecem individuais por usuário; a tesouraria não armazena senha compartilhada. Ao entrar por uma filial, a unidade fica travada durante a sessão até logout. O ADMINISTRADOR pode alternar unidades para auditoria/operação.

## V25.4 - Troca segura de usuário
- Exibe **Usuário ativo** junto de **Unidade em análise/operação**.
- Adiciona **Trocar usuário**, **Sair** e **Minha conta / Alterar senha** na barra lateral.
- Trocar usuário limpa integralmente a sessão e exige novo login/senha.
- Não altera dados financeiros nem a migração das filiais.


## V25.5 - Login limpo sem menu lateral

- Antes da autenticação, a barra lateral multipágina do Streamlit fica totalmente oculta.
- A tela pública mostra somente o portal de acesso, seleção de perfil/unidade, login e senha.
- Após autenticação bem-sucedida, o aplicativo executa `rerun` e a barra lateral autorizada volta a aparecer normalmente.
- Nenhum dado financeiro, migração, usuário, senha ou vínculo de tesouraria é alterado por esta versão.

## V25.6 — Contextos exclusivos por usuário/perfil
A V25.6 separa completamente a interface por contexto autenticado. ADMINISTRADOR opera somente a Central; usuários de filiais operam somente a filial escolhida; usuários do TESTE operam somente o Ambiente de Teste. Trocar usuário encerra a sessão anterior e exige novo login. Menus e páginas de outros contextos deixam de aparecer e também são bloqueados em acesso direto por URL.

## V25.8 - Correção cirúrgica de integridade
- Corrige o import `listar_lancamentos` no `app.py`.
- Adiciona teste de regressão para imports locais do Dashboard.
- Mantém dados, banco, perfis, isolamento e credenciais sem alteração.

## V25.9 — Importação em lote por PDF
- Nova página **Importar Movimento PDF** para demonstrativos mensais Banco/Caixa em lote.
- Nova página **Importar Extratos PDF** para múltiplos extratos bancários.
- Todo lote passa por prévia, Conferência e liberação humana antes da base oficial.
- Hash do arquivo bloqueia reimportação acidental do mesmo PDF na mesma tesouraria.
- Duplicidade por lançamento continua sendo validada pelo motor determinístico existente.


## V25.10 - Codigos por filial / DRE central
Cada filial administra seu Plano de Codigos e seus Bancos/Contas. A estrutura e o enquadramento da DRE sao exclusivos da Central.


## V25.11 - Recuperacao segura do Administrador
- Mantem o administrador existente e suas permissoes.
- Adiciona reset unico por variaveis de ambiente `TESOURARIA_ADMIN_RESET_TOKEN` e `TESOURARIA_ADMIN_RESET_PASSWORD`.
- O token e armazenado somente como SHA-256 para impedir repeticao do mesmo reset.
- Senhas das filiais Araci e TESTE nao sao alteradas.

## V25.13 - Consolidacao de navegacao e isolamento
- Remove a navegacao automatica do Streamlit e mantem somente o menu do perfil autenticado.
- CENTRAL, FILIAL e TESTE passam a ter navegacao visual mutuamente exclusiva.
- Importacoes PDF ficam explicitamente bloqueadas na CENTRAL.
- Administrador da Central nao e mais operador de filial.
- Toda nova filial recebe conta operacional administrativa propria com alias `admin` e senha inicial temporaria `123` (sem reset automatico depois de alterada).


## V26 - Recuperacao de senha por e-mail
Recuperacao no proprio portal com token temporario, uso unico, SMTP e invalidacao de sessoes apos troca de senha.

## V26 — Login por e-mail

A V26 estabiliza identidade e recuperação de senha: e-mail único como login público, ativação única das contas legadas, recuperação por link temporário de uso único e diagnóstico SMTP na Central. Veja `docs/IMPLEMENTACAO_V26_RECUPERACAO_SENHA_EMAIL.md`.

## V26.1 — Estabilização final do acesso por e-mail

A V26.1 torna a migração legada realmente transitória: o bloco de primeiro acesso só aparece enquanto houver conta ativa sem e-mail e lista apenas contextos pendentes. Novas filiais criadas pela Central já nascem com administrador operacional por e-mail e senha inicial própria, sem depender de `admin/123`. Veja `docs/IMPLEMENTACAO_V26_1_ESTABILIZACAO_LOGIN.md`.

## V26.6 — Fluxo de Caixa completo

A V26.6 implementa a estrutura completa de Fluxo de Caixa Realizado e Projetado prevista no organograma, adiciona cenários, recorrência, filtros por classificação, comparação projetado x realizado, alertas, gráficos, relatórios PDF/Excel e ajuda `❓`. Datas de Patrimônio e Fluxo passam a ser exibidas em `DD/MM/AAAA`. Veja `docs/IMPLEMENTACAO_V26_5_FLUXO_CAIXA_COMPLETO.md`.


## V26.6 — Fluxo de Caixa Completo + Patrimônio Completo
Acumula integralmente a V26.5 e amplia o Patrimônio com Nº patrimonial, categoria, aquisição, valor, fornecedor/Favorecido, NF, local, responsável, estado de conservação, vida útil, situação (Ativo/Inativo/Manutenção/Obsoleto/Transferido/Baixado), anexos persistidos no banco, competência e relatórios PDF/Excel.

## V26.7 — Fechamento dos pontos amarelos do organograma
Versão acumulativa sobre a V26.6. Acrescenta ajuda contextual `❓` nos módulos incompletos, edição em massa auditada na Conferência, relatório de divergências na Conciliação, alerta de pendências bancárias no Fechamento Mensal, filtros/exportação na Pesquisa Avançada e orientação contextual em Relatórios. A regra de revisão humana antes da base oficial permanece obrigatória.

## V26.9 — Folha de Pagamento e Recibos Avulsos
Base acumulativa da V26.8. Inclui cadastro de trabalhadores, eventos parametrizáveis, competências (mensal, 13º, férias, rescisão e complementar) e recibos avulsos persistentes por filial. Recibos reaproveitam o cadastro do prestador, preservam cada emissão, documento e comprovante e geram PDF no leiaute do modelo oficial fornecido. O módulo possui ajuda didática ❓ e foi desenhado para evoluir sem lançar rascunhos diretamente na base financeira oficial.

## V26.10 — Folha Parametrizada, Vigências e Fechamento Auditável

A V26.10 é acumulativa sobre a V26.9 e acrescenta governança anual da Folha de Pagamento sem fixar alíquotas legais no código.

- Parâmetros por grupo e vigência: PISO, INSS, IRRF, FGTS, BENEFÍCIO, FÉRIAS, 13º, RESCISÃO, CONSIGNAÇÃO e outros.
- Histórico salarial por trabalhador, com nova vigência sem apagar o salário anterior.
- Calendário operacional por competência: abertura, limite de eventos, conferência, fechamento e pagamento previsto.
- Fluxo de status: RASCUNHO → EM_CONFERENCIA → APROVADA → FECHADA → PAGA.
- Checklist obrigatório de fechamento.
- Snapshot no fechamento preservando os parâmetros e o checklist utilizados.
- Folha complementar como caminho para diferenças posteriores, sem reabrir silenciosamente competência fechada.
- Ajuda ❓ didática em cada subárea da Folha.
- Recibos avulsos preservados da V26.9.

As regras legais e tributárias continuam parametrizáveis e devem ser validadas pelo responsável/contador antes de uso em produção.
