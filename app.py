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
    [data-testid="stMetricValue"] {{ font-size: 32px; color: #1E3A8A; font-weight: 700; }}
    [data-testid="stMetricLabel"] {{ font-size: 16px; color: #4B5563; font-weight: 600; }}
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

    # KPIs - Clareza nos textos
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bateria Corporal (Atual)", f"{int(latest['body_battery_recent'])}%", f"Recarga no Sono: +{int(latest['bb_sleep_charge'])}")
    eff_val = latest.get('sleep_efficiency', 0)
    c2.metric("Qualidade do Sono", f"{eff_val:.1f}%", delta="Excelente" if eff_val > 90 else "Abaixo do Ideal" if eff_val < 80 else "Normal")
    avg_rhr = df_saude['resting_hr'].mean()
    delta_rhr = latest['resting_hr'] - avg_rhr
    c3.metric("FC Repouso", f"{int(latest['resting_hr'])} bpm", f"{delta_rhr:+.1f} vs média", delta_color="inverse")
    
    # Garantir que training_status seja string para evitar erro com NaN/Nulo
    t_status = str(latest.get('training_status', 'N/A'))
    if t_status == '0' or t_status == '0.0' or t_status == 'nan':
        t_status = 'N/A'
    
    c4.metric("Status de Treino", t_status.replace('_', ' ').title())

    st.divider()

    # RECUPERAÇÃO (Sono e Body Battery)
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("😴 Estágios do Sono & Recarga")
        fig_sleep = go.Figure()
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_deep'], name="Profundo", marker_color="#001a33"))
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_rem'], name="REM", marker_color="#004080"))
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_light'], name="Leve", marker_color="#3399ff"))
        fig_sleep.add_trace(go.Bar(x=df_saude['date'], y=df_saude['sleep_awake'], name="Acordado", marker_color="#ccdbe3"))
        sleep_sum = df_saude['sleep_rem'] + df_saude['sleep_deep'] + df_saude['sleep_light'] + df_saude['sleep_awake']
        fig_sleep.add_trace(go.Scatter(x=df_saude['date'], y=sleep_sum + 0.2, text=df_saude['bb_sleep_charge'].apply(lambda x: f"+{int(x)}🔋"), mode="text", name="Recarga BB", textposition="top center"))
        fig_sleep.update_layout(barmode='stack', height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"), yaxis_title="Horas")
        st.plotly_chart(fig_sleep, use_container_width=True)
    with col2:
        st.subheader("🔋 Tendência de Body Battery")
        fig_bb = go.Figure()
        fig_bb.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['body_battery_max'], fill='tonexty', mode='lines', name='Nível Máximo', line_color='#4169E1'))
        fig_bb.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['body_battery_min'], fill='tozeroy', mode='lines', name='Nível Mínimo', line_color='#87CEEB'))
        fig_bb.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_bb, use_container_width=True)

    st.divider()

    # SAÚDE CARDIOVASCULAR E ESTRESSE
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("📈 Frequência Cardíaca de Repouso")
        fig_rhr = go.Figure()
        fig_rhr.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['resting_hr'], mode='markers', name='Diário', marker=dict(color='#87CEEB', size=4)))
        fig_rhr.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['rhr_ma7'], mode='lines', name='Média Móvel (7 dias)', line=dict(color='#4169E1', width=3)))
        fig_rhr.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_rhr, use_container_width=True)
    with col4:
        st.subheader("📊 Composição do Estresse Diário")
        fig_stress = go.Figure()
        for col, label, color in [('stress_rest_min', 'Repouso', '#cccccc'), ('stress_low_min', 'Baixo', COLOR_TEAL), ('stress_med_min', 'Médio', '#ff8c00'), ('stress_high_min', 'Alto', '#8b0000')]:
            fig_stress.add_trace(go.Bar(x=df_saude['date'], y=df_saude[col], name=label, marker_color=color))
        fig_stress.update_layout(barmode='stack', height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_stress, use_container_width=True)

    st.divider()

    # RESPIRAÇÃO E PERFORMANCE AERÓBICA
    col5, col6 = st.columns(2)
    with col5:
        st.subheader("🫁 Tendência de Respiração")
        fig_resp = go.Figure()
        fig_resp.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['avg_respiration_awake'], mode='lines+markers', name='Média Acordado', line=dict(color=COLOR_TEAL)))
        fig_resp.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['avg_respiration_sleep'], mode='lines+markers', name='Média Dormindo', line=dict(color='#87CEEB')))
        fig_resp.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"), yaxis_title="Respirações por min")
        st.plotly_chart(fig_resp, use_container_width=True)
    with col6:
        st.subheader("🏆 Evolução do VO2 Máximo")
        df_vo2 = df_saude[df_saude['vo2_max'] > 0]
        if not df_vo2.empty:
            fig_vo2 = px.line(df_vo2, x='date', y='vo2_max', markers=True, color_discrete_sequence=[COLOR_TEAL])
            fig_vo2.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig_vo2, use_container_width=True)
        else:
            st.info("Dados de VO2 Máximo insuficientes.")

    st.divider()
    
    # ATIVIDADE DIÁRIA (Passos e Calorias)
    col7, col8 = st.columns(2)
    with col7:
        st.subheader("👣 Passos Diários")
        fig_steps = go.Figure()
        fig_steps.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['steps'], mode='markers', name='Diário', marker=dict(color='#87CEEB', size=4)))
        fig_steps.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['steps_ma7'], mode='lines', name='Média 7 dias', line=dict(color=COLOR_GOLD, width=3)))
        fig_steps.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_steps, use_container_width=True)
    with col8:
        st.subheader("🔥 Queima Calórica")
        fig_cal = go.Figure()
        fig_cal.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['calories'], mode='markers', name='Diário', marker=dict(color="#FFDAB9", size=4)))
        fig_cal.add_trace(go.Scatter(x=df_saude['date'], y=df_saude['calories_ma7'], mode='lines', name='Média 7 dias', line=dict(color="#FF4500", width=3)))
        fig_cal.update_layout(height=350, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
        st.plotly_chart(fig_cal, use_container_width=True)



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
    metric_y = 'distance'
    label_y = 'Distância (km)'
    if df_filtered['distance'].sum() == 0:
        metric_y = 'calories'
        label_y = 'Calorias (kcal)'

    st.markdown(f"##### 📊 Volume por Atividade: {label_y}")
    fig_vol = px.bar(df_filtered, x='date', y=metric_y, color='type', 
                     hover_data=['name', 'duration_min', 'avg_pace', 'calories'],
                     title=f"{metric_y.capitalize()} por Atividade",
                     color_discrete_sequence=px.colors.qualitative.Safe)
    
    # Ajustar bargap para barras mais largas e hovermode para facilitar a interação
    fig_vol.update_layout(
        height=450, 
        xaxis_title="Data", 
        yaxis_title=label_y,
        bargap=0.01,  # Praticamente sem espaço entre barras
        bargroupgap=0.0,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_vol, use_container_width=True)

    # Tabela Detalhada
    st.markdown("##### 📝 Detalhes das Atividades")
    df_display = df_filtered[['date', 'name', 'type', 'distance', 'duration_min', 'avg_pace', 'avg_hr', 'calories', 'vo2_max']].copy()
    df_display.columns = ['Data', 'Nome', 'Tipo', 'Dist (km)', 'Dur (min)', 'Ritmo (min/km)', 'FC Média', 'Calorias', 'VO2 Max']
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
    col_i1.metric("ACWR (Carga)", f"{acwr:.2f}", status_acwr, delta_color="inverse" if acwr > 1.5 else "normal",
                  help="ACWR: Razão entre sua carga de treino dos últimos 7 dias vs os últimos 28. Entre 0.8 e 1.3 é o ideal para evolução sem lesão.")
    
    # 2. Cardiac Efficiency Index
    df_runs = df_act[df_act['type'] == 'running'].head(5)
    if not df_runs.empty:
        eff_idx = df_runs['cardiac_efficiency'].mean()
        prev_eff = df_act[df_act['type'] == 'running'].iloc[5:10]['cardiac_efficiency'].mean() if len(df_act) > 10 else eff_idx
        col_i2.metric("Eficiência Cardíaca", f"{eff_idx:.2f}", f"{eff_idx - prev_eff:.2f} vs ant",
                      help="Mede quanto ritmo (velocidade) você entrega por cada batimento. Quanto maior, mais condicionado seu coração está.")
    
    # 3. Recovery Efficiency
    rhr_delta = latest_health.get('rhr_delta', 0)
    recovery_status = "Recuperado" if rhr_delta <= 0 else "Estressado" if rhr_delta > 3 else "Moderado"
    col_i3.metric("Recuperação (RHR Delta)", f"{rhr_delta:+.1f} bpm", recovery_status, delta_color="inverse",
                  help="Diferença da sua FC de repouso atual para sua média de 7 dias. Valores positivos altos indicam fadiga ou estresse.")

    # 4. Stress Ratio
    sleep_eff = df_health['sleep_efficiency'].mean()
    col_i4.metric("Razão de Estresse", f"{latest_health['stress_ratio']:.2f}", 
                  help="Razão de Estresse: Compara o estresse dormindo vs acordado. Valores abaixo de 0.4 indicam uma excelente recuperação noturna.")

    st.divider()

    # Gráficos de Correlação
    c_col1, c_col2 = st.columns(2)
    
    with c_col1:
        st.markdown("##### 📉 Evolução do ACWR (Gestão de Carga)")
        st.caption("Razão entre carga aguda (7d) e crônica (28d). Evite picos bruscos.")
        fig_acwr = go.Figure()
        fig_acwr.add_trace(go.Scatter(x=df_act['date'], y=df_act['acwr'], mode='lines+markers', name="ACWR", line_color=COLOR_TEAL))
        
        # Zonas de segurança com divisórias e RÓTULOS
        fig_acwr.add_hrect(y0=0.8, y1=1.3, fillcolor="green", opacity=0.08, line_width=0)
        fig_acwr.add_hline(y=0.8, line_color="white", line_width=1, opacity=0.3)
        fig_acwr.add_hline(y=1.3, line_color="white", line_width=1, opacity=0.3)
        
        # Anotações para os limites
        fig_acwr.add_annotation(x=df_act['date'].min(), y=1.05, text="SWEET SPOT", showarrow=False, xanchor="left", font=dict(color="green", size=9), opacity=0.6)
        fig_acwr.add_annotation(x=df_act['date'].min(), y=1.6, text="RISCO DE LESÃO", showarrow=False, xanchor="left", font=dict(color="red", size=9), opacity=0.6)
        
        fig_acwr.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=40),
                              xaxis=dict(showgrid=False, title="Data"), 
                              yaxis=dict(showgrid=False, title="Razão ACWR"),
                              plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_acwr, use_container_width=True)

    with c_col2:
        st.markdown("##### 🏎️ Eficiência Cardíaca (Corrida)")
        st.caption("Evolução do ritmo por batimento. Quanto mais alto, mais condicionado.")
        if not df_runs.empty:
            fig_eff = px.scatter(df_runs, x='date', y='cardiac_efficiency', size='distance', 
                                 color='avg_hr',
                                 labels={'date': 'Data', 'cardiac_efficiency': 'Eficiência (Ritmo/FC)', 'avg_hr': 'FC Média'},
                                 color_continuous_scale='RdYlGn_r')
            
            avg_eff = df_runs['cardiac_efficiency'].median()
            fig_eff.add_hrect(y0=avg_eff, y1=df_runs['cardiac_efficiency'].max()*1.2, fillcolor="green", opacity=0.08, line_width=0)
            fig_eff.add_hline(y=avg_eff, line_color="white", line_width=1, opacity=0.3)
            
            # Anotação para o limite de eficiência
            fig_eff.add_annotation(x=df_runs['date'].min(), y=avg_eff * 1.05, text="ALTA PERFORMANCE", showarrow=False, xanchor="left", font=dict(color="green", size=9), opacity=0.6)
            
            fig_eff.update_layout(height=350, margin=dict(l=0, r=0, t=30, b=40),
                                 xaxis=dict(showgrid=False, title="Data"), 
                                 yaxis=dict(showgrid=False, title="Índice de Eficiência"),
                                 plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_eff, use_container_width=True)

    st.divider()
    
    # Análise de Correlação Sono vs Stress
    st.markdown("##### 😴 Correlação: Eficiência do Sono vs. Razão de Estresse")
    fig_corr = px.scatter(df_health, x='sleep_efficiency', y='stress_ratio', 
                         size='stress_avg', color='body_battery_max',
                         labels={'sleep_efficiency': 'Eficiência do Sono (%)', 'stress_ratio': 'Razão de Estresse'},
                         color_continuous_scale='Viridis')
    
    # Quadrante de Ouro com transparência e divisórias brancas sutis
    fig_corr.add_vrect(x0=85, x1=100, fillcolor="green", opacity=0.04, line_width=0)
    fig_corr.add_hrect(y0=0, y1=0.4, fillcolor="green", opacity=0.04, line_width=0)
    fig_corr.add_vline(x=85, line_color="white", line_width=1, opacity=0.3)
    fig_corr.add_hline(y=0.4, line_color="white", line_width=1, opacity=0.3)
    
    fig_corr.add_annotation(x=92.5, y=0.1, text="REPARAÇÃO TOTAL", showarrow=False, font=dict(color="green", size=9, family="Arial Black"), opacity=0.5)

    fig_corr.update_layout(height=450, xaxis=dict(showgrid=False), yaxis=dict(showgrid=False),
                          plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig_corr, use_container_width=True)
    st.caption("Foco: Bolinhas no quadrante inferior direito indicam sono eficiente que realmente reduz o estresse corporal.")

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
