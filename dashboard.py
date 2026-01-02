import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- 1. KONFIGURACJA TERMINALA ---
st.set_page_config(
    page_title="Terminal Analityczny // BetBot Pro",
    page_icon="📉",
    layout="wide"
)

# --- 2. FINANCIAL DARK UI (CSS) ---
st.markdown("""
    <style>
    /* Głęboki granatowy motyw profesjonalny */
    .stApp {
        background-color: #0b0e14;
        color: #d1d4dc;
        font-family: 'Inter', -apple-system, sans-serif;
    }

    /* Karty Metryk (Kompaktowe) */
    [data-testid="stMetric"] {
        background-color: #131722 !important;
        border: 1px solid #363a45 !important;
        border-radius: 4px !important;
        padding: 15px !important;
    }

    [data-testid="stMetricValue"] {
        color: #ffffff !important;
        font-size: 1.6rem !important;
        font-weight: 600 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #787b86 !important;
        font-size: 0.8rem !important;
    }

    /* Stylizacja tabeli TradingView */
    .stDataFrame {
        border: 1px solid #363a45;
    }

    /* Nagłówki sekcji */
    h1, h2, h3 {
        color: #ffffff !important;
        font-weight: 500 !important;
        letter-spacing: -0.5px;
    }

    /* Pasek boczny */
    [data-testid="stSidebar"] {
        background-color: #131722 !important;
        border-right: 1px solid #363a45;
    }

    /* Ukrycie elementów Streamlit */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. SILNIK DANYCH ---
def load_data():
    file_path = "coupons.json"
    if not os.path.exists(file_path):
        return pd.DataFrame()
    try:
        with open(file_path, "r") as f:
            return pd.DataFrame(json.load(f))
    except:
        return pd.DataFrame()

df = load_data()

# --- 4. LAYOUT GŁÓWNY ---
st.markdown("### TERMINAL ANALITYCZNY V2.0")
st.caption(f"Status: Połączono // Ostatnia aktualizacja: {datetime.now().strftime('%H:%M:%S')}")

if df.empty:
    st.warning("OCZEKIWANIE NA DANE WEJŚCIOWE (coupons.json)...")
else:
    # Obliczenia finansowe
    df['stake'] = pd.to_numeric(df['stake'])
    df['win_val'] = pd.to_numeric(df['win_val'])
    df['net_profit'] = df.apply(lambda r: round(r['win_val'] - r['stake'], 2) if r['status'] == 'win' else -r['stake'], axis=1)
    df['cum_profit'] = df['net_profit'].cumsum()
    
    # Panel KPI
    m1, m2, m3, m4 = st.columns(4)
    total_profit = df['net_profit'].sum()
    total_staked = df['stake'].sum()
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0
    
    m1.metric("BILANS CAŁKOWITY", f"{total_profit:,.2f} PLN")
    m2.metric("SKUTECZNOŚĆ", f"{(len(df[df['status']=='win'])/len(df)*100):.1f}%")
    m3.metric("ROI (%)", f"{roi:.2f}%", delta=f"{roi:.2f}%")
    m4.metric("OBRÓT (VOL)", f"{total_staked:,.2f} PLN")

    st.markdown("---")

    # Wykres Progresji (Style: TradingView)
    st.subheader("Krzywa Kapitału (Equity)")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(df))), 
        y=df['cum_profit'],
        mode='lines',
        line=dict(color='#2962ff', width=3), # Klasyczny błękit finansowy
        fill='tozeroy',
        fillcolor='rgba(41, 98, 255, 0.1)',
        hovertemplate='Zysk: %{y:.2f} PLN<extra></extra>'
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#787b86',
        margin=dict(l=0, r=0, t=10, b=0),
        height=400,
        xaxis=dict(showgrid=True, gridcolor='#1e222d', title="Kolejne Zakłady"),
        yaxis=dict(showgrid=True, gridcolor='#1e222d', title="Kapitał (PLN)")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabela Operacji
    st.subheader("Log Transakcyjny")
    
    def style_status(val):
        color = '#089981' if val == 'win' else '#f23645' if val == 'loss' else '#787b86'
        return f'color: {color}; font-weight: bold;'

    # Wyświetlamy tylko kluczowe dane finansowe
    log_df = df[['status', 'stake', 'win_val', 'net_profit']].iloc[::-1]
    st.dataframe(
        log_df.style.applymap(style_status, subset=['status']),
        use_container_width=True,
        height=300
    )

# Sidebar z narzędziami
with st.sidebar:
    st.markdown("### PANEL KONTROLNY")
    if st.button("ODŚWIEŻ TERMINAL"):
        st.rerun()
    
    st.markdown("---")
    st.markdown("Automatyzacja: **Aktywna**")
    st.markdown("Źródło danych: `JSON_FEED`")
