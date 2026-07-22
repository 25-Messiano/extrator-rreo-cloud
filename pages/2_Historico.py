from __future__ import annotations

import pandas as pd
import streamlit as st

from core.database import Database

st.set_page_config(page_title="Histórico", page_icon="🕘", layout="wide")
st.title("🕘 Histórico")
rows = Database().list_history(200)
if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.info("Ainda não há processamentos registrados.")
