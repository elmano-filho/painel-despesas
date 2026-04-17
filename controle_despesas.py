import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# --- CONFIGURAÇÕES DE LAYOUT ---
st.set_page_config(page_title="Gestão Financeira Familiar", layout="wide")

# Dicionário para exibição dos meses em português
MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

# --- FUNÇÃO DE CARREGAMENTO COM LIMPEZA ---
@st.cache_data(ttl=60)
def carregar_dados(gid):
    try:
        sheet_id = st.secrets["ID_PLANILHA"]
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
        
        df = pd.read_csv(url)
        
        # 1. Remoção de linhas sem data
        if 'Data' in df.columns:
            df = df.dropna(subset=['Data'])
        else:
            st.error("A coluna 'Data' não foi encontrada. Verifique o cabeçalho.")
            return None
            
        # 2. Conversão da Data
        df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Data'])
        
        # 3. Verificação da coluna 'Tipo'
        if 'Tipo' not in df.columns:
            df['Tipo'] = 'Despesa'
            
        # 4. Conversão de valores monetários (Texto para Número)
        if 'Valor (R$)' in df.columns:
            valores = df['Valor (R$)'].astype(str)
            valores = valores.str.replace('R$', '', regex=False).str.replace(' ', '', regex=False)
            valores = valores.str.replace('.', '', regex=False) 
            valores = valores.str.replace(',', '.', regex=False)
            df['Valor (R$)'] = pd.to_numeric(valores, errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        st.error(f"Erro na ligação com a folha de cálculo: {e}")
        return None

# --- GESTÃO DE ACESSO ---
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.usuario = None

if not st.session_state.logado:
    st.title("🔐 Acesso ao Painel Financeiro")
    senha_digitada = st.text_input("Introduza a palavra-passe de acesso:", type="password")
    
    if st.button("Entrar"):
        # Verifica se a senha existe no dicionário 'senhas' do Secrets
        if senha_digitada in st.secrets["senhas"]:
            st.session_state.logado = True
            st.session_state.usuario = st.secrets["senhas"][senha_digitada]
            st.rerun()
        else:
            st.error("Palavra-passe incorreta. Tente novamente.")
else:
    # --- DASHBOARD LOGADO ---
    usuario_id = st.session_state.usuario
    gid_aba = st.secrets["abas"][usuario_id]
    
    st.sidebar.title(f"👤 {usuario_id}")
    if st.sidebar.button("Terminar Sessão"):
        st.session_state.logado = False
        st.rerun()

    st.title(f"💰 Painel de Controle - {usuario_id}")

    # Processamento do carregamento dinâmico
    df = carregar_dados(gid_aba)

    if df is not None and not df.empty:
        # --- FILTROS LATERAIS ---
        st.sidebar.header("Seleção do Período")
        
        anos_disponiveis = sorted([int(a) for a in df['Data'].dt.year.unique()])
        ano_selecionado = st.sidebar.selectbox("Ano", anos_disponiveis, index=len(anos_disponiveis)-1)
        
        meses_disponiveis = sorted([int(m) for m in df[df['Data'].dt.year == ano_selecionado]['Data'].dt.month.unique()])
        mes_selecionado = st.sidebar.selectbox(
            "Mês", 
            meses_disponiveis, 
            format_func=lambda x: MESES_PT.get(x, str(x))
        )

        # Filtragem dos dados
        dados_filtrados = df[(df['Data'].dt.month == mes_selecionado) & (df['Data'].dt.year == ano_selecionado)]

        if dados_filtrados.empty:
            st.warning(f"Não existem registos para {MESES_PT.get(mes_selecionado)} de {ano_selecionado}.")
        else:
            # --- CÁLCULOS FINANCEIROS ---
            receitas = dados_filtrados[dados_filtrados['Tipo'] == 'Receita']['Valor (R$)'].sum()
            despesas = dados_filtrados[dados_filtrados['Tipo'] == 'Despesa']['Valor (R$)'].sum()
            saldo = receitas - despesas

            # --- EXIBIÇÃO DE INDICADORES ---
            st.subheader(f"Resumo de {MESES_PT.get(mes_selecionado)} de {ano_selecionado}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Receitas (Entradas)", f"R$ {receitas:,.2f}")
            c2.metric("Despesas (Saídas)", f"R$ {despesas:,.2f}", delta=f"-{despesas:,.2f}", delta_color="inverse")
            c3.metric("Saldo Líquido", f"R$ {saldo:,.2f}", delta=f"{saldo:,.2f}")

            st.markdown("---")

            # --- VISUALIZAÇÃO GRÁFICA ---
            col_grafico, col_lista = st.columns([1, 1.2])

            with col_grafico:
                st.subheader("📊 Fluxo de Caixa")
                fig_bar, ax_bar = plt.subplots(figsize=(5, 4))
                ax_bar.bar(['Receitas', 'Despesas'], [receitas, despesas], color=['#2ecc71', '#e74c3c'])
                st.pyplot(fig_bar)

                st.subheader("🥧 Gastos por Categoria")
                por_categoria = dados_filtrados[dados_filtrados['Tipo'] == 'Despesa'].groupby('Categoria')['Valor (R$)'].sum()
                if not por_categoria.empty:
                    fig_pie, ax_pie = plt.subplots()
                    por_categoria.plot(kind='pie', autopct='%1.1f%%', ax=ax_pie, startangle=140, cmap='Set3')
                    ax_pie.set_ylabel('')
                    st.pyplot(fig_pie)

            with col_lista:
                st.subheader("📋 Lista de Movimentações")
                exibicao = dados_filtrados.sort_values(by='Data', ascending=False).copy()
                exibicao['Data'] = exibicao['Data'].dt.strftime('%d/%m/%Y')
                
                st.dataframe(
                    exibicao[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']],
                    use_container_width=True,
                    hide_index=True
                )
