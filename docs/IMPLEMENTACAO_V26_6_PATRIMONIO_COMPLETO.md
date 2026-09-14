# V26.6 — Fluxo de Caixa Completo + Patrimônio Completo

Versão cumulativa construída sobre a V26.5.

## Patrimônio
- Cadastro completo de bens permanentes.
- Nº patrimonial único por filial.
- Descrição, categoria, data de aquisição, valor, fornecedor, NF, local de uso e responsável.
- Estado de conservação e vida útil em anos.
- Situações: ATIVO, INATIVO, EM_MANUTENCAO, OBSOLETO, TRANSFERIDO, BAIXADO.
- Documentos anexos persistidos no PostgreSQL e isolados por tesouraria, até 10 MB por arquivo.
- Anexos podem ser arquivados com auditoria; o histórico não é apagado silenciosamente.
- Integração com lançamentos oficiais e Importação de Movimento PDF.
- Movimentação por competência com datas DD/MM/AAAA.
- Relatórios PDF/Excel com filtros por situação e contagem de anexos.
- Ajuda contextual ❓ atualizada com todas as regras.

## Fluxo de caixa
Todo o conteúdo da V26.5 é preservado sem regressão.
