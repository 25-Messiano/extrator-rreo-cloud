import ast
from pathlib import Path


def test_app_importa_nome_real_do_financeiro():
    root = Path(__file__).resolve().parents[1]
    app_tree = ast.parse((root / "app.py").read_text(encoding="utf-8"))
    fin_tree = ast.parse((root / "services" / "financeiro.py").read_text(encoding="utf-8"))
    exported = {
        n.name for n in fin_tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    imports = []
    for n in app_tree.body:
        if isinstance(n, ast.ImportFrom) and n.module == "services.financeiro":
            imports.extend(a.name for a in n.names)
    missing = [name for name in imports if name not in exported]
    assert missing == []
    assert "listar_lancamentos" in imports


def test_nao_existe_import_acidentado_listar_lancamentos():
    root = Path(__file__).resolve().parents[1]
    ocorrencias = []
    for p in [root / "app.py"] + list((root / "pages").glob("*.py")) + list((root / "ui").glob("*.py")):
        txt = p.read_text(encoding="utf-8")
        if "listar_lançamentos" in txt:
            ocorrencias.append(str(p.relative_to(root)))
    assert ocorrencias == []
