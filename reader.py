import os
import logging
import pandas as pd
from fitparse import FitFile
from datetime import datetime

# Configuração de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def save_to_csv(df, output_path):
    """
    Salva o DataFrame em um arquivo CSV.
    """
    if df.empty:
        logging.warning("Nenhum dado para salvar.")
        return
    try:
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        logging.info(f"Dados salvos com sucesso em: {output_path}")
    except Exception as e:
        logging.error(f"Erro ao salvar CSV: {e}")

def read_fit_file_generic(file_path, message_type):
    """
    Lê um arquivo .fit e extrai dados de um tipo de mensagem específico.
    """
    data_list = []
    try:
        fitfile = FitFile(file_path)
        for record in fitfile.get_messages(message_type):
            msg_data = {data.name: data.value for data in record}
            msg_data['file_source'] = os.path.basename(file_path)
            data_list.append(msg_data)
        return data_list
    except Exception as e:
        logging.error(f"Erro ao ler {file_path} para {message_type}: {e}")
        return []

def batch_read_files(directory_path, message_type):
    """
    Lê todos os arquivos .fit de um diretório para um tipo de mensagem.
    """
    all_data = []
    if not os.path.exists(directory_path):
        logging.warning(f"Diretório não encontrado: {directory_path}")
        return pd.DataFrame()

    files = [f for f in os.listdir(directory_path) if f.endswith('.fit')]
    logging.info(f"Processando {len(files)} arquivos em {directory_path} para '{message_type}'")

    for file_name in files:
        file_path = os.path.join(directory_path, file_name)
        data = read_fit_file_generic(file_path, message_type)
        all_data.extend(data)

    return pd.DataFrame(all_data)

def run_full_ingestion():
    """
    Executa a ingestão completa de todas as categorias de dados.
    """
    base_path = r"D:\GARMIN"
    
    config = {
        'atividades': (os.path.join(base_path, 'ACTIVITY'), 'session', 'atividades_garmin.csv'),
        'monitoramento': (os.path.join(base_path, 'Monitor'), 'monitoring', 'monitoramento_garmin.csv'),
        'saude': (os.path.join(base_path, 'Metrics'), 'wellbeing_report', 'saude_garmin.csv'),
        'sono': (os.path.join(base_path, 'Sleep'), 'sleep_level', 'sono_garmin.csv')
    }

    for category, (folder, msg_type, output) in config.items():
        logging.info(f"Iniciando {category}...")
        df = batch_read_files(folder, msg_type)
        if not df.empty:
            save_to_csv(df, output)
        else:
            logging.info(f"Nenhum dado encontrado para {category}.")

if __name__ == "__main__":
    run_full_ingestion()
