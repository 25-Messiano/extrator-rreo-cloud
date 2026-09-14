# TESOURARIA APLB V25.3 - Portal de Perfis com Senha

A entrada no sistema passa a começar pela escolha explícita do perfil/unidade:
- Perfil ADMINISTRADOR (Central), com credencial de administrador;
- cada Tesouraria Filiada, exigindo usuário e senha com vínculo ativo;
- AMBIENTE DE TESTE, igualmente autenticado e isolado.

As senhas continuam individuais por usuário. Não existe senha compartilhada gravada na tesouraria. Isso preserva a auditoria nominal de cada ação.

Ao entrar por uma filial, a unidade fica travada durante a sessão; para mudar de filial é necessário sair e autenticar novamente no perfil desejado. O ADMINISTRADOR pode alternar unidades para auditoria/operação.
