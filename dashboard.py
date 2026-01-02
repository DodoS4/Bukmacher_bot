import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime
import os

# 1. KONFIGURACJA STRONY
st.set_page_config(
    page_title="BetBot Pro Dashboard",
    page_icon="🏆",
    layout="wide"
)

# Stylizacja CSS
st.markdown("""
    <style>
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Panel Statystyk Bota Bukmacherskiego")
st.markdown(f"Ostatnia aktualizacja danych: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
st.divider()

# 2. FUNKCJA WCZYTYWANIA DANYCH
def load_data():
    file_path = "coupons.json"
    if not os.path.exists(file_path):
        return pd.DataFrame()
    try:
        with open(file_path, "r") as f:
            content = f.read()
            if not content.strip():
                return pd.DataFrame()
            data = json.loads(content)
            return pd.DataFrame(data)
    except Exception:
        return pd.DataFrame()

df = load_data()

# 3. LOGIKA I OBLICZENIA
if df.empty:
    st.info("👋 Witaj! Twój bot nie wygenerował jeszcze żadnych danych.")
    st.warning("Uruchom bota w zakładce **GitHub Actions**, aby zobaczyć tutaj pierwsze dane.")
else:
    # Funkcja obliczania zysku netto
    def calculate_profit(row):
        try:
            stake = float(row.get('stake', 0))
            win_val = float(row.get('win_val', 0))
            status = row.get('status', 'pending')
            if status == 'win': return round(win_val - stake, 2)
            if status == 'loss': return -stake
            return 0.0
        except: return 0.0

    df['net_profit'] = df.apply(calculate_profit, axis=1)
    
    # Wyciąganie nazwy sportu
    def get_sport(matches):
        try:
            key = matches[0].get('sport_key', 'Inne')
            if 'soccer' in key: return "⚽ Piłka Nożna"
            if 'basketball' in key: return "🏀 Koszykówka"
            if 'icehockey' in key: return "🏒 Hokej"
            return f"❓ {key}"
        except: return "❓ Inne"

    df['sport'] = df['matches'].apply(get_sport)

    # Statystyki główne
    settled_df = df[df['status'].isin(['win', 'loss'])]
    total_settled = len(settled_df)
    wins = len(df[df['status'] == 'win'])
    total_profit = df['net_profit'].sum()
    total_stake = df['stake'].astype(float).sum()
    
    win_rate = (wins / total_settled * 100) if total_settled > 0 else 0
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0

    # 4. PANEL METRYK
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Wszystkie Kupony", len(df))
    m2.metric("Skuteczność", f"{win_rate:.1f}%")
    m3.metric("Bilans (Profit)", f"{total_profit:.2f} PLN", delta=f"{total_profit:.2f} PLN")
    m4.metric("ROI", f"{roi:.1f}%")

    st.divider()

    # 5. WYKRESY W ZAKŁADKACH
    tab1, tab2 = st.tabs(["📈 Historia Kapitału", "🎯 Analiza Sportów"])

    with tab1:
        col_l, col_r = st.columns([2, 1])
        with col_l:
            st.subheader("Progresja zysku")
            df['cumulative_profit'] = df['net_profit'].cumsum()
            fig_line = px.line(df, y='cumulative_profit', markers=True, template="plotly_dark")
            fig_line.update_traces(line_color='#00ff41')
            st.plotly_chart(fig_line, use_container_width=True)
        with col_r:
            st.subheader("Rozkład statusów")
            fig_pie = px.pie(df, names='status', color='status',
                            color_discrete_map={'win': '#2ecc71', 'loss': '#e74c3c', 'pending': '#95a5a6'},
                            hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

    with tab2:
        col_l2, col_r2 = st.columns(2)
        with col_l2:
            st.subheader("Zysk netto wg dyscypliny")
            sport_profit = df.groupby('sport')['net_profit'].sum().reset_index()
            fig_sport = px.bar(sport_profit, x='sport', y='net_profit', 
                              color='net_profit', color_continuous_scale='RdYlGn', template="plotly_dark")
            st.plotly_chart(fig_sport, use_container_width=True)
        with col_r2:
            st.subheader("Liczba kuponów wg dyscypliny")
            sport_count = df['sport'].value_counts().reset_index()
            # Naprawa błędu nazw kolumn w nowym pandas
            sport_count.columns = ['sport', 'count']
            fig_count = px.bar(sport_count, x='sport', y='count', template="plotly_dark")
            st.plotly_chart(fig_count, use_container_width=True)

    # 6. TABELA Z DANYMI
    st.subheader("📋 Lista Kuponów")
    display_df = df[['status', 'sport', 'stake', 'win_val', 'net_profit']].iloc[::-1]
    st.dataframe(display_df, use_container_width=True)

# Sidebar
st.sidebar.title("Nawigacja")
if st.sidebar.button("🔄 Odśwież dane"):
    st.rerun()
