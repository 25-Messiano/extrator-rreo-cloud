from __future__ import annotations
import streamlit as st

AJUDAS = {

"dashboard": ("❓ Como usar o Dashboard", """
### Objetivo
O Dashboard resume a situação financeira e operacional da **filial autenticada**. Ele não mistura dados de outras unidades.

- **Saldos** mostram Banco, Caixa e total acumulado da base oficial.
- **Entradas/Saídas/Resultado** respeitam o mês e exercício selecionados.
- **Situação operacional** destaca conferências, conciliações, rascunhos e importações pendentes.
- **Fluxo projetado** é apenas previsão; não altera o realizado.
- **Lançamentos recentes** vêm da base oficial da filial.

Use **Atualizar painel** depois de lançar, conferir, conciliar ou fechar uma competência.
"""),
"lancamentos": ("❓ Como usar Lançamentos", """
### Lançamentos oficiais
Registre movimentos manuais somente quando a origem não for uma importação que deva passar pela Conferência.

Informe data, competência, Banco/Caixa, conta, código, centro de custo, favorecido, documento, especificação, natureza e valor. O **Código APLB** identifica a natureza contábil; o favorecido identifica quem participa do movimento.

- **APROVADO** entra na base oficial.
- **RASCUNHO** permanece fora dos totais oficiais até conclusão.
- Transferência Banco → Caixa deve usar a função própria para manter as duas pontas vinculadas.
- Nunca apague histórico para corrigir: use **Correção / Estorno / Cancelamento**.
"""),
"correcao": ("❓ Como usar Correção / Estorno", """
### Preservação do histórico
A correção altera somente o que é permitido e deixa trilha de auditoria. **Estorno** cria o movimento inverso vinculado ao original. **Cancelamento** torna o lançamento invisível na operação normal, mas ele continua na Auditoria.

Sempre informe o motivo. Competência fechada não deve ser alterada silenciosamente; quando necessário, use o fluxo de reabertura autorizado.
"""),
"banco": ("❓ Como usar Banco", """
Esta visão mostra somente movimentações classificadas como **Banco** na filial ativa. O saldo é calculado a partir dos registros oficiais e saldos de abertura. Para cadastrar/alterar contas, use **Contas Bancárias**; para comparar com extratos, use **Conciliação Bancária**.
"""),
"caixa": ("❓ Como usar Caixa", """
Esta visão mostra somente movimentações classificadas como **Caixa** na filial ativa. Use a transferência interna quando houver passagem de recursos entre Banco e Caixa para preservar a rastreabilidade das duas pontas.
"""),
"codigos": ("❓ Como usar o Plano de Códigos", """
Cada filial possui **seu próprio Plano de Códigos**. O código define a natureza administrativa/contábil do lançamento e pode permitir Entrada, Saída ou ambas conforme regra autorizada.

A estrutura oficial da **DRE** é administrada pela Central. Marque **Gerar/identificar patrimônio** apenas em códigos que representam aquisição de bens permanentes. Inativar um código não apaga o histórico dos lançamentos já existentes.
"""),
"favorecidos": ("❓ Como usar Pessoas / Favorecidos", """
Cadastre pessoas, fornecedores, prestadores, entidades e demais participantes das movimentações. Esse cadastro identifica **quem** recebeu ou originou o recurso e pode ser reutilizado em lançamentos, fluxo de caixa e patrimônio.

Não confunda o código individual do favorecido com o Código APLB/DRE.
"""),
"contas": ("❓ Como usar Contas Bancárias / Financeiras", """
Cadastre contas do tipo **BANCO** ou **CAIXA**, informe banco/agência/conta quando aplicável e registre o saldo inicial com data de referência. Desativar uma conta impede novos usos, mas preserva todo o histórico.

Confira o saldo inicial antes de iniciar a conciliação e os relatórios oficiais.
"""),
"centros": ("❓ Como usar Centros de Custo", """
Centros de custo classificam **onde/para qual finalidade interna** o recurso foi utilizado, sem substituir o Código APLB nem a DRE. Podem ser criados, editados e inativados sem apagar o histórico antigo.
"""),
"auditoria": ("❓ Como usar Auditoria", """
A Auditoria é a trilha histórica do sistema. Registra ações, usuário, data/hora, entidade afetada e, quando disponível, valores anteriores/novos e motivo.

Lançamentos cancelados permanecem consultáveis aqui mesmo quando deixam de aparecer na operação normal. Use os filtros e exportações para conferência; não utilize a Auditoria como área de edição financeira.
"""),
"usuarios": ("❓ Como usar Usuários e Permissões", """
O Administrador gerencia usuários, perfis, e-mails de login, permissões e vínculos com unidades. As permissões valem imediatamente e o servidor também bloqueia acesso direto a páginas não autorizadas.

Nunca remova/desative o último Administrador ativo. Prefira os perfis oficiais; use permissões individuais apenas quando houver necessidade específica.
"""),
"backup": ("❓ Como usar Backup e Recuperação", """
### Proteção e recuperação
O backup completo reúne banco, estrutura, documentos suportados, anexos e manifesto/checksums. Gere backup manual antes de mudanças relevantes e mantenha o backup automático ativo.

- **Validar integridade** não altera produção.
- **Simular restauração** testa em ambiente isolado.
- **Restaurar produção** é operação de desastre e substitui dados atuais, portanto exige confirmação explícita.

O disco local do serviço não deve ser tratado como cofre permanente; para redundância real, configure armazenamento externo compatível quando definido pela administração.
"""),
"extratos": ("❓ Como usar Extratos Bancários", """
### Objetivo
Importar o extrato da conta da filial sem lançar nada diretamente na base oficial.

**Fluxo seguro:** `Arquivo → leitura → classificação → Conferência → liberação humana → base oficial → Conciliação`.

1. Selecione exercício, competência e a conta bancária correta.
2. Opcionalmente defina um centro de custo padrão para o lote.
3. Envie PDF, Excel ou CSV. A IA pode interpretar PDF/scan quando estiver configurada.
4. Confira a prévia: data, histórico, entrada/saída, valor, favorecido, código e confiança.
5. Clique **Gerar arquivo de conferência**. Isso ainda não cria lançamento oficial.

⚠️ Data fora da competência, baixa confiança e duplicidades exigem revisão humana. Nunca use a importação para contornar a Conferência.
"""),
"ia": ("❓ Como usar Importação com IA", """
### O que a IA faz
A IA auxilia na leitura de PDF/scan e **sugere** favorecido, Código APLB, especificação e nível de confiança. Regras determinísticas continuam responsáveis por duplicidade e consistência.

### O que a IA não faz
Ela não aprova, não concilia e não grava diretamente na base oficial. Itens de baixa confiança, sem código/pessoa ou com possível duplicidade permanecem pendentes.

**Regra fundamental:** toda sugestão passa pela Conferência e por decisão humana antes da liberação.
"""),
"conferencia": ("❓ Como usar o Arquivo de Conferência", """
### Barreira antes da base oficial
Aqui o conferente revisa cada item extraído/importado. Os estados são **PENDENTE, APROVADO, CORRIGIR e IGNORADO**; após a liberação, o item fica vinculado ao lançamento criado.

- **Aprovar:** aceita o item revisado.
- **Corrigir:** mantém o item fora da liberação até nova revisão.
- **Ignorar:** preserva o histórico, mas não cria lançamento.
- **Edição em massa:** use somente quando os itens selecionados realmente tiverem a mesma decisão.
- **Excel/JSON:** servem para revisão e rastreabilidade.

A liberação só é habilitada quando não existem pendências impeditivas. Duplicado exato permanece bloqueado.
"""),
"conciliacao": ("❓ Como usar a Conciliação Bancária", """
### Objetivo
Provar a correspondência entre movimentos do extrato e lançamentos oficiais.

A conciliação automática usa **data + entrada/saída + valor + conta**; descrição, favorecido e documento apenas ajudam a desempatar. Ela nunca cria lançamento.

Estados: **CONCILIADO**, **PENDENTE** e **DIVERGENTE**. Itens ambíguos ou sem correspondência exigem revisão manual. Use o relatório de divergências para corrigir pendências antes do fechamento mensal.
"""),
"pesquisa": ("❓ Como usar a Pesquisa Avançada", """
Combine período, Banco/Caixa, natureza, código, status, faixa de valor e texto. O campo de texto pesquisa código, descrição, especificação, favorecido e documento. A pesquisa é somente leitura e respeita a filial ativa.
"""),
"relatorios": ("❓ Como usar os Relatórios", """
Os relatórios são produzidos a partir da base oficial e respeitam a filial ativa. DRE possui página própria; os demais relatórios financeiros ficam nas páginas exclusivas do menu. Antes de emitir prestação definitiva, confira competência, conciliação e fechamento mensal.
"""),
"fechamento": ("❓ Como usar o Fechamento Mensal", """
O fechamento trava a competência para impedir alterações silenciosas. Antes de fechar, resolva importações/conferências pendentes e movimentos bancários não conciliados. Ao fechar, o sistema grava um snapshot auditável. Reabertura é excepcional, exclusiva de Administrador, exige motivo e restaura os estados registrados no snapshot.
"""),
"config": ("❓ Como usar Configurações", """
Esta área administra apenas parâmetros **não secretos**. Senhas, tokens, chaves de API e credenciais permanecem nas Environment Variables do Render. Como configurações podem ser globais, alterações devem ser feitas conscientemente pelo administrador e ficam auditadas.
"""),
"monitor": ("❓ Como usar o Monitoramento", """
Painel somente leitura para acompanhar saúde, segurança, pendências, acessos, IA, conciliações, fechamentos e continuidade/backup. **Verde** = normal; **amarelo** = requer acompanhamento; **vermelho** = requer ação. O monitoramento não executa movimentação financeira.
"""),
}

def botao_ajuda(chave: str, label: str = "❓") -> None:
    titulo, texto = AJUDAS[chave]
    @st.dialog(titulo, width="large")
    def _abrir():
        st.markdown(texto)
        if st.button("Fechar", key=f"fechar_ajuda_{chave}", width="stretch"):
            st.rerun()
    if st.button(label, key=f"ajuda_{chave}", help=titulo):
        _abrir()
