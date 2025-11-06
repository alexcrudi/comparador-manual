import pandas as pd
from io import BytesIO
import zipfile
from rapidfuzz import fuzz, process

def preparar_pareamento(siga_df, form_df):
    # copia e normaliza colunas básicas
    df_siga = siga_df.copy()
    df_form = form_df.copy()
    # garantir colunas esperadas
    if "codigo_siga" not in df_siga.columns:
        df_siga = df_siga.rename(columns={df_siga.columns[0]: "codigo_siga"})
    if "nome_siga" not in df_siga.columns:
        df_siga = df_siga.rename(columns={df_siga.columns[1] if len(df_siga.columns)>1 else df_siga.columns[0]: "nome_siga"})
    if "codigo_tally" not in df_form.columns:
        df_form = df_form.rename(columns={df_form.columns[0]: "codigo_tally"})
    if "nome_form" not in df_form.columns:
        df_form = df_form.rename(columns={df_form.columns[1] if len(df_form.columns)>1 else df_form.columns[0]: "nome_form"})

    pares_df = df_siga.copy()
    pares_df["codigo_tally"] = None
    return pares_df, df_siga, df_form

def sugerir_candidatos(nome_siga, form_df, k=5):
    # usa rapidfuzz to get top candidates based on nome and codigo
    choices = form_df.apply(lambda r: (str(r.get("codigo_tally","")), str(r.get("nome_form",""))), axis=1).tolist()
    # build a list of strings to match against: "codigo | nome"
    strings = [f"{c[0]} | {c[1]}" for c in choices]
    results = process.extract(str(nome_siga), strings, scorer=fuzz.token_set_ratio, limit=k)
    # results: list of (choice, score, idx)
    out = []
    for match, score, idx in results:
        code, name = choices[idx]
        out.append((code, name, int(score)))
    return out

def gerar_exportacao(pares_df, somente_siga, somente_form, nome_base="comparador_manual", compact=False):
    # preparar DataFrames antes de exportar
    pareados = pares_df.copy()
    # construir DataFrame de pareados com campos padrão
    pareados_out = pareados.copy()
    pareados_out["status"] = pareados_out["codigo_tally"].apply(lambda x: "Pareado" if pd.notna(x) and x!=\"None\" else "Pendente")
    # somente_siga e somente_form já são DataFrames
    output = BytesIO()
    if compact:
        # criar planilhas separadas e zipar CSVs
        mem = BytesIO()
        with zipfile.ZipFile(mem, mode="w") as z:
            z.writestr("pareados.csv", pareados_out.to_csv(index=False))
            z.writestr("somente_siga.csv", somente_siga.to_csv(index=False))
            z.writestr("somente_form.csv", somente_form.to_csv(index=False))
        mem.seek(0)
        return mem
    else:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            pareados_out.to_excel(writer, index=False, sheet_name="Pareados")
            somente_siga.to_excel(writer, index=False, sheet_name="Somente_SIGA")
            somente_form.to_excel(writer, index=False, sheet_name="Somente_Form")
        output.seek(0)
        return output
