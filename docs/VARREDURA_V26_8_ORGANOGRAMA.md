# V26.8 — Varredura de aderência ao Organograma Geral

## Resultado
A arquitetura funcional central do organograma está implementada: lançamentos, Banco/Caixa, extratos, IA assistiva, Conferência, conciliação, fluxo realizado/projetado, patrimônio, códigos/DRE, cadastros, pesquisa, fechamento, auditoria, usuários/permissões, configurações, backup e monitoramento.

## Regras confirmadas
- Nenhuma importação/IA entra diretamente na base oficial: Conferência e liberação humana permanecem obrigatórias.
- Central e filiais permanecem isoladas por contexto e filial.
- Correção/estorno/cancelamento preservam histórico e Auditoria.
- Fechamento mensal bloqueia alteração silenciosa e reabertura é auditada.
- Patrimônio e Fluxo de Caixa mantêm as extensões das V26.5/V26.6.

## Pendências que dependem de definição/configuração externa, não de ausência do núcleo
1. **Mapa oficial Código APLB → DRE e regras de vigência histórica:** a estrutura existe, mas o conteúdo oficial final precisa ser homologado pela Central.
2. **Layouts finais de todos os 19 modelos de relatório:** o motor e vários relatórios existem; a fidelidade visual final depende da homologação de cada modelo.
3. **Cloud Storage externo permanente:** o backup integral existe; a redundância externa depende da escolha/configuração de S3/R2/Azure/compatível.
4. **Canais externos de notificação:** há base para webhook/e-mail e monitoramento; Telegram/WhatsApp exigem provedor, credenciais e política de uso.
5. **Matriz final de aprovação e campos obrigatórios por tipo de lançamento:** o mecanismo de permissões existe, mas essas regras de negócio ainda precisam de decisão administrativa final.

## Didática V26.8
Todos os 23 módulos principais do organograma possuem orientação por ❓, usando diálogo/modal ou ajuda equivalente já existente.

## Objetivo no Dashboard
O texto institucional do organograma foi inserido no topo do Dashboard e também na entrada da Central para manter identidade única do sistema.
