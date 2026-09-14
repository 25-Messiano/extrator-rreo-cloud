# TESOURARIA APLB V25.12 - Consolidacao de navegacao, perfis e isolamento

## Objetivo
Consolidar a separacao entre CENTRAL, FILIAIS e TESTE e eliminar a navegacao automatica do Streamlit que ainda expunha paginas de outros contextos.

## Correcoes principais
1. Navegacao multipagina nativa do Streamlit desativada em `.streamlit/config.toml`. Somente o menu autenticado do TESOURARIA APLB fica visivel.
2. Paginas 37 (Importar Movimento PDF) e 38 (Importar Extratos PDF) passam a ser explicitamente OPERACIONAIS e sao bloqueadas para a CENTRAL inclusive por URL direta.
3. Cabecalho (`topbar`) passa a usar o contexto autenticado, nao uma lista de titulos. Toda pagina da CENTRAL mostra identidade da Central; toda pagina operacional mostra somente a filial/teste autenticado.
4. Administrador da CENTRAL deixa de ser considerado operador de filial. Vínculos legados CENTRAL -> FILIAL/TESTE sao desativados pelo bootstrap.
5. Nova filial nao recebe automaticamente o usuario ADMINISTRADOR da Central.
6. Toda filial ativa recebe conta operacional administrativa propria, com alias visual `admin` e login interno `admin__CODIGO`. A senha inicial `123` e criada apenas quando a conta ainda nao existe e nao e redefinida em deploys futuros.
7. O alias `admin` passa a funcionar genericamente para filiais futuras, nao apenas ARACI-01 e TESTE.
8. Na Central, tela de vinculo de usuarios nao oferece a CENTRAL como destino operacional.
9. Menu da CENTRAL inclui link explicito `Inicio da Central`.

## Dados
Nenhum lancamento, extrato, saldo, conta, codigo, patrimonio ou prestacao e alterado por esta versao. As mudancas sao de navegacao, autenticacao, vinculos de usuario e protecao de contexto.

## Validacao
- Todos os arquivos Python compilados.
- Todos os `page_link` apontam para arquivos existentes.
- Todas as paginas, exceto Minha Conta e Prestacoes de Contas (compartilhadas), possuem contexto CENTRAL ou OPERACIONAL explicito.
- 67 testes automatizados aprovados em banco SQLite limpo.
