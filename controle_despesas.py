import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import re
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
                df_total['Data'] = pd.to_datetime(df_total['Data']).dt.tz_localize(None)
                data_limite = datetime.now() - timedelta(days=7)
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
            
            # =========================================================
            # SELEÇÃO INTELIGENTE DE DATA (Mês atual como padrão)
            # =========================================================
            st.sidebar.header("Seleção do Período Mensal")
            hoje = datetime.now()
            ano_atual = hoje.year
            mes_atual = hoje.month

            anos_disponiveis = sorted([int(a) for a in df['Data'].dt.year.unique()])
            try:
                index_ano = anos_disponiveis.index(ano_atual)
            except ValueError:
                index_ano = len(anos_disponiveis) - 1 

            ano_selecionado = st.sidebar.selectbox("Ano", anos_disponiveis, index=index_ano)
            
            df_ano = df[df['Data'].dt.year == ano_selecionado]
            meses_disponiveis = sorted([int(m) for m in df_ano['Data'].dt.month.unique()])
            
            try:
                index_mes = meses_disponiveis.index(mes_atual)
            except ValueError:
                index_mes = len(meses_disponiveis) - 1 

            mes_selecionado = st.sidebar.selectbox(
                "Mês", 
                meses_disponiveis, 
                index=index_mes,
                format_func=lambda x: MESES_PT.get(x, str(x))
            )

            # --- FILTRAGEM DE DADOS MENSAL ---
            dados_filtrados = df[(df['Data'].dt.month == mes_selecionado) & (df['Data'].dt.year == ano_selecionado)]

            if dados_filtrados.empty:
                st.warning(f"Sem registos para {MESES_PT.get(mes_selecionado)} de {ano_selecionado}.")
            else:
                receitas = dados_filtrados[dados_filtrados['Tipo'] == 'Receita']['Valor (R$)'].sum()
                despesas = dados_filtrados[dados_filtrados['Tipo'] == 'Despesa']['Valor (R$)'].sum()
                
                st.subheader(f"Resumo de {MESES_PT.get(mes_selecionado)} de {ano_selecionado}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Receitas", f"R$ {receitas:,.2f}")
                c2.metric("Despesas", f"R$ {despesas:,.2f}", delta=f"-{despesas:,.2f}", delta_color="inverse")
                c3.metric("Saldo do Mês", f"R$ {(receitas - despesas):,.2f}")

                st.markdown("---")
                col_grafico, col_lista = st.columns([1, 1.2])

                with col_grafico:
                    st.subheader("📊 Fluxo de Caixa Mensal")
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
                    st.subheader("📋 Movimentações do Mês")
                    exibicao = dados_filtrados.sort_values(by='Data', ascending=False).copy()
                    exibicao['Data'] = exibicao['Data'].dt.strftime('%d/%m/%Y')
                    st.dataframe(exibicao[['Data', 'Tipo', 'Categoria', 'Descrição', 'Valor (R$)']], use_container_width=True, hide_index=True)

            # =========================================================
            # BALANÇO HISTÓRICO GERAL E ACERTO DE CONTAS
            # =========================================================
            st.markdown("---")
            with st.expander("🏦 Ver Balanço Histórico Acumulado (Todo o Período)", expanded=False):
                # 1. BALANÇO GERAL DA CONTA
                rec_hist = df[df['Tipo'] == 'Receita']['Valor (R$)'].sum()
                des_hist = df[df['Tipo'] == 'Despesa']['Valor (R$)'].sum()
                saldo_hist = rec_hist - des_hist
                
                if saldo_hist > 0:
                    status = "✅ Dinheiro em Caixa (Sobras)"
                    cor_delta = "normal"
                elif saldo_hist < 0:
                    status = "⚠️ Déficit Acumulado (Injetado a mais)"
                    cor_delta = "inverse"
                else:
                    status = "⚖️ Contas perfeitamente equilibradas"
                    cor_delta = "off"

                st.write(f"**Status Global da Conta:** {status}")
                ch1, ch2, ch3 = st.columns(3)
                ch1.metric("Total de Receitas", f"R$ {rec_hist:,.2f}")
                ch2.metric("Total de Despesas", f"R$ {des_hist:,.2f}")
                ch3.metric("Saldo Acumulado", f"R$ {saldo_hist:,.2f}", delta=f"R$ {saldo_hist:,.2f}", delta_color=cor_delta)

                st.markdown("---")
                
                # 2. ACERTO DE CONTAS ENTRE PESSOAS (COMPLEMENTAÇÃO)
                st.subheader("🤝 Acerto de Contas (Contribuintes)")
                st.caption("Baseado nas rubricas *Complementação - [Nome] - Outras Despesas*")

                # Padrão flexível para encontrar a rubrica ignorando espaços extras e maiúsculas/minúsculas
                padrao_nome = r'Complementa[çc][ãa]o\s*-\s*([A-Za-zÀ-ÿ]+)\s*-\s*Outras Despesas'

                def extrair_contribuinte(texto):
                    if pd.isna(texto): return None
                    match = re.search(padrao_nome, str(texto), re.IGNORECASE)
                    if match: return match.group(1).strip().capitalize()
                    return None

                # Procura o nome na Descrição ou na Categoria
                df_temp = df.copy()
                df_temp['Contribuinte'] = df_temp['Descrição'].apply(extrair_contribuinte)
                if 'Categoria' in df_temp.columns:
                    df_temp.loc[df_temp['Contribuinte'].isnull(), 'Contribuinte'] = df_temp['Categoria'].apply(extrair_contribuinte)

                df_comp = df_temp.dropna(subset=['Contribuinte'])

                if df_comp.empty:
                    st.info("Nenhum registo de 'Complementação' encontrado no histórico.")
                else:
                    saldos_pessoas = {}
                    for pessoa in df_comp['Contribuinte'].unique():
                        df_p = df_comp[df_comp['Contribuinte'] == pessoa]
                        rec_p = df_p[df_p['Tipo'] == 'Receita']['Valor (R$)'].sum()
                        desp_p = df_p[df_p['Tipo'] == 'Despesa']['Valor (R$)'].sum()

                        # Saldo da pessoa = Tudo o que injetou (Receita) - Tudo o que retirou/gastou (Despesa)
                        saldos_pessoas[pessoa] = rec_p - desp_p

                    num_pessoas = len(saldos_pessoas)
                    total_contribuido = sum(saldos_pessoas.values())
                    media_ideal = total_contribuido / num_pessoas if num_pessoas > 0 else 0

                    c_pessoas = st.columns(num_pessoas)
                    i = 0
                    for pessoa, saldo in saldos_pessoas.items():
                        diferenca = saldo - media_ideal

                        if diferenca > 0:
                            texto_acerto = f"🟢 Tem a receber: **R$ {diferenca:,.2f}**"
                        elif diferenca < 0:
                            texto_acerto = f"🔴 Deve compensar: **R$ {abs(diferenca):,.2f}**"
                        else:
                            texto_acerto = "⚪ Tudo quite"

                        with c_pessoas[i]:
                            st.write(f"**{pessoa}**")
                            st.write(f"Injeção Líquida: R$ {saldo:,.2f}")
                            st.markdown(texto_acerto)
                        i += 1

                    st.caption(f"*(A média ideal de injeção financeira por pessoa foi de R$ {media_ideal:,.2f})*")
