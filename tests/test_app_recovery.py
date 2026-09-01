from __future__ import annotations

import base64
import io
import zipfile

from core import app_recovery


def test_snapshot_recovery_script_contains_project_files(tmp_path, monkeypatch):
    root = tmp_path / "app"
    (root / "core").mkdir(parents=True)
    (root / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (root / "core" / "x.py").write_text("X=1\n", encoding="utf-8")
    monkeypatch.setattr(app_recovery, "_ROOT", root)
    files = app_recovery.iter_project_files()
    fp, manifest = app_recovery.project_fingerprint(files)
    assert {m[0] for m in manifest} == {"app.py", "core/x.py"}
    zipped = app_recovery._snapshot_zip(files)
    with zipfile.ZipFile(io.BytesIO(zipped), "r") as zf:
        assert sorted(zf.namelist()) == ["app.py", "core/x.py"]
    script = app_recovery._recovery_script(zipped, fp, "2026-08-22T00:00:00+00:00")
    payload = script.split('SNAPSHOT_B64 = """', 1)[1].split('"""', 1)[0]
    assert base64.b64decode(payload) == zipped
