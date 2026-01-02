import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(
    page_title="BetBot Pro Intelligence",
    page_icon="💰",
    layout="wide"
)

# Rozszerzona stylizacja CSS dla lepszego UX
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .main-header { font-size: 2.5rem; font-weight: 800; color: #f0f2f6; margin-bottom: 0.5rem; }
    .status-card { padding: 1rem; border-radius: 0.5rem; background: #262730; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. FUNKCJE POMOCNICZE ---
@st.cache_data(ttl=60) # Cache danych na 60 sekund
def load_data():
    file_path = "coupons.json"
    if not os.path.exists(file_path): return pd.DataFrame()
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            df = pd.DataFrame(data)
            if df.empty: return df
            
            # Konwersja typów i dat
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
            else:
                df['date'] = datetime.now() # Fallback
            
            df['stake'] = pd.to_numeric(df['stake'], errors='coerce').fillna(0)
            df['win_val'] = pd.to_numeric(df['win_val'], errors='coerce').fillna(0)
            return df
    except Exception as e:
        st.error(f"Błąd ładowania danych: {e}")
        return pd.DataFrame()

def get_sport_label(matches):
    try:
        key = matches[0].get('sport_key', '').lower()
        mapping = {
            'soccer': "⚽ Piłka Nożna",
            'basketball': "🏀 Koszykówka",
            'icehockey': "🏒 Hokej",
            'tennis': "🎾 Tenis",
            'americanfootball': "🏈 Futbol Am."
        }
        for k, v in mapping.items():
            if k in key: return v
        return "❓ Inne"
    except: return "❓ Inne"

# --- 3. LOGIKA GŁÓWNA ---
df_raw = load_data()

if df_raw.empty:
    st.title("🚀 BetBot Pro")
    st.info("Oczekiwanie na pierwsze dane z GitHub Actions...")
    st.image("https://streamlit.io/images/brand/streamlit-mark-color.png", width=100)
else:
    # Processing
    df = df_raw.copy()
    df['net_profit'] = df.apply(lambda r: 
        round(r['win_val'] - r['stake'], 2) if r['status'] == 'win' 
        else (-r['stake'] if r['status'] == 'loss' else 0.0), axis=1)
    
    df['sport'] = df['matches'].apply(get_sport_label)
    
    # --- SIDEBAR: FILTRY ---
    st.sidebar.header("🎯 Filtry i Ustawienia")
    selected_sport = st.sidebar.multiselect("Dyscyplina", options=df['sport'].unique(), default=df['sport'].unique())
    date_range = st.sidebar.date_input("Zakres dat", [])
    
    # Aplikowanie filtrów
    df_filtered = df[df['sport'].isin(selected_sport)]
    
    # --- NAGŁÓWEK ---
    st.markdown('<p class="main-header">📊 Dashboard Analityczny BetBot</p>', unsafe_allow_html=True)
    st.caption(f"Aktualizacja: {datetime.now().strftime('%H:%M:%S')} | Dane: {len(df_filtered)} kuponów")

    # --- 4. KPI METRICS ---
    settled = df_filtered[df_filtered['status'].isin(['win', 'loss'])]
    total_profit = settled['net_profit'].sum()
    wins_count = len(settled[settled['status'] == 'win'])
    wr = (wins_count / len(settled) * 100) if not settled.empty else 0
    total_staked = settled['stake'].sum()
    roi = (total_profit / total_staked * 100) if total_staked > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zysk Netto", f"{total_profit:,.2f} PLN", delta=f"{roi:.1f}% ROI")
    c2.metric("Skuteczność (WR)", f"{wr:.1f}%", delta=f"{wins_count} wygranych")
    c3.metric("Obrót", f"{total_staked:,.2f} PLN")
    c4.metric("Średni Kurs", f"{(settled['win_val']/settled['stake']).mean():.2f}" if not settled.empty else "0.00")

    st.divider()

    # --- 5. WIZUALIZACJE ---
    col_main, col_side = st.columns([2, 1])

    with col_main:
        # Wykres skumulowanego zysku z wypełnieniem (Area Chart)
        st.subheader("Linia Kapitału (Equity Curve)")
        df_filtered['cum_profit'] = df_filtered['net_profit'].cumsum()
        
        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=list(range(len(df_filtered))), 
            y=df_filtered['cum_profit'],
            fill='tozeroy',
            line=dict(color='#00cf8d', width=3),
            name="Profit"
        ))
        fig_equity.update_layout(template="plotly_dark", margin=dict(l=20, r=20, t=20, b=20), height=350)
        st.plotly_chart(fig_equity, use_container_width=True)

    with col_side:
        st.subheader("Struktura Wyników")
        fig_pie = px.pie(
            df_filtered, names='status', 
            color='status',
            color_discrete_map={'win': '#00cf8d', 'loss': '#ff4b4b', 'pending': '#ffa500'},
            hole=0.6
        )
        fig_pie.update_layout(showlegend=False, template="plotly_dark", height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 6. SZCZEGÓŁY I TABELA ---
    t1, t2 = st.tabs(["🎾 Analiza Sportów", "📄 Historia Zakładów"])
    
    with t1:
        st.subheader("Efektywność wg dyscyplin")
        sport_stats = df_filtered.groupby('sport').agg({
            'net_profit': 'sum',
            'status': 'count'
        }).rename(columns={'status': 'Liczba'}).reset_index()
        
        fig_bar = px.bar(sport_stats, x='sport', y='net_profit', color='net_profit',
                         text='Liczba', color_continuous_scale='RdYlGn')
        st.plotly_chart(fig_bar, use_container_width=True)

    with t2:
        # Kolorowanie tabeli
        def color_status(val):
            color = '#2ecc71' if val == 'win' else '#e74c3c' if val == 'loss' else '#95a5a6'
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            df_filtered[['date', 'sport', 'stake', 'net_profit', 'status']].sort_index(ascending=False).style.applymap(color_status, subset=['status']),
            use_container_width=True
        )

# Przycisk odświeżania w sidebarze
if st.sidebar.button("⚡ Wymuś odświeżenie"):
    st.cache_data.clear()
    st.rerun()
