import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from garminconnect import Garmin

# Carrega variáveis de ambiente
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


class GarminCloudClient:
    """Cliente para integração com a API do Garmin Connect Cloud."""

    def __init__(self):
        """Inicializa o cliente com credenciais do ambiente."""
        self.email = os.getenv("GARMIN_EMAIL")
        self.password = os.getenv("GARMIN_PASSWORD")
        self.token_file = os.path.join("data", "session_token.json")
        self.client = None

    def login(self):
        """Realiza o login na API do Garmin Connect usando cache se disponível."""
        try:
            os.makedirs("data", exist_ok=True)
            self.client = Garmin(self.email, self.password)
            
            # Tenta carregar sessão do arquivo
            if os.path.exists(self.token_file):
                try:
                    with open(self.token_file, 'r') as f:
                        token_data = json.load(f)
                    self.client.login(token_data)
                    logging.info("Login realizado via cache de sessão.")
                    return True
                except Exception as e:
                    logging.warning(f"Não foi possível usar o cache: {e}. Tentando novo login...")

            # Se não houver cache ou falhar, faz login normal
            self.client.login()
            
            # Salva a nova sessão (tenta atributos comuns dependendo da versão da lib)
            session = getattr(self.client, 'session_data', getattr(self.client, 'login_data', None))
            if session:
                with open(self.token_file, 'w') as f:
                    json.dump(session, f)
                logging.info("Novo login realizado e sessão salva.")
            
            return True
        except Exception as e:
            logging.error(f"Erro ao fazer login: {e}")
            return False

    def get_user_info(self):
        """Busca informações básicas do perfil e métricas físicas."""
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            summary = self.client.get_user_summary(today)
            return {
                "full_name": self.client.get_full_name(),
                "display_name": self.client.display_name,
                "fitness_age": summary.get("fitnessAge"),
                "weight": round(summary.get("weight", 0) / 1000, 1) if summary.get("weight") else None,
                "unit_system": self.client.get_unit_system()
            }
        except Exception as e:
            logging.error(f"Erro ao buscar info de perfil: {e}")
            return {"full_name": self.client.get_full_name() if self.client else "Usuário"}

    def get_daily_stats(self, date=None):
        """Busca métricas de saúde e sono para uma data específica."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        try:
            stats = self.client.get_stats(date)
            sleep = self.client.get_sleep_data(date)
            training = self.client.get_training_status(date)
            user_summary = self.client.get_user_summary(date)
            
            # Busca VO2 Max específico (mais preciso que o do resumo)
            vo2_data = self.client.get_max_metrics(date)
            vo2_max = None
            if vo2_data:
                # Tenta pegar o valor genérico ou de corrida
                vo2_max = vo2_data[0].get('generic', {}).get('vo2MaxPreciseValue')

            sleep_dto = sleep.get('dailySleepDTO', {})
            
            # Cálculo de Eficiência de Sono
            sleep_efficiency = None
            total_sleep = sleep_dto.get('sleepTimeSeconds', 0)
            awake_sleep = sleep_dto.get('awakeSleepSeconds', 0)
            if total_sleep > 0:
                sleep_efficiency = round(((total_sleep - awake_sleep) / total_sleep) * 100, 1)

            # Métricas de Respiração (Acordado vs Dormindo)
            resp_awake = stats.get('avgWakingRespirationValue')
            resp_sleep = sleep_dto.get('averageRespirationValue')

            # Razão de Estresse (Sono / Dia)
            stress_day = stats.get('averageStressLevel', 0) or 0
            sleep_stress_data = sleep.get('sleepStress', [])
            stress_sleep = sum([s['value'] for s in sleep_stress_data if s['value'] > 0]) / len(sleep_stress_data) if sleep_stress_data else 0
            stress_ratio = round(stress_sleep / stress_day, 2) if stress_day > 0 else 0

            # HRV (Tentativa de buscar do resumo ou endpoint dedicado)
            hrv_summary = stats.get('hrvSummary', {})
            hrv_val = hrv_summary.get('lastNightAvg') if hrv_summary else None

            # Consistência de Sono (Horários)
            def ts_to_decimal_hour(ts_ms):
                if not ts_ms: return 0
                dt = datetime.fromtimestamp(ts_ms / 1000)
                return round(dt.hour + dt.minute / 60, 2)

            sleep_start = ts_to_decimal_hour(sleep_dto.get('sleepStartTimestampLocal'))
            sleep_end = ts_to_decimal_hour(sleep_dto.get('sleepEndTimestampLocal'))

            mod = stats.get('moderateIntensityMinutes', 0) or 0
            vig = stats.get('vigorousIntensityMinutes', 0) or 0
            total_intensity = mod + (vig * 2)

            return {
                'date': date,
                'steps': stats.get('totalSteps'),
                'calories': stats.get('totalKilocalories'),
                'resting_hr': stats.get('restingHeartRate'),
                'min_hr': stats.get('minHeartRate'),
                'max_hr': stats.get('maxHeartRate'),
                'abnormal_hr_alerts': stats.get('abnormalHeartRateAlertsCount', 0),
                'avg_respiration_awake': resp_awake,
                'avg_respiration_sleep': resp_sleep,
                'stress_avg': stress_day,
                'stress_sleep': round(stress_sleep, 1),
                'stress_ratio': stress_ratio,
                'sleep_start_hour': sleep_start,
                'sleep_end_hour': sleep_end,
                'stress_qualifier': stats.get('stressQualifier'),
                'stress_rest_min': round((stats.get('restStressDuration', 0) or 0) / 60, 1),
                'stress_low_min': round((stats.get('lowStressDuration', 0) or 0) / 60, 1),
                'stress_med_min': round((stats.get('mediumStressDuration', 0) or 0) / 60, 1),
                'stress_high_min': round((stats.get('highStressDuration', 0) or 0) / 60, 1),
                'body_battery_recent': stats.get('bodyBatteryMostRecentValue'),
                'body_battery_max': stats.get('bodyBatteryHighestValue'),
                'body_battery_min': stats.get('bodyBatteryLowestValue'),
                'bb_sleep_charge': stats.get('bodyBatteryDuringSleep'),
                'active_time_min': round((stats.get('activeSeconds', 0) or 0) / 60, 1),
                'sedentary_time_min': round((stats.get('sedentarySeconds', 0) or 0) / 60, 1),
                'sleep_rem': round(sleep_dto.get('remSleepSeconds', 0) / 3600, 1),
                'sleep_deep': round(sleep_dto.get('deepSleepSeconds', 0) / 3600, 1),
                'sleep_light': round(sleep_dto.get('lightSleepSeconds', 0) / 3600, 1),
                'sleep_awake': round(sleep_dto.get('awakeSleepSeconds', 0) / 3600, 1),
                'sleep_efficiency': sleep_efficiency,
                'training_status': training.get('mostRecentTrainingStatus'),
                'training_load': training.get('mostRecentTrainingLoadBalance'),
                'fitness_age': user_summary.get('fitnessAge'),
                'intensity_min_total': total_intensity,
                'vo2_max': vo2_max if vo2_max else training.get('vo2Max')
            }
        except Exception as e:
            logging.error(f"Erro ao buscar stats de {date}: {e}")
            return None

    def get_activities(self, start=0, limit=20):
        """Busca a lista de atividades recentes."""
        try:
            activities = self.client.get_activities(start, limit)
            processed = []
            for a in activities:
                processed.append({
                    'activity_id': a.get('activityId'),
                    'name': a.get('activityName'),
                    'type': a.get('activityType', {}).get('typeKey'),
                    'date': a.get('startTimeLocal'),
                    'distance': round(a.get('distance', 0) / 1000, 2) if a.get('distance') else 0,
                    'duration_min': round(a.get('duration', 0) / 60, 1) if a.get('duration') else 0,
                    'calories': a.get('calories'),
                    'avg_hr': a.get('averageHR'),
                    'max_hr': a.get('maxHR'),
                    'avg_cadence': a.get('averageRunningCadenceInStepsPerMinute'),
                    'elev_gain': a.get('elevationGain'),
                    'vo2_max': a.get('vO2MaxValue'),
                    'avg_pace': round(a.get('duration', 0) / (a.get('distance', 0) / 1000) / 60, 2) if a.get('distance') and a.get('distance') > 0 else 0
                })
            return processed
        except Exception as e:
            logging.error(f"Erro ao buscar atividades: {e}")
            return []

def run_cloud_sync(start_date=None, days=None):
    """Executa o fluxo de sincronização."""
    client = GarminCloudClient()
    if client.login():
        health_data = []
        dates_to_sync = []
        today = datetime.now()
        
        # Datas para Saúde
        if start_date:
            current = start_date
            while current <= today:
                dates_to_sync.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
        elif days:
            for i in range(days):
                dates_to_sync.append((today - timedelta(days=i)).strftime("%Y-%m-%d"))
        else:
            for i in range(3):
                dates_to_sync.append((today - timedelta(days=i)).strftime("%Y-%m-%d"))

        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(base_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        # Sincronização de Saúde
        health_file = os.path.join(data_dir, "saude_cloud.csv")
        existing_health_df = pd.DataFrame()
        if os.path.exists(health_file):
            existing_health_df = pd.read_csv(health_file)

        for date_str in dates_to_sync:
            logging.info(f"Sincronizando Saúde: {date_str}")
            day_data = client.get_daily_stats(date_str)
            if day_data:
                health_data.append(day_data)

        if health_data:
            df_new = pd.DataFrame(health_data)
            if not existing_health_df.empty:
                df_final = pd.concat([df_new, existing_health_df]).drop_duplicates(subset=['date'], keep='first')
            else:
                df_final = df_new
            df_final.sort_values('date', ascending=False).to_csv(health_file, index=False)
        
        # Sincronização de Atividades (Últimas 50)
        logging.info("Sincronizando Atividades...")
        activities_data = client.get_activities(limit=50)
        if activities_data:
            activities_file = os.path.join(data_dir, "atividades_cloud.csv")
            df_act = pd.DataFrame(activities_data)
            df_act.to_csv(activities_file, index=False)

        profile = client.get_user_info()
        with open(os.path.join(data_dir, "profile.json"), "w") as f:
            json.dump(profile, f)
        logging.info("Sincronização concluída.")
        return profile
    return None

if __name__ == "__main__":
    run_cloud_sync(days=14)
