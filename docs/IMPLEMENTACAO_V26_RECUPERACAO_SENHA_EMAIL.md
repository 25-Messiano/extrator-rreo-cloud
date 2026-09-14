# TESOURARIA APLB V26 — Identidade por e-mail e recuperação de senha

## Regra principal

A partir da V26, o **e-mail é a identidade pública do usuário**. O campo `login` continua existindo apenas como identificador técnico legado/interno para compatibilidade com versões anteriores.

- Tela pública: **E-mail + Senha**.
- O perfil/unidade não é mais uma credencial. Após autenticar, o sistema abre apenas as unidades autorizadas para aquele usuário.
- Se o usuário tiver acesso a mais de uma unidade, escolhe uma delas depois de autenticar.
- ADMINISTRADOR entra exclusivamente na CENTRAL.
- Filiais e TESTE continuam isolados por `tesouraria_id`.

## Migração segura das contas antigas

Na data de criação da V26, o banco de produção possui contas antigas sem e-mail. Por isso a V26 não bloqueia essas contas de imediato.

Existe uma opção pública **Primeiro acesso / ativar e-mail de uma conta antiga**. Ela exige:

1. a conta/unidade antiga;
2. o login antigo (normalmente `admin`);
3. a senha atual;
4. um e-mail válido e exclusivo.

A credencial antiga é validada antes de qualquer alteração. O e-mail só é gravado se ainda não estiver vinculado a outro usuário. Depois da ativação, o acesso normal passa a ser pelo e-mail.

## Recuperação de senha

`Esqueci minha senha` aceita somente o e-mail cadastrado. A resposta pública é sempre genérica para não revelar se um endereço existe no banco.

- token aleatório forte;
- somente o hash do token é armazenado;
- validade configurável, padrão 30 minutos;
- uso único;
- solicitação nova invalida tokens anteriores;
- no máximo 3 solicitações por usuário em 15 minutos;
- redefinição incrementa `senha_versao`, invalidando sessões antigas;
- auditoria registra solicitação e redefinição sem gravar senha em texto.

## Unicidade do e-mail

A V26 cria índice único normalizado (`lower(email)`) para e-mails não vazios. A aplicação também valida a unicidade antes de gravar. Se houver duplicidade legada, a inicialização aborta com mensagem explícita em vez de escolher uma conta arbitrariamente.

## SMTP necessário no Render

O login por e-mail não depende de SMTP. O envio de recuperação depende.

Variáveis esperadas:

- `TESOURARIA_PUBLIC_URL=https://app-tesouraria-aplb.onrender.com`
- `TESOURARIA_SMTP_HOST`
- `TESOURARIA_SMTP_PORT` (padrão 587)
- `TESOURARIA_SMTP_USER`
- `TESOURARIA_SMTP_PASSWORD`
- `TESOURARIA_SMTP_FROM_EMAIL`
- `TESOURARIA_SMTP_FROM_NAME`
- `TESOURARIA_SMTP_USE_TLS=1`
- `TESOURARIA_PASSWORD_RESET_MINUTES=30`
- opcional: `TESOURARIA_ADMIN_EMAIL` para preencher o e-mail do administrador somente se a conta ainda estiver sem e-mail e o endereço não estiver em uso.

A Central mostra o status **Recuperação por e-mail: ATIVA / CONFIGURAR SMTP** e a quantidade de contas antigas ainda sem e-mail.

## Política de senha

Nova senha: no mínimo 10 caracteres, com pelo menos uma letra e um número. Senhas existentes são preservadas durante a migração. A senha nunca é exibida nem enviada por e-mail.

## O que a V26 não altera

A migração de identidade não altera lançamentos, extratos, contas bancárias, códigos, DRE, patrimônio, conciliações, saldos, prestações de contas ou os vínculos financeiros das filiais.
