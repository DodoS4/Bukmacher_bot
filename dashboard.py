import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime
import os

# --- 1. KONFIGURACJA ---
st.set_page_config(
    page_title="BetBot Dashboard",
    page_icon="📊",
    layout="wide"
)

# --- 2. FUNKCJE DANYCH ---
def load_data():
    file_path = "coupons.json"
    if not os.path.exists(file_path):
        return pd.DataFrame()
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            df = pd.DataFrame(data)
            if df.empty:
                return df
            # Konwersja na liczby, aby uniknąć błędów w obliczeniach
            df['stake'] = pd.to_numeric(df['stake'], errors='coerce')
            df['win_val'] = pd.to_numeric(df['win_val'], errors='coerce')
            return df
    except Exception:
        return pd.DataFrame()

# --- 3. LOGIKA I OBLICZENIA ---
df = load_data()

st.title("📊 Panel Statystyk Bota")
st.info(f"Ostatnia synchronizacja: {datetime.now().strftime('%H:%M:%S')}")

if df.empty:
    st.warning("Nie znaleziono danych w pliku coupons.json. Uruchom bota, aby wygenerować wyniki.")
else:
    # Obliczanie zysku netto dla każdego wiersza
    def calculate_net(row):
        if row['status'] == 'win':
            return round(row['win_val'] - row['stake'], 2)
        elif row['status'] == 'loss':
            return -row['stake']
        return 0.0

    df['net_profit'] = df.apply(calculate_net, axis=1)
    df['cumulative_profit'] = df['net_profit'].cumsum()

    # --- 4. METRYKI GŁÓWNE ---
    col1, col2, col3, col4 = st.columns(4)
    
    total_profit = df['net_profit'].sum()
    total_stake = df['stake'].sum()
    wins = len(df[df['status'] == 'win'])
    settled = len(df[df['status'].isin(['win', 'loss'])])
    win_rate = (wins / settled * 100) if settled > 0 else 0
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0

    col1.metric("Wszystkie kupony", len(df))
    col2.metric("Skuteczność (WR)", f"{win_rate:.1f}%")
    col3.metric("Zysk Netto", f"{total_profit:.2f} PLN", delta=f"{total_profit:.2f} PLN")
    col4.metric("ROI", f"{roi:.1f}%")

    st.divider()

    # --- 5. WYKRESY ---
    tab1, tab2 = st.tabs(["📈 Wykres Zysku", "📊 Rozkład Wyników"])

    with tab1:
        st.subheader("Progresja kapitału w czasie")
        fig_line = px.line(
            df, 
            y='cumulative_profit', 
            markers=True,
            labels={'cumulative_profit': 'Zysk skumulowany (PLN)', 'index': 'Numer kuponu'},
            title="Linia wzrostu portfela"
        )
        st.plotly_chart(fig_line, use_container_width=True)

    with tab2:
        st.subheader("Statusy kuponów")
        fig_pie = px.pie(
            df, 
            names='status', 
            color='status',
            color_discrete_map={'win': '#2ecc71', 'loss': '#e74c3c', 'pending': '#95a5a6'}
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 6. TABELA DANYCH ---
    st.subheader("📋 Historia zakładów")
    
    # Formatowanie kolorów w tabeli
    def highlight_status(val):
        if val == 'win': return 'color: green; font-weight: bold'
        if val == 'loss': return 'color: red; font-weight: bold'
        return 'color: gray'

    st.dataframe(
        df[['status', 'stake', 'win_val', 'net_profit']].iloc[::-1].style.applymap(highlight_status, subset=['status']),
        use_container_width=True
    )

# Sidebar
st.sidebar.header("Ustawienia")
if st.sidebar.button("Odśwież dane"):
    st.cache_data.clear()
    st.rerun()
