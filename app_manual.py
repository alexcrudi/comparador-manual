# app_manual.py
import streamlit as st
import pandas as pd
from utils.manual import (
    ler_planilha_siga,
    ler_planilha_form,
    preparar_pareamento,
    gerar_exportacao
)
from datetime import datetime

st.set_page_config(page_title="Comparador Manual - SIGA x Formulário", layout="wide")
st.title("📊 Comparador Manual — SIGA x Formulário (Manual 100%)")
st.caption("Formato do dropdown: <Código Formulário> — <Nome> | <Observações>")

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Upload & Configurações")
    st.markdown("Envie os arquivos (CSV ou XLSX).")
    siga_file = st.file_uploader("Arquivo SIGA", type=["csv", "xlsx"])
    form_file = st.file_uploader("Arquivo Formulário (exportação)", type=["csv", "xlsx"])
    st.markdown("---")
    st.subheader("Exibição")
    mostrar_preview = st.checkbox("Mostrar pré-visualização das planilhas", value=True)
    st.markdown("Ocultar/mostrar colunas é apenas visual e NÃO altera a exportação.")
    st.markdown("---")
    st.info("Este modo é 100% manual: você decide o pareamento. Itens escolhidos não podem ser escolhidos novamente.")

# ---------------- Require uploads ----------------
if not (siga_file and form_file):
    st.info("Envie os dois arquivos na barra lateral para iniciar.")
    st.stop()

# ---------------- Ler planilhas ----------------
try:
    siga_df = ler_planilha_siga(siga_file)
    form_df = ler_planilha_form(form_file)
except Exception as e:
    st.error(f"Erro ao ler arquivos: {e}")
    st.stop()

# garantir colunas observacao nas duas (vazias se não existirem)
if "observacao" not in siga_df.columns:
    siga_df["observacao"] = ""
if "observacao" not in form_df.columns:
    form_df["observacao"] = ""

# criar campo visual (apenas para exibir)
siga_df["nome_visual"] = siga_df.apply(lambda r: f"{r.get('nome','')}" + (f" | {r.get('observacao','')}" if r.get('observacao') else ""), axis=1)
form_df["nome_visual"] = form_df.apply(lambda r: f"{r.get('nome_form','')}" + (f" | {r.get('observacao','')}" if r.get('observacao') else ""), axis=1)

# ---------------- Colunas visíveis (multiselect) - visual only ----------------
st.subheader("🔧 Ocultar / Mostrar Colunas (visual)")
col1, col2 = st.columns(2)
with col1:
    cols_siga_default = ["codigo", "nome_visual", "dependencia"]
    cols_siga = st.multiselect("Colunas SIGA (visual)", options=list(siga_df.columns), default=cols_siga_default)
with col2:
    # default pick codigo_form if exists else the first
    default_form = ["codigo_form", "nome_visual", "dependencia_form"]
    available_form_cols = list(form_df.columns)
    # ensure defaults present in available
    default_present = [c for c in default_form if c in available_form_cols]
    if not default_present:
        default_present = available_form_cols[:3] if len(available_form_cols) >= 3 else available_form_cols
    cols_form = st.multiselect("Colunas Formulário (visual)", options=available_form_cols, default=default_present)

# previews
if mostrar_preview:
    left, right = st.columns(2)
    with left:
        st.subheader("📘 Preview SIGA (visual)")
        try:
            st.dataframe(siga_df[cols_siga], use_container_width=True, height=300)
        except Exception:
            st.dataframe(siga_df.head(10), use_container_width=True, height=300)
    with right:
        st.subheader("📙 Preview Formulário (visual)")
        try:
            st.dataframe(form_df[cols_form], use_container_width=True, height=300)
        except Exception:
            st.dataframe(form_df.head(10), use_container_width=True, height=300)

st.markdown("---")

# ---------------- Preparar pareamento ----------------
pares_df, somente_siga_df, somente_form_df = preparar_pareamento(siga_df, form_df)

st.subheader("🔗 Pareamento Manual — Itens SIGA")
st.write("Para cada item SIGA escolha manualmente o item correspondente do Formulário. Use o filtro global ou por linha para encontrar o item desejado. Uma vez selecionado, o item ficará indisponível para os outros (controle 1-para-1).")

# global search
global_search = st.text_input("🔎 Buscar globalmente no formulário (filtra opções):", value="", placeholder="ex: banco, R-001, 2.50m").strip().lower()

# session_state structures to keep selections persistent
if "selection_map" not in st.session_state:
    # maps row_idx -> codigo_form (or None)
    st.session_state.selection_map = {}
if "selected_forms" not in st.session_state:
    # set of codigo_form currently selected
    st.session_state.selected_forms = set()

# loop through itens SIGA
pares_confirmados = []
for idx, siga_row in pares_df.reset_index(drop=True).iterrows():
    codigo_siga = str(siga_row.get("codigo", ""))
    nome_siga = str(siga_row.get("nome", ""))
    nome_visual_siga = str(siga_row.get("nome_visual", nome_siga))

    # display card with divider
    st.markdown(f"**{codigo_siga} — {nome_visual_siga}**")
    # per-row filter
    filtro = st.text_input("🔎 Filtrar opções (por código/nome/obs):", key=f"filtro_{idx}", value="").strip().lower()

    # build options DataFrame copy
    df_opts = form_df.copy()

    # apply global filter if present
    if global_search:
        mask_global = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(global_search, na=False)).any(axis=1)
        df_opts = df_opts[mask_global]

    # apply per-row filter if present
    if filtro:
        mask_row = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(filtro, na=False)).any(axis=1)
        df_opts = df_opts[mask_row]

    # remove already selected forms (1-para-1)
    available_df = df_opts[~df_opts["codigo_form"].astype(str).isin(st.session_state.selected_forms)].copy()

    # options list formatted: "<codigo_form> — <nome> | <observacao>"
    def _fmt(r):
        code = str(r.get("codigo_form", ""))
        name = str(r.get("nome_form", ""))
        obs = str(r.get("observacao", ""))
        if obs:
            return f"{code} — {name} | {obs}"
        else:
            return f"{code} — {name}"

    options = ["(Nenhum)"] + [ _fmt(r) for _, r in available_df.iterrows() ]

    # restore previous selection for this row if exists and still available; else default to "(Nenhum)"
    prev = st.session_state.selection_map.get(str(idx), None)
    # determine index for selectbox
    index_default = 0
    if prev:
        # prev might have been removed by global filters; if prev not in current available_df keep "(Nenhum)"
        prev_in_avail = prev in available_df["codigo_form"].astype(str).tolist()
        if prev_in_avail:
            # find position in options (offset +1 because of "(Nenhum)")
            try:
                index_default = 1 + available_df["codigo_form"].astype(str).tolist().index(prev)
            except ValueError:
                index_default = 0
        else:
            # keep the previous as selected but still show it so user can deselect
            # we will prepend prev as a special option so user sees it and can change
            if prev != "(Nenhum)":
                # find details for prev to display
                prev_row = form_df[form_df["codigo_form"].astype(str) == str(prev)]
                if not prev_row.empty:
                    prev_fmt = _fmt(prev_row.iloc[0])
                else:
                    prev_fmt = f"{prev} — (selecionado anteriormente)"
                # ensure prev is first after "(Nenhum)"
                options = ["(Nenhum)", prev_fmt] + [opt for opt in options[1:] if prev not in opt]
                index_default = 1

    sel = st.selectbox("Selecionar item do formulário para parear:", options, key=f"sel_{idx}", index=index_default)

    # process selection change: map selection string to code
    chosen_code = None
    if sel and sel != "(Nenhum)":
        # extract code before first " — "
        if " — " in sel:
            chosen_code = sel.split(" — ")[0].strip()
        else:
            chosen_code = sel.strip()

    # update session_state.selected_forms and selection_map accordingly
    prev_selected = st.session_state.selection_map.get(str(idx), None)
    if prev_selected and prev_selected != chosen_code:
        # user changed selection: remove previous from global selected set
        if prev_selected in st.session_state.selected_forms:
            st.session_state.selected_forms.discard(prev_selected)

    if chosen_code:
        # add new chosen
        st.session_state.selected_forms.add(chosen_code)
        st.session_state.selection_map[str(idx)] = chosen_code
    else:
        # none chosen
        if str(idx) in st.session_state.selection_map:
            # remove previous mapping
            prev_v = st.session_state.selection_map.pop(str(idx))
            if prev_v in st.session_state.selected_forms:
                st.session_state.selected_forms.discard(prev_v)

    # prepare registro para export
    chosen_row = {}
    chosen_row["codigo_siga"] = codigo_siga
    chosen_row["nome_siga"] = nome_siga
    chosen_row["observacao_siga"] = siga_row.get("observacao", "")
    chosen_row["dependencia_siga"] = siga_row.get("dependencia", "")

    if chosen_code:
        fr = form_df[form_df["codigo_form"].astype(str) == str(chosen_code)]
        if not fr.empty:
            fr = fr.iloc[0].to_dict()
            chosen_row["codigo_form"] = fr.get("codigo_form", "")
            chosen_row["nome_form"] = fr.get("nome_form", "")
            chosen_row["observacao_form"] = fr.get("observacao", "")
            chosen_row["dependencia_form"] = fr.get("dependencia_form", "")
        else:
            # fallback empty
            chosen_row["codigo_form"] = chosen_code
            chosen_row["nome_form"] = ""
            chosen_row["observacao_form"] = ""
            chosen_row["dependencia_form"] = ""
    else:
        chosen_row["codigo_form"] = ""
        chosen_row["nome_form"] = ""
        chosen_row["observacao_form"] = ""
        chosen_row["dependencia_form"] = ""

    pares_confirmados.append(chosen_row)

    st.markdown("---")

# ---------------- Construir dataframes finais ----------------
pareados_df = pd.DataFrame(pares_confirmados)

# Itens somente no SIGA: aqueles códigos SIGA que não possuem codigo_form preenchido
somente_siga_df = somente_siga_df = somente_siga_df = None
try:
    somente_siga_df = siga_df[~siga_df["codigo"].astype(str).isin(pareados_df[pareados_df["codigo_form"].astype(str) != "" ]["codigo_siga"].astype(str))]
except Exception:
    somente_siga_df = siga_df.copy()

# Itens somente no Formulário: aqueles codigo_form que não aparecem em pareados_df
selecionados_forms = set(pareados_df[pareados_df["codigo_form"].astype(str) != ""]["codigo_form"].astype(str).tolist())
somente_form_df = form_df[~form_df["codigo_form"].astype(str).isin(selecionados_forms)].copy()

st.success("Conferência construída na interface. Se necessário ajuste seleções antes de exportar.")

# ---------------- Exportação ----------------
st.subheader("📤 Exportar Resultado (XLSX com 3 abas)")

nome_base = st.text_input("Nome base do arquivo", value=f"comparador_manual_{datetime.now().strftime('%Y%m%d_%H%M')}")

col1, col2 = st.columns(2)
with col1:
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
with col2:
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
        st.success("ZIP pronto.")
        st.download_button("⬇️ Baixar ZIP", data=zip_bytes.getvalue(), file_name=f"{nome_base}.zip", mime="application/zip")

st.sidebar.markdown("---")
st.sidebar.write("Comparador Manual — 100% manual, itens exclusivos por seleção.")
