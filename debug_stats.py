import os
from dotenv import load_dotenv
from garminconnect import Garmin

load_dotenv(r'garmin_reader/.env')
client = Garmin(os.getenv('GARMIN_EMAIL'), os.getenv('GARMIN_PASSWORD'))
client.login()

# Pegar dados de um dia recente que tenha sono
stats = client.get_stats('2026-04-26')

print("--- DIAGNÓSTICO DE DADOS ---")
fields = [
    'avgSleepRespirationValue', 'avgWakingRespirationValue', 
    'floorsAscended', 'restStressDuration', 'lowStressDuration', 
    'mediumStressDuration', 'highStressDuration'
]

for f in fields:
    print(f"{f}: {stats.get(f)}")
