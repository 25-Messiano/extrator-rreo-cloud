# V24 — Filiais com código-base único e atualização centralizada

## Princípio estrutural
A Central e todas as tesourarias filiadas executam **o mesmo código do aplicativo**. Não existe cópia do programa por filial.

- Uma nova filial cria somente uma nova unidade lógica no banco (`tesourarias.id`).
- Os dados operacionais ficam isolados por `tesouraria_id`.
- Menus, telas, regras de negócio, relatórios, segurança e futuras correções pertencem ao código-base único.
- Ao publicar V25, V26 etc. na Central, todas as filiais passam automaticamente para a nova versão porque executam o mesmo deploy.
- Dados de uma filial nunca são copiados para outra durante atualização de versão.

## Cadastro visível
A V24 cria a página exclusiva **Cadastrar Nova Tesouraria** e um atalho visível na área Central.

Campos administrativos: código, nome, CNPJ, município, UF, responsável, telefone, e-mail, ambiente e observações.

## Gestão de filiais
A Central permite:
- listar filiais e mostrar a versão compartilhada;
- editar dados cadastrais;
- ativar/inativar filiais;
- vincular usuários e papéis por unidade;
- manter ambientes TESTE separados da produção.

## Regra para novas filiais
A filial nasce **sem lançamentos**, mas já possui acesso imediato à mesma estrutura funcional da versão corrente do sistema. Catálogos estruturais globais (como código-base e telas) são compartilhados; dados financeiros permanecem segregados.
