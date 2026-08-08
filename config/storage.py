import os

GCS_BUCKET = os.getenv("GCS_BUCKET", "calendario-messiano-dados")
GCS_BASE = os.getenv("GCS_BASE", "ARQUIVO_PARA_CALENDARIO_TXT")

GCS_OBJECTS = {
    "calendario": os.getenv(
        "GCS_OBJECT",
        f"{GCS_BASE}/Calendario_Gregoriano_Messiano_4000ac_3000dc.txt",
    ),
    "lua": os.getenv(
        "GCS_MOON_OBJECT",
        f"{GCS_BASE}/fases_lua_completo/fases_lua_completo.txt",
    ),
    "estacoes": os.getenv(
        "GCS_SEASONS_OBJECT",
        f"{GCS_BASE}/marcos_estacoes_completo/marcos_estacoes_completo.txt",
    ),
    "pascoa": os.getenv(
        "GCS_EASTER_OBJECT",
        f"{GCS_BASE}/pascoa_15_ruben_completo/pascoa_15_ruben_completo.txt",
    ),
    "festas": os.getenv(
        "GCS_FEASTS_OBJECT",
        f"{GCS_BASE}/festas_biblicas_pre_cativeiro/festas_biblicas_pre_cativeiro.txt",
    ),
}

GOOGLE_CSE_API_KEY = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
GOOGLE_CSE_CX = os.getenv("GOOGLE_CSE_CX", "").strip()
