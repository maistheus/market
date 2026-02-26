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
AGG_FILE = DATA_DIR / "cards_daily_aggregated.csv"
ADVERTS_FILE = DATA_DIR / "cards_adverts_history.csv"

st.set_page_config(page_title="Ragnarok Cards Dashboard", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# FUNÇÕES DE CARREGAMENTO (com cache)
# -------------------------
@st.cache_data(ttl=3600)
def load_agg(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["date_collected"])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar {path.name}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_adverts(path: Path):
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, parse_dates=["date_collected"])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar {path.name}: {e}")
        return pd.DataFrame()

# -------------------------
# UTILITÁRIOS
# -------------------------
def safe_col(df, col, default=np.nan):
    return df[col] if col in df.columns else pd.Series([default]*len(df), index=df.index)

def top_n(df, col, n=10, ascending=False):
    return df.sort_values(col, ascending=ascending).head(n)

# -------------------------
# LOAD DATA
# -------------------------
agg = load_agg(AGG_FILE)
adverts = load_adverts(ADVERTS_FILE)

# -------------------------
# CHECK DATA
# -------------------------
if agg.empty:
    st.warning("Arquivo de base agregada (cards_daily_aggregated.csv) não encontrado ou vazio. Rode o processamento incremental primeiro.")
    st.stop()

# Normalize column names if necessary
agg.columns = [c.strip() for c in agg.columns]

# -------------------------
# SIDEBAR - FILTROS GLOBAIS
# -------------------------
st.sidebar.title("Filtros")
min_date = agg['date_collected'].min()
max_date = agg['date_collected'].max()
date_range = st.sidebar.date_input("Intervalo de datas", [min_date.date(), max_date.date()])

# Ensure date_range valid
start_date = pd.to_datetime(date_range[0])
end_date = pd.to_datetime(date_range[1]) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

# Unique cards
all_cards = sorted(agg['card_name'].dropna().unique())
selected_cards = st.sidebar.multiselect("Selecionar cartas (várias)", options=all_cards, default=[])

# Liquidity & volatility filters
min_listed = st.sidebar.slider("Lista mínima (listed_today >= )", min_value=int(agg['listed_today'].min()), max_value=int(agg['listed_today'].max()), value=int(max(1, agg['listed_today'].quantile(0.25))))
max_volatility = st.sidebar.slider("Volatilidade máxima (std_price <= )", min_value=float(0), max_value=float(agg['std_price'].fillna(0).max()), value=float(agg['std_price'].fillna(0).quantile(0.75)))

# Quick toggles
show_only_alerts = st.sidebar.checkbox("Mostrar só alertas (potential_buy/potential_sell)", value=False)

# -------------------------
# FILTRAR DADOS
# -------------------------
mask_date = (agg['date_collected'] >= start_date) & (agg['date_collected'] <= end_date)
df = agg.loc[mask_date].copy()

if selected_cards:
    df = df[df['card_name'].isin(selected_cards)]

# Apply liquidity/volatility filters
df = df[df['listed_today'] >= min_listed]
df = df[df['std_price'].fillna(0) <= max_volatility]

if show_only_alerts:
    df = df[(df.get('potential_buy', False)) | (df.get('potential_sell', False))]

# -------------------------
# Top row: KPIs and alerts
# -------------------------
st.title("Ragnarok — Dashboard de Compra & Revenda de Cartas")
st.markdown("Painel interativo para identificar oportunidades de compra, venda e monitorar liquidez/risco.")

k1, k2, k3, k4 = st.columns(4)
total_announcements = int(df['listed_today'].sum())
unique_cards = int(df['card_name'].nunique())
avg_volatility = float(df['std_price'].mean(skipna=True))
avg_turnover = float(df['turnover_rate'].mean(skipna=True))

k1.metric("Anúncios (visíveis no filtro)", f"{total_announcements:,}")
k2.metric("Cartas distintas", f"{unique_cards:,}")
k3.metric("Volatilidade média (std)", f"{avg_volatility:.2f}")
k4.metric("Turnover médio", f"{avg_turnover:.3f}")

# Alerts panels
st.markdown("### Alertas rápidos")
col_a1, col_a2, col_a3 = st.columns([1,1,2])

# Top liquid cards (by turnover_rate desc)
top_liquid = df.groupby('card_name').agg(listed=('listed_today','max'), turnover=('turnover_rate','mean')).reset_index()
top_liquid = top_liquid.sort_values('turnover', ascending=False).head(10)
with col_a1:
    st.write("Top Cartas Líquidas")
    st.dataframe(top_liquid.style.format({"listed":"{:,}", "turnover":"{:.3f}"}), height=250)

# Top volatility
top_vol = df.groupby('card_name').agg(std=('std_price','max'), listed=('listed_today','max')).reset_index().sort_values('std', ascending=False).head(10)
with col_a2:
    st.write("Top Volatilidade")
    st.dataframe(top_vol.style.format({"std":"{:.2f}", "listed":"{:,}"}), height=250)

# Buy / Sell signals
signals = df.groupby('card_name').agg(
    potential_buy=('potential_buy','max'),
    potential_sell=('potential_sell','max'),
    min_price=('min_price','min'),
    avg_price=('avg_price','mean'),
    listed=('listed_today','max'),
    turnover=('turnover_rate','mean')
).reset_index()

buy_signals = signals[signals['potential_buy']].sort_values('turnover', ascending=False).head(10)
sell_signals = signals[signals['potential_sell']].sort_values('turnover', ascending=False).head(10)

with col_a3:
    st.write("Sinais de Compra (verde) / Venda (vermelho)")
    col_buy, col_sell = st.columns(2)
    with col_buy:
        st.markdown("**Compra**")
        if not buy_signals.empty:
            st.dataframe(buy_signals[['card_name','min_price','avg_price','listed','turnover']].style.format({"min_price":"{:,}", "avg_price":"{:,}", "listed":"{:,}", "turnover":"{:.3f}"}))
        else:
            st.write("Nenhuma oportunidade de compra no filtro.")
    with col_sell:
        st.markdown("**Venda**")
        if not sell_signals.empty:
            st.dataframe(sell_signals[['card_name','min_price','avg_price','listed','turnover']].style.format({"min_price":"{:,}", "avg_price":"{:,}", "listed":"{:,}", "turnover":"{:.3f}"}))
        else:
            st.write("Nenhuma oportunidade de venda no filtro.")

# -------------------------
# Middle row: detalhe por carta (time series + histogram + heatmap)
# -------------------------
st.markdown("---")
st.markdown("## Análise por Carta")

# Select a card for detail
card_for_detail = st.selectbox("Escolha uma carta para detalhar (ou deixe em branco para top liquidas)", options=[""] + all_cards)

if card_for_detail:
    df_card = agg[agg['card_name'] == card_for_detail].sort_values('date_collected')
else:
    # take top liquid card if none selected
    top_card_name = top_liquid['card_name'].iloc[0] if not top_liquid.empty else None
    df_card = agg[agg['card_name'] == top_card_name].sort_values('date_collected') if top_card_name else pd.DataFrame()

if df_card.empty:
    st.info("Sem dados para a carta selecionada no intervalo/filtragem atual.")
else:
    # Time series: min/avg/max + rolling
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df_card['date_collected'], y=df_card['min_price'], mode='lines+markers', name='Min Price'))
    fig.add_trace(go.Scatter(x=df_card['date_collected'], y=df_card['avg_price'], mode='lines+markers', name='Avg Price'))
    fig.add_trace(go.Scatter(x=df_card['date_collected'], y=df_card['max_price'], mode='lines+markers', name='Max Price'))
    if 'rolling_avg_price' in df_card.columns:
        fig.add_trace(go.Scatter(x=df_card['date_collected'], y=df_card['rolling_avg_price'], mode='lines', name=f'Rolling Avg ({7}d)', line=dict(dash='dash')))
    fig.update_layout(title=f"Tendência de preço — {card_for_detail or top_card_name}", xaxis_title="Data", yaxis_title="Preço (zeny)", legend=dict(orientation="h"))
    st.plotly_chart(fig, use_container_width=True)

    # Histogram price distribution (last N days)
    last_window = df_card.tail(30)
    fig_h = px.histogram(last_window, x='avg_price', nbins=20, title=f"Distribuição de preços (ult. {len(last_window)} registros)")
    st.plotly_chart(fig_h, use_container_width=True)

    # Liquidity heatmap for this card (disappeared vs listed)
    heat = df_card[['date_collected','listed_today','disappeared_today']].set_index('date_collected').fillna(0)
    if not heat.empty:
        heat_df = heat[['listed_today','disappeared_today']].reset_index().melt(id_vars='date_collected', var_name='metric', value_name='value')
        fig_heat = px.bar(heat_df, x='date_collected', y='value', color='metric', title="Listagens vs Desaparecimentos (por dia)", barmode='group')
        st.plotly_chart(fig_heat, use_container_width=True)

# -------------------------
# Bottom row: scatter risk x opportunity + heatmap global
# -------------------------
st.markdown("---")
st.markdown("## Comparativo: Risco × Oportunidade")

df_scatter = df.groupby('card_name').agg(
    std_price=('std_price','mean'),
    margin=('margin_opportunity','mean'),
    listed=('listed_today','max'),
    potential_buy=('potential_buy','max'),
    potential_sell=('potential_sell','max')
).reset_index().dropna(subset=['std_price','margin'])

if df_scatter.empty:
    st.info("Sem dados suficientes para scatter plot.")
else:
    fig_s = px.scatter(df_scatter, x='std_price', y='margin', size='listed', color=df_scatter.apply(lambda r: 'Buy' if r['potential_buy'] else ('Sell' if r['potential_sell'] else 'Neutral'), axis=1),
                       hover_data=['card_name','listed'], title="Risco (std) x Oportunidade (margem)")
    fig_s.update_xaxes(title="Volatilidade (std price)")
    fig_s.update_yaxes(title="Margem (avg - min)")
    st.plotly_chart(fig_s, use_container_width=True)

# Global heatmap of turnover_rate (most frequent cards)
st.markdown("### Heatmap diário de Turnover (top cartas por movimento)")
turnover_pivot = agg.pivot_table(index='card_name', columns='date_collected', values='turnover_rate', aggfunc='mean').fillna(0)
# limit to top N by average turnover
topN = int(st.slider("N cartas para heatmap", min_value=5, max_value=50, value=20))
top_cards_by_turn = turnover_pivot.mean(axis=1).sort_values(ascending=False).head(topN).index
heat_df = turnover_pivot.loc[top_cards_by_turn]
fig_hm = px.imshow(heat_df, labels=dict(x="Data", y="Carta", color="Turnover"), aspect='auto', title="Turnover por dia (Top cartas)")
st.plotly_chart(fig_hm, use_container_width=True, height=400)

# -------------------------
# Tabela interativa completa e export
# -------------------------
st.markdown("---")
st.markdown("## Tabela de Dados (resultado do filtro)")

# show summary table
summary_cols = ['card_name','date_collected','min_price','avg_price','max_price','std_price','listed_today','disappeared_today','turnover_rate','rolling_avg_price','margin_opportunity','risk_score','potential_buy','potential_sell']
present_cols = [c for c in summary_cols if c in df.columns]
st.dataframe(df[present_cols].sort_values(['date_collected','card_name'], ascending=[False, True]).reset_index(drop=True), height=400)

# CSV export
@st.cache_data
def convert_df_to_csv(dataframe):
    return dataframe.to_csv(index=False).encode('utf-8')

csv = convert_df_to_csv(df[present_cols])
st.download_button(label="Download CSV (filtro atual)", data=csv, file_name="cards_filtered.csv", mime="text/csv")

st.markdown("### Observações / Notas")
st.markdown("""
- Os sinais `potential_buy` / `potential_sell` são regras iniciais (heurísticas) e devem ser ajustadas com base em sua experiência.
- Atualize a base (rodando o script de ingestão) diariamente antes de abrir o dashboard.
- Se quiser, eu posso transformar esse app em um deploy (Streamlit Cloud / VPS) e adicionar autenticação.
""")
