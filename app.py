# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# -------------------------
# CONFIGURAÇÃO DE ARQUIVOS
# -------------------------
DATA_DIR = Path(".")
# Updated extensions to .parquet
AGG_FILE = DATA_DIR / "cards_daily_aggregated.parquet"
ADVERTS_FILE = DATA_DIR / "cards_adverts_history.parquet"

st.set_page_config(page_title="Ragnarok Cards Dashboard", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# FUNÇÕES DE CARREGAMENTO (com cache)
# -------------------------
@st.cache_data(ttl=3600)
def load_agg(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        # Changed to read_parquet with pyarrow engine
        df = pd.read_parquet(path, engine='pyarrow')
        # Ensure date_collected is datetime (Parquet usually preserves this, but safety first)
        if 'date_collected' in df.columns:
            df['date_collected'] = pd.to_datetime(df['date_collected'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar {path.name}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_adverts(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        # Changed to read_parquet
        df = pd.read_parquet(path, engine='pyarrow')
        if 'date_collected' in df.columns:
            df['date_collected'] = pd.to_datetime(df['date_collected'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar {path.name}: {e}")
        return pd.DataFrame()

# ... [The rest of your filtering and chart logic remains the same] ...

# -------------------------
# LOAD DATA
# -------------------------
agg = load_agg(AGG_FILE)
adverts = load_adverts(ADVERTS_FILE)

# -------------------------
# CHECK DATA
# -------------------------
if agg.empty:
    st.warning(f"Arquivo {AGG_FILE.name} não encontrado ou vazio. Rode o scraper primeiro.")
    st.stop()

# ... [Rest of the script follows: Sidebar, KPIs, Charts, and Table] ...
