# app_manual.py
# Comparador Manual de Inventário — versão estável e final (com destaque de pareados)
# Cole inteiro no arquivo app_manual.py

import os
import streamlit as st
import pandas as pd
import sqlite3
from io import BytesIO
from datetime import datetime

# --- Config ---
st.set_page_config(page_title="Comparador Manual de Inventário", layout="wide")
PROJECTS_DIR = "projetos"
os.makedirs(PROJECTS_DIR, exist_ok=True)

# ----------------- Helpers -----------------
def _read_table(uploaded):
    """Read CSV or Excel uploaded file robustly into a DataFrame of strings."""
    name = getattr(uploaded, "name", "")
    if str(name).lower().endswith(".csv"):
        try:
            df = pd.read_csv(uploaded, dtype=str, keep_default_na=False).fillna("")
        except Exception:
            df = pd.read_csv(uploaded, dtype=str, encoding="latin-1", keep_default_na=False).fillna("")
    else:
        df = pd.read_excel(uploaded, dtype=str).fillna("")
    # normalize column names
    df.columns = [str(c).strip() for c in df.columns]
    # drop Unnamed and empty-only columns
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", na=False)]
    non_empty = [c for c in df.columns if not df[c].astype(str).str.strip().eq("").all()]
    if non_empty:
        df = df[non_empty]
    return df

def _find_column(df: pd.DataFrame, candidates):
    """Find best matching column name from candidates (exact case-insensitive, then contains)."""
    cols = list(df.columns)
    for cand in candidates:
        for c in cols:
            if c.strip().lower() == cand.strip().lower():
                return c
    for cand in candidates:
        for c in cols:
            if cand.strip().lower() in c.strip().lower():
                return c
    return None

def generate_unique_codes(base_ids):
    """Turn base_ids into unique codes by appending -01, -02 for duplicates."""
    counts = {}
    for b in base_ids:
        b = str(b)
        counts[b] = counts.get(b, 0) + 1
    seq = {}
    out = []
    for b in base_ids:
        b = str(b)
        if counts.get(b, 0) <= 1 or b.strip() == "":
            out.append(b)
        else:
            seq[b] = seq.get(b, 0) + 1
            out.append(f"{b}-{seq[b]:02d}")
    return out

def _safe(val):
    return "" if val is None else str(val)

def _ensure_project(name):
    path = os.path.join(PROJECTS_DIR, name)
    os.makedirs(path, exist_ok=True)
    return path

# ----------------- UI: Project selector -----------------
st.sidebar.header("Projeto")
mode = st.sidebar.radio("", ["Criar novo projeto", "Abrir projeto existente"])

if mode == "Criar novo projeto":
    new_name = st.sidebar.text_input("Nome do novo projeto")
    if st.sidebar.button("Criar projeto"):
        if not new_name or not new_name.strip():
            st.sidebar.error("Informe um nome válido.")
        else:
            _ensure_project(new_name.strip())
            st.sidebar.success(f"Projeto '{new_name.strip()}' criado. Agora escolha 'Abrir projeto existente'.")
            st.experimental_rerun()
    st.stop()

# Abrir existente
projects = sorted([p for p in os.listdir(PROJECTS_DIR) if os.path.isdir(os.path.join(PROJECTS_DIR, p))])
if not projects:
    st.sidebar.warning("Nenhum projeto encontrado. Crie um novo projeto primeiro.")
    st.stop()
project_name = st.sidebar.selectbox("Selecione o projeto", projects)
project_path = _ensure_project(project_name)
st.sidebar.write(f"Pasta do projeto: {os.path.abspath(project_path)}")

st.title(f"Comparador Manual — Projeto: {project_name}")

# ----------------- Uploads -----------------
st.header("1) Carregue as planilhas (SIGA e Formulário)")
col1, col2 = st.columns(2)
with col1:
    file_siga = st.file_uploader("SIGA (CSV ou XLSX)", type=["csv", "xlsx"], key="u_siga")
with col2:
    file_form = st.file_uploader("Formulário (CSV ou XLSX)", type=["csv", "xlsx"], key="u_form")

if not (file_siga and file_form):
    st.info("Envie ambos os arquivos para começar (SIGA e Formulário).")
    st.stop()

# ----------------- Read and normalize -----------------
try:
    siga_df = _read_table(file_siga)
    form_df = _read_table(file_form)
except Exception as e:
    st.error(f"Erro ao ler arquivos: {e}")
    st.stop()

# find useful columns (robust)
siga_code_col = _find_column(siga_df, ["Código", "Codigo", "CODIGO", "Cód. Item", "ID", "Cod"])
siga_name_col = _find_column(siga_df, ["Nome", "Nome do Bem", "Descrição", "Descricao", "Item", "ITEM"])
siga_dep_col = _find_column(siga_df, ["Dependência", "Dependencia", "Localidade", "Local"])

form_code_col = _find_column(form_df, ["Submission ID", "SubmissionID", "codigo_form", "codigo_formulario", "ID", "id"])
form_name_col = _find_column(form_df, ["Nome / Tipo de Bens", "Nome", "name", "Item", "Tipo"])
form_obs_col = _find_column(form_df, ["Observações", "Observacoes", "Observacao", "Obs", "observacao"])
form_dep_col = _find_column(form_df, ["Dependência / Localização", "Dependência", "Dependencia", "Local"])

# fallback guarantees
if siga_code_col is None:
    siga_df = siga_df.reset_index().rename(columns={"index": "Código"})
    siga_code_col = "Código"
if siga_name_col is None:
    siga_df["Nome"] = ""
    siga_name_col = "Nome"
if siga_dep_col is None:
    siga_df["Dependência"] = ""
    siga_dep_col = "Dependência"

if form_code_col is None:
    form_df = form_df.reset_index().rename(columns={"index": "Submission ID"})
    form_code_col = "Submission ID"
if form_name_col is None:
    form_df["Nome / Tipo de Bens"] = ""
    form_name_col = "Nome / Tipo de Bens"
if form_obs_col is None:
    form_df["Observações"] = ""
    form_obs_col = "Observações"
if form_dep_col is None:
    form_df["Dependência / Localização"] = ""
    form_dep_col = "Dependência / Localização"

# normalize strings
siga_df[siga_code_col] = siga_df[siga_code_col].astype(str).str.strip()
siga_df[siga_name_col] = siga_df[siga_name_col].astype(str).str.strip()
siga_df[siga_dep_col] = siga_df[siga_dep_col].astype(str).str.strip()

form_df[form_code_col] = form_df[form_code_col].astype(str).str.strip()
form_df[form_name_col] = form_df[form_name_col].astype(str).str.strip()
form_df[form_obs_col] = form_df[form_obs_col].astype(str).str.strip()
form_df[form_dep_col] = form_df[form_dep_col].astype(str).str.strip()

# ----------------- Generate unique form codes when duplicates exist -----------------
base_ids = form_df[form_code_col].astype(str).tolist()
base_ids_normalized = [b if b.strip() != "" else f"__FROW__{i}" for i, b in enumerate(base_ids)]
unique_codes = generate_unique_codes(base_ids_normalized)
final_codes = []
auto_counter = 1
for orig, uniq in zip(base_ids, unique_codes):
    if orig.strip() != "":
        final_codes.append(uniq)
    else:
        final_codes.append(f"FORM-{auto_counter:05d}")
        auto_counter += 1
form_df["codigo_form"] = final_codes

# ----------------- Visual columns -----------------
siga_df["codigo_siga"] = siga_df[siga_code_col]
siga_df["nome_siga"] = siga_df[siga_name_col]
siga_df["dependencia_siga"] = siga_df[siga_dep_col]

form_df["nome_form"] = form_df[form_name_col]
form_df["observacao_form"] = form_df[form_obs_col]
form_df["dependencia_form"] = form_df[form_dep_col]
form_df["nome_visual"] = form_df.apply(
    lambda r: f"{_safe(r['nome_form'])}" + (f" — {_safe(r['observacao_form'])}" if str(r['observacao_form']).strip() else ""),
    axis=1
)
siga_df["nome_visual"] = siga_df["nome_siga"]

# ----------------- Column visibility controls -----------------
st.subheader("2) Colunas (visual)")
col_siga_choices = [c for c in siga_df.columns if not str(c).startswith("__")]
col_form_choices = [c for c in form_df.columns if not str(c).startswith("__")]

cols = st.columns(2)
with cols[0]:
    default_siga = ["codigo_siga", "nome_visual", "dependencia_siga"]
    visible_siga = st.multiselect("Colunas SIGA (visual)", options=col_siga_choices, default=[c for c in default_siga if c in col_siga_choices])
with cols[1]:
    default_form = ["codigo_form", "nome_visual", "dependencia_form"]
    visible_form = st.multiselect("Colunas Formulário (visual)", options=col_form_choices, default=[c for c in default_form if c in col_form_choices])

# preview
st.subheader("3) Pré-visualização")
left, right = st.columns(2)
with left:
    st.write("SIGA")
    st.dataframe(siga_df[visible_siga] if visible_siga else siga_df.head(10), use_container_width=True, height=300)
with right:
    st.write("Formulário")
    st.dataframe(form_df[visible_form] if visible_form else form_df.head(10), use_container_width=True, height=300)

st.markdown("---")

# ----------------- Prepare pairing UI -----------------
st.subheader("4) Pareamento Manual (100% manual)")
global_search = st.text_input("🔎 Buscar globalmente no formulário (filtra opções):", value="", placeholder="ex: banco, FORM-00001, 2.50m").strip().lower()

if "selections" not in st.session_state:
    st.session_state.selections = {}  # codigo_siga -> codigo_form
if "selected_forms" not in st.session_state:
    st.session_state.selected_forms = set()

# prefill from history if exists
db_path = os.path.join(project_path, "history.db")
if os.path.exists(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT codigo_siga, codigo_form FROM pareamentos ORDER BY id")
        rows = cur.fetchall()
        for r in rows:
            cs, cf = r
            if cs and cf:
                # restore last saved mapping if not already in session
                if cs not in st.session_state.selections:
                    st.session_state.selections[cs] = cf
                    st.session_state.selected_forms.add(cf)
        conn.close()
    except Exception:
        pass

# pre-generate formatted option strings
form_df["option_display"] = form_df.apply(
    lambda r: f"{r['codigo_form']} — {r['nome_visual']}" + (f"  |  Dep: {r['dependencia_form']}" if str(r['dependencia_form']).strip() else ""),
    axis=1
)

pareados_for_export = []

# iterate SIGA rows for manual pairing
for idx, srow in siga_df.reset_index(drop=True).iterrows():
    codigo_siga = _safe(srow.get("codigo_siga", f"SIGA_{idx}"))
    nome_visual_siga = _safe(srow.get("nome_visual", ""))
    dep_siga = _safe(srow.get("dependencia_siga", ""))
    header_line = f"{codigo_siga} — {nome_visual_siga}"
    if dep_siga.strip():
        header_line = f"{header_line}  |  Dep: {dep_siga}"

    # show check if already selected
    is_pareado = codigo_siga in st.session_state.selections and st.session_state.selections[codigo_siga]
    if is_pareado:
        st.markdown(f"✅ **(Pareado)** {header_line}")
    else:
        st.markdown(f"🔸 {header_line}")

    filtro = st.text_input("🔎 Filtrar opções (por código/nome/obs/dep):", key=f"filtro_{idx}", value="").strip().lower()

    df_opts = form_df.copy()
    if global_search:
        mask_global = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(global_search, na=False)).any(axis=1)
        df_opts = df_opts[mask_global]
    if filtro:
        mask_row = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(filtro, na=False)).any(axis=1)
        df_opts = df_opts[mask_row]

    # exclude already selected codes (one-to-one)
    available_df = df_opts[~df_opts["codigo_form"].astype(str).isin(st.session_state.selected_forms)].copy()

    # build options (include previous selection even if not in available_df)
    options = ["(Nenhum)"] + available_df["option_display"].tolist()
    prev = st.session_state.selections.get(codigo_siga, "")
    index_default = 0
    if prev:
        # check if prev is still among available
        if prev in available_df["codigo_form"].astype(str).tolist():
            index_default = 1 + available_df["codigo_form"].astype(str).tolist().index(prev)
        else:
            prev_row = form_df[form_df["codigo_form"].astype(str) == str(prev)]
            if not prev_row.empty:
                prev_fmt = prev_row.iloc[0]["option_display"]
            else:
                prev_fmt = f"{prev} — (anterior)"
            options = ["(Nenhum)", prev_fmt] + [o for o in options[1:] if prev not in o]
            index_default = 1

    sel = st.selectbox("Selecionar item do formulário para parear:", options, key=f"sel_{idx}", index=index_default)

    chosen_code = None
    if sel and sel != "(Nenhum)":
        if " — " in sel:
            chosen_code = sel.split(" — ")[0].strip()
        else:
            chosen_code = sel.strip()

    # manage session_state.selected_forms to enforce one-to-one
    prev_code = st.session_state.selections.get(codigo_siga, "")
    if prev_code and prev_code != chosen_code:
        if prev_code in st.session_state.selected_forms:
            st.session_state.selected_forms.discard(prev_code)
    if chosen_code:
        st.session_state.selected_forms.add(chosen_code)
        st.session_state.selections[codigo_siga] = chosen_code
    else:
        if codigo_siga in st.session_state.selections:
            old = st.session_state.selections.pop(codigo_siga)
            if old in st.session_state.selected_forms:
                st.session_state.selected_forms.discard(old)

    # prepare row object for export later
    chosen_row = {
        "codigo_siga": codigo_siga,
        "nome_siga": _safe(srow.get(siga_name_col, srow.get("nome_siga", ""))),
        "observacao_siga": _safe(srow.get("observacao", "")),
        "dependencia_siga": _safe(srow.get(siga_dep_col, srow.get("dependencia_siga", ""))),
        "codigo_form": "",
        "nome_form": "",
        "observacao_form": "",
        "dependencia_form": ""
    }
    if chosen_code:
        fr = form_df[form_df["codigo_form"].astype(str) == str(chosen_code)]
        if not fr.empty:
            fr = fr.iloc[0].to_dict()
            chosen_row["codigo_form"] = fr.get("codigo_form", "")
            chosen_row["nome_form"] = fr.get("nome_form", fr.get(form_name_col, fr.get("Nome", "")))
            chosen_row["observacao_form"] = fr.get("observacao_form", fr.get(form_obs_col, fr.get("Observações", "")))
            chosen_row["dependencia_form"] = fr.get("dependencia_form", fr.get(form_dep_col, fr.get("Dependência / Localização", "")))
    pareados_for_export.append(chosen_row)

    st.markdown("---")

# ----------------- Save / Export -----------------
st.subheader("5) Salvar / Exportar resultados")
col_a, col_b = st.columns(2)
with col_a:
    if st.button("💾 Salvar pareamentos no projeto"):
        if not project_name:
            st.error("Selecione um projeto válido na barra lateral.")
        else:
            db_path = os.path.join(project_path, "history.db")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pareamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    codigo_siga TEXT, nome_siga TEXT, observacao_siga TEXT, dependencia_siga TEXT,
                    codigo_form TEXT, nome_form TEXT, observacao_form TEXT, dependencia_form TEXT,
                    usuario TEXT, timestamp TEXT
                )
            """)
            now = datetime.utcnow().isoformat(timespec="seconds")
            for r in pareados_for_export:
                cur.execute(
                    "INSERT INTO pareamentos (codigo_siga, nome_siga, observacao_siga, dependencia_siga, codigo_form, nome_form, observacao_form, dependencia_form, usuario, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        r.get("codigo_siga",""),
                        r.get("nome_siga",""),
                        r.get("observacao_siga",""),
                        r.get("dependencia_siga",""),
                        r.get("codigo_form",""),
                        r.get("nome_form",""),
                        r.get("observacao_form",""),
                        r.get("dependencia_form",""),
                        "local",
                        now
                    )
                )
            conn.commit()
            conn.close()
            st.success(f"Pareamentos salvos em: {os.path.join(project_path, 'history.db')}")

with col_b:
    nome_base = st.text_input("Nome base do arquivo exportado", value=f"comparacao_{datetime.now().strftime('%Y%m%d_%H%M')}")
    if st.button("📤 Exportar XLSX e CSV"):
        # compute sets of pareados
        codigo_sigas_pareados = { r["codigo_siga"] for r in pareados_for_export if r.get("codigo_form") }
        codigo_forms_pareados = { r["codigo_form"] for r in pareados_for_export if r.get("codigo_form") }

        # prepare pareados sheet
        pareados_out = []
        for r in pareados_for_export:
            codigo_siga = r.get("codigo_siga","")
            siga_rows = siga_df[siga_df["codigo_siga"].astype(str) == str(codigo_siga)]
            siga_row = siga_rows.iloc[0].to_dict() if not siga_rows.empty else {}
            codigo_form = r.get("codigo_form","")
            form_row = {}
            if codigo_form:
                fr = form_df[form_df["codigo_form"].astype(str) == str(codigo_form)]
                if not fr.empty:
                    form_row = fr.iloc[0].to_dict()
            combined = {}
            for c in siga_df.columns:
                combined[f"SIGA__{c}"] = siga_row.get(c, "")
            for c in form_df.columns:
                combined[f"FORM__{c}"] = form_row.get(c, "")
            combined["Status"] = "Pareado" if codigo_form else "Pendente"
            pareados_out.append(combined)
        pareados_df = pd.DataFrame(pareados_out)

        # somente_siga: exclude pareados
        somente_siga_out = []
        for _, r in siga_df.iterrows():
            codigo = r.get("codigo_siga","")
            if str(codigo) in codigo_sigas_pareados:
                continue
            row = {}
            for c in siga_df.columns:
                row[f"SIGA__{c}"] = r.get(c, "")
            for c in form_df.columns:
                row[f"FORM__{c}"] = ""
            row["Status"] = "Somente_SIGA"
            somente_siga_out.append(row)
        somente_siga_df = pd.DataFrame(somente_siga_out)

        # somente_form: exclude pareados
        somente_form_out = []
        for _, r in form_df.iterrows():
            codigo = r.get("codigo_form","")
            if str(codigo) in codigo_forms_pareados:
                continue
            row = {}
            for c in siga_df.columns:
                row[f"SIGA__{c}"] = ""
            for c in form_df.columns:
                row[f"FORM__{c}"] = r.get(c, "")
            row["Status"] = "Somente_Formulario"
            somente_form_out.append(row)
        somente_form_df = pd.DataFrame(somente_form_out)

        # write xlsx
        xlsx_path = os.path.join(project_path, f"{nome_base}.xlsx")
        with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
            pareados_df.to_excel(writer, index=False, sheet_name="Pareados")
            somente_siga_df.to_excel(writer, index=False, sheet_name="Somente_SIGA")
            somente_form_df.to_excel(writer, index=False, sheet_name="Somente_Formulário")

        # write csv combined (pareados + somente_siga + somente_form)
        frames = [df for df in [pareados_df, somente_siga_df, somente_form_df] if not df.empty]
        if frames:
            csv_all = pd.concat(frames, ignore_index=True, sort=False)
        else:
            csv_all = pd.DataFrame()
        csv_path = os.path.join(project_path, f"{nome_base}.csv")
        csv_all.to_csv(csv_path, index=False, encoding="utf-8-sig")

        st.success("Exportação concluída")
        with open(xlsx_path, "rb") as f:
            st.download_button("⬇️ Baixar XLSX", data=f, file_name=os.path.basename(xlsx_path))
        with open(csv_path, "rb") as f:
            st.download_button("⬇️ Baixar CSV", data=f, file_name=os.path.basename(csv_path))

st.markdown("---")
st.markdown("Comparador Manual — Desenvolvido por Alex Crudi — 📱 (15) 9.9127-6070")
