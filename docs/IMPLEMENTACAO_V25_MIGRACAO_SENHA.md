# V25 — Central não operacional, migração segura e Minha Conta

## 1. Central de Auditoria não é tesouraria operacional

A partir da V25, a unidade `CENTRAL` deixa de aparecer no seletor de **Unidade operacional ativa**. A Central continua existindo como camada estrutural para administração, auditoria, cadastro de filiais e análise de prestações, mas não deve ser utilizada para lançar movimentos financeiros.

## 2. Migração dos dados legados

A página **Migração de Dados da Central** permite ao Administrador transferir os registros operacionais historicamente vinculados à CENTRAL para uma filial de PRODUÇÃO já cadastrada, como `ARACI-01`.

A rotina:

1. identifica a CENTRAL como origem;
2. exige uma FILIADA de PRODUÇÃO ativa como destino;
3. mostra contagens e totais financeiros antes da migração;
4. verifica conflitos de fechamento e prestação de contas;
5. exige e valida backup pré-migração;
6. exige confirmação textual com o código da filial;
7. altera somente `tesouraria_id`, preservando IDs, valores, datas, códigos, documentos e vínculos;
8. executa todos os `UPDATEs` em uma única transação;
9. valida que a CENTRAL ficou sem registros operacionais diretos;
10. registra a operação na Auditoria.

Tabelas filhas, como itens de extrato, conciliações e carga inicial, permanecem ligadas aos mesmos registros-pai por chave estrangeira, portanto acompanham a migração sem recriação.

## 3. Senha do próprio usuário

A página **Minha Conta / Senha** fica disponível para todos os usuários autenticados. Para alterar a própria senha, o usuário deve informar:

- senha atual;
- nova senha;
- confirmação da nova senha.

A nova senha deve conter ao menos 10 caracteres, uma letra e um número. A senha atual nunca é exibida ou recuperada. Administradores continuam podendo redefinir uma senha pela página Usuários e Permissões, sem visualizar a senha anterior.

## 4. Código-base único

A V25 preserva a arquitetura da V24: Central e filiais operam um único código-base. Atualizações futuras são implantadas uma única vez e passam a valer simultaneamente em todas as filiais; somente os dados permanecem isolados por `tesouraria_id`.
