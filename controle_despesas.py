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
        st.error("⚠️ Erro nas configurações de Secrets. Verifique o ficheiro secrets.toml.")
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

    # --- TELA DE NOVIDADES (Últimos 7 dias) ---
    if not st.session_state.viu_novidades:
        st.title(f"🔔 Olá, {usuario_id.replace('_', ' ')}!")
        st.subheader("Lançamentos Recentes (Últimos 7 dias)")
        
        with st.spinner("A verificar lançamentos..."):
            df_total = carregar_dados(gid_aba)
            
            if df_total is not None and not df_total.empty:
                # Remove fusos horários para evitar erros na comparação
                df_total['Data'] = pd.to_datetime(df_total['Data']).dt.tz_localize(None)
                
                # Calcula a data de 7 dias atrás
                data_limite = datetime.now() - timedelta(days=7)
                
                # Filtra apenas o que é igual ou mais recente que a data limite
                recentes = df_total[df_total['Data'] >= data_limite].copy()
            else:
                recentes = pd.DataFrame()
        
        if not recentes.empty:
            st.write(f"Foram detetados **{len(recentes)}** registos recentes:")
            recentes['Data'] = recentes['Data'].dt.strftime('%d/%m/%Y')
            st.dataframe(recentes[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']], use_container_width=True, hide_index=True)
        else:
            st.info("Não existem lançamentos recentes nos últimos 7 dias.")

        if st.button("Ir para o Painel Principal"):
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
                # LINHAS CORRIGIDAS: O erro de corte (unterminated string literal) foi consertado aqui.
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
                    st.subheader("📋 Movimentações")
                    exibicao = dados_filtrados.sort_values(by='Data', ascending=False).copy()
                    exibicao['Data'] = exibicao['Data'].dt.strftime('%d/%m/%Y')
                    st.dataframe(exibicao[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']], use_container_width=True, hide_index=True)
