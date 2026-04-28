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

            sleep_dto = sleep.get('dailySleepDTO', {})

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
                'avg_respiration': stats.get('avgWakingRespirationValue'),
                'stress_avg': stats.get('averageStressLevel'),
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
                'training_status': training.get('status'),
                'fitness_age': user_summary.get('fitnessAge'),
                'intensity_min_total': total_intensity,
                'vo2_max': training.get('vo2Max')
            }
        except Exception as e:
            logging.error(f"Erro ao buscar stats de {date}: {e}")
            return None

def run_cloud_sync(start_date=None, days=None):
    """Executa o fluxo de sincronização."""
    client = GarminCloudClient()
    if client.login():
        health_data = []
        dates_to_sync = []
        today = datetime.now()
        
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

        file_path = os.path.join("data", "saude_cloud.csv")
        existing_df = pd.DataFrame()
        if os.path.exists(file_path):
            existing_df = pd.read_csv(file_path)

        for date_str in dates_to_sync:
            logging.info(f"Sincronizando: {date_str}")
            day_data = client.get_daily_stats(date_str)
            if day_data:
                health_data.append(day_data)

        if health_data:
            df_new = pd.DataFrame(health_data)
            if not existing_df.empty:
                df_final = pd.concat([df_new, existing_df]).drop_duplicates(subset=['date'], keep='first')
            else:
                df_final = df_new
            os.makedirs("data", exist_ok=True)
            df_final.sort_values('date', ascending=False).to_csv(file_path, index=False)
        
        profile = client.get_user_info()
        with open(os.path.join("data", "profile.json"), "w") as f:
            json.dump(profile, f)
        logging.info("Sincronização concluída.")
        return profile
    return None

if __name__ == "__main__":
    run_cloud_sync(days=14)
