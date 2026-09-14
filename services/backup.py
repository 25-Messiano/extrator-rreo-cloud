from __future__ import annotations

import hashlib
import base64
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from database.db import Base, engine, session_scope
from models.entities import (
    AcessoLog,
    Auditoria,
    CargaInicialItem,
    CentroCusto,
    CodigoAPLB,
    Conciliacao,
    ConfiguracaoSistema,
    ContaFinanceira,
    Favorecido,
    FechamentoMensal,
    FluxoProjetado,
    GrupoCodigoVinculo,
    GrupoDRE,
    ImportacaoExtrato,
    ItemConferencia,
    Lancamento,
    Patrimonio,
    PatrimonioMovimento,
    PatrimonioAnexo,
    SaldoInicial,
    Usuario,
    Tesouraria,
    UsuarioTesouraria,
    PrestacaoContas,
)

BACKUP_SCHEMA = "tesouraria_aplb.backup_completo.v14"
BACKUP_DIR = "data/backups"

MODELOS = {
    # V25: a estrutura multiunidade também faz parte do backup integral.
    "tesourarias": Tesouraria,
    "usuarios": Usuario,
    "usuario_tesouraria": UsuarioTesouraria,
    "codigos_aplb": CodigoAPLB,
    "grupos_dre": GrupoDRE,
    "grupo_codigo_vinculo": GrupoCodigoVinculo,
    "contas_financeiras": ContaFinanceira,
    "saldos_iniciais": SaldoInicial,
    "favorecidos": Favorecido,
    "centros_custo": CentroCusto,
    "lancamentos": Lancamento,
    "carga_inicial_itens": CargaInicialItem,
    "fluxo_projetado": FluxoProjetado,
    "patrimonio": Patrimonio,
    "patrimonio_movimentos": PatrimonioMovimento,
    "patrimonio_anexos": PatrimonioAnexo,
    "importacoes_extrato": ImportacaoExtrato,
    "itens_conferencia": ItemConferencia,
    "conciliacoes": Conciliacao,
    "fechamentos_mensais": FechamentoMensal,
    "prestacoes_contas": PrestacaoContas,
    "auditoria": Auditoria,
    "acessos_log": AcessoLog,
    "configuracoes_sistema": ConfiguracaoSistema,
}


def _json_value(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        return {"__base64__": base64.b64encode(bytes(v)).decode("ascii")}
    return v


def _rows_for_model(session, cls):
    rows = session.scalars(select(cls)).all()
    return [
        {c.name: _json_value(getattr(row, c.name)) for c in cls.__table__.columns}
        for row in rows
    ]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def gerar_snapshot_config(output_dir=BACKUP_DIR):
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    with session_scope() as s:
        payload = {
            "schema": "tesouraria_aplb.estrutura.v14",
            "gerado_em": datetime.utcnow().isoformat() + "Z",
            "codigos": _rows_for_model(s, CodigoAPLB),
            "grupos": _rows_for_model(s, GrupoDRE),
            "vinculos": _rows_for_model(s, GrupoCodigoVinculo),
            "contas": _rows_for_model(s, ContaFinanceira),
            "usuarios": _rows_for_model(s, Usuario),
            "centros_custo": _rows_for_model(s, CentroCusto),
            "configuracoes": _rows_for_model(s, ConfiguracaoSistema),
        }
    path = p / f"estrutura_sistema_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    path.write_bytes(raw)
    return path


def gerar_backup_completo(output_dir=BACKUP_DIR):
    """Gera pacote ZIP versionado com dados, manifesto, contagens e checksums.

    O pacote inclui todas as tabelas operacionais do TESOURARIA APLB. O envio
    para S3/R2/objeto compatível é opcional e nunca impede o backup local.
    """
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    agora = datetime.utcnow()
    stamp = agora.strftime("%Y%m%d_%H%M%S")

    with session_scope() as s:
        payload = {
            "schema": BACKUP_SCHEMA,
            "gerado_em": agora.isoformat() + "Z",
            "backend_origem": engine.url.get_backend_name(),
            "tabelas": {},
        }
        contagens = {}
        for nome, cls in MODELOS.items():
            rows = _rows_for_model(s, cls)
            payload["tabelas"][nome] = rows
            contagens[nome] = len(rows)

    data_raw = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    data_hash = _sha256_bytes(data_raw)
    manifest = {
        "schema": "tesouraria_aplb.manifest.v14",
        "gerado_em": agora.isoformat() + "Z",
        "arquivo_dados": "backup.json",
        "sha256_backup_json": data_hash,
        "contagens": contagens,
        "total_registros": sum(contagens.values()),
    }
    manifest_raw = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")

    zip_path = p / f"TESOURARIA_APLB_BACKUP_{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("backup.json", data_raw)
        z.writestr("manifest.json", manifest_raw)
        recovery = Path("docs/RECOVERY_MASTER.txt")
        if recovery.exists():
            z.write(recovery, arcname="RECOVERY_MASTER.txt")

    cloud_ok, cloud_msg = _upload_cloud_opcional(zip_path)
    meta = {
        "arquivo": zip_path.name,
        "sha256": _sha256_file(zip_path),
        "tamanho_bytes": zip_path.stat().st_size,
        "gerado_em": agora.isoformat() + "Z",
        "cloud_ok": cloud_ok,
        "cloud_mensagem": cloud_msg,
        "total_registros": manifest["total_registros"],
    }
    (p / "ultimo_backup.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return zip_path


def validar_backup(path_or_bytes) -> dict:
    """Valida estrutura, checksum interno e contagens do pacote sem restaurar nada."""
    if isinstance(path_or_bytes, (bytes, bytearray)):
        tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        tmp.write(path_or_bytes)
        tmp.close()
        path = Path(tmp.name)
        cleanup = True
    else:
        path = Path(path_or_bytes)
        cleanup = False
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = set(z.namelist())
            if not {"backup.json", "manifest.json"}.issubset(names):
                raise ValueError("Pacote inválido: backup.json/manifest.json ausentes.")
            data_raw = z.read("backup.json")
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
            if _sha256_bytes(data_raw) != manifest.get("sha256_backup_json"):
                raise ValueError("Checksum interno divergente. Backup pode estar corrompido.")
            payload = json.loads(data_raw.decode("utf-8"))
            if payload.get("schema") != BACKUP_SCHEMA:
                raise ValueError(f"Schema de backup não suportado: {payload.get('schema')}")
            tabelas = payload.get("tabelas", {})
            calc = {k: len(v) for k, v in tabelas.items()}
            if calc != manifest.get("contagens", {}):
                raise ValueError("Contagens do manifesto não conferem com o conteúdo.")
            return {
                "valido": True,
                "schema": payload.get("schema"),
                "gerado_em": payload.get("gerado_em"),
                "contagens": calc,
                "total_registros": sum(calc.values()),
            }
    finally:
        if cleanup:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


def testar_restauracao(path_or_bytes) -> dict:
    """Restaura o pacote em SQLite temporário, sem tocar no banco de produção."""
    valid = validar_backup(path_or_bytes)
    if isinstance(path_or_bytes, (bytes, bytearray)):
        zpath = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        zpath.write(path_or_bytes)
        zpath.close()
        path = Path(zpath.name)
        cleanup_zip = True
    else:
        path = Path(path_or_bytes)
        cleanup_zip = False

    db_tmp = Path(tempfile.mkstemp(suffix=".db")[1])
    try:
        with zipfile.ZipFile(path, "r") as z:
            payload = json.loads(z.read("backup.json").decode("utf-8"))
        # Cria o schema real do aplicativo em uma cópia SQLite temporária.
        from sqlalchemy import create_engine
        eng_tmp = create_engine(f"sqlite:///{db_tmp}", future=True)
        Base.metadata.create_all(bind=eng_tmp)
        eng_tmp.dispose()

        conn = sqlite3.connect(db_tmp)
        try:
            conn.execute("PRAGMA foreign_keys=OFF")
            for nome, cls in MODELOS.items():
                rows = payload["tabelas"].get(nome, [])
                if not rows:
                    continue
                table = cls.__tablename__
                cols = [c.name for c in cls.__table__.columns]
                placeholders = ",".join(["?"] * len(cols))
                sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
                vals = []
                for row in rows:
                    converted=[]
                    for c in cols:
                        v=row.get(c)
                        if isinstance(v, dict) and "__base64__" in v:
                            v=base64.b64decode(v["__base64__"])
                        converted.append(v)
                    vals.append(tuple(converted))
                conn.executemany(sql, vals)
            conn.commit()
            contagens = {}
            esperado_chaves = set(valid["contagens"].keys())
            for nome, cls in MODELOS.items():
                if nome in esperado_chaves:
                    contagens[nome] = conn.execute(f"SELECT COUNT(*) FROM {cls.__tablename__}").fetchone()[0]
        finally:
            conn.close()

        esperado = valid["contagens"]
        if contagens != esperado:
            raise ValueError("Teste de restauração falhou: contagens restauradas divergentes.")
        return {
            "sucesso": True,
            "total_registros": sum(contagens.values()),
            "contagens": contagens,
            "mensagem": "Restauração simulada em banco temporário concluída sem tocar na produção.",
        }
    finally:
        try:
            db_tmp.unlink(missing_ok=True)
        except Exception:
            pass
        if cleanup_zip:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass




def _coerce_row_for_model(cls, row: dict) -> dict:
    out = {}
    for c in cls.__table__.columns:
        v = row.get(c.name)
        if v is None:
            out[c.name] = None
            continue
        try:
            py = c.type.python_type
        except Exception:
            py = None
        try:
            if py is datetime and isinstance(v, str):
                out[c.name] = datetime.fromisoformat(v.replace("Z", "+00:00")).replace(tzinfo=None)
            elif py is date and isinstance(v, str):
                out[c.name] = date.fromisoformat(v[:10])
            elif py is Decimal:
                out[c.name] = Decimal(str(v))
            elif py is bool:
                out[c.name] = v if isinstance(v, bool) else str(v).lower() in ("1", "true", "t", "yes")
            elif py is int:
                out[c.name] = int(v)
            elif py is float:
                out[c.name] = float(v)
            elif py is bytes and isinstance(v, dict) and "__base64__" in v:
                out[c.name] = base64.b64decode(v["__base64__"])
            else:
                out[c.name] = v
        except Exception:
            out[c.name] = v
    return out

def restaurar_backup_producao(path_or_bytes, confirmacao: str) -> dict:
    """Restauração real, protegida por confirmação textual explícita.

    Esta função existe para recuperação de desastre. A interface exige a frase
    RESTAURAR PRODUCAO e faz validação + simulação antes de tocar nos dados.
    """
    if confirmacao.strip().upper() != "RESTAURAR PRODUCAO":
        raise ValueError("Confirmação inválida. Digite exatamente RESTAURAR PRODUCAO.")
    testar_restauracao(path_or_bytes)

    if isinstance(path_or_bytes, (bytes, bytearray)):
        zpath = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        zpath.write(path_or_bytes)
        zpath.close()
        path = Path(zpath.name)
        cleanup = True
    else:
        path = Path(path_or_bytes)
        cleanup = False
    try:
        with zipfile.ZipFile(path, "r") as z:
            payload = json.loads(z.read("backup.json").decode("utf-8"))
        # Usa SQLAlchemy Core para manter transação única. Desabilita FKs apenas no SQLite.
        with engine.begin() as conn:
            if engine.url.get_backend_name() == "sqlite":
                conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            # Ordem reversa para exclusão. Pacotes antigos não continham as tabelas
            # multiunidade; nesse caso elas são preservadas em vez de serem apagadas.
            presentes = set(payload.get("tabelas", {}).keys())
            for nome, cls in reversed(list(MODELOS.items())):
                if nome in presentes:
                    conn.execute(cls.__table__.delete())
            for nome, cls in MODELOS.items():
                if nome not in presentes:
                    continue
                rows = payload["tabelas"].get(nome, [])
                if rows:
                    typed_rows = [_coerce_row_for_model(cls, row) for row in rows]
                    conn.execute(cls.__table__.insert(), typed_rows)
            if engine.url.get_backend_name() == "sqlite":
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        return {"sucesso": True, "total_registros": sum(len(v) for v in payload["tabelas"].values())}
    finally:
        if cleanup:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


def _upload_cloud_opcional(path: Path):
    bucket = os.getenv("CLOUD_BACKUP_BUCKET", "").strip()
    endpoint = os.getenv("CLOUD_BACKUP_ENDPOINT", "").strip() or None
    key = os.getenv("CLOUD_BACKUP_ACCESS_KEY", "").strip()
    secret = os.getenv("CLOUD_BACKUP_SECRET_KEY", "").strip()
    region = os.getenv("CLOUD_BACKUP_REGION", "").strip() or None
    if not bucket or not key or not secret:
        return False, "Cloud externo não configurado; pacote local/downloadável foi gerado."
    try:
        import boto3
        cli = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
            region_name=region,
        )
        remote_key = f"tesouraria_aplb/{datetime.utcnow().strftime('%Y/%m/%d')}/{path.name}"
        cli.upload_file(str(path), bucket, remote_key)
        return True, f"Enviado para {bucket}/{remote_key}"
    except Exception as exc:
        return False, f"Falha no envio Cloud: {type(exc).__name__}: {exc}"


def status_ultimo_backup(output_dir=BACKUP_DIR):
    p = Path(output_dir)
    meta = p / "ultimo_backup.json"
    if not meta.exists():
        return None
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        return None


def backup_automatico_diario(output_dir=BACKUP_DIR):
    p = Path(output_dir)
    p.mkdir(parents=True, exist_ok=True)
    hoje = datetime.utcnow().strftime("%Y%m%d")
    if list(p.glob(f"TESOURARIA_APLB_BACKUP_{hoje}_*.zip")):
        return None
    return gerar_backup_completo(output_dir)
