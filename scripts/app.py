"""Compatibilidade: inicia o app principal localizado na raiz."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[1] / "app.py"), run_name="__main__")
