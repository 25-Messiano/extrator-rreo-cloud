from __future__ import annotations

from modules.database.connection import conectar


def _dict(row):
    return dict(row) if row else None


def _enriquecer(conn, row):
    if not row:
        return None
    r = dict(row)
    eventos = [dict(x) for x in conn.execute(
        "SELECT tipo,codigo,nome,prioridade FROM eventos_g WHERE data_g=? ORDER BY prioridade,nome",
        (r["data_g"],),
    ).fetchall()]
    festas = [dict(x) for x in conn.execute(
        """
        SELECT id AS codigo, nome, tipo, dia_inicio, dia_fim
        FROM festas_m
        WHERE status='ATIVO' AND mes=? AND dia_inicio<=? AND dia_fim>=?
        ORDER BY dia_inicio, nome
        """,
        (r["m_mes"], int(r["data_m"][:2]), int(r["data_m"][:2])),
    ).fetchall()]
    if any(e["tipo"] == "pascoa" for e in eventos):
        festas = [f for f in festas if f["codigo"] != "PASCOA"]
    r["eventos"] = eventos
    r["festas"] = festas
    return r


def buscar_por_g(valor):
    valor = valor.strip()
    if valor.startswith("G."):
        valor = valor[2:]
        if "." in valor:
            possivel_data, possivel_dia = valor.rsplit(".", 1)
            if possivel_dia in {"DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"}:
                valor = possivel_data
    conn = conectar()
    row = conn.execute("SELECT * FROM calendario WHERE data_g=? LIMIT 1", (valor,)).fetchone()
    result = _enriquecer(conn, row)
    conn.close()
    return result


def buscar_por_m(valor):
    valor = valor.strip().split("|", 1)[0]
    if valor.startswith("M."):
        valor = valor[2:]
    conn = conectar()
    row = conn.execute("SELECT * FROM calendario WHERE data_m=? LIMIT 1", (valor,)).fetchone()
    result = _enriquecer(conn, row)
    conn.close()
    return result


def buscar_por_id(registro_id):
    conn = conectar()
    row = conn.execute("SELECT * FROM calendario WHERE id=? LIMIT 1", (registro_id,)).fetchone()
    result = _enriquecer(conn, row)
    conn.close()
    return result


def _listar_mes(tipo, mes, ano_num):
    prefix = "g" if tipo == "g" else "m"
    conn = conectar()
    rows = conn.execute(
        f"SELECT * FROM calendario WHERE {prefix}_ano_num=? AND {prefix}_mes=? ORDER BY id",
        (ano_num, mes),
    ).fetchall()
    result = [_enriquecer(conn, row) for row in rows]
    conn.close()
    return result


def listar_mes_g(mes, ano_num):
    return _listar_mes("g", mes, ano_num)


def listar_mes_m(mes, ano_num):
    return _listar_mes("m", mes, ano_num)


def listar_ano(tipo: str, ano_num: int, enriquecer: bool = True):
    prefix = "g" if tipo == "g" else "m"
    conn = conectar()
    rows = conn.execute(
        f"SELECT * FROM calendario WHERE {prefix}_ano_num=? ORDER BY id",
        (ano_num,),
    ).fetchall()
    result = [_enriquecer(conn, row) for row in rows] if enriquecer else [dict(r) for r in rows]
    conn.close()
    return result


def listar_intervalo_ids(id_inicial: int, id_final: int, limite: int = 10000, enriquecer: bool = True):
    if id_inicial > id_final:
        id_inicial, id_final = id_final, id_inicial
    quantidade = id_final - id_inicial + 1
    if quantidade > limite:
        raise ValueError(f"O intervalo possui {quantidade:,} dias; o limite por PDF é {limite:,} dias.")
    conn = conectar()
    rows = conn.execute(
        "SELECT * FROM calendario WHERE id BETWEEN ? AND ? ORDER BY id",
        (id_inicial, id_final),
    ).fetchall()
    result = [_enriquecer(conn, row) for row in rows] if enriquecer else [dict(r) for r in rows]
    conn.close()
    return result


def listar_eventos_por_tipo(tipo: str, id_inicial: int | None = None, id_final: int | None = None, limite: int = 20000):
    conn = conectar()
    params: list = [tipo]
    where = "e.tipo=?"
    if id_inicial is not None and id_final is not None:
        if id_inicial > id_final:
            id_inicial, id_final = id_final, id_inicial
        where += " AND c.id BETWEEN ? AND ?"
        params.extend([id_inicial, id_final])
    rows = conn.execute(
        f"""
        SELECT c.id,c.data_g,c.dia_semana,c.data_m,e.tipo,e.codigo,e.nome,e.prioridade
        FROM eventos_g e
        JOIN calendario c ON c.data_g=e.data_g
        WHERE {where}
        ORDER BY c.id,e.prioridade,e.nome
        LIMIT ?
        """,
        (*params, limite),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def listar_festas_ativas():
    conn = conectar()
    rows = conn.execute(
        """
        SELECT id,tipo,mes,dia_inicio,dia_fim,nome,status,referencia,observacao
        FROM festas_m WHERE status='ATIVO' ORDER BY mes,dia_inicio,nome
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def meses_do_ano(tipo, ano_num):
    prefix = "g" if tipo == "g" else "m"
    conn = conectar()
    rows = conn.execute(
        f"SELECT DISTINCT {prefix}_mes AS mes FROM calendario WHERE {prefix}_ano_num=? ORDER BY {prefix}_mes",
        (ano_num,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def limites():
    conn = conectar()
    rows = conn.execute("SELECT chave,valor FROM meta").fetchall()
    conn.close()
    return {r["chave"]: int(r["valor"]) for r in rows}


def estatisticas():
    d = limites()
    return {
        "total": d.get("total", 0),
        "limites": {
            "g": [d.get("g_min"), d.get("g_max")],
            "m": [d.get("m_min"), d.get("m_max")],
        },
    }
