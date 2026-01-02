import streamlit as st
import pandas as pd
import json
import plotly.express as px

st.set_page_config(page_title="BetBot Stats", layout="wide")

st.title("📊 Statystyki Mojego Bota Bukmacherskiego")

# Wczytywanie danych
try:
    with open("coupons.json", "r") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
except:
    st.error("Nie znaleziono pliku coupons.json lub jest pusty.")
    st.stop()

# Podstawowe metryki
total_stake = df['stake'].sum()
# Obliczamy zysk: win_val - stake dla wygranych, oraz -stake dla przegranych
df['net_profit'] = df.apply(lambda x: x['win_val'] - x['stake'] if x['status'] == 'win' else (-x['stake'] if x['status'] == 'loss' else 0), axis=1)
total_profit = df['net_profit'].sum()
win_rate = (len(df[df['status'] == 'win']) / len(df[df['status'].isin(['win', 'loss'])])) * 100

col1, col2, col3 = st.columns(3)
col1.metric("Łączny Obrót", f"{total_stake:.2f} PLN")
col2.metric("Bilans (Profit)", f"{total_profit:.2f} PLN", delta=f"{total_profit:.2f} PLN")
col3.metric("Win Rate", f"{win_rate:.1f}%")

# Wykres progresji kapitału
st.subheader("📈 Progresja zysku w czasie")
df['cumulative_profit'] = df['net_profit'].cumsum()
fig = px.line(df, x=df.index, y='cumulative_profit', labels={'index': 'Kupony', 'cumulative_profit': 'Zysk (PLN)'})
st.plotly_chart(fig, use_container_width=True)

# Tabela z ostatnimi kuponami
st.subheader("📑 Ostatnie kupony")
st.dataframe(df.tail(10)[['status', 'stake', 'win_val', 'net_profit']].sort_index(ascending=False))
