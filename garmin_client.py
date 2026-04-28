import os
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
        self.client = None

    def login(self):
        """Realiza o login na API do Garmin Connect.

        Returns:
            bool: True se o login for bem-sucedido, False caso contrário.
        """
        try:
            self.client = Garmin(self.email, self.password)
            self.client.login()
            return True
        except Exception as e:
            logging.error(f"Erro ao fazer login: {e}")
            return False

    def get_daily_stats(self, date=None):
        """Busca métricas de saúde e sono para uma data específica.

        Args:
            date (str, optional): Data no formato YYYY-MM-DD. Default é hoje.

        Returns:
            dict: Dicionário contendo as métricas processadas ou None em caso de erro.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        try:
            stats = self.client.get_stats(date)
            sleep = self.client.get_sleep_data(date)
            training = self.client.get_training_status(date)
            user_summary = self.client.get_user_summary(date)

            sleep_dto = sleep.get('dailySleepDTO', {})

            # Cálculo de Intensidade (Minutos Vigorosos valem o dobro)
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

    def get_activities(self, limit=30):
        """Busca as últimas atividades sincronizadas na nuvem.

        Args:
            limit (int): Número máximo de atividades a retornar.

        Returns:
            pd.DataFrame: DataFrame com o histórico de atividades.
        """
        try:
            activities = self.client.get_activities(0, limit)
            return pd.DataFrame(activities)
        except Exception as e:
            logging.error(f"Erro ao buscar atividades: {e}")
            return pd.DataFrame()


def run_cloud_sync():
    """Executa o fluxo de sincronização completa dos últimos 14 dias."""
    client = GarminCloudClient()
    if client.login():
        health_data = []
        today = datetime.now()
        for i in range(14):
            date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            logging.info(f"Sincronizando dados de saúde: {date_str}")
            day_data = client.get_daily_stats(date_str)
            if day_data:
                health_data.append(day_data)

        df_health = pd.DataFrame(health_data)
        df_health.to_csv("saude_cloud.csv", index=False)
        logging.info("Sincronização em nuvem concluída com sucesso!")


if __name__ == "__main__":
    run_cloud_sync()
