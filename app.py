import os
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from garmin_client import run_cloud_sync

# Configuração da Página
st.set_page_config(page_title="Garmin Health Monitor Pro", layout="wide")

# --- CONSTANTES DE ESTILO ---
COLOR_DARK_BLUE = "#001f3f"
COLOR_LIGHT_BLUE = "#ADD8E6"
COLOR_GRAY_DARK = "#333333"
COLOR_TEAL = "#008080"
COLOR_GOLD = "#FFD700"

DATA_PATH = os.path.join("data", "saude_cloud.csv")
PROFILE_PATH = os.path.join("data", "profile.json")

st.markdown(f"""
    <style>
    .main {{ background-color: #f0f2f6; }}
    [data-testid="stMetricValue"] {{ font-size: 32px; color: {COLOR_DARK_BLUE}; }}
    </style>
    """, unsafe_allow_html=True)


def load_data(file_path):
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        return df.sort_values('date', ascending=False).fillna(0)
    return pd.DataFrame()

def load_profile():
    if os.path.exists(PROFILE_PATH):
        with open(PROFILE_PATH, 'r') as f:
            return json.load(f)
    return {}

def sync_cloud(start_date=None, days=None):
    with st.spinner("Sincronizando com Garmin Cloud..."):
        run_cloud_sync(start_date=start_date, days=days)
    st.rerun()


# --- CARREGAMENTO ---
df_saude = load_data(DATA_PATH)
profile = load_profile()

# --- SIDEBAR ---
with st.sidebar:
    if profile:
        with st.expander(f"👤 {profile.get('full_name', 'Perfil')}", expanded=True):
            if profile.get('weight'):
                st.write(f"⚖️ **Peso:** {profile.get('weight')} kg")
            if profile.get('fitness_age'):
                st.write(f"🎂 **Idade Fitness:** {int(profile.get('fitness_age'))} anos")
            st.write(f"🌍 **Sistema:** {profile.get('unit_system', 'Métrico')}")
    
    st.header("Status de Dados")
    if not df_saude.empty:
        last_date_dt = df_saude['date'].max()
        st.info(f"📅 Dados até: **{last_date_dt.strftime('%d/%m/%Y')}**")
        
        if st.button("🔄 Sincronizar Novos Dados", use_container_width=True):
            # Busca do último dia que temos até hoje
            sync_cloud(start_date=last_date_dt)
    else:
        st.warning("Nenhum dado encontrado.")
        if st.button("🚀 Sincronização Inicial", use_container_width=True):
            sync_cloud(days=14)

# --- CONTEÚDO PRINCIPAL ---
st.title("🛡️ Garmin Health Monitor Pro")

if not df_saude.empty:
    latest = df_saude.iloc[0]

    # --- KPIs PRINCIPAIS ---
    calm_labels = ['CALM', 'BALANCED', 'RELAXED']
    calm_days = len(df_saude[df_saude['stress_qualifier'].str.upper().isin(calm_labels)])
    perc_calm = (calm_days / len(df_saude)) * 100

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Body Battery", f"{int(latest['body_battery_recent'])}%",
              f"Recarga: +{int(latest['bb_sleep_charge'])}")
    c2.metric("Dias Equilibrados", f"{perc_calm:.1f}%")
    c3.metric("FC Repouso (Avg)", f"{int(df_saude['resting_hr'].mean())} bpm")
    c4.metric("Alertas FC", int(df_saude['abnormal_hr_alerts'].sum()))

    st.divider()

    # --- GRID DE GRÁFICOS ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔋 Recuperação: Body Battery")
        fig_bb = go.Figure()
        fig_bb.add_trace(go.Scatter(
            x=df_saude['date'], y=df_saude['body_battery_max'],
            fill='tonexty', mode='lines', name='Máximo', line_color=COLOR_DARK_BLUE
        ))
        fig_bb.add_trace(go.Scatter(
            x=df_saude['date'], y=df_saude['body_battery_min'],
            fill='tozeroy', mode='lines', name='Mínimo', line_color=COLOR_LIGHT_BLUE
        ))
        fig_bb.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_bb, use_container_width=True)

    with col2:
        st.subheader("📊 Composição do Estresse Diário")
        fig_stress = go.Figure()
        fig_stress.add_trace(go.Bar(x=df_saude['date'], y=df_saude['stress_rest_min'],
                                   name="Repouso", marker_color="#cccccc"))
        fig_stress.add_trace(go.Bar(x=df_saude['date'], y=df_saude['stress_low_min'],
                                   name="Baixo", marker_color=COLOR_TEAL))
        fig_stress.add_trace(go.Bar(x=df_saude['date'], y=df_saude['stress_med_min'],
                                   name="Médio", marker_color="#ff8c00"))
        fig_stress.add_trace(go.Bar(x=df_saude['date'], y=df_saude['stress_high_min'],
                                   name="Alto", marker_color="#8b0000"))
        fig_stress.update_layout(barmode='stack', height=350, margin=dict(l=0, r=0, t=20, b=0),
                                legend=dict(orientation="h"))
        st.plotly_chart(fig_stress, use_container_width=True)

    col3, col4 = st.columns(2)

    with col3:
        st.subheader("😴 Estágios do Sono & Recuperação")
        fig_sleep = go.Figure()
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_deep'],
                                   name="Profundo", marker_color="#001a33"))
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_rem'],
                                   name="REM", marker_color="#004080"))
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_light'],
                                   name="Leve", marker_color="#3399ff"))
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_awake'],
                                   name="Acordado", marker_color="#ccdbe3"))

        # Rótulo de recarga de bateria
        sleep_sum = df_saude['sleep_rem'] + df_saude['sleep_deep'] + \
            df_saude['sleep_light'] + df_saude['sleep_awake']
        fig_sleep.add_trace(go.Scatter(
            x=df_saude['date'], y=sleep_sum + 0.5,
            text=df_saude['bb_sleep_charge'].apply(lambda x: f"+{int(x)}🔋"),
            mode="text", name="Recuperação BB", textposition="top center"
        ))
        fig_sleep.update_layout(barmode='stack', height=350, margin=dict(l=0, r=0, t=20, b=0),
                                legend=dict(orientation="h"))
        st.plotly_chart(fig_sleep, use_container_width=True)

    with col4:
        st.subheader("⚖️ Atividade: Ativo vs Sedentário")
        available_dates = df_saude['date'].dt.strftime('%Y-%m-%d').tolist()
        selected_date = st.selectbox("Selecione o dia para análise", available_dates)
        day_data = df_saude[df_saude['date'].dt.strftime('%Y-%m-%d') == selected_date].iloc[0]

        labels = ['Ativo', 'Sedentário']
        values = [day_data['active_time_min'], day_data['sedentary_time_min']]
        fig_pie = px.pie(names=labels, values=values,
                         color_discrete_sequence=[COLOR_TEAL, COLOR_GRAY_DARK], hole=0.4)
        fig_pie.update_layout(height=300, margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- LINHA FINAL: PASSOS E INTENSIDADE ---
    col5, col6 = st.columns(2)

    with col5:
        st.subheader("🏃 Movimentação: Passos & Calorias")
        fig_steps = go.Figure()
        fig_steps.add_trace(go.Bar(x=df_saude['date'], y=df_saude['steps'],
                                   name="Passos", marker_color=COLOR_LIGHT_BLUE, opacity=0.8))
        fig_steps.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['calories'],
                                       name="Calorias", yaxis="y2", line_color=COLOR_GOLD,
                                       line=dict(width=3)))
        fig_steps.update_layout(
            height=350, yaxis=dict(title="Passos"),
            yaxis2=dict(title="Calorias", overlaying="y", side="right"),
            legend=dict(orientation="h")
        )
        st.plotly_chart(fig_steps, use_container_width=True)

    with col6:
        st.subheader("🔥 Meta Semanal: Intensidade Acumulada")
        df_week = df_saude.head(7).iloc[::-1].copy()
        df_week['intensity_cum'] = df_week['intensity_min_total'].cumsum()

        fig_intensity = go.Figure()
        fig_intensity.add_trace(go.Scatter(
            x=df_week['date'], y=df_week['intensity_cum'],
            fill='tozeroy', name="Minutos Acumulados",
            line_color=COLOR_TEAL, mode='lines+markers'
        ))
        fig_intensity.add_hline(y=150, line_dash="dash", line_color="red",
                               annotation_text="Meta OMS (150 min)", annotation_position="top left")
        fig_intensity.update_layout(height=350, yaxis_title="Minutos (Acumulado)")
        st.plotly_chart(fig_intensity, use_container_width=True)

    col7, col8 = st.columns(2)
    with col7:
        st.subheader("📉 Frequência Cardíaca Diária")
        fig_hr = px.line(df_saude, x='date', y=['resting_hr', 'min_hr', 'max_hr'],
                        color_discrete_sequence=[COLOR_DARK_BLUE, COLOR_TEAL, "#D0021B"])
        fig_hr.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_hr, use_container_width=True)
    with col8:
        st.subheader("🫁 Respiração Média (Acordado)")
        fig_resp = px.line(df_saude, x='date', y='avg_respiration', markers=True,
                          color_discrete_sequence=[COLOR_TEAL])
        fig_resp.update_layout(height=300, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig_resp, use_container_width=True)

else:
    st.warning("Aguardando sincronização de dados...")

# Sidebar Sync
if st.sidebar.button("🔄 Sincronizar Nuvem"):
    sync_cloud()
