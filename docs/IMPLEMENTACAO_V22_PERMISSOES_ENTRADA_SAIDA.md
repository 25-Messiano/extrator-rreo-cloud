# TESOURARIA APLB — V22

## Permissões administrativas de Entrada e Saída por código

A V22 parte integralmente da V21 e não reclassifica lançamentos históricos.

Cada código oficial passa a ter duas permissões independentes:

- `permite_entrada`: pode ser usado em receitas/entradas;
- `permite_saida`: pode ser usado em despesas/saídas.

O administrador pode autorizar um código para Entrada, Saída ou Ambos. Um código habilitado nos dois lados continua sendo um único cadastro. Os valores nunca são duplicados: cada lançamento é somado apenas na natureza gravada no próprio lançamento.

### Regra inicial de migração

- códigos originalmente de Entrada ficam autorizados para Entrada e Saída;
- códigos originalmente de Saída permanecem somente Saída, salvo códigos já reconhecidos como bidirecionais;
- `0703`, `0801` e `0804` ficam autorizados para Entrada e Saída;
- depois da migração, o administrador pode alterar as permissões pela interface.

### Relatórios

Resumo Banco, Resumo Caixa e Banco + Caixa passam a decidir a presença do código em cada quadro pelas permissões administrativas. Entretanto, movimentos históricos reais continuam visíveis mesmo se a permissão for alterada posteriormente.

A soma continua exclusivamente pela natureza real do lançamento (`ENTRADA` ou `SAIDA`), preservando a conferência contra a base oficial.

### Lançamentos

A tela de novo lançamento exibe somente os códigos autorizados para a natureza escolhida. A base histórica e rotinas técnicas não são reclassificadas automaticamente; assim, estornos e dados antigos continuam preservados. A permissão administrativa controla o uso normal pela interface e a presença dos códigos nos quadros de relatórios.

### Transferência Banco → Caixa

A transferência exige código autorizado simultaneamente para Entrada e Saída. O código `0801` é priorizado na interface quando disponível.
