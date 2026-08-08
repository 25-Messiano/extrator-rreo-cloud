from __future__ import annotations

from datetime import date
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file

from modules.database.consultas import (
    buscar_por_g,
    buscar_por_id,
    buscar_por_m,
    estatisticas,
    listar_mes_g,
    listar_mes_m,
    meses_do_ano,
)
from modules.reports import REPORT_TYPES, ReportRequest, generate_pdf
from modules.web_search import pesquisar_web

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False

MESES_M = {
    1: "Rúben", 2: "Simeão", 3: "Levi", 4: "Judá", 5: "Dã", 6: "Naftali",
    7: "Gade", 8: "Aser", 9: "Issacar", 10: "Zebulom", 11: "Diná", 12: "José", 13: "Benjamim",
}


@app.get("/")
def inicio():
    return render_template("index.html")


@app.get("/api/saude")
def saude():
    try:
        return jsonify({"ok": True, **estatisticas()})
    except Exception:
        return jsonify({"ok": False, "erro": "Banco indisponível."}), 500


@app.get("/api/g")
def api_g():
    valor = request.args.get("data", "").strip()
    if not valor:
        return jsonify({"erro": "Informe uma data G."}), 400
    r = buscar_por_g(valor)
    return jsonify(r) if r else (jsonify({"erro": "Data G não encontrada no registro oficial."}), 404)


@app.get("/api/m")
def api_m():
    valor = request.args.get("data", "").strip()
    if not valor:
        return jsonify({"erro": "Informe uma data M."}), 400
    r = buscar_por_m(valor)
    return jsonify(r) if r else (jsonify({"erro": "Data M não encontrada no registro oficial."}), 404)


@app.get("/api/registro/<int:registro_id>")
def api_registro(registro_id):
    r = buscar_por_id(registro_id)
    return jsonify(r) if r else (jsonify({"erro": "Registro não encontrado."}), 404)


@app.get("/api/mes/<tipo>")
def api_mes(tipo):
    if tipo not in {"g", "m"}:
        return jsonify({"erro": "Calendário inválido."}), 400
    try:
        mes = int(request.args.get("mes", "0"))
        ano_num = int(request.args.get("ano_num", "999999"))
    except ValueError:
        return jsonify({"erro": "Mês/ano inválidos."}), 400
    max_mes = 12 if tipo == "g" else 13
    if not 1 <= mes <= max_mes:
        return jsonify({"erro": "Mês inválido."}), 400
    registros = listar_mes_g(mes, ano_num) if tipo == "g" else listar_mes_m(mes, ano_num)
    return jsonify({
        "tipo": tipo,
        "mes": mes,
        "ano_num": ano_num,
        "mes_nome": MESES_M.get(mes, "") if tipo == "m" else "",
        "registros": registros,
    })


@app.get("/api/ano/<tipo>")
def api_ano(tipo):
    if tipo not in {"g", "m"}:
        return jsonify({"erro": "Calendário inválido."}), 400
    try:
        ano_num = int(request.args.get("ano_num", "999999"))
    except ValueError:
        return jsonify({"erro": "Ano inválido."}), 400
    meses = meses_do_ano(tipo, ano_num)
    if not meses:
        return jsonify({"erro": "Ano fora da base oficial."}), 404
    return jsonify({"tipo": tipo, "ano_num": ano_num, "meses": meses})


@app.get("/api/hoje")
def api_hoje():
    hoje = date.today().strftime("%d/%m/%YdC")
    r = buscar_por_g(hoje)
    return jsonify(r) if r else (jsonify({"erro": "A data de hoje não foi localizada."}), 404)


@app.get("/api/pesquisa")
def api_pesquisa():
    q = request.args.get("q", "").strip()
    try:
        return jsonify(pesquisar_web(q))
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except Exception:
        return jsonify({"erro": "A pesquisa externa está indisponível no momento."}), 502


@app.get("/api/relatorios/tipos")
def api_relatorios_tipos():
    return jsonify({"tipos": REPORT_TYPES})


def _bool(payload, key: str, default: bool = True) -> bool:
    value = payload.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "sim", "yes", "on"}


@app.post("/api/relatorios/pdf")
def api_relatorio_pdf():
    payload = request.get_json(silent=True) or {}
    try:
        ano = payload.get("ano")
        mes = payload.get("mes")
        req = ReportRequest(
            tipo=str(payload.get("tipo", "")).strip(),
            calendario=str(payload.get("calendario", "both")).strip(),
            referencia=str(payload.get("referencia", "g")).strip(),
            ano=int(ano) if ano not in {None, ""} else None,
            mes=int(mes) if mes not in {None, ""} else None,
            data=str(payload.get("data", "")).strip(),
            inicio=str(payload.get("inicio", "")).strip(),
            fim=str(payload.get("fim", "")).strip(),
            lua=_bool(payload, "lua"),
            estacoes=_bool(payload, "estacoes"),
            pascoa=_bool(payload, "pascoa"),
            festas=_bool(payload, "festas"),
        )
        pdf_bytes, filename = generate_pdf(req)
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400
    except Exception:
        app.logger.exception("Falha ao gerar relatório PDF")
        return jsonify({"erro": "Não foi possível gerar o PDF no momento."}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
