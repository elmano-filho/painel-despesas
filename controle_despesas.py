import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="Gestão Financeira", layout="wide")

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

SCOPE = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

# --- FUNÇÕES DE PERSISTÊNCIA (GOOGLE SHEETS) ---

def obter_cliente_gspread():
    """Inicializa o cliente gspread com as credenciais locais."""
    creds = Credentials.from_service_account_file("credenciais.json", scopes=SCOPE)
    return gspread.authorize(creds)

def gerir_timestamp_acesso(gid, modo="ler"):
    """Lê ou atualiza o timestamp na célula Z1 da aba específica."""
    try:
        client = obter_cliente_gspread()
        sheet_id = st.secrets["ID_PLANILHA"]
        planilha = client.open_by_key(sheet_id)
        # Localiza a aba pelo GID numérico
        aba = next(w for w in planilha.worksheets() if str(w.id) == str(gid))
        
        if modo == "ler":
            valor = aba.acell('Z1').value
            return pd.to_datetime(valor, dayfirst=True) if valor else pd.to_datetime("2000-01-01")
        else:
            agora = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            aba.update_acell('Z1', agora)
    except Exception as e:
        return pd.to_datetime("2000-01-01") if modo == "ler" else None

# --- FUNÇÃO DE CARREGAMENTO ---

@st.cache_data(ttl=60)
def carregar_dados(gid):
    try:
        sheet_id = st.secrets["ID_PLANILHA"]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        df = pd.read_csv(url)
        
        if 'Data' in df.columns:
            df = df.dropna(subset=['Data'])
            df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Data'])
            
            if 'Tipo' not in df.columns: df['Tipo'] = 'Despesa'
            
            if 'Valor (R$)' in df.columns:
                valores = df['Valor (R$)'].astype(str)
                valores = valores.str.replace('R$', '', regex=False).str.replace(' ', '', regex=False)
                valores = valores.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
                df['Valor (R$)'] = pd.to_numeric(valores, errors='coerce').fillna(0)
            return df
        return None
    except Exception as e:
        st.error(f"Erro na ligação: {e}")
        return None

# --- GESTÃO DE ACESSO E SESSÃO ---

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.viu_novidades = False

if not st.session_state.logado:
    st.title("🔐 Acesso ao Painel Financeiro")
    try:
        teste_senhas = st.secrets["senhas"]
    except:
        st.error("⚠️ Erro nas configurações de Secrets.")
        st.stop()

    senha_digitada = st.text_input("Introduza a palavra-passe:", type="password")
    if st.button("Entrar"):
        if senha_digitada in st.secrets["senhas"]:
            st.session_state.log
