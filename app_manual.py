# app_manual.py
import streamlit as st
import pandas as pd
from pathlib import Path
from utils.manual import ler_planilha_siga, ler_planilha_form, preparar_pareamento, gerar_exportacao
from utils.history import insert_pareamentos, load_pareamentos, list_projects, ensure_db
from datetime import datetime
import io
import os

# ---------- Config ----------
APP_TITLE = "Comparador Manual de Inventário"
DB_FILENAME = "projects_history.db"   # arquivo .db na mesma pasta do EXE
ASSETS_DIR = Path("assets")
LOGO_PATH = ASSETS_DIR / "logo_placeholder.png"
ABOUT_TEXT = """Comparador Manual de Inventário
Desenvolvido para uso local — versão portátil.
Contato: Alex Crudi
📱 (15) 9.9127-6070
"""

st.set_page_config(page_title=APP_TITLE, layout="wide")

# ensure assets folder and logo placeholder
ASSETS_DIR.mkdir(exist_ok=True)
if not LOGO_PATH.exists():
    # create a simple placeholder logo PNG
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (600,140), color=(43,108,176))
        draw = ImageDraw.Draw(img)
        try:
            fnt = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
        except Exception:
            fnt = None
        text = "Comparador\nManual"
        draw.text((22,20), "Comparador Manual de Inventário", fill=(255,255,255), font=fnt)
        draw.text((22,80), "Comparação SIGA ⇄ Formulário", fill=(255,255,255), font=fnt)
        img.save(str(LOGO_PATH))
    except Exception:
        # fallback: create a tiny file so app doesn't crash
        with open(LOGO_PATH, "wb") as f:
            f.write(b"")

# ---------- UI: Header ----------
st.image(str(LOGO_PATH), width=280)
st.title(APP_TITLE)
st.caption("Modo 100% manual — salve projetos localmente e recupere depois")

# ---------- Sidebar: project controls ----------
st.sidebar.header("Projeto / Histórico")
db_path = Path(DB_FILENAME)
ensure_db(db_path)

# project selection: list existing + create new
projects = list_projects(db_path)
proj_choice = st.sidebar.selectbox("Projeto (selecione ou crie novo)", options=["<Novo Projeto>"] + projects, index=0)
if proj_choice == "<Novo Projeto>":
    new_proj = st.sidebar.text_input("Nome do novo projeto (ex: Igreja Central)")
    create_btn = st.sidebar.button("Criar projeto")
    if create_btn and new_proj.strip():
        proj_name = new_proj.strip()
        # initialize empty entry - no need to write yet
        st.sidebar.success(f"Projeto '{proj_name}' criado. Selecione-o no menu.")
        # insert nothing, just reload list (user will select manually)
        projects = list_projects(db_path)
else:
    proj_name = proj_choice

st.sidebar.markdown("---")
st.sidebar.header("Ajuda & Sobre")
st.sidebar.info("App offline — os dados ficam salvos localmente.")
if st.sidebar.button("Sobre / Contato"):
    st.sidebar.info(ABOUT_TEXT)

st.sidebar.markdown("---")
st.sidebar.write("Arquivo DB: " + str(db_path.resolve()))

# ---------- Uploads ----------
st.subheader("1) Carregue as planilhas")
col1, col2 = st.columns(2)
with col1:
    siga_file = st.file_uploader("Upload SIGA (CSV ou XLSX)", type=["csv","xlsx"], key="u_siga")
with col2:
    form_file = st.file_uploader("Upload Formulário (CSV ou XLSX)", type=["csv","xlsx"], key="u_form")

if not (siga_file and form_file):
    st.info("Envie ambos os arquivos para começar. Você pode abrir um projeto existente pela barra lateral.")
    st.stop()

# ---------- Ler planilhas ----------
try:
    siga_df = ler_planilha_siga(siga_file)
    form_df = ler_planilha_form(form_file)
except Exception as e:
    st.error(f"Erro ao ler arquivos: {e}")
    st.stop()

# create visual fields
if "observacao" not in siga_df.columns:
    siga_df["observacao"] = ""
if "observacao" not in form_df.columns:
    form_df["observacao"] = ""
siga_df["nome_visual"] = siga_df.apply(lambda r: f"{r.get('nome','')}"+ (f" | {r.get('observacao','')}" if r.get('observacao') else ""), axis=1)
form_df["nome_visual"] = form_df.apply(lambda r: f"{r.get('nome_form','')}"+ (f" | {r.get('observacao','')}" if r.get('observacao') else ""), axis=1)

# ---------- visual column controls ----------
st.subheader("2) Colunas (apenas visual)")
col_siga, col_form = st.columns(2)
with col_siga:
    default_siga = ["codigo", "nome_visual", "dependencia"]
    cols_siga = st.multiselect("Colunas SIGA (visual)", options=list(siga_df.columns), default=[c for c in default_siga if c in siga_df.columns])
with col_form:
    default_form = ["codigo_form", "nome_visual", "dependencia_form"]
    available_form_cols = list(form_df.columns)
    default_present = [c for c in default_form if c in available_form_cols]
    if not default_present:
        default_present = available_form_cols[:3] if len(available_form_cols) >= 3 else available_form_cols
    cols_form = st.multiselect("Colunas Formulário (visual)", options=available_form_cols, default=default_present)

# previews
st.subheader("3) Pré-visualização (apenas visual)")
left, right = st.columns(2)
with left:
    st.markdown("### SIGA")
    st.dataframe(siga_df[cols_siga] if cols_siga else siga_df.head(10), use_container_width=True, height=280)
with right:
    st.markdown("### Formulário")
    st.dataframe(form_df[cols_form] if cols_form else form_df.head(10), use_container_width=True, height=280)

st.markdown("---")

# ---------- Prepare pareamento ----------
pares_df, somente_siga_df, somente_form_df = preparar_pareamento(siga_df, form_df)

# ---------- Load existing pareamentos for this project ----------
if proj_name and proj_name != "<Novo Projeto>":
    stored = load_pareamentos(db_path, proj_name)
else:
    stored = []

# map stored pareamentos to selection_map for UI restore
selection_map = {}
for s in stored:
    # key by codigo_siga (assuming codes unique in SIGA)
    key = str(s.get("codigo_siga",""))
    if key:
        selection_map[key] = {
            "codigo_form": s.get("codigo_form",""),
            "nome_form": s.get("nome_form",""),
            "observacao_form": s.get("observacao_form",""),
            "dependencia_form": s.get("dependencia_form","")
        }

# ---------- Pareamento Manual (100% manual) ----------
st.subheader("4) Pareamento Manual (100% manual)")

global_search = st.text_input("🔎 Buscar globalmente no formulário (filtra opções):", value="", placeholder="ex: banco, R-001, 2.50m").strip().lower()

# session selections for persistence during the run
if "selections" not in st.session_state:
    st.session_state.selections = {}  # maps codigo_siga -> codigo_form
if "selected_forms" not in st.session_state:
    st.session_state.selected_forms = set()

# If there were stored pareamentos, prefill session_state
for k, v in selection_map.items():
    if k not in st.session_state.selections or not st.session_state.selections[k]:
        st.session_state.selections[k] = v.get("codigo_form") or ""

# iterate SIGA rows
pareados_for_export = []
for idx, srow in pares_df.reset_index(drop=True).iterrows():
    codigo_siga = str(srow.get("codigo",""))
    nome_visual_siga = str(srow.get("nome_visual",""))
    st.markdown(f"**{codigo_siga} — {nome_visual_siga}**")

    filtro = st.text_input("🔎 Filtrar opções (por código/nome/obs):", key=f"filtro_{idx}", value="").strip().lower()
    df_opts = form_df.copy()

    # apply global filter and row filter
    if global_search:
        mask_global = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(global_search, na=False)).any(axis=1)
        df_opts = df_opts[mask_global]
    if filtro:
        mask_row = df_opts.apply(lambda r: r.astype(str).str.lower().str.contains(filtro, na=False)).any(axis=1)
        df_opts = df_opts[mask_row]

    # options formatted: "<codigo_form> — <nome> | <observacao>"
    def fmt_row(r):
        code = str(r.get("codigo_form",""))
        name = str(r.get("nome_form",""))
        obs = str(r.get("observacao",""))
        if obs:
            return f"{code} — {name} | {obs}"
        else:
            return f"{code} — {name}"

    # Available options exclude those already selected in this session (1-para-1)
    available_df = df_opts[~df_opts["codigo_form"].astype(str).isin(st.session_state.selected_forms)].copy()

    options = ["(Nenhum)"] + [fmt_row(r) for _, r in available_df.iterrows()]

    # restore previous selection logic
    prev = st.session_state.selections.get(codigo_siga, "")
    index_default = 0
    if prev:
        # if prev still available, select it; otherwise add it specially
        if prev in available_df["codigo_form"].astype(str).tolist():
            index_default = 1 + available_df["codigo_form"].astype(str).tolist().index(prev)
        else:
            # include previous at index 1 so user can see it and remove if wanted
            prev_row = form_df[form_df["codigo_form"].astype(str) == str(prev)]
            if not prev_row.empty:
                prev_fmt = fmt_row(prev_row.iloc[0])
            else:
                prev_fmt = f"{prev} — (selecionado anteriormente)"
            # ensure prev is first after "(Nenhum)"
            options = ["(Nenhum)", prev_fmt] + [o for o in options[1:] if prev not in o]
            index_default = 1

    sel = st.selectbox("Selecionar item do formulário para parear:", options, key=f"sel_{idx}", index=index_default)

    chosen_code = None
    if sel and sel != "(Nenhum)":
        if " — " in sel:
            chosen_code = sel.split(" — ")[0].strip()
        else:
            chosen_code = sel.strip()

    # update selections (session)
    prev_code = st.session_state.selections.get(codigo_siga, "")
    if prev_code and prev_code != chosen_code:
        # unselect previous
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

    # prepare row for export / save
    chosen_row = {
        "codigo_siga": codigo_siga,
        "nome_siga": srow.get("nome",""),
        "observacao_siga": srow.get("observacao",""),
        "dependencia_siga": srow.get("dependencia",""),
        "codigo_form": "",
        "nome_form": "",
        "observacao_form": "",
        "dependencia_form": ""
    }
    if chosen_code:
        fr = form_df[form_df["codigo_form"].astype(str) == str(chosen_code)]
        if not fr.empty:
            fr = fr.iloc[0].to_dict()
            chosen_row["codigo_form"] = fr.get("codigo_form","")
            chosen_row["nome_form"] = fr.get("nome_form","")
            chosen_row["observacao_form"] = fr.get("observacao","")
            chosen_row["dependencia_form"] = fr.get("dependencia_form","")
    pareados_for_export.append(chosen_row)

    st.markdown("---")

# ---------- Save / Export / Persist ----------
st.subheader("5) Salvar / Exportar resultados")

col_a, col_b = st.columns(2)
with col_a:
    if st.button("💾 Salvar pareamentos no histórico (DB)"):
        if not proj_name or proj_name == "<Novo Projeto>":
            st.error("Escolha ou crie um projeto na barra lateral antes de salvar.")
        else:
            # Commit session selections into DB
            insert_pareamentos(db_path, proj_name, pareados_for_export, usuario="local")
            st.success(f"Pareamentos salvos no projeto '{proj_name}' (arquivo: {db_path.name})")

with col_b:
    nome_base = st.text_input("Nome base do arquivo exportado", value=f"comparador_manual_{datetime.now().strftime('%Y%m%d_%H%M')}")
    if st.button("📤 Exportar XLSX (3 abas)"):
        xlsx_bytes = gerar_exportacao(pd.DataFrame(pareados_for_export), somente_siga_df, somente_form_df, siga_df, form_df, nome_base=nome_base, compact=False)
        st.download_button("⬇️ Baixar XLSX", data=xlsx_bytes.getvalue(), file_name=f"{nome_base}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ---------- Quick history view ----------
st.subheader("6) Histórico salvo (visualização rápida)")
if proj_name and proj_name != "<Novo Projeto>":
    history = load_pareamentos(db_path, proj_name)
    if history:
        hist_df = pd.DataFrame(history)
        st.dataframe(hist_df.head(200), use_container_width=True)
    else:
        st.info("Nenhum pareamento salvo ainda neste projeto.")
else:
    st.info("Selecione um projeto para visualizar o histórico salvo.")
