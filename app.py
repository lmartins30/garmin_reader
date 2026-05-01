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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEALTH_DATA_PATH = os.path.join(BASE_DIR, "data", "saude_cloud.csv")
ACTIVITY_DATA_PATH = os.path.join(BASE_DIR, "data", "atividades_cloud.csv")
PROFILE_PATH = os.path.join(BASE_DIR, "data", "profile.json")

st.markdown(f"""
    <style>
    .main {{ background-color: #f0f2f6; }}
    [data-testid="stMetricValue"] {{ font-size: 32px; color: {COLOR_DARK_BLUE}; }}
    </style>
    """, unsafe_allow_html=True)


# --- FUNÇÕES DE DADOS ---

def load_health_data():
    if os.path.exists(HEALTH_DATA_PATH):
        df = pd.read_csv(HEALTH_DATA_PATH)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=True)
        
        # Feature Engineering de Saúde
        df['rhr_ma7'] = df['resting_hr'].rolling(window=7).mean()
        df['steps_ma7'] = df['steps'].rolling(window=7).mean()
        df['calories_ma7'] = df['calories'].rolling(window=7).mean()
        df['vo2_max'] = df['vo2_max'].ffill()
        
        # Recovery Score Feature: Delta RHR em relação à média
        df['rhr_delta'] = df['resting_hr'] - df['rhr_ma7']
        
        return df.sort_values('date', ascending=False).fillna(0)
    return pd.DataFrame()

def load_activity_data():
    if os.path.exists(ACTIVITY_DATA_PATH):
        df = pd.read_csv(ACTIVITY_DATA_PATH)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date', ascending=True)
        
        # Feature: Índice de Eficiência Cardíaca (Pace / HR)
        # Quanto maior, mais eficiente (mais "ritmo" por "batida")
        # Usamos 1/pace para ter velocidade, e dividimos pela FC
        df['cardiac_efficiency'] = df.apply(
            lambda x: (1 / x['avg_pace'] / x['avg_hr'] * 1000) if x['avg_pace'] > 0 and x['avg_hr'] > 0 else 0, axis=1
        )
        
        # Feature: ACWR (Acute:Chronic Workload Ratio) baseado em duração
        df['load_acute'] = df['duration_min'].rolling(window=7, min_periods=1).mean()
        df['load_chronic'] = df['duration_min'].rolling(window=28, min_periods=1).mean()
        df['acwr'] = df['load_acute'] / df['load_chronic']
        
        return df.sort_values('date', ascending=False)
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


# --- COMPONENTES DA UI ---

def render_sidebar(profile, df_health):
    with st.sidebar:
        if profile:
            with st.expander(f"👤 {profile.get('full_name', 'Perfil')}", expanded=True):
                if profile.get('weight'):
                    st.write(f"⚖️ **Peso:** {profile.get('weight')} kg")
                if profile.get('fitness_age'):
                    st.write(f"🎂 **Idade Fitness:** {int(profile.get('fitness_age'))} anos")
                st.write(f"🌍 **Sistema:** {profile.get('unit_system', 'Métrico')}")
        
        st.header("Status de Dados")
        if not df_health.empty:
            last_date_dt = df_health['date'].max()
            st.info(f"📅 Dados até: **{last_date_dt.strftime('%d/%m/%Y')}**")
            
            if st.button("🔄 Sincronizar Novos Dados", use_container_width=True):
                sync_cloud(start_date=last_date_dt)
        else:
            st.warning("Nenhum dado encontrado.")
            if st.button("🚀 Sincronização Inicial", use_container_width=True):
                sync_cloud(days=14)
        
        if st.button("🔄 Sincronizar Tudo", use_container_width=True, key="sync_all"):
            sync_cloud(days=14)

def render_health_tab(df_saude):
    if df_saude.empty:
        st.warning("Aguardando sincronização de dados de saúde...")
        return

    latest = df_saude.iloc[0]

    # KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Body Battery", f"{int(latest['body_battery_recent'])}%", f"Recarga: +{int(latest['bb_sleep_charge'])}")
    eff_val = latest.get('sleep_efficiency', 0)
    c2.metric("Eficiência de Sono", f"{eff_val:.1f}%", delta="Ótima" if eff_val > 90 else "Alerta" if eff_val < 80 else None)
    avg_rhr = df_saude['resting_hr'].mean()
    delta_rhr = latest['resting_hr'] - avg_rhr
    c3.metric("FC Repouso", f"{int(latest['resting_hr'])} bpm", f"{delta_rhr:.1f} vs avg", delta_color="inverse")
    c4.metric("Status de Treino", latest.get('training_status', 'N/A'))

    st.divider()

    # Performance & Trends
    st.subheader("📈 Performance & Tendências (Long Term)")
    t1, t2 = st.columns(2)
    with t1:
        fig_rhr = go.Figure()
        fig_rhr.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['resting_hr'], mode='markers', name='Diário', marker=dict(color=COLOR_LIGHT_BLUE, size=4)))
        fig_rhr.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['rhr_ma7'], mode='lines', name='Média 7 dias', line=dict(color=COLOR_DARK_BLUE, width=3)))
        fig_rhr.update_layout(title="Tendência de FC de Repouso", height=300, margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_rhr, use_container_width=True)
    with t2:
        df_vo2 = df_saude[df_saude['vo2_max'] > 0]
        if not df_vo2.empty:
            fig_vo2 = px.line(df_vo2, x='date', y='vo2_max', markers=True, color_discrete_sequence=[COLOR_TEAL], title="Evolução do VO2 Max")
            fig_vo2.update_layout(height=300, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_vo2, use_container_width=True)
        else:
            st.info("Dados de VO2 Max insuficientes.")

    t3, t4 = st.columns(2)
    with t3:
        fig_steps = go.Figure()
        fig_steps.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['steps'], mode='markers', name='Diário', marker=dict(color=COLOR_LIGHT_BLUE, size=4)))
        fig_steps.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['steps_ma7'], mode='lines', name='Média 7 dias', line=dict(color=COLOR_GOLD, width=3)))
        fig_steps.update_layout(title="Tendência de Passos", height=300, margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_steps, use_container_width=True)
    with t4:
        fig_cal = go.Figure()
        fig_cal.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['calories'], mode='markers', name='Diário', marker=dict(color="#FFDAB9", size=4)))
        fig_cal.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['calories_ma7'], mode='lines', name='Média 7 dias', line=dict(color="#FF4500", width=3)))
        fig_cal.update_layout(title="Tendência de Calorias", height=300, margin=dict(l=0, r=0, t=40, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_cal, use_container_width=True)

    st.divider()
    
    # Recuperação e Sono (Gráficos originais simplificados)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔋 Recuperação: Body Battery")
        fig_bb = go.Figure()
        fig_bb.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['body_battery_max'], fill='tonexty', mode='lines', name='Máximo', line_color=COLOR_DARK_BLUE))
        fig_bb.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['body_battery_min'], fill='tozeroy', mode='lines', name='Mínimo', line_color=COLOR_LIGHT_BLUE))
        fig_bb.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_bb, use_container_width=True)
    with col2:
        st.subheader("📊 Composição do Estresse Diário")
        fig_stress = go.Figure()
        for col, label, color in [('stress_rest_min', 'Repouso', '#cccccc'), ('stress_low_min', 'Baixo', COLOR_TEAL), ('stress_med_min', 'Médio', '#ff8c00'), ('stress_high_min', 'Alto', '#8b0000')]:
            fig_stress.add_trace(go.Bar(x=df_saude['date'], y=df_saude[col], name=label, marker_color=color))
        fig_stress.update_layout(barmode='stack', height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_stress, use_container_width=True)

def render_activities_tab(df_act):
    if df_act.empty:
        st.warning("Aguardando sincronização de atividades...")
        return

    st.subheader("🏃 Histórico de Atividades")
    
    # Filtros
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        tipos = ['Todas'] + sorted(df_act['type'].unique().tolist())
        tipo_sel = st.selectbox("Filtrar por Tipo", tipos)
    
    df_filtered = df_act.copy()
    if tipo_sel != 'Todas':
        df_filtered = df_filtered[df_filtered['type'] == tipo_sel]
    
    # KPIs de Atividade
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Atividades", len(df_filtered))
    c2.metric("Distância Total", f"{df_filtered['distance'].sum():.1f} km")
    c3.metric("Duração Total", f"{df_filtered['duration_min'].sum()/60:.1f} h")
    c4.metric("Calorias Totais", f"{int(df_filtered['calories'].sum())} kcal")

    st.divider()

    # Gráfico de Volume Semanal
    st.markdown("##### 📊 Volume por Atividade")
    fig_vol = px.bar(df_filtered, x='date', y='distance', color='type', 
                     hover_data=['name', 'duration_min', 'avg_pace'],
                     title="Distância por Atividade (km)",
                     color_discrete_sequence=px.colors.qualitative.Safe)
    fig_vol.update_layout(height=400)
    st.plotly_chart(fig_vol, use_container_width=True)

    # Tabela Detalhada
    st.markdown("##### 📝 Detalhes das Atividades")
    df_display = df_filtered[['date', 'name', 'type', 'distance', 'duration_min', 'avg_pace', 'avg_hr', 'vo2_max']].copy()
    df_display.columns = ['Data', 'Nome', 'Tipo', 'Dist (km)', 'Dur (min)', 'Ritmo (min/km)', 'FC Média', 'VO2 Max']
    st.dataframe(df_display, use_container_width=True, hide_index=True)


def render_insights_tab(df_health, df_act):
    if df_health.empty or df_act.empty:
        st.warning("Dados insuficientes para gerar insights avançados. Sincronize saúde e atividades.")
        return

    st.subheader("🧠 Análise Preditiva & Performance")

    # Cruzamento de dados: Pega a última atividade e o sono da noite anterior
    latest_act = df_act.iloc[0]
    latest_health = df_health.iloc[0]
    
    col_i1, col_i2, col_i3, col_i4 = st.columns(4)

    # 1. ACWR (Acute:Chronic Workload Ratio)
    acwr = latest_act.get('acwr', 1.0)
    status_acwr = "Sweet Spot" if 0.8 <= acwr <= 1.3 else "Risco de Lesão" if acwr > 1.5 else "Subtreino"
    col_i1.metric("ACWR (Workload)", f"{acwr:.2f}", status_acwr, delta_color="inverse" if acwr > 1.5 else "normal")
    
    # 2. Cardiac Efficiency Index (Média das últimas 5 atividades de corrida)
    df_runs = df_act[df_act['type'] == 'running'].head(5)
    if not df_runs.empty:
        eff_idx = df_runs['cardiac_efficiency'].mean()
        prev_eff = df_act[df_act['type'] == 'running'].iloc[5:10]['cardiac_efficiency'].mean() if len(df_act) > 10 else eff_idx
        col_i2.metric("Eficiência Cardíaca", f"{eff_idx:.2f}", f"{eff_idx - prev_eff:.2f} vs ant")
    
    # 3. Recovery Efficiency (Impacto do treino no RHR de hoje)
    # RHR Delta: RHR hoje vs média 7d. Se positivo, indica estresse.
    rhr_delta = latest_health.get('rhr_delta', 0)
    recovery_status = "Recuperado" if rhr_delta <= 0 else "Estressado" if rhr_delta > 3 else "Moderado"
    col_i3.metric("Recuperação (RHR Delta)", f"{rhr_delta:+.1f} bpm", recovery_status, delta_color="inverse")

    # 4. Sleep Impact on Performance (Média de Eficiência do Sono vs VO2 Max)
    sleep_eff = df_health['sleep_efficiency'].mean()
    col_i4.metric("Qualidade Base (Sono)", f"{sleep_eff:.1f}%")

    st.divider()

    # Gráficos de Correlação
    c_col1, c_col2 = st.columns(2)
    
    with c_col1:
        st.markdown("##### 📉 Evolução do ACWR (Gestão de Carga)")
        fig_acwr = go.Figure()
        fig_acwr.add_trace(go.Scatter(x=df_act['date'], y=df_act['acwr'], mode='lines+markers', name="ACWR", line_color=COLOR_TEAL))
        # Zonas de segurança
        fig_acwr.add_hrect(y0=0.8, y1=1.3, fillcolor="green", opacity=0.1, line_width=0, annotation_text="Sweet Spot")
        fig_acwr.add_hrect(y0=1.5, y1=2.5, fillcolor="red", opacity=0.1, line_width=0, annotation_text="Danger Zone")
        fig_acwr.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_acwr, use_container_width=True)

    with c_col2:
        st.markdown("##### 🏎️ Eficiência Cardíaca por Atividade (Corrida)")
        if not df_runs.empty:
            fig_eff = px.scatter(df_runs, x='date', y='cardiac_efficiency', size='distance', 
                                 color='avg_hr', title="Ritmo por Batimento (Maior é melhor)",
                                 color_continuous_scale='RdYlGn_r')
            fig_eff.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=0))
            st.plotly_chart(fig_eff, use_container_width=True)

    st.divider()
    
    # Análise de Correlação Sono vs Stress
    st.markdown("##### 😴 Correlação: Eficiência do Sono vs. Razão de Estresse")
    fig_corr = px.scatter(df_health, x='sleep_efficiency', y='stress_ratio', 
                         size='stress_avg', color='body_battery_max',
                         labels={'sleep_efficiency': 'Eficiência do Sono (%)', 'stress_ratio': 'Razão de Estresse (Sono/Dia)'},
                         color_continuous_scale='Viridis')
    fig_corr.update_layout(height=400)
    st.plotly_chart(fig_corr, use_container_width=True)
    st.caption("Este gráfico mostra se noites com melhor eficiência de sono resultam em uma menor razão de estresse no dia seguinte.")

# --- MAIN ---

df_health = load_health_data()
df_act = load_activity_data()
profile = load_profile()

render_sidebar(profile, df_health)

st.title("🛡️ Garmin Health Monitor Pro")

tab_saude, tab_act, tab_insights = st.tabs(["🏥 Visão de Saúde", "🏃 Atividades & Treinos", "🧠 Insights Avançados"])

with tab_saude:
    render_health_tab(df_health)

with tab_act:
    render_activities_tab(df_act)

with tab_insights:
    render_insights_tab(df_health, df_act)
