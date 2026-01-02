import streamlit as st
import pandas as pd
import json
import plotly.express as px
from datetime import datetime
import os

# 1. KONFIGURACJA STRONY
st.set_page_config(
    page_title="BetBot Pro Dashboard",
    page_icon="📈",
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
    except (json.JSONDecodeError, Exception):
        return pd.DataFrame()

df = load_data()

# 3. LOGIKA WYŚWIETLANIA
if df.empty:
    st.info("👋 Witaj! Twój bot nie wygenerował jeszcze żadnych danych lub plik coupons.json jest pusty.")
    st.warning("Uruchom bota ręcznie w zakładce **GitHub Actions**, aby pobrać pierwsze mecze.")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Kupony", "0")
    c2.metric("Profit", "0.00 PLN")
    c3.metric("Win Rate", "0%")
else:
    # Obliczanie zysku netto
    def calculate_profit(row):
        try:
            stake = float(row.get('stake', 0))
            win_val = float(row.get('win_val', 0))
            status = row.get('status', 'pending')
            
            if status == 'win':
                return round(win_val - stake, 2)
            elif status == 'loss':
                return -stake
            return 0.0
        except:
            return 0.0

    df['net_profit'] = df.apply(calculate_profit, axis=1)

    # Statystyki ogólne
    total_coupons = len(df)
    settled_df = df[df['status'].isin(['win', 'loss'])]
    total_settled = len(settled_df)
    
    wins = len(df[df['status'] == 'win'])
    total_profit = df['net_profit'].sum()
    total_stake = df['stake'].astype(float).sum()
    
    # Bezpieczne obliczanie procentów
    win_rate = (wins / total_settled * 100) if total_settled > 0 else 0
    roi = (total_profit / total_stake * 100) if total_stake > 0 else 0

    # 4. PANEL METRYK
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Wszystkie Kupony", total_coupons)
    m2.metric("Skuteczność", f"{win_rate:.1f}%")
    m3.metric("Bilans Całkowity", f"{total_profit:.2f} PLN", delta=f"{total_profit:.2f} PLN")
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
            template="plotly_dark"
        )
        fig_line.update_traces(line_color='#00ff41')
        st.plotly_chart(fig_line, use_container_width=True)

    with col_right:
        st.subheader("🎯 Statusy")
        if not df['status'].empty:
            fig_pie = px.pie(
                df, 
                names='status', 
                color='status',
                color_discrete_map={'win': '#2ecc71', 'loss': '#e74c3c', 'pending': '#95a5a6'},
                hole=0.4,
                template="plotly_dark"
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.write("Brak statusów do wyświetlenia.")

    # 6. TABELA Z DANYMI (Poprawiona - bez stylizacji powodującej błędy)
    st.subheader("📋 Lista Kuponów")
    
    # Wybieramy kolumny i odwracamy kolejność (najnowsze na górze)
    if not df.empty:
        display_cols = ['status', 'stake', 'win_val', 'net_profit']
        # Sprawdzamy czy kolumny istnieją w DF
        available_cols = [c for c in display_cols if c in df.columns]
        table_df = df[available_cols].iloc[::-1]
        
        st.dataframe(table_df, use_container_width=True)

# Sidebar
st.sidebar.title("Opcje")
if st.sidebar.button("🔄 Odśwież stronę"):
    st.rerun()

st.sidebar.divider()
st.sidebar.write("System: **Bukmacher Bot Pro**")
st.sidebar.write("Status bazy: ✅ Połączono")
