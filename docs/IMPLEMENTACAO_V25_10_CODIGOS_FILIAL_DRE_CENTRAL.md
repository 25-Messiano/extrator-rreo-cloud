# V25.10 - Plano de Codigos por Filial e DRE Central

- Cada FILIADA e o AMBIENTE DE TESTE possuem Plano de Codigos proprio, isolado por `tesouraria_id`.
- O mesmo numero de codigo pode existir em filiais diferentes com descricoes e permissoes diferentes.
- Bancos/Contas Bancarias aparecem em Cadastros para usuarios TESOURARIA e permanecem isolados por filial.
- A estrutura de grupos da DRE e unica e so pode ser editada pela CENTRAL.
- O vinculo Codigo da Filial -> Grupo DRE Oficial tambem e feito somente pela CENTRAL.
- A filial pode consultar sua DRE, mas nao alterar sua estrutura nem o enquadramento.
- Nao existe mais enquadramento automatico por numero de codigo: sem vinculo central, o codigo fica pendente de classificacao DRE.
