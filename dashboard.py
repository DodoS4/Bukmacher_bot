import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime

# 1. KONFIGURACJA STRONY
st.set_page_config(
    page_title="BetBot Pro Dashboard",
    page_icon="📈",
    layout="wide"
)

# Stylizacja CSS dla lepszego wyglądu
st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stMetric {
        background-color: #161b22;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #30363d;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Panel Statystyk Bota Bukmacherskiego")
st.markdown(f"Ostatnia aktualizacja: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
st.divider()

# 2. FUNKCJA WCZYTYWANIA DANYCH
def load_data():
    try:
        with open("coupons.json", "r") as f:
            content = f.read()
            if not content.strip():
                return pd.DataFrame()
            data = json.loads(content)
            return pd.DataFrame(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return pd.DataFrame()

df = load_data()

# 3. LOGIKA WYŚWIETLANIA
if df.empty or len(df) == 0:
    st.info("👋 Witaj! Twój bot nie wygenerował jeszcze żadnych kuponów.")
    st.warning("Uruchom bota ręcznie w zakładce **GitHub Actions**, aby zobaczyć tutaj pierwsze dane.")
    
    # Przykładowe metryki dla pustego stanu
    c1, c2, c3 = st.columns(3)
    c1.metric("Kupony", "0")
    c2.metric("Profit", "0.00 PLN")
    c3.metric("Win Rate", "0%")
else:
    # Obliczanie zysku netto dla każdego kuponu
    def calculate_profit(row):
        if row['status'] == 'win':
            return round(float(row['win_val']) - float(row['stake']), 2)
        elif row['status'] == 'loss':
            return -float(row['stake'])
        return 0.0

    df['net_profit'] = df.apply(calculate_profit, axis=1)

    # Statystyki ogólne
    total_coupons = len(df)
    settled_df = df[df['status'].isin(['win', 'loss'])]
    total_settled = len(settled_df)
    
    wins = len(df[df['status'] == 'win'])
    total_profit = df['net_profit'].sum()
    total_stake = df['stake'].sum()
    
    # BEZPIECZNE OBLICZANIE PROCENTÓW (Zapobiega ZeroDivisionError)
    win_rate = (wins / total_settled * 100) if total_settled > 0 else 0
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0

    # 4. PANEL METRYK (Górne karty)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Wszystkie Kupony", total_coupons)
    m2.metric("Skuteczność", f"{win_rate:.1f}%")
    
    # Kolor zielony dla zysku, czerwony dla straty
    m3.metric("Bilans Całkowity", f"{total_profit:.2f} PLN", 
              delta=f"{total_profit:.2f} PLN", delta_color="normal")
    
    m4.metric("ROI", f"{roi:.1f}%")

    st.divider()

    # 5. WYKRESY
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("📈 Historia Kapitału")
        df['cumulative_profit'] = df['net_profit'].cumsum()
        fig_line = px.line(
            df, 
            y='cumulative_profit', 
            markers=True,
            title="Zysk kumulatywny (PLN)",
            labels={'index': 'Kolejny kupon', 'cumulative_profit': 'Suma zysku'}
        )
        fig_line.update_traces(line_color='#00ff41')
        st.plotly_chart(fig_line, use_container_width=True)

    with col_right:
        st.subheader("🎯 Statusy")
        fig_pie = px.pie(
            df, 
            names='status', 
            color='status',
            color_discrete_map={'win': '#2ecc71', 'loss': '#e74c3c', 'pending': '#95a5a6'},
            hole=0.4
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # 6. TABELA Z DANYMI
    st.subheader("📋 Lista Kuponów")
    # Formaty tabeli - najnowsze na górze
    styled_df = df[['status', 'stake', 'win_val', 'net_profit']].iloc[::-1]
    
    st.dataframe(
        styled_df.style.background_gradient(subset=['net_profit'], cmap='RdYlGn'),
        use_container_width=True
    )

# Sidebar z informacjami pomocniczymi
st.sidebar.title("O Bocie")
st.sidebar.info("Bot analizuje kursy w poszukiwaniu niskiej wariancji u bukmacherów i wysyła typy Single/Double na Telegram.")
if st.sidebar.button("🔄 Odśwież Dane"):
    st.rerun()
