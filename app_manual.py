import streamlit as st
import pandas as pd
from datetime import datetime
from utils.ler_planilhas import ler_planilha_siga, ler_planilha_form
from utils.manual import preparar_pareamento, sugerir_candidatos, gerar_exportacao

st.set_page_config(page_title="Comparador Manual - Patrimônio", layout="wide")
st.title("📊 Comparador Manual de Inventário Patrimonial")

# --- Sidebar / Configurações e Tema ---
st.sidebar.header("⚙️ Configurações")
limiar = st.sidebar.slider("Limiar similaridade (para sugestões)", 40, 100, 70)
top_k = st.sidebar.number_input("Número de sugestões automáticas", min_value=1, max_value=10, value=5)
show_preview = st.sidebar.checkbox("Mostrar pré-visualização dos dados", value=True)
st.sidebar.markdown("---")
st.sidebar.markdown("Tema & Logo")
st.sidebar.image("assets/logo_placeholder.png", use_column_width=True)

# --- Uploads ---
col1, col2 = st.columns(2)
with col1:
    siga_file = st.file_uploader("Upload planilha SIGA (CSV/XLSX)", type=["csv", "xlsx"], key="siga")
with col2:
    form_file = st.file_uploader("Upload planilha do Formulário (Tally) (CSV/XLSX)", type=["csv", "xlsx"], key="form")

if not (siga_file and form_file):
    st.info("Faça o upload das duas planilhas para começar. Exemplos em /example.")
    st.stop()

# --- Ler planilhas ---
try:
    siga_df = ler_planilha_siga(siga_file)
    form_df = ler_planilha_form(form_file)
except Exception as e:
    st.error(f"Erro ao ler planilhas: {e}")
    st.stop()

# --- Seleção de colunas a exibir ---
st.subheader("🔧 Ocultar / Mostrar Colunas")
col1, col2 = st.columns(2)
with col1:
    colunas_siga = st.multiselect("Colunas SIGA", siga_df.columns.tolist(), default=siga_df.columns.tolist())
with col2:
    colunas_form = st.multiselect("Colunas Formulário", form_df.columns.tolist(), default=form_df.columns.tolist())

siga_view = siga_df[colunas_siga] if colunas_siga else pd.DataFrame()
form_view = form_df[colunas_form] if colunas_form else pd.DataFrame()

if show_preview:
    left, right = st.columns(2)
    with left:
        st.subheader("📘 Visualização SIGA")
        st.dataframe(siga_view, use_container_width=True, height=300)
    with right:
        st.subheader("📙 Visualização Formulário (Tally)")
        st.dataframe(form_view, use_container_width=True, height=300)

# --- Preparar dataframes para pareamento ---
pares_df, somente_siga, somente_form = preparar_pareamento(siga_df, form_df)

st.markdown("---")
st.subheader("🔗 Pareamento Manual (Dropdown inteligente)")

# Disponíveis para seleção (copiar)
disponiveis_full = somente_form.copy()

# Global filter
global_search = st.text_input("🔍 Buscar globalmente no Formulário (filtra opções)", value="", placeholder="ex: cadeira, R-001")

# Table header
cols = st.columns([3,5,5,2])
cols[0].markdown("**Código SIGA**")
cols[1].markdown("**Nome SIGA**")
cols[2].markdown("**Selecionar no Formulário**")
cols[3].markdown("**Ação**")

# Track selected codes to prevent duplicates
selecionados = set()

# Iterate rows
for idx, row in pares_df.iterrows():
    codigo_siga = str(row.get("codigo_siga",""))
    nome_siga = str(row.get("nome_siga",""))

    with st.container():
        rcols = st.columns([3,5,5,2])
        rcols[0].write(codigo_siga)
        rcols[1].write(nome_siga)

        # build options filtered by global_search or per-row search
        df_opts = disponiveis_full.copy()
        # remove already selected
        if selecionados:
            df_opts = df_opts[~df_opts["codigo_tally"].astype(str).isin(selecionados)]

        # per-row search box
        search_key = f"search_{idx}"
        term = rcols[2].text_input("🔎 Filtrar opções (por código/nome)", value="", key=search_key, placeholder="digite para filtrar opções")

        if global_search:
            mask_global = df_opts.apply(lambda x: x.astype(str).str.contains(global_search, case=False, na=False)).any(axis=1)
            df_opts = df_opts[mask_global]

        if term:
            mask = df_opts.apply(lambda x: x.astype(str).str.contains(term, case=False, na=False)).any(axis=1)
            df_opts = df_opts[mask]

        # format options as "code — name"
        options = ["(Nenhum)"] + df_opts.apply(lambda r: f"{r.get('codigo_tally','')} — {r.get('nome_form','')}", axis=1).tolist()

        sel_key = f"sel_{idx}"
        escolha = rcols[2].selectbox("Selecione", options, key=sel_key, index=0)

        if escolha != "(Nenhum)":
            codigo_escolhido = escolha.split(" — ")[0].strip()
            pares_df.at[idx, "codigo_tally"] = codigo_escolhido
            selecionados.add(codigo_escolhido)

        # suggestions button
        if rcols[3].button("Sugestões", key=f"sug_{idx}"):
            candidatos = sugerir_candidatos(nome_siga, disponiveis_full, k=top_k)
            st.session_state[f"sug_list_{idx}"] = candidatos

        # show suggestions
        if f"sug_list_{idx}" in st.session_state:
            cand = st.session_state[f"sug_list_{idx}"]
            if isinstance(cand, list) and len(cand)>0:
                st.write("Sugestões (similaridade):")
                for code, name, score in cand:
                    st.write(f"- {code} — {name}  ({score}%)")

st.markdown("---")

# --- Exportação ---
st.subheader("📤 Exportar Resultado")
nome_base = st.text_input("Nome base do arquivo", value=f"comparador_manual_{datetime.now().strftime('%Y%m%d_%H%M')}")
col1, col2 = st.columns(2)
with col1:
    if st.button("Gerar XLSX (abas)"):
        out = gerar_exportacao(pares_df, somente_siga, somente_form, nome_base=nome_base, compact=False)
        st.download_button("⬇️ Baixar XLSX", data=out.getvalue(), file_name=f"{nome_base}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with col2:
    if st.button("Gerar ZIP (CSVs)"):
        outzip = gerar_exportacao(pares_df, somente_siga, somente_form, nome_base=nome_base, compact=True)
        st.download_button("⬇️ Baixar ZIP", data=outzip.getvalue(), file_name=f"{nome_base}.zip", mime="application/zip")

st.sidebar.markdown("---")
st.sidebar.markdown("Made with ❤️ — Comparador Manual")
