import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- 1. KONFIGURACJA TERMINALA ---
st.set_page_config(
    page_title="BETBOT_OS // TERMINAL",
    page_icon="📟",
    layout="wide"
)

# --- 2. CYBERPUNK CSS UI ---
st.markdown("""
    <style>
    /* Główny kontener Matrix */
    .stApp {
        background-color: #050505;
        color: #00ff41;
        font-family: 'Courier New', Courier, monospace;
    }

    /* Neonowe karty statystyk (Glow Effect) */
    [data-testid="stMetric"] {
        background: rgba(10, 10, 10, 0.9) !important;
        border: 1px solid #bc13fe !important;
        box-shadow: 0 0 15px rgba(188, 19, 254, 0.4) !important;
        border-radius: 4px !important;
        padding: 20px !important;
    }

    [data-testid="stMetricValue"] {
        color: #00ff41 !important;
        text-shadow: 0 0 10px #00ff41;
        font-size: 2rem !important;
    }

    [data-testid="stMetricLabel"] {
        color: #bc13fe !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        font-weight: bold;
    }

    /* Nagłówki */
    h1, h2, h3 {
        color: #bc13fe !important;
        text-shadow: 0 0 10px rgba(188, 19, 254, 0.8);
        border-bottom: 1px solid #bc13fe;
        padding-bottom: 10px;
    }

    /* Customizacja Scrollbara */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-track { background: #050505; }
    ::-webkit-scrollbar-thumb { background: #bc13fe; }

    /* Ukrywanie standardowych elementów Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. LOGIKA DANYCH ---
def load_data():
    file_path = "coupons.json"
    if not os.path.exists(file_path):
        return pd.DataFrame()
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            return pd.DataFrame(data)
    except:
        return pd.DataFrame()

df = load_data()

# --- 4. INTERFEJS TERMINALA ---
st.markdown("# 📟 BETBOT_PRO // CORE_INTERFACE")
st.markdown(f"**SYSTEM_STATUS:** `OPERATIONAL` | **TIME:** `{datetime.now().strftime('%H:%M:%S')}`")

if df.empty:
    st.error("❌ ERROR: DATA_SOURCE_NOT_FOUND // Oczekiwanie na coupons.json")
    st.info("Uruchom bota, aby wygenerować dane wejściowe.")
else:
    # Obliczenia
    def calc_profit(row):
        s = float(row.get('stake', 0))
        w = float(row.get('win_val', 0))
        if row.get('status') == 'win': return round(w - s, 2)
        if row.get('status') == 'loss': return -s
        return 0.0

    df['net_profit'] = df.apply(calc_profit, axis=1)
    df['cum_profit'] = df['net_profit'].cumsum()
    
    # Metryki Główne
    m1, m2, m3, m4 = st.columns(4)
    
    total_profit = df['net_profit'].sum()
    win_rate = (len(df[df['status']=='win']) / len(df[df['status']!='pending']) * 100) if len(df[df['status']!='pending']) > 0 else 0
    
    m1.metric("TOTAL_TRADES", len(df))
    m2.metric("WIN_RATE", f"{win_rate:.1f}%")
    m3.metric("NET_PROFIT", f"{total_profit:.2f} PLN", delta=f"{total_profit:.2f} PLN")
    m4.metric("ROI", f"{(total_profit / df['stake'].astype(float).sum() * 100):.1f}%")

    st.markdown("### 📈 EQUITY_CURVE // ANALYST")
    
    # Cyberpunkowy Wykres
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(df))), 
        y=df['cum_profit'],
        mode='lines+markers',
        line=dict(color='#00ff41', width=4),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 65, 0.1)',
        marker=dict(size=8, color='#bc13fe', symbol='square')
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#00ff41',
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="TRADE_ID"),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', title="PLN_BALANCE")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabela transakcji
    st.markdown("### 📄 TRANSACTION_LOG")
    
    def color_status(val):
        color = '#00ff41' if val == 'win' else '#ff4b4b' if val == 'loss' else '#bc13fe'
        return f'color: {color}'

    styled_df = df[['status', 'stake', 'win_val', 'net_profit']].iloc[::-1]
    st.dataframe(styled_df.style.applymap(color_status, subset=['status']), use_container_width=True)

# Sidebar
with st.sidebar:
    st.markdown("### 🛠 SYSTEM_TOOLS")
    if st.button("RELOAD_SYSTEM"):
        st.rerun()
    st.markdown("---")
    st.markdown("BUILD: `v2.0.4-NEON`")

