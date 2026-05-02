from garmin_client import run_cloud_sync
from datetime import datetime

def build_history():
    print("🚀 Iniciando sincronização completa de 2026...")
    
    # Data de início: 01 de Janeiro de 2026
    start_date = datetime(2026, 1, 1)
    today = datetime.now()
    
    # Calcula quantos dias e quantas atividades (estimativa alta para não faltar nada)
    dias_total = (today - start_date).days + 1
    # Assumindo uma média de até 1.5 atividades por dia
    limite_atividades = max(100, int(dias_total * 1.5))
    
    print(f"📅 Período: {start_date.strftime('%d/%m/%Y')} até hoje ({dias_total} dias).")
    print(f"🏃 Buscando até {limite_atividades} atividades...")
    
    run_cloud_sync(start_date=start_date, act_limit=limite_atividades)
    
    print("\n✅ Histórico completo de 2026 sincronizado com sucesso!")

if __name__ == "__main__":
    build_history()
