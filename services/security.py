from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select

from config.settings import settings
from database.db import session_scope
from models.entities import AcessoLog, Usuario, UsuarioTesouraria, ConfiguracaoSistema, PasswordResetToken
from services.auditoria import registrar_auditoria
from services.notificacoes import notificar_acesso_programador

PBKDF2_ITERATIONS = 310_000
PERFIS_VALIDOS = ("ADMINISTRADOR", "TESOURARIA", "CONFERENTE", "CONSULTA", "AUDITORIA")

# Matriz oficial V16. Permissões individuais, quando existentes, substituem o perfil padrão.
PERMISSOES = {
    "ADMINISTRADOR": {"*"},
    "TESOURARIA": {
        "LANCAR", "CORRIGIR", "IMPORTAR", "CONFERIR", "CONCILIAR", "CONSULTAR",
        "RELATORIOS", "PATRIMONIO", "FLUXO", "FECHAR", "CADASTROS",
    },
    "CONFERENTE": {"CONFERIR", "CONCILIAR", "CONSULTAR", "RELATORIOS", "FLUXO"},
    "CONSULTA": {"CONSULTAR", "RELATORIOS"},
    "AUDITORIA": {"CONSULTAR", "RELATORIOS", "AUDITORIA", "MONITORAR"},
}

DESCRICOES_PERMISSOES = {
    "LANCAR": "Criar lançamentos",
    "CORRIGIR": "Corrigir, estornar ou cancelar lançamentos",
    "IMPORTAR": "Importar e processar extratos",
    "CONFERIR": "Conferir itens importados",
    "CONCILIAR": "Executar conciliação bancária",
    "CONSULTAR": "Consultar dados financeiros",
    "RELATORIOS": "Emitir relatórios e DRE",
    "PATRIMONIO": "Administrar patrimônio",
    "FLUXO": "Consultar/administrar fluxo de caixa",
    "FECHAR": "Fechar competências mensais",
    "CADASTROS": "Administrar pessoas/entidades operacionais",
    "USUARIOS": "Administrar usuários e permissões",
    "CONFIGURAR": "Alterar configurações estruturais",
    "AUDITORIA": "Consultar trilha de auditoria",
    "BACKUP": "Gerar, validar e restaurar backups",
    "MONITORAR": "Consultar monitoramento do sistema",
}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def validar_senha(password: str) -> None:
    if len(password or "") < 10:
        raise ValueError("A senha deve ter pelo menos 10 caracteres.")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError("A senha deve conter pelo menos uma letra e um número.")


def normalizar_email(email: str) -> str:
    valor = (email or "").strip().lower()
    if len(valor) > 160 or "@" not in valor:
        raise ValueError("Informe um e-mail válido.")
    local, dominio = valor.rsplit("@", 1)
    if not local or "." not in dominio or dominio.startswith(".") or dominio.endswith("."):
        raise ValueError("Informe um e-mail válido.")
    if any(c.isspace() for c in valor):
        raise ValueError("Informe um e-mail válido.")
    return valor


def _email_em_uso(s, email: str, ignorar_usuario_id: int | None = None) -> bool:
    q = select(Usuario.id).where(func.lower(Usuario.email) == email.lower())
    if ignorar_usuario_id:
        q = q.where(Usuario.id != int(ignorar_usuario_id))
    return s.scalar(q) is not None


def email_login_pronto(usuario_id: int) -> bool:
    with session_scope() as s:
        u=s.get(Usuario, int(usuario_id))
        return bool(u and u.ativo and (u.email or "").strip())




def contextos_legados_sem_email() -> list[dict]:
    """Retorna somente contextos que ainda possuem conta ativa sem e-mail.

    A tela pública usa esta função apenas para decidir se a migração legada deve
    existir e quais contextos podem ser escolhidos. Não expõe nomes de usuários.
    """
    from models.entities import Tesouraria
    out=[]
    with session_scope() as s:
        admin_sem_email = s.scalar(select(Usuario.id).where(
            Usuario.ativo.is_(True),
            Usuario.perfil == "ADMINISTRADOR",
            func.coalesce(func.trim(Usuario.email), "") == "",
        ))
        if admin_sem_email:
            out.append({"key": "ADMIN", "label": "👑 ADMINISTRADOR / CENTRAL", "tid": None})

        rows = s.execute(
            select(Tesouraria.id, Tesouraria.nome, Tesouraria.ambiente)
            .join(UsuarioTesouraria, UsuarioTesouraria.tesouraria_id == Tesouraria.id)
            .join(Usuario, Usuario.id == UsuarioTesouraria.usuario_id)
            .where(
                Tesouraria.tipo != "CENTRAL",
                Tesouraria.ativa.is_(True),
                UsuarioTesouraria.ativo.is_(True),
                Usuario.ativo.is_(True),
                func.coalesce(func.trim(Usuario.email), "") == "",
            )
            .distinct()
            .order_by(Tesouraria.nome)
        ).all()
        for tid, nome, ambiente in rows:
            out.append({
                "key": f"T:{tid}",
                "label": f"{'🧪' if ambiente == 'TESTE' else '🏛️'} {nome}",
                "tid": int(tid),
            })
    return out

def ensure_admin() -> None:
    """Garante o administrador e executa, se solicitado, um reset unico seguro.

    O reset so ocorre quando TESOURARIA_ADMIN_RESET_TOKEN e
    TESOURARIA_ADMIN_RESET_PASSWORD estao definidos. O token e gravado apenas
    como hash em configuracoes_sistema; assim o mesmo reset nao se repete em
    reinicios/deploys subsequentes.
    """
    with session_scope() as s:
        admin = s.scalar(select(Usuario).where(Usuario.login == "admin"))
        if not admin and settings.admin_password:
            admin = Usuario(
                nome="Administrador",
                login="admin",
                senha_hash=hash_password(settings.admin_password),
                perfil="ADMINISTRADOR",
                ativo=True,
            )
            s.add(admin)
            s.flush()
        if admin and settings.admin_email and not admin.email:
            try:
                email_admin = normalizar_email(settings.admin_email)
                if not _email_em_uso(s, email_admin, admin.id):
                    admin.email = email_admin
            except ValueError:
                pass

        token = settings.admin_reset_token or ""
        reset_password = settings.admin_reset_password or ""
        if admin and token and reset_password:
            validar_senha(reset_password)
            token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
            chave = "ADMIN_RESET_TOKEN_APLICADO"
            cfg = s.get(ConfiguracaoSistema, chave)
            if not cfg or cfg.valor != token_hash:
                admin.senha_hash = hash_password(reset_password)
                admin.senha_versao = int(admin.senha_versao or 1) + 1
                admin.ativo = True
                if cfg:
                    cfg.valor = token_hash
                    cfg.atualizado_em = datetime.utcnow()
                else:
                    s.add(ConfiguracaoSistema(chave=chave, valor=token_hash))


def authenticate(login: str, password: str) -> dict | None:
    login = login.strip()
    with session_scope() as s:
        user = s.scalar(select(Usuario).where(Usuario.login == login, Usuario.ativo.is_(True)))
        ok = bool(user and verify_password(password, user.senha_hash))
        s.add(AcessoLog(usuario_id=user.id if user else None, login_informado=login, sucesso=ok))
        if not ok:
            return None
        user.ultimo_acesso = datetime.utcnow()
        result = {"id": user.id, "nome": user.nome, "login": user.login, "perfil": user.perfil, "senha_versao": int(user.senha_versao or 1)}
    notificar_acesso_programador(result)
    registrar_auditoria(result["id"], "LOGIN", "usuarios", result["id"], novo={"login": login})
    return result


def authenticate_email(email: str, password: str) -> dict | None:
    """Autenticação pública V26: e-mail é a identidade principal e deve ser único."""
    try:
        ident = normalizar_email(email)
    except ValueError:
        ident = (email or "").strip().lower()
    with session_scope() as s:
        users = s.scalars(select(Usuario).where(
            func.lower(Usuario.email) == ident, Usuario.ativo.is_(True)
        )).all()
        # Mais de uma conta com o mesmo e-mail é uma inconsistência de segurança; nunca escolhemos uma arbitrariamente.
        user = users[0] if len(users) == 1 else None
        ok = bool(user and verify_password(password or "", user.senha_hash))
        s.add(AcessoLog(usuario_id=user.id if user else None, login_informado=ident, sucesso=ok))
        if not ok:
            return None
        user.ultimo_acesso = datetime.utcnow()
        result = {
            "id": user.id, "nome": user.nome, "login": user.login, "email": user.email or "",
            "perfil": user.perfil, "senha_versao": int(user.senha_versao or 1),
        }
    notificar_acesso_programador(result)
    registrar_auditoria(result["id"], "LOGIN_EMAIL", "usuarios", result["id"], novo={"email": ident})
    return result


def ativar_email_conta_legada(email: str, password: str, tesouraria_id: int | None = None, admin: bool = False, legacy_login: str = "admin") -> dict:
    """Migração única: valida a credencial antiga e associa um e-mail exclusivo.

    Depois dessa associação, o acesso público é feito somente pelo e-mail.
    """
    novo_email = normalizar_email(email)
    login_antigo=(legacy_login or "admin").strip() or "admin"
    if admin:
        user = authenticate(login_antigo, password)
        if not user or user.get("perfil") != "ADMINISTRADOR":
            raise ValueError("Credencial atual inválida.")
    else:
        if not tesouraria_id:
            raise ValueError("Selecione a unidade da conta antiga.")
        user = authenticate_for_tenant(login_antigo, password, int(tesouraria_id))
        if not user or user.get("perfil") in ("ADMINISTRADOR", "AUDITORIA"):
            raise ValueError("Credencial atual inválida.")
    with session_scope() as s:
        u=s.get(Usuario, int(user["id"]))
        if not u or not u.ativo:
            raise ValueError("Conta indisponível.")
        if u.email:
            raise ValueError("Esta conta já possui e-mail. Use o e-mail cadastrado para entrar ou recuperar a senha.")
        if _email_em_uso(s, novo_email, u.id):
            raise ValueError("Este e-mail já está vinculado a outro usuário.")
        u.email=novo_email
        uid=u.id
    registrar_auditoria(uid, "ATIVAR_LOGIN_EMAIL", "usuarios", uid, novo={"email": novo_email})
    return {**user, "email": novo_email}




def usuario_pode_acessar_tesouraria(usuario_id: int, tesouraria_id: int) -> bool:
    """Valida acesso operacional a uma unidade.

    Administradores da CENTRAL não são usuários operacionais de filiais. A Central
    audita e administra por suas telas próprias; para operar uma filial é obrigatório
    autenticar uma conta vinculada àquela filial.
    """
    if not usuario_id or not tesouraria_id:
        return False
    from models.entities import Tesouraria
    with session_scope() as s:
        u = s.get(Usuario, int(usuario_id))
        t = s.get(Tesouraria, int(tesouraria_id))
        if not u or not u.ativo or not t or not t.ativa:
            return False
        if u.perfil == "ADMINISTRADOR":
            return t.tipo == "CENTRAL"
        return bool(s.scalar(select(UsuarioTesouraria.id).where(
            UsuarioTesouraria.usuario_id == int(usuario_id),
            UsuarioTesouraria.tesouraria_id == int(tesouraria_id),
            UsuarioTesouraria.ativo.is_(True),
        )))


def carregar_usuario_sessao(usuario_id: int) -> dict | None:
    """Recarrega perfil/estado do banco em toda navegação.

    Isso faz alteração de perfil, desativação e permissões entrarem em vigor imediatamente,
    sem depender de novo login ou de dados antigos da sessão Streamlit.
    """
    with session_scope() as s:
        u = s.get(Usuario, usuario_id)
        if not u or not u.ativo:
            return None
        return {"id": u.id, "nome": u.nome, "login": u.login, "perfil": u.perfil, "senha_versao": int(u.senha_versao or 1), "email": u.email or ""}


def _permissoes_usuario(u: Usuario) -> set[str]:
    # Administrador é sempre acesso total; não existe administrador parcial.
    if u.perfil == "ADMINISTRADOR":
        return {"*"}
    if u.permissoes_json:
        try:
            return set(json.loads(u.permissoes_json))
        except Exception:
            return set()
    return set(PERMISSOES.get(u.perfil, set()))


def permitido(perfil: str, acao: str, usuario_id: int | None = None) -> bool:
    # Se há ID, o banco é a fonte de verdade. Isso evita perfil antigo em sessão.
    if usuario_id:
        try:
            with session_scope() as s:
                u = s.get(Usuario, usuario_id)
                if not u or not u.ativo:
                    return False
                p = _permissoes_usuario(u)
                return "*" in p or acao in p
        except Exception:
            return False
    p = PERMISSOES.get(perfil, set())
    return "*" in p or acao in p


def permissoes_efetivas(usuario_id: int) -> list[str]:
    with session_scope() as s:
        u = s.get(Usuario, usuario_id)
        if not u or not u.ativo:
            return []
        p = _permissoes_usuario(u)
        if "*" in p:
            return sorted(DESCRICOES_PERMISSOES)
        return sorted(p)


def eh_admin_ativo(usuario_id: int | None) -> bool:
    if not usuario_id:
        return False
    with session_scope() as s:
        u = s.get(Usuario, usuario_id)
        return bool(u and u.ativo and u.perfil == "ADMINISTRADOR")


def _exigir_admin(usuario_id: int | None) -> None:
    if not eh_admin_ativo(usuario_id):
        raise PermissionError("Operação permitida somente a Administrador ativo.")



def _tenant_admin_login(codigo: str) -> str:
    """Login interno estável para o alias visual ``admin`` de cada unidade."""
    import re
    safe = re.sub(r"[^A-Z0-9]+", "_", (codigo or "").upper()).strip("_") or "UNIDADE"
    return f"admin__{safe}"


def ensure_operational_admins() -> None:
    """Garante um administrador operacional próprio para cada filial ativa.

    O login exibido no portal é ``admin``; internamente cada filial possui conta
    diferente (admin__CODIGO). A senha 123 é apenas inicial e nunca é redefinida
    se a conta já existir. Isso vale também para filiais criadas no futuro.
    """
    from models.entities import Tesouraria
    with session_scope() as s:
        filiais = s.scalars(select(Tesouraria).where(
            Tesouraria.tipo != "CENTRAL", Tesouraria.ativa.is_(True)
        )).all()
        for t in filiais:
            # V26.1: filiais criadas no padrão por e-mail já possuem um administrador
            # operacional vinculado. Nesse caso não criamos a conta legada admin/123.
            admin_link = s.scalar(select(UsuarioTesouraria.id).join(
                Usuario, Usuario.id == UsuarioTesouraria.usuario_id
            ).where(
                UsuarioTesouraria.tesouraria_id == t.id,
                UsuarioTesouraria.papel == "ADMIN_UNIDADE",
                UsuarioTesouraria.ativo.is_(True),
                Usuario.ativo.is_(True),
            ))
            if admin_link:
                continue
            internal_login = _tenant_admin_login(t.codigo)
            u = s.scalar(select(Usuario).where(Usuario.login == internal_login))
            if not u:
                u = Usuario(
                    nome=f"Administrador - {t.nome}", login=internal_login,
                    senha_hash=hash_password("123"), perfil="TESOURARIA", ativo=True,
                )
                s.add(u); s.flush()
            link = s.scalar(select(UsuarioTesouraria).where(
                UsuarioTesouraria.usuario_id == u.id,
                UsuarioTesouraria.tesouraria_id == t.id,
            ))
            if link:
                link.ativo = True
                link.papel = "ADMIN_UNIDADE"
            else:
                s.add(UsuarioTesouraria(
                    usuario_id=u.id, tesouraria_id=t.id, papel="ADMIN_UNIDADE", ativo=True
                ))


def authenticate_for_tenant(login: str, password: str, tesouraria_id: int) -> dict | None:
    """Autentica exclusivamente no contexto da filial selecionada."""
    from models.entities import Tesouraria
    login_informado = (login or "").strip()
    login_real = login_informado
    with session_scope() as s:
        t = s.get(Tesouraria, int(tesouraria_id))
        if not t or not t.ativa or t.tipo == "CENTRAL":
            return None
        if login_informado.lower() == "admin":
            login_real = _tenant_admin_login(t.codigo)
    result = authenticate(login_real, password)
    if result:
        result["login_exibicao"] = login_informado
    return result


def senha_inicial_temporaria(usuario_id: int) -> bool:
    """Indica se uma conta administrativa de filial ainda usa a senha inicial 123."""
    with session_scope() as s:
        u = s.get(Usuario, int(usuario_id))
        if not u or not (u.login or "").startswith("admin__"):
            return False
        return verify_password("123", u.senha_hash)


def criar_usuario(
    nome: str,
    login: str,
    senha: str,
    perfil: str,
    email: str | None = None,
    usuario_id: int | None = None,
) -> int:
    _exigir_admin(usuario_id)
    validar_senha(senha)
    if perfil not in PERFIS_VALIDOS:
        raise ValueError("Perfil inválido.")
    email_norm = normalizar_email(email or "")
    login_interno = (login or "").strip() or email_norm
    if not nome.strip():
        raise ValueError("Nome é obrigatório.")
    with session_scope() as s:
        if s.scalar(select(Usuario).where(func.lower(Usuario.login) == login_interno.lower())):
            raise ValueError("Já existe usuário com esse identificador interno.")
        if _email_em_uso(s, email_norm):
            raise ValueError("Já existe usuário com esse e-mail.")
        u = Usuario(
            nome=nome.strip(),
            login=login_interno,
            email=email_norm,
            senha_hash=hash_password(senha),
            perfil=perfil,
            ativo=True,
        )
        s.add(u)
        s.flush()
        uid = u.id
    registrar_auditoria(
        usuario_id,
        "CRIAR_USUARIO",
        "usuarios",
        uid,
        novo={"nome": nome.strip(), "login": login_interno, "email": email_norm, "perfil": perfil, "ativo": True},
    )
    return uid


def alterar_senha(usuario_id_alvo: int, nova_senha: str, usuario_id_executor: int | None = None) -> None:
    _exigir_admin(usuario_id_executor)
    validar_senha(nova_senha)
    with session_scope() as s:
        u = s.get(Usuario, usuario_id_alvo)
        if not u:
            raise ValueError("Usuário não encontrado.")
        u.senha_hash = hash_password(nova_senha)
        u.senha_versao = int(u.senha_versao or 1) + 1
        login = u.login
    registrar_auditoria(
        usuario_id_executor,
        "REDEFINIR_SENHA",
        "usuarios",
        usuario_id_alvo,
        novo={"login": login, "senha": "REDEFINIDA"},
    )


def alterar_minha_senha(usuario_id: int, senha_atual: str, nova_senha: str) -> None:
    """Permite ao próprio usuário trocar a senha, exigindo a senha atual.

    A senha nunca é recuperada/exibida; apenas o hash é substituído após validação.
    """
    validar_senha(nova_senha)
    with session_scope() as s:
        u = s.get(Usuario, usuario_id)
        if not u or not u.ativo:
            raise ValueError("Usuário não encontrado ou inativo.")
        if not verify_password(senha_atual or "", u.senha_hash):
            raise ValueError("Senha atual incorreta.")
        if verify_password(nova_senha, u.senha_hash):
            raise ValueError("A nova senha deve ser diferente da senha atual.")
        u.senha_hash = hash_password(nova_senha)
        u.senha_versao = int(u.senha_versao or 1) + 1
        login = u.login
    registrar_auditoria(
        usuario_id,
        "ALTERAR_MINHA_SENHA",
        "usuarios",
        usuario_id,
        novo={"login": login, "senha": "ALTERADA_PELO_PROPRIO_USUARIO"},
    )


def quantidade_admins_ativos() -> int:
    with session_scope() as s:
        return int(
            s.scalar(
                select(func.count(Usuario.id)).where(
                    Usuario.perfil == "ADMINISTRADOR", Usuario.ativo.is_(True)
                )
            )
            or 0
        )


def atualizar_meu_email(usuario_id: int, senha_atual: str, novo_email: str) -> None:
    email = normalizar_email(novo_email)
    with session_scope() as s:
        u = s.get(Usuario, int(usuario_id))
        if not u or not u.ativo:
            raise ValueError("Usuário não encontrado ou inativo.")
        if not verify_password(senha_atual or "", u.senha_hash):
            raise ValueError("Senha atual incorreta.")
        if _email_em_uso(s, email, u.id):
            raise ValueError("Este e-mail já está vinculado a outro usuário.")
        anterior = u.email
        u.email = email
    registrar_auditoria(usuario_id, "ALTERAR_MEU_EMAIL", "usuarios", usuario_id,
                        anterior={"email": anterior}, novo={"email": email})


def atualizar_email_usuario(usuario_id_alvo: int, email: str | None, usuario_id_executor: int) -> None:
    _exigir_admin(usuario_id_executor)
    valor = normalizar_email(email or "")
    with session_scope() as s:
        u = s.get(Usuario, int(usuario_id_alvo))
        if not u:
            raise ValueError("Usuário não encontrado.")
        if _email_em_uso(s, valor, u.id):
            raise ValueError("Este e-mail já está vinculado a outro usuário.")
        anterior = u.email
        u.email = valor
        u.senha_versao = int(u.senha_versao or 1) + 1
    registrar_auditoria(usuario_id_executor, "ALTERAR_EMAIL_USUARIO", "usuarios", usuario_id_alvo,
                        anterior={"email": anterior}, novo={"email": valor})


def _resolver_usuario_recuperacao(identificador: str, tesouraria_id: int | None = None, admin: bool = False):
    """V26: recuperação resolve exclusivamente por e-mail único; contexto não influencia identidade."""
    try:
        ident = normalizar_email(identificador)
    except ValueError:
        return None
    with session_scope() as s:
        ids=s.scalars(select(Usuario.id).where(Usuario.ativo.is_(True), func.lower(Usuario.email)==ident)).all()
        return ids[0] if len(ids)==1 else None


def solicitar_recuperacao_senha(identificador: str, tesouraria_id: int | None = None, admin: bool = False) -> dict:
    """Gera token de uso único e envia link de recuperação por e-mail.

    Retorna resposta genérica; o chamador público não deve revelar se a conta existe.
    """
    from config.settings import settings
    from services.email_service import enviar_email, email_configurado
    uid = _resolver_usuario_recuperacao(identificador, tesouraria_id, admin)
    if not uid:
        return {"aceito": True, "enviado": False, "motivo": "NAO_LOCALIZADO"}
    with session_scope() as s:
        limite = datetime.utcnow() - timedelta(minutes=15)
        recentes = s.scalar(select(func.count(PasswordResetToken.id)).where(
            PasswordResetToken.usuario_id == int(uid), PasswordResetToken.criado_em >= limite
        )) or 0
        if int(recentes) >= 3:
            return {"aceito": True, "enviado": False, "motivo": "LIMITE_TEMPORARIO"}
        u = s.get(Usuario, int(uid))
        if not u or not u.email:
            return {"aceito": True, "enviado": False, "motivo": "SEM_EMAIL"}
        # Invalida tokens anteriores ainda não usados.
        ativos = s.scalars(select(PasswordResetToken).where(
            PasswordResetToken.usuario_id == u.id,
            PasswordResetToken.usado_em.is_(None),
        )).all()
        agora = datetime.utcnow()
        for x in ativos:
            x.usado_em = agora
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        expira = agora + timedelta(minutes=max(10, int(settings.password_reset_minutes or 30)))
        row = PasswordResetToken(usuario_id=u.id, token_hash=token_hash, expira_em=expira,
                                 email_destino=u.email, enviado=False)
        s.add(row); s.flush(); rid=row.id
        destino=u.email; nome=u.nome
    base=(settings.public_url or "").rstrip("/")
    link=f"{base}/?reset_token={token}"
    corpo=(f"Olá, {nome}.\n\nRecebemos uma solicitação para redefinir sua senha do TESOURARIA APLB.\n"
           f"Use o link abaixo em até {max(10, int(settings.password_reset_minutes or 30))} minutos:\n\n{link}\n\n"
           "Se você não solicitou esta alteração, ignore esta mensagem. O link só pode ser usado uma vez.")
    ok, erro = enviar_email(destino, "TESOURARIA APLB - Recuperação de senha", corpo)
    with session_scope() as s:
        row=s.get(PasswordResetToken, rid)
        if row:
            row.enviado=bool(ok); row.erro_envio=None if ok else (erro or "Falha no envio")
            if not ok: row.usado_em=datetime.utcnow()
    registrar_auditoria(uid, "SOLICITAR_RECUPERACAO_SENHA", "usuarios", uid,
                        novo={"email": destino, "enviado": bool(ok), "smtp_configurado": email_configurado()})
    return {"aceito": True, "enviado": bool(ok), "motivo": None if ok else "ENVIO_FALHOU"}


def validar_token_recuperacao(token: str) -> dict | None:
    raw=(token or "").strip()
    if not raw:
        return None
    h=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with session_scope() as s:
        row=s.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash==h))
        if not row or row.usado_em is not None or not row.enviado or row.expira_em < datetime.utcnow():
            return None
        u=s.get(Usuario,row.usuario_id)
        if not u or not u.ativo:
            return None
        return {"usuario_id":u.id,"nome":u.nome,"email":u.email or "","expira_em":row.expira_em}


def redefinir_senha_por_token(token: str, nova_senha: str) -> int:
    validar_senha(nova_senha)
    raw=(token or "").strip(); h=hashlib.sha256(raw.encode("utf-8")).hexdigest()
    with session_scope() as s:
        row=s.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash==h))
        if not row or row.usado_em is not None or not row.enviado or row.expira_em < datetime.utcnow():
            raise ValueError("Link de recuperação inválido, expirado ou já utilizado.")
        u=s.get(Usuario,row.usuario_id)
        if not u or not u.ativo:
            raise ValueError("Usuário não encontrado ou inativo.")
        if verify_password(nova_senha,u.senha_hash):
            raise ValueError("A nova senha deve ser diferente da senha atual.")
        u.senha_hash=hash_password(nova_senha)
        u.senha_versao=int(u.senha_versao or 1)+1
        row.usado_em=datetime.utcnow(); uid=u.id
        # invalida qualquer outro token pendente
        outros=s.scalars(select(PasswordResetToken).where(
            PasswordResetToken.usuario_id==uid, PasswordResetToken.id!=row.id,
            PasswordResetToken.usado_em.is_(None))).all()
        for x in outros: x.usado_em=datetime.utcnow()
    registrar_auditoria(uid,"REDEFINIR_SENHA_POR_EMAIL","usuarios",uid,novo={"senha":"REDEFINIDA_POR_TOKEN"})
    return uid
