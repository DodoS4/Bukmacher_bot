import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime

# Konfiguracja strony
st.set_page_config(page_title="BetBot Dashboard", layout="wide", page_icon="📊")

# Stylizacja nagłówka
st.title("📊 Statystyki Mojego Bota Bukmacherskiego")
st.markdown("---")

# Funkcja do wczytywania danych
def load_data():
    try:
        with open("coupons.json", "r") as f:
            data = json.load(f)
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("⚠️ Baza danych jest pusta. Uruchom bota na GitHubie, aby wygenerować pierwsze kupony.")
else:
    # 1. PRZYGOTOWANIE DANYCH
    # Obliczamy zysk netto dla każdego kuponu
    def calculate_net(row):
        if row['status'] == 'win':
            return round(row['win_val'] - row['stake'], 2)
        elif row['status'] == 'loss':
            return -row['stake']
        return 0  # Dla statusu 'pending'

    df['net_profit'] = df.apply(calculate_net, axis=1)
    
    # Podstawowe statystyki
    total_coupons = len(df)
    settled_df = df[df['status'].isin(['win', 'loss'])]
    total_settled = len(settled_df)
    
    wins = len(df[df['status'] == 'win'])
    total_stake = df['stake'].sum()
    total_profit = df['net_profit'].sum()
    
    # Uniknięcie błędu dzielenia przez zero
    win_rate = (wins / total_settled * 100) if total_settled > 0 else 0
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0

    # 2. PANEL METRYK
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Wszystkie kupony", total_coupons)
    col2.metric("Skuteczność (Win Rate)", f"{win_rate:.1f}%")
    col3.metric("Łączny profit", f"{total_profit:+.2f} PLN", delta=f"{total_profit:.2f} PLN")
    col4.metric("ROI", f"{roi:.1f}%")

    st.markdown("---")

    # 3. WYKRESY
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.subheader("📈 Progresja kapitału")
        df['cumulative_profit'] = df['net_profit'].cumsum()
        fig_line = px.line(df, y='cumulative_profit', title="Zysk w czasie (PLN)",
                          labels={'index': 'Numer kuponu', 'cumulative_profit': 'Suma zysku'})
        st.plotly_chart(fig_line, use_container_width=True)

    with col_chart2:
        st.subheader("🎯 Rozkład statusów")
        fig_pie = px.pie(df, names='status', title="Udział statusów",
                        color='status', color_discrete_map={'win':'#2ca02c', 'loss':'#d62728', 'pending':'#7f7f7f'})
        st.plotly_chart(fig_pie, use_container_width=True)

    # 4. TABELA SZCZEGÓŁOWA
    st.subheader("📑 Ostatnie kupony")
    # Odwracamy kolejność, żeby najnowsze były na górze
    display_df = df[['status', 'stake', 'win_val', 'net_profit']].copy()
    display_df = display_df.iloc[::-1] 
    st.dataframe(display_df.style.applymap(
        lambda x: 'color: green' if x == 'win' else ('color: red' if x == 'loss' else 'color: gray'),
        subset=['status']
    ), use_container_width=True)

# Stopka
st.sidebar.info(f"Ostatnia aktualizacja strony: {datetime.now().strftime('%H:%M:%S')}")
if st.sidebar.button("Odśwież dane"):
    st.rerun()
