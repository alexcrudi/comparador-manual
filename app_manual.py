import streamlit as st
import pandas as pd
from io import BytesIO
from utils.manual import (
    ler_planilha_siga,
    ler_planilha_form,
    preparar_pareamento,
    sugerir_candidatos,
    gerar_exportacao
)
from datetime import datetime

st.set_page_config(page_title="Comparador Manual - SIGA x Formulário", layout="wide")
st.title("📊 Comparador Manual — SIGA x Formulário (Formulário = Submission ID → Código Formulário)")
st.caption("Visualização concatenada (Nome + Observações). Exporta XLSX com 3 abas: Pareados / Somente_SIGA / Somente_Formulário")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("⚙️ Configurações & Upload")
    st.markdown("Faça upload das planilhas abaixo (CSV ou XLSX).")
    siga_file = st.file_uploader("Arquivo SIGA", type=["csv", "xlsx"])
    form_file = st.file_uploader("Arquivo Formulário (exportação do formulário)", type=["csv", "xlsx"])

    st.markdown("---")
    st.subheader("Sugestões (fuzzy)")
    limiar = st.slider("Limiar mínimo para sugerir", 40, 95, 65)
    top_k = st.number_input("Sugestões por item (k)", min_value=1, max_value=10, value=5)

    st.markdown("---")
    st.subheader("Exibição")
    mostrar_preview = st.checkbox("Mostrar pré-visualização das planilhas", value=True)
    st.markdown("Escolha colunas visíveis (UI somente) — você pode ocultar e reexibir a qualquer momento.")

# ---------- Carregamento ----------
if not (siga_file and form_file):
    st.info("Envie ambos os arquivos (SIGA e Formulário) na barra lateral para começar.")
    st.stop()

# Ler planilhas (funções tratam nomes reais das colunas)
siga_df = ler_planilha_siga(siga_file)
form_df = ler_planilha_form(form_file)  # aqui Submission ID vira codigo_form internamente

# Criar campos visuais (sem alterar originais)
# SIGA: assume colunas originais como: Código, Nome, Fornecedor, Localidade, Conta, Nº Documento, Dependência, Dt. Aquisição, Vl. Aquisição, Vl. Deprec., Vl. Atual, Status
siga_df = siga_df.copy()
if "observacao" not in siga_df.columns:
    # garante coluna observacao mesmo vazia para concat
    siga_df["observacao"] = ""

siga_df["nome_visual"] = siga_df.apply(
    lambda r: f"{r.get('nome','')}" + (f" ({r.get('observacao','')})" if r.get("observacao") else ""),
    axis=1
)

# Formulário: campos reais fornecidos — criamos nome_visual a partir de "Nome / Tipo de Bens" + "Observações"
form_df = form_df.copy()
if "observacoes" not in form_df.columns and "observacao" not in form_df.columns:
    # garantir chave 'observacao' com preferência por 'Observações' ou 'observacoes'
    form_df["observacao"] = ""
else:
    # padronizar para 'observacao'
    if "observacoes" in form_df.columns and "observacao" not in form_df.columns:
        form_df = form_df.rename(columns={"observacoes": "observacao"})

# nome_form já mapeado em ler_planilha_form como 'nome_form' e código como 'codigo_form'
form_df["nome_visual"] = form_df.apply(
    lambda r: f"{r.get('nome_form','')}" + (f" ({r.get('observacao','')})" if r.get("observacao") else ""),
    axis=1
)

# ---------- Escolha de colunas visíveis (somente visual) ----------
st.subheader("🔧 Ocultar / Mostrar Colunas (visual)")
col1, col2 = st.columns(2)

with col1:
    cols_siga = st.multiselect(
        "Colunas SIGA (visual)",
        options=list(siga_df.columns),
        default=["codigo", "nome_visual", "dependencia"]
    )
with col2:
    cols_form = st.multiselect(
        "Colunas Formulário (visual)",
        options=list(form_df.columns),
        default=["codigo_form", "nome_visual", "dependencia_form"]
    )

# Mostrar previews (opcional)
if mostrar_preview:
    left, right = st.columns(2)
    with left:
        st.subheader("📘 Preview SIGA")
        try:
            st.dataframe(siga_df[cols_siga], use_container_width=True, height=300)
        except Exception:
            st.dataframe(siga_df.head(10), use_container_width=True, height=300)
    with right:
        st.subheader("📙 Preview Formulário")
        try:
            st.dataframe(form_df[cols_form], use_container_width=True, height=300)
        except Exception:
            st.dataframe(form_df.head(10), use_container_width=True, height=300)

st.markdown("---")

# ---------- Preparar pareamento ----------
pares_df, somente_siga, somente_form = preparar_pareamento(siga_df, form_df)

st.subheader("🔗 Pareamento Manual — Lista de Itens SIGA")
st.write("Use o campo de busca por linha ou o filtro global para restringir as opções do formulário. Ao selecionar um item do formulário, ele fica indisponível para outros itens (pareamento 1-para-1).")

# global search para filtrar opções do formulário
global_search = st.text_input("🔎 Buscar globalmente no formulário (filtra opções para todos)", value="", placeholder="ex: cadeira, R-001, microfone").strip().lower()

# container para controle de selecionados
if "selecionados" not in st.session_state:
    st.session_state["selecionados"] = set()

# pré-cálculo de sugestões fuzzy (apenas para mostrar sugestão)
sugestao_df = sugerir_candidatos(pares_df, form_df, k=top_k)
# juntar sugestao_df na ordem de pares_df
# garantimos que 'sugestao_df' tenha índice alinhado ao pares_df (mesma ordem)
sugestao_df = sugestao_df.reindex(pares_df.index).reset_index(drop=True)

# Loop para cada item SIGA
pares_confirmados = []
for idx, siga_row in pares_df.reset_index(drop=True).iterrows():
    codigo_siga = str(siga_row.get("codigo", ""))
    nome_siga = str(siga_row.get("nome", ""))
    nome_visual_siga = str(siga_row.get("nome_visual", nome_siga))
    score_sug = int(sugestao_df.at[idx, "score"]) if ("score" in sugestao_df.columns and idx in sugestao_df.index) else None
    melhor_code = sugestao_df.at[idx, "best_code"] if ("best_code" in sugestao_df.columns and idx in sugestao_df.index) else None

    # cartão com informação e similaridade
    st.markdown(
        f"""
        <div style="border:1px solid #e6e6e6;padding:12px;border-radius:8px;margin-bottom:8px;">
            <b>{codigo_siga}</b> — <span style="font-size:1.05em">{nome_visual_siga}</span>
            <div style="float:right;"><small>Sugestão: <b>{melhor_code or '-'}</b> | Score: <b>{score_sug if score_sug is not None else '-'}</b>%</small></div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # campo de busca por linha (funcional)
    filtro_key = f"filtro_{idx}"
    filtro = st.text_input("🔎 Filtrar opções (por código/nome):", key=filtro_key, value="").strip().lower()

    # construir opções filtradas
    df_opts = form_df.copy()

    # aplica filtro global
    if global_search:
        mask_global = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(global_search, na=False)).any(axis=1)
        df_opts = df_opts[mask_global]

    # aplica filtro linha
    if filtro:
        mask_row = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(filtro, na=False)).any(axis=1)
        df_opts = df_opts[mask_row]

    # remove já selecionados (1-para-1)
    if st.session_state["selecionados"]:
        df_opts = df_opts[~df_opts["codigo_form"].astype(str).isin(st.session_state["selecionados"])]

    # criar lista de opções formatadas
    options = ["(Nenhum)"] + df_opts.apply(lambda r: f"{r.get('codigo_form','')} — {r.get('nome_visual','')}", axis=1).tolist()

    sel_key = f"sel_{idx}"
    escolha = st.selectbox("Selecionar item do formulário para parear:", options, key=sel_key, index=0)

    codigo_form_escolhido = None
    if escolha and escolha != "(Nenhum)":
        codigo_form_escolhido = escolha.split(" — ")[0].strip()
        # registra selecionado globalmente
        st.session_state["selecionados"].add(codigo_form_escolhido)

    # registra o par (mesmo que vazio)
    pares_confirmados.append({
        "codigo_siga": codigo_siga,
        "nome_siga": nome_siga,
        "observacao_siga": siga_row.get("observacao", ""),
        "dependencia_siga": siga_row.get("dependencia", ""),
        "codigo_form": codigo_form_escolhido,
        "nome_form": form_df.loc[form_df["codigo_form"] == codigo_form_escolhido, "nome_form"].squeeze() if codigo_form_escolhido is not None else "",
        "observacao_form": form_df.loc[form_df["codigo_form"] == codigo_form_escolhido, "observacao"].squeeze() if codigo_form_escolhido is not None else "",
        "dependencia_form": form_df.loc[form_df["codigo_form"] == codigo_form_escolhido, "dependencia_form"].squeeze() if codigo_form_escolhido is not None else "",
        "similaridade": score_sug if score_sug is not None else ""
    })

    st.markdown("---")

# ---------- Após loop: preparar DataFrames finais ----------
pareados_df = pd.DataFrame(pares_confirmados)

# Itens somente no SIGA -> aqueles cujo codigo_siga aparece e codigo_form é None ou '(Nenhum)'
somente_siga_df = siga_df[~siga_df["codigo"].isin(pareados_df[pareados_df["codigo_form"].notna()]["codigo_siga"])].copy()
# Observação: acima assume que itens pareados possuem codigo_form não nulo. Para incluir todos os não pareados:
somente_siga_df = siga_df[~siga_df["codigo"].isin(pareados_df[pareados_df["codigo_form"].notna()]["codigo_siga"])]

# Itens somente no Formulário -> aqueles cujo codigo_form não foi selecionado por nenhum pares_confirmados
selecionados_forms = set(pareados_df["codigo_form"].dropna().astype(str).tolist())
somente_form_df = form_df[~form_df["codigo_form"].astype(str).isin(selecionados_forms)].copy()

st.success("Conferência concluída na UI. Agora você pode exportar os resultados.")

# ---------- Exportar: XLSX com 3 abas ----------
st.subheader("📤 Exportar Resultado")
nome_base = st.text_input("Nome base do arquivo:", value=f"comparador_manual_{datetime.now().strftime('%Y%m%d_%H%M')}")

col_exp1, col_exp2 = st.columns(2)
with col_exp1:
    if st.button("Gerar XLSX (3 abas)"):
        xlsx_bytes = gerar_exportacao(
            pareados_df,
            somente_siga_df,
            somente_form_df,
            siga_df,
            form_df,
            nome_base=nome_base,
            compact=False
        )
        st.success("XLSX pronto.")
        st.download_button("⬇️ Baixar XLSX", data=xlsx_bytes.getvalue(), file_name=f"{nome_base}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
with col_exp2:
    if st.button("Gerar ZIP (CSVs)"):
        zip_bytes = gerar_exportacao(
            pareados_df,
            somente_siga_df,
            somente_form_df,
            siga_df,
            form_df,
            nome_base=nome_base,
            compact=True
        )
        st.success("ZIP com CSVs pronto.")
        st.download_button("⬇️ Baixar ZIP", data=zip_bytes.getvalue(), file_name=f"{nome_base}.zip", mime="application/zip")

st.sidebar.markdown("---")
st.sidebar.write("Comparador Manual — exporta tudo em XLSX (3 abas).")
