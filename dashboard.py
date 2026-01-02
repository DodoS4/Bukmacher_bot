import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="BetBot Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. CLEAN WHITE UI (CSS) ---
st.markdown("""
    <style>
    /* Tło strony i ogólna typografia */
    .stApp {
        background-color: #f8f9fa;
        color: #1e1e1e;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    /* Karty statystyk w stylu Apple */
    [data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e1e4e8 !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02) !important;
        border-radius: 12px !important;
        padding: 20px !important;
    }

    [data-testid="stMetricValue"] {
        color: #000000 !important;
        font-weight: 700 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #6a737d !important;
        font-size: 0.9rem !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Przyciski i interakcje */
    .stButton>button {
        background-color: #ffffff !important;
        color: #1e1e1e !important;
        border: 1px solid #d1d5da !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }

    .stButton>button:hover {
        border-color: #0366d6 !important;
        color: #0366d6 !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }

    /* Nagłówki */
    h1, h2, h3 {
        color: #1b1f23 !important;
        font-weight: 700 !important;
    }
    
    /* Ukrycie dekoracji Streamlit */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. DANE ---
def load_data():
    file_path = "coupons.json"
    if not os.path.exists(file_path): return pd.DataFrame()
    try:
        with open(file_path, "r") as f:
            return pd.DataFrame(json.load(f))
    except: return pd.DataFrame()

df = load_data()

# --- 4. UKŁAD STRONY ---
col_header, col_refresh = st.columns([8, 1])

with col_header:
    st.title("BetBot Analytics")
    st.markdown(f"<p style='color: #6a737d;'>Raport wygenerowany: {datetime.now().strftime('%d.%m.%Y, %H:%M')}</p>", unsafe_allow_html=True)

with col_refresh:
    if st.button("Odśwież"):
        st.rerun()

st.divider()

if df.empty:
    st.info("Brak aktywnych danych. System oczekuje na plik coupons.json.")
else:
    # Kalkulacje
    df['net_profit'] = df.apply(lambda r: round(float(r['win_val']) - float(r['stake']), 2) if r['status'] == 'win' else -float(r['stake']), axis=1)
    df['cum_profit'] = df['net_profit'].cumsum()
    
    # Główne metryki
    m1, m2, m3, m4 = st.columns(4)
    total_profit = df['net_profit'].sum()
    win_rate = (len(df[df['status']=='win']) / len(df) * 100)
    
    m1.metric("Liczba kuponów", len(df))
    m2.metric("Skuteczność", f"{win_rate:.1f}%")
    m3.metric("Zysk netto", f"{total_profit:,.2f} PLN", delta=f"{total_profit:,.2f} PLN")
    m4.metric("ROI", f"{(total_profit / df['stake'].astype(float).sum() * 100):.1f}%")

    # Wykresy
    st.subheader("Historia portfela")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(df))), 
        y=df['cum_profit'],
        mode='lines',
        line=dict(color='#0366d6', width=3),
        fill='tozeroy',
        fillcolor='rgba(3, 102, 214, 0.05)',
    ))
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#1b1f23',
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(showgrid=True, gridcolor='#f1f1f1', title="ID Transakcji"),
        yaxis=dict(showgrid=True, gridcolor='#f1f1f1', title="Bilans (PLN)")
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabela
    st.subheader("Ostatnie zakłady")
    
    def color_status(val):
        color = '#28a745' if val == 'win' else '#d73a49' if val == 'loss' else '#6a737d'
        return f'background-color: transparent; color: {color}; font-weight: bold;'

    display_df = df[['status', 'stake', 'win_val', 'net_profit']].iloc[::-1]
    st.table(display_df.style.applymap(color_status, subset=['status']))
