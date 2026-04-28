from garmin_client import run_cloud_sync
from datetime import datetime, timedelta

def build_history():
    print("Iniciando busca de histórico...")
    
    # Configurável: Altere aqui para pegar períodos maiores (ex: 30, 60, 365 dias)
    dias_para_tras = 7 
    
    print(f"Buscando os últimos {dias_para_tras} dias...")
    run_cloud_sync(days=dias_para_tras)
    print("Histórico atualizado com sucesso!")

if __name__ == "__main__":
    build_history()
