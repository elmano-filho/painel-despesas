import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# Configurações de exibição e meses
MESES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

st.set_page_config(page_title="Controle Financeiro Familiar", layout="wide")
st.title("💰 Gestão Mensal: Receitas vs Despesas")

# Identificadores da sua planilha específica
SHEET_ID = "1vUqxY2JKJVDiie7Nmq6bUktYYpd_TKjUQn6ZHav0AsY"
GID = "1458453182"

@st.cache_data(ttl=60) # Atualiza os dados a cada 60 segundos
def carregar_dados():
    try:
        # Monta a URL de exportação para CSV incluindo o GID da aba correta
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}"
        
        # Lê os dados diretamente da web
        df = pd.read_csv(url)
        
        # Limpeza: remove linhas onde a coluna 'Data' está vazia para evitar erros de conversão
        if 'Data' in df.columns:
            df = df.dropna(subset=['Data'])
        else:
            st.error("A coluna 'Data' não foi encontrada na planilha. Verifique o cabeçalho.")
            return None
            
        # Converte para datetime (ajusta conforme o formato da planilha: dia/mês/ano)
        df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Data']) # Remove datas que não puderam ser convertidas
        
        # Garante a existência da coluna 'Tipo' (Receita/Despesa)
        if 'Tipo' not in df.columns:
            df['Tipo'] = 'Despesa'
            
        return df
    except Exception as e:
        st.error(f"Erro ao conectar com o Google Sheets: {e}")
        return None

# Execução do carregamento
df = carregar_dados()

if df is not None and not df.empty:
    # --- FILTROS LATERAIS ---
    st.sidebar.header("Período de Análise")
    
    anos_disp = sorted([int(a) for a in df['Data'].dt.year.unique()])
    ano_sel = st.sidebar.selectbox("Ano", anos_disp, index=len(anos_disp)-1)
    
    # Filtra meses disponíveis para o ano selecionado
    meses_disp = sorted([int(m) for m in df[df['Data'].dt.year == ano_sel]['Data'].dt.month.unique()])
    mes_sel = st.sidebar.selectbox(
        "Mês", 
        meses_disp, 
        format_func=lambda x: MESES_PT.get(x, str(x))
    )

    # Filtragem final dos dados para exibição
    dados_mes = df[(df['Data'].dt.month == mes_sel) & (df['Data'].dt.year == ano_sel)]

    if dados_mes.empty:
        st.warning(f"Nenhum registro encontrado para {MESES_PT.get(mes_sel)} de {ano_sel}.")
    else:
        # --- CÁLCULOS ---
        receitas = dados_mes[dados_mes['Tipo'] == 'Receita']['Valor (R$)'].sum()
        despesas = dados_mes[dados_mes['Tipo'] == 'Despesa']['Valor (R$)'].sum()
        saldo = receitas - despesas

        # --- MÉTRICAS ---
        st.subheader(f"Resumo de {MESES_PT.get(mes_sel)} de {ano_sel}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Faturamento (Receitas)", f"R$ {receitas:,.2f}")
        c2.metric("Gastos (Despesas)", f"R$ {despesas:,.2f}", delta=f"-{despesas:,.2f}", delta_color="inverse")
        c3.metric("Saldo do Mês", f"R$ {saldo:,.2f}", delta=f"{saldo:,.2f}")

        st.markdown("---")

        # --- VISUALIZAÇÃO ---
        col_graf, col_tab = st.columns([1, 1.2])

        with col_graf:
            st.subheader("📊 Fluxo de Caixa")
            fig_bar, ax_bar = plt.subplots(figsize=(5, 4))
            ax_bar.bar(['Entradas', 'Saídas'], [receitas, despesas], color=['#2ecc71', '#e74c3c'])
            st.pyplot(fig_bar)

            st.subheader("🥧 Distribuição por Categoria")
            gastos_cat = dados_mes[dados_mes['Tipo'] == 'Despesa'].groupby('Categoria')['Valor (R$)'].sum()
            if not gastos_cat.empty:
                fig_pie, ax_pie = plt.subplots()
                gastos_cat.plot(kind='pie', autopct='%1.1f%%', ax=ax_pie, startangle=140, cmap='Pastel1')
                ax_pie.set_ylabel('')
                st.pyplot(fig_pie)

        with col_tab:
            st.subheader("📋 Lançamentos Detalhados")
            # Formatação para exibição na tabela
            exibicao = dados_mes.sort_values(by='Data', ascending=False).copy()
            exibicao['Data'] = exibicao['Data'].dt.strftime('%d/%m/%Y')
            
            st.dataframe(
                exibicao[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']],
                use_container_width=True,
                hide_index=True
            )
            
            # Atalho para preenchimento
            st.info("Para adicionar novos gastos, utilize o link da sua planilha compartilhada no Google Drive.")