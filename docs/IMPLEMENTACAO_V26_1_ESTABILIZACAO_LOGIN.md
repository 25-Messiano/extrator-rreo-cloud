# TESOURARIA APLB V26.1 — Estabilização do login por e-mail

A V26.1 consolida a transição iniciada na V26.

## Ajustes

- O bloco **Primeiro acesso / ativar e-mail de uma conta antiga** agora é realmente transitório.
- Ele só aparece quando existe pelo menos uma conta ativa sem e-mail de login.
- A lista mostra somente contextos/unidades que ainda têm conta legada pendente; contas já migradas não voltam a aparecer.
- Quando todas as contas possuem e-mail, a tela pública fica reduzida a **E-mail + Senha + Esqueci minha senha**.
- Novas filiais criadas pela Central passam a nascer com administrador operacional já cadastrado por e-mail e com senha inicial definida no momento do cadastro.
- O bootstrap não cria a antiga conta `admin/123` quando a filial já possui administrador operacional ativo.
- O fallback legado continua existindo somente para unidades antigas ou criadas por rotas técnicas sem administrador, preservando compatibilidade e recuperação.

## Segurança

Nenhum lançamento, saldo, extrato, código, DRE, vínculo financeiro ou histórico é migrado nesta versão. A alteração é restrita à autenticação/onboarding de usuários e filiais.
