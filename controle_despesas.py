import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# --- CONFIGURAÇÕES INICIAIS ---
st.set_page_config(page_title="Gestão Financeira", layout="wide")

MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

# --- FUNÇÃO DE CARREGAMENTO (MÉTODO SIMPLES E SEGURO) ---

@st.cache_data(ttl=60)
def carregar_dados(gid):
    try:
        sheet_id = st.secrets["ID_PLANILHA"]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        df = pd.read_csv(url)
        
        if 'Data' in df.columns:
            df = df.dropna(subset=['Data'])
            # Converte para data e remove informações de fuso horário para evitar conflitos
            df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce').dt.tz_localize(None)
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
        st.error(f"Erro na ligação com a folha de cálculo: {e}")
        return None

# --- GESTÃO DE ACESSO E SESSÃO ---

if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None
    st.session_state.viu_novidades = False

if not st.session_state.logado:
    st.title("🔐 Acesso ao Painel Financeiro")
    
    # Validação simples dos Secrets
    if "senhas" not in st.secrets:
        st.error("⚠️ Configuração 'senhas' não encontrada no Streamlit Cloud.")
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

    # --- TELA DE NOVIDADES (JANELA DE 7 DIAS) ---
    if not st.session_state.viu_novidades:
        st.title(f"🔔 Olá, {usuario_id.replace('_', ' ')}!")
        st.subheader("Lançamentos dos últimos 7 dias")
        
        with st.spinner("A procurar registos recentes..."):
            df_total = carregar_dados(gid_aba)
            
            if df_total is not None and not df_total.empty:
                # Define o limite de 7 dias atrás a partir de hoje
                data_limite = datetime.now() - timedelta(days=7)
                
                # Filtra apenas o que é igual ou posterior à data limite
                recentes = df_total[df_total['Data'] >= data_limite].copy()
            else:
                recentes = pd.DataFrame()
        
        if not recentes.empty:
            st.write(f"Foram encontrados **{len(recentes)}** registos na última semana:")
            # Formata a data apenas para exibição na tabela
            exibicao_novos = recentes.copy()
            exibicao_novos['Data'] = exibicao_novos['Data'].dt.strftime('%d/%m/%Y')
            st.dataframe(exibicao_novos[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']], 
                         use_container_width=True, hide_index=True)
        else:
            st.info("Não foram detetados novos lançamentos nos últimos 7 dias.")

        if st.button("Continuar para o Painel Completo"):
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
            
            # Filtros de Data
            anos_disponiveis = sorted([int(a) for a in df['Data'].dt.year.unique()])
            ano_selecionado = st.sidebar.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis)-1)
            
            meses_disponiveis = sorted([int(m) for m in df[df['Data'].dt.year == ano_selecionado]['Data'].dt.month.unique()])
            mes_selecionado = st.sidebar.selectbox("Mês", meses_disponiveis, format_func=lambda x: MESES_PT.get(x, str(x)))

            # Filtra os dados para o mês selecionado
            dados_filtrados = df[(df['Data'].dt.month == mes_selecionado) & (df['Data'].dt.year == ano_selecionado)]

            if dados_filtrados.empty:
                st.warning(f"Sem registos para {MESES_PT.get(mes_selecionado)}.")
            else:
                # Cálculos rápidos
                receitas = dados_filtrados[dados_filtrados['Tipo'] == 'Receita']['Valor (R$)'].sum()
                despesas = dados_filtrados[dados_filtrados['Tipo'] == '
