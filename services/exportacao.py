from __future__ import annotations
import io,json
import pandas as pd


def dataframe_excel_bytes(df: pd.DataFrame, sheet_name="Relatorio") -> bytes:
    bio=io.BytesIO()
    with pd.ExcelWriter(bio,engine="openpyxl") as w:
        df.to_excel(w,index=False,sheet_name=sheet_name[:31])
    return bio.getvalue()


def json_bytes(data) -> bytes:
    return json.dumps(data,ensure_ascii=False,indent=2,default=str).encode("utf-8")
