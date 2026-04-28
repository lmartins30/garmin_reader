# 🛡️ Garmin Health Monitor Pro

Um dashboard interativo em Streamlit para visualização de métricas de saúde e performance sincronizadas diretamente da nuvem do Garmin Connect.

## 🚀 Funcionalidades

- **Sincronização Cloud:** Integração com a API do Garmin Connect para buscar dados dos últimos 14 dias.
- **Insights de Recuperação:** Gráficos detalhados de Body Battery (Máx/Mín) e recarga durante o sono.
- **Análise de Sono:** Visualização empilhada de estágios (REM, Profundo, Leve, Acordado).
- **Monitoramento de Estresse:** Composição diária de níveis de estresse (Repouso até Alto).
- **Metas Semanais:** Acompanhamento acumulado de Minutos de Intensidade (Meta OMS).
- **Métricas de Saúde:** FC de repouso, respiração, passos, calorias e alertas de FC anômala.

## 🛠️ Instalação

1. **Ative o ambiente virtual:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

2. **Instale as dependências:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure suas credenciais:**
   Crie ou edite o arquivo `.env` na raiz da pasta:
   ```env
   GARMIN_EMAIL=seu_email@exemplo.com
   GARMIN_PASSWORD=sua_senha_aqui
   ```

## 📊 Como Usar

1. **Sincronize os dados:**
   Execute o script para baixar as métricas mais recentes da nuvem:
   ```powershell
   python garmin_client.py
   ```

2. **Inicie o Dashboard:**
   ```powershell
   streamlit run app.py
   ```

## 📂 Estrutura do Projeto

- `app.py`: Interface gráfica em Streamlit.
- `garmin_client.py`: Script de integração com a API Garmin Connect.
- `reader.py`: Leitor modular de arquivos `.fit` locais.
- `.env`: Arquivo de configuração de credenciais (protegido pelo .gitignore).

---
*Desenvolvido com auxílio do Gemini CLI.*
