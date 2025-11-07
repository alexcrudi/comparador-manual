import streamlit as st
import pandas as pd
import os
from utils.manual import carregar_csv_siga, carregar_csv_form, preparar_dados_para_visual, \
                         gerar_excel_completo, gerar_csv_completo, gerar_codigo_unico

# -------------------------
# CONFIGURAÇÃO DO APP
# -------------------------
st.set_page_config(
    page_title="Comparador Manual de Inventário",
    layout="wide",
)

st.title("📊 Comparador Manual de Inventário")

st.markdown("""
Sistema desenvolvido para facilitar a comparação manual entre:

✅ Planilha SIGA  
✅ Planilha de Formulário (Tally ou qualquer outra)  

Os arquivos **NÃO são enviados para a internet**, tudo roda localmente.
""")

# -------------------------
# UPLOAD DOS ARQUIVOS
# -------------------------
st.header("📁 Importar arquivos")

uploaded_siga = st.file_uploader("Selecione o arquivo do SIGA (.csv)", type=["csv"])
uploaded_form = st.file_uploader("Selecione o arquivo do Formulário (.csv)", type=["csv"])

if not uploaded_siga or not uploaded_form:
    st.info("⏳ Aguarde… envie os dois arquivos para continuar.")
    st.stop()

# -------------------------
# CARREGAR DATAFRAMES
# -------------------------
df_siga = carregar_csv_siga(uploaded_siga)
df_form = carregar_csv_form(uploaded_form)

# Gerar códigos únicos para itens repetidos do formulário
df_form["codigo_formulario"] = [
    gerar_codigo_unico(i) for i in range(len(df_form))
]

# Criar coluna visual somente para o FORMULÁRIO
df_form["nome_visual"] = df_form.apply(
    lambda row: f"{row.get('Nome', '')} — {row.get('Observações', '')}".strip(" —"),
    axis=1
)

# SIGA usa apenas o nome real
df_siga["nome_visual"] = df_siga["Nome"]

# -------------------------
# PREPARAR LISTA DE OPÇÕES
# -------------------------
opcoes_form = (
    df_form.apply(
        lambda r: f"{r['codigo_formulario']} | {r['nome_visual']}",
        axis=1
    ).tolist()
)

# -------------------------
# TABELA PRINCIPAL DE COMPARAÇÃO
# -------------------------
st.header("✅ Comparação Manual")

st.markdown("""
Selecione manualmente qual item do formulário corresponde a cada item do SIGA.

Cada escolha só pode ser usada **uma vez**.
""")

pareamentos = {}

with st.form("form_comparacao"):
    for idx, row in df_siga.iterrows():
        col1, col2 = st.columns([1.3, 2])

        with col1:
            st.markdown(f"**SIGA:** `{row['Código']}` — {row['Nome']}")

        with col2:
            escolha = st.selectbox(
                f"Selecione o correspondente do Formulário para o item do SIGA {row['Código']}:",
                ["(Nenhum)"] + opcoes_form,
                key=f"sel_{idx}"
            )
            pareamentos[idx] = escolha

    submit = st.form_submit_button("💾 Salvar pareamentos")

if submit:
    st.success("✅ Pareamentos salvos com sucesso!")

# -------------------------
# EXPORTAÇÃO FINAL
# -------------------------
st.header("📤 Exportar Resultados")

if st.button("📘 Exportar XLSX Completo"):
    caminho = gerar_excel_completo(df_siga, df_form, pareamentos)
    st.success(f"Arquivo gerado: `{caminho}`")
    with open(caminho, "rb") as f:
        st.download_button("📥 Baixar XLSX", f, file_name="comparacao_completa.xlsx")

if st.button("📄 Exportar CSV Completo"):
    caminho_csv = gerar_csv_completo(df_siga, df_form, pareamentos)
    st.success(f"Arquivo gerado: `{caminho_csv}`")
    with open(caminho_csv, "rb") as f:
        st.download_button("📥 Baixar CSV", f, file_name="comparacao_completa.csv")

# -------------------------
# RODAPÉ
# -------------------------
st.markdown("---")
st.markdown("""
**Comparador Manual de Inventário**  
Desenvolvido com apoio de ChatGPT  
**Contato:** Alex Crudi — 📱 (15) 9.9127-6070
""")
