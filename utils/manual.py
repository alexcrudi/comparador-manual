import pandas as pd
from io import BytesIO
import zipfile
from rapidfuzz import fuzz, process

def preparar_pareamento(siga_df, form_df):
    df_siga = siga_df.copy()
    df_form = form_df.copy()
    # normalize expected column names if needed
    if "codigo_siga" not in df_siga.columns:
        df_siga = df_siga.rename(columns={df_siga.columns[0]: "codigo_siga"})
    if "nome_siga" not in df_siga.columns:
        if len(df_siga.columns) > 1:
            df_siga = df_siga.rename(columns={df_siga.columns[1]: "nome_siga"})
        else:
            df_siga["nome_siga"] = ""
    if "codigo_tally" not in df_form.columns:
        df_form = df_form.rename(columns={df_form.columns[0]: "codigo_tally"})
    if "nome_form" not in df_form.columns:
        if len(df_form.columns) > 1:
            df_form = df_form.rename(columns={df_form.columns[1]: "nome_form"})
        else:
            df_form["nome_form"] = ""
    pares_df = df_siga.copy().reset_index(drop=True)
    pares_df["codigo_tally"] = None
    return pares_df, df_siga.reset_index(drop=True), df_form.reset_index(drop=True)

def sugerir_candidatos(nome_siga, form_df, k=5):
    # build list of strings to match
    choices = form_df.apply(lambda r: f"{r.get('codigo_tally','')} | {r.get('nome_form','')}", axis=1).tolist()
    results = process.extract(str(nome_siga), choices, scorer=fuzz.token_set_ratio, limit=k)
    out = []
    for match, score, idx in results:
        # match is the string from choices; extract code and name from form_df
        row = form_df.iloc[idx]
        code = str(row.get("codigo_tally",""))
        name = str(row.get("nome_form",""))
        out.append((code, name, int(score)))
    return out

def gerar_exportacao(pares_df, somente_siga, somente_form, nome_base="comparador_manual", compact=False):
    # Prepare outputs
    pareados = pares_df.copy()
    pareados["status"] = pareados["codigo_tally"].apply(lambda x: "Pareado" if pd.notna(x) and x not in [None,"None",""] else "Pendente")
    # XLSX with three sheets
    if not compact:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            pareados.to_excel(writer, index=False, sheet_name="Pareados")
            somente_siga.to_excel(writer, index=False, sheet_name="Somente_SIGA")
            somente_form.to_excel(writer, index=False, sheet_name="Somente_Form")
        output.seek(0)
        return output
    else:
        mem = BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("pareados.csv", pareados.to_csv(index=False))
            z.writestr("somente_siga.csv", somente_siga.to_csv(index=False))
            z.writestr("somente_form.csv", somente_form.to_csv(index=False))
        mem.seek(0)
        return mem
