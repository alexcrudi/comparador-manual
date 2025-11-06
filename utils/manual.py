# utils/manual.py
import pandas as pd
from io import BytesIO
import zipfile
from pathlib import Path
from typing import Tuple
import math

def _read_file(file):
    name = getattr(file, "name", str(file))
    if str(name).lower().endswith(".csv"):
        return pd.read_csv(file, dtype=str, keep_default_na=False).fillna("")
    else:
        return pd.read_excel(file, dtype=str).fillna("")

def _normalize_columns(df):
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df

def ler_planilha_siga(file) -> pd.DataFrame:
    """
    Lê SIGA e mapeia colunas importantes para: codigo, nome, dependencia
    Mantém todas as outras colunas para export.
    """
    df = _read_file(file)
    df = _normalize_columns(df)
    rename_map = {}
    if "Código" in df.columns:
        rename_map["Código"] = "codigo"
    if "Nome" in df.columns:
        rename_map["Nome"] = "nome"
    if "Dependência" in df.columns:
        rename_map["Dependência"] = "dependencia"
    if rename_map:
        df = df.rename(columns=rename_map)
    # garantias
    if "codigo" not in df.columns:
        df = df.reset_index().rename(columns={"index": "codigo"})
    if "nome" not in df.columns:
        df["nome"] = ""
    if "dependencia" not in df.columns:
        df["dependencia"] = ""
    # padronizar strings
    df["codigo"] = df["codigo"].astype(str)
    df["nome"] = df["nome"].astype(str)
    df["dependencia"] = df["dependencia"].astype(str)
    return df

def ler_planilha_form(file) -> pd.DataFrame:
    """
    Lê formulário (Tally) e mapeia:
      Submission ID -> codigo_form (base)
      Nome / Tipo de Bens -> nome_form
      Observações -> observacao
      Dependência / Localização -> dependencia_form
    Gera codigo_form único quando há duplicates (Opção C).
    """
    df = _read_file(file)
    df = _normalize_columns(df)
    rename_map = {}
    if "Submission ID" in df.columns:
        rename_map["Submission ID"] = "codigo_form"
    if "Nome / Tipo de Bens" in df.columns:
        rename_map["Nome / Tipo de Bens"] = "nome_form"
    if "Observações" in df.columns:
        rename_map["Observações"] = "observacao"
    if "Dependência / Localização" in df.columns:
        rename_map["Dependência / Localização"] = "dependencia_form"
    if rename_map:
        df = df.rename(columns=rename_map)
    # guarantees
    if "codigo_form" not in df.columns:
        df = df.reset_index().rename(columns={"index":"codigo_form"})
        df["codigo_form"] = df["codigo_form"].apply(lambda x: f"F{int(x)+1:03d}")
    if "nome_form" not in df.columns:
        poss = [c for c in df.columns if "nome" in c.lower() or "item" in c.lower() or "tipo" in c.lower()]
        if poss:
            df = df.rename(columns={poss[0]: "nome_form"})
        else:
            df["nome_form"] = ""
    if "observacao" not in df.columns:
        df["observacao"] = ""
    if "dependencia_form" not in df.columns:
        poss = [c for c in df.columns if "depend" in c.lower() or "local" in c.lower()]
        if poss:
            df = df.rename(columns={poss[0]: "dependencia_form"})
        else:
            df["dependencia_form"] = ""
    # generate unique codes when duplicates exist (Option C)
    df = df.reset_index(drop=True)
    df["__base_id"] = df["codigo_form"].astype(str)
    counts = df["__base_id"].value_counts().to_dict()
    seq_counters = {}
    new_codes = []
    for base in df["__base_id"]:
        if counts.get(base, 0) <= 1:
            new_codes.append(base)
        else:
            seq = seq_counters.get(base, 0) + 1
            seq_counters[base] = seq
            new_codes.append(f"{base}-{seq:02d}")
    df["codigo_form"] = new_codes
    df = df.drop(columns=["__base_id"])
    # ensure types
    df["codigo_form"] = df["codigo_form"].astype(str)
    df["nome_form"] = df["nome_form"].astype(str)
    df["observacao"] = df["observacao"].astype(str)
    df["dependencia_form"] = df["dependencia_form"].astype(str)
    return df

def preparar_pareamento(siga_df: pd.DataFrame, form_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Retorna:
      pares_df (cópia do siga com coluna codigo_form vazia para UI),
      somente_siga (cópia completa),
      somente_form (cópia completa)
    """
    pares_df = siga_df.copy().reset_index(drop=True)
    pares_df["codigo_form"] = None
    if "nome" not in pares_df.columns:
        pares_df["nome"] = ""
    if "observacao" not in pares_df.columns:
        pares_df["observacao"] = ""
    if "dependencia" not in pares_df.columns:
        pares_df["dependencia"] = ""
    return pares_df, siga_df.copy().reset_index(drop=True), form_df.copy().reset_index(drop=True)

def gerar_exportacao(pareados_df: pd.DataFrame, somente_siga_df: pd.DataFrame, somente_form_df: pd.DataFrame, siga_df_full: pd.DataFrame, form_df_full: pd.DataFrame, nome_base: str = "comparador_manual", compact: bool = False) -> BytesIO:
    """
    Exporta XLSX com 3 abas (Pareados, Somente_SIGA, Somente_Formulário)
    Em 'Pareados' as colunas são prefixadas com SIGA__ e FORM__ e contém todos os campos originais.
    """
    pareados_out = []
    for _, r in pareados_df.iterrows():
        codigo_siga = r.get("codigo_siga", "")
        siga_rows = siga_df_full[siga_df_full["codigo"].astype(str) == str(codigo_siga)]
        siga_row = siga_rows.iloc[0].to_dict() if not siga_rows.empty else {}
        codigo_form = r.get("codigo_form", "")
        form_row = {}
        if codigo_form and str(codigo_form) != "" and "codigo_form" in form_df_full.columns:
            fr = form_df_full[form_df_full["codigo_form"].astype(str) == str(codigo_form)]
            if not fr.empty:
                form_row = fr.iloc[0].to_dict()
        combined = {}
        for c in siga_df_full.columns:
            combined[f"SIGA__{c}"] = siga_row.get(c, "")
        for c in form_df_full.columns:
            combined[f"FORM__{c}"] = form_row.get(c, "")
        combined["Status"] = "Pareado" if codigo_form and str(codigo_form) != "" else "Pendente"
        pareados_out.append(combined)
    pareados_out_df = pd.DataFrame(pareados_out)
    if pareados_out_df.empty:
        pareados_out_df = pd.DataFrame(columns=["SIGA__codigo"])
    somente_siga_out = somente_siga_df.copy().reset_index(drop=True)
    somente_form_out = somente_form_df.copy().reset_index(drop=True)
    if not compact:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
            pareados_out_df.to_excel(writer, index=False, sheet_name="Pareados")
            somente_siga_out.to_excel(writer, index=False, sheet_name="Somente_SIGA")
            somente_form_out.to_excel(writer, index=False, sheet_name="Somente_Formulário")
        out.seek(0)
        return out
    else:
        mem = BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("pareados.csv", pareados_out_df.to_csv(index=False))
            z.writestr("somente_siga.csv", somente_siga_out.to_csv(index=False))
            z.writestr("somente_form.csv", somente_form_out.to_csv(index=False))
        mem.seek(0)
        return mem
