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
            st.session_state.logado = True
            st.session_state.usuario = st.secrets["senhas"][senha_digitada]
            st.rerun()
        else:
            st.error("Palavra-passe incorreta.")

else:
    usuario_id = st.session_state.usuario
    gid_aba = st.secrets["abas"][usuario_id]

    # --- NOVO: TELA DE NOVIDADES (ANTES DO DASHBOARD) ---
    if not st.session_state.viu_novidades:
        st.title(f"🔔 Olá, {usuario_id.replace('_', ' ')}!")
        st.subheader("Novidades desde a sua última consulta")
        
        with st.spinner("A verificar novos lançamentos..."):
            data_ultimo_acesso = gerir_timestamp_acesso(gid_aba, modo="ler")
            df_total = carregar_dados(gid_aba)
            
            # Filtra lançamentos com data superior ao último acesso
            novos = df_total[df_total['Data'] > data_ultimo_acesso].copy()
        
        if not novos.empty:
            st.write(f"Foram detetados **{len(novos)}** novos registos:")
            novos['Data'] = novos['Data'].dt.strftime('%d/%m/%Y')
            st.dataframe(novos[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']], use_container_width=True, hide_index=True)
        else:
            st.info("Não existem novos lançamentos desde a última vez que consultou o painel.")

        if st.button("Ir para o Painel Principal"):
            gerir_timestamp_acesso(gid_aba, modo="gravar") # Atualiza o Z1 na planilha
            st.session_state.viu_novidades = True
            st.rerun()

    # --- PAINEL PRINCIPAL (DASHBOARD) ---
    else:
        st.sidebar.title(f"👤 {usuario_id.replace('_', ' ')}")
        if st.sidebar.button("Terminar Sessão"):
            st.session_state.logado = False
            st.session_state.viu_novidades = False
            st.rerun()

        st.title("💰 Painel de Controle")
        df = carregar_dados(gid_aba)

        if df is not None and not df.empty:
            st.sidebar.header("Seleção do Período")
            anos_disponiveis = sorted([int(a) for a in df['Data'].dt.year.unique()])
            ano_selecionado = st.sidebar.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis)-1)
            
            meses_disponiveis = sorted([int(m) for m in df[df['Data'].dt.year == ano_selecionado]['Data'].dt.month.unique()])
            mes_selecionado = st.sidebar.selectbox("Mês", meses_disponiveis, format_func=lambda x: MESES_PT.get(x, str(x)))

            dados_filtrados = df[(df['Data'].dt.month == mes_selecionado) & (df['Data'].dt.year == ano_selecionado)]

            if dados_filtrados.empty:
                st.warning(f"Sem registos para {MESES_PT.get(mes_selecionado)}.")
            else:
                receitas = dados_filtrados[dados_filtrados['Tipo'] == 'Receita']['Valor (R$)'].sum()
                despesas = dados_filtrados[dados_filtrados['Tipo'] == 'Despesa']['Valor (R$)'].sum()
                
                st.subheader(f"Resumo de {MESES_PT.get(mes_selecionado)} de {ano_selecionado}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Receitas", f"R$ {receitas:,.2f}")
                c2.metric("Despesas", f"R$ {despesas:,.2f}", delta=f"-{despesas:,.2f}", delta_color="inverse")
                c3.metric("Saldo", f"R$ {(receitas - despesas):,.2f}")

                st.markdown("---")
                col_grafico, col_lista = st.columns([1, 1.2])

                with col_grafico:
                    st.subheader("📊 Fluxo")
                    fig_bar, ax_bar = plt.subplots(figsize=(5, 4))
                    ax_bar.bar(['Receitas', 'Despesas'], [receitas, despesas], color=['#2ecc71', '#e74c3c'])
                    st.pyplot(fig_bar)

                with col_lista:
                    st.subheader("📋 Movimentações")
                    exibicao = dados_filtrados.sort_values(by='Data', ascending=False).copy()
                    exibicao['Data'] = exibicao['Data'].dt.strftime('%d/%m/%Y')
                    st.dataframe(exibicao[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']], use_container_width=True, hide_index=True)
