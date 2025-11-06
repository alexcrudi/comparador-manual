import streamlit as st
import pandas as pd
from utils.ler_planilhas import ler_planilha_siga, ler_planilha_form
from utils.manual import preparar_pareamento, gerar_exportacao, sugerir_candidatos
from datetime import datetime

st.set_page_config(page_title="Comparador Manual - Patrimônio", layout="wide")
st.title("📊 Comparador Manual de Inventário Patrimonial")

# Sidebar / configurações
st.sidebar.header("⚙️ Configurações")
limiar = st.sidebar.slider("Limiar similaridade (para sugestões)", 40, 100, 70)
top_k = st.sidebar.number_input("Número de sugestões automáticas", min_value=1, max_value=10, value=5)
show_preview = st.sidebar.checkbox("Mostrar pré-visualização dos dados", value=True)
st.sidebar.markdown("---")
st.sidebar.markdown("Tema: cores e logo")
st.sidebar.image("assets/logo_placeholder.png", use_column_width=True)

# Uploads
col1, col2 = st.columns(2)
with col1:
    siga_file = st.file_uploader("Upload planilha SIGA (CSV/XLSX)", type=["csv", "xlsx"], key="siga")
with col2:
    form_file = st.file_uploader("Upload planilha do Formulário (Tally) (CSV/XLSX)", type=["csv", "xlsx"], key="form")

if not (siga_file and form_file):
    st.info("Faça o upload das duas planilhas para começar. Há exemplos em `example/`.")
    st.stop()

# Ler planilhas
siga_df = ler_planilha_siga(siga_file)
form_df = ler_planilha_form(form_file)

# Preservar colunas originais
siga_df = siga_df.copy()
form_df = form_df.copy()

# Escolha de colunas a exibir
st.subheader("🔧 Ocultar / Mostrar Colunas")
col1, col2 = st.columns(2)
with col1:
    colunas_siga = st.multiselect("Colunas SIGA", siga_df.columns.tolist(), default=siga_df.columns.tolist())
with col2:
    colunas_form = st.multiselect("Colunas Formulário", form_df.columns.tolist(), default=form_df.columns.tolist())

siga_view = siga_df[colunas_siga]
form_view = form_df[colunas_form]

if show_preview:
    left, right = st.columns(2)
    with left:
        st.subheader("📘 Visualização SIGA")
        st.dataframe(siga_view, use_container_width=True, height=300)
    with right:
        st.subheader("📙 Visualização Formulário (Tally)")
        st.dataframe(form_view, use_container_width=True, height=300)

# Preparar dataframe de pareamento
pares_df, somente_siga, somente_form = preparar_pareamento(siga_df, form_df)

st.markdown("---")
st.subheader("🔗 Pareamento Manual (Dropdown inteligente)")

# Convert somente_form to list of dicts for quick filtering
disponiveis = somente_form.copy()

# Provide a global search box to filter form side if user wants
global_search = st.text_input("🔍 Buscar (para filtrar opções do formulário globalmente) — digite parte do nome ou código", value="", placeholder="ex: cadeira, AC-123, motor")

# For each item in SIGA we render a row with search + selectbox
st.write("Digite para filtrar as opções do formulário ou clique em 'Sugestões automáticas' para preencher usando fuzzy matching.")
cols = st.columns([3,4,3,2])
cols[0].markdown("**Código SIGA**")
cols[1].markdown("**Nome SIGA**")
cols[2].markdown("**Busque / Selecione no Formulário**")
cols[3].markdown("**Ação**")

# We'll store selections in a local dict to keep which codes were chosen
selecionados = {}

for idx, row in pares_df.iterrows():
    c_siga = row.get("codigo_siga", "")
    n_siga = row.get("nome_siga", "")
    with st.container():
        rcols = st.columns([3,4,3,2])
        rcols[0].write(str(c_siga))
        rcols[1].write(str(n_siga))
        # Search input for this row
        search_key = f"search_{idx}"
        term = rcols[2].text_input("🔎", value="", key=search_key, placeholder="Digite para filtrar (ex: parte do nome ou código)")
        # Build options: filter disponiveis by term OR global_search
        df_opts = disponiveis.copy()
        if global_search:
            mask = df_opts.apply(lambda x: x.astype(str).str.contains(global_search, case=False, na=False)).any(axis=1)
            df_opts = df_opts[mask]
        if term:
            mask = df_opts.apply(lambda x: x.astype(str).str.contains(term, case=False, na=False)).any(axis=1)
            df_opts = df_opts[mask]
        # Format options as "codigo_tally - nome_form"
        options = ["(Nenhum)"] + (df_opts.apply(lambda r: f\"{r.get('codigo_tally','')}\t - \t{r.get('nome_form','')}\", axis=1).tolist())
        sel_key = f"sel_{idx}"
        escolha = rcols[2].selectbox("Selecione", options, key=sel_key, index=0)
        if escolha != "(Nenhum)":
            # Extract codigo_tally from escolha (before tab)
            codigo_escolhido = escolha.split("\t")[0].strip()
            pares_df.at[idx, "codigo_tally"] = codigo_escolhido
            selecionados[codigo_escolhido] = True
            # remove selecionado from disponiveis
            disponiveis = disponiveis[disponiveis["codigo_tally"].astype(str) != codigo_escolhido]
        # Suggest button
        if rcols[3].button("Sugestões automáticas", key=f"sug_{idx}"):
            candidatos = sugerir_candidatos(n_siga, disponiveis, k=top_k)
            st.session_state[f"sug_list_{idx}"] = candidatos
        # Show suggestions if exist
        if f"sug_list_{idx}" in st.session_state:
            cand = st.session_state[f"sug_list_{idx}"]
            if isinstance(cand, list) and len(cand)>0:
                st.write("Sugestões (Similaridade):")
                for code, name, score in cand:
                    st.write(f\"- {code} — {name}  ({score}%)\")
st.markdown("---")

# Export / salvar mapeamentos
st.subheader("📤 Exportar Resultado")
nome_arquivo = st.text_input("Nome base do arquivo", value=f\"comparador_manual_{datetime.now().strftime('%Y%m%d_%H%M')}\")
col1, col2 = st.columns(2)
with col1:
    if st.button("Gerar XLSX com abas"):
        out = gerar_exportacao(pares_df, somente_siga, somente_form, nome_arquivo)
        st.download_button("⬇️ Baixar XLSX", data=out.getvalue(), file_name=f\"{nome_arquivo}.xlsx\", mime=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\")
with col2:
    if st.button("Gerar CSV compactado (ZIP)"):
        zip_bytes = gerar_exportacao(pares_df, somente_siga, somente_form, nome_arquivo, compact=True)
        st.download_button("⬇️ Baixar ZIP", data=zip_bytes.getvalue(), file_name=f\"{nome_arquivo}.zip\", mime=\"application/zip\")

st.sidebar.markdown(\"---\")
st.sidebar.markdown(\"Made with ❤️ — Comparador Manual\") 
