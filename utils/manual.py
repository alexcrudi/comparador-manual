# utils/manual.py
import pandas as pd
from io import BytesIO
import zipfile

def _read_file(file):
    """Lê CSV ou Excel (UploadedFile ou caminho)."""
    name = getattr(file, "name", str(file))
    if str(name).lower().endswith(".csv"):
        return pd.read_csv(file, dtype=str, keep_default_na=False).fillna("")
    else:
        return pd.read_excel(file, dtype=str).fillna("")

def _normalize_columns(df):
    """Strip nos nomes das colunas mantendo case original (para export)."""
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df

# -----------------------
# Leitura e normalização
# -----------------------
def ler_planilha_siga(file):
    """
    Lê SIGA (CSV/XLSX) e renomeia colunas-chave para uso interno:
      'Código' -> 'codigo'
      'Nome'   -> 'nome'
      'Dependência' -> 'dependencia'
    Mantém todas as demais colunas para exportação.
    """
    df = _read_file(file)
    df = _normalize_columns(df)

    # renomear se colunas existirem
    rename_map = {}
    if "Código" in df.columns:
        rename_map["Código"] = "codigo"
    if "Nome" in df.columns:
        rename_map["Nome"] = "nome"
    if "Dependência" in df.columns:
        rename_map["Dependência"] = "dependencia"

    if rename_map:
        df = df.rename(columns=rename_map)

    # garantir colunas mínimas para o app
    if "codigo" not in df.columns:
        df = df.reset_index().rename(columns={"index": "codigo"})
        df["codigo"] = df["codigo"].astype(str)
    if "nome" not in df.columns:
        # tentativa: segunda coluna como nome
        cols = list(df.columns)
        if len(cols) > 1:
            df = df.rename(columns={cols[1]: "nome"})
        else:
            df["nome"] = ""
    if "dependencia" not in df.columns:
        df["dependencia"] = ""

    # manter ordem e retornar
    return df

def ler_planilha_form(file):
    """
    Lê a planilha do formulário (Tally) e renomeia colunas:
      'Submission ID' -> 'codigo_form' (base)
      'Nome / Tipo de Bens' -> 'nome_form'
      'Observações' -> 'observacao'
      'Dependência / Localização' -> 'dependencia_form'
    Gera códigos únicos (Opção C):
      - se Submission ID é único -> mantém
      - se existe mais de 1 linha com mesmo Submission ID -> cria suffix "-01","-02",...
    Mantém todas as demais colunas originais.
    """
    df = _read_file(file)
    df = _normalize_columns(df)

    # padrão de renomeio
    rename_map = {}
    if "Submission ID" in df.columns:
        rename_map["Submission ID"] = "codigo_form"
    if "Nome / Tipo de Bens" in df.columns:
        rename_map["Nome / Tipo de Bens"] = "nome_form"
    if "Observações" in df.columns:
        rename_map["Observações"] = "observacao"
    if "Dependência / Localização" in df.columns:
        rename_map["Dependência / Localização"] = "dependencia_form"
    # outros mapeamentos opcionais
    if "Respondent ID" in df.columns:
        rename_map["Respondent ID"] = "respondent_id"
    if "Submitted at" in df.columns:
        rename_map["Submitted at"] = "submitted_at"

    if rename_map:
        df = df.rename(columns=rename_map)

    # garantias mínimas
    if "codigo_form" not in df.columns:
        # gerar codigo_form automático F001...
        df = df.reset_index().rename(columns={"index": "codigo_form"})
        df["codigo_form"] = df["codigo_form"].apply(lambda x: f"F{int(x)+1:03d}")

    if "nome_form" not in df.columns:
        # tentar mapear por outras colunas
        possible = [c for c in df.columns if "nome" in c.lower() or "item" in c.lower() or "tipo" in c.lower()]
        if possible:
            df = df.rename(columns={possible[0]: "nome_form"})
        else:
            df["nome_form"] = ""

    if "observacao" not in df.columns:
        # aceitar 'Observações' já tratado, se outro nome não existir cria vazio
        df["observacao"] = ""

    if "dependencia_form" not in df.columns:
        possible = [c for c in df.columns if "depend" in c.lower() or "local" in c.lower()]
        if possible:
            df = df.rename(columns={possible[0]: "dependencia_form"})
        else:
            df["dependencia_form"] = ""

    # Agora: gerar codigo_form único quando houver duplicates (Opção C)
    # contamos ocorrências do valor original (antes de sobrescrever)
    # usar a string original do campo que foi mapeado para 'codigo_form'
    df = df.reset_index(drop=True)
    # preserve original id value as base (string)
    df["__base_id"] = df["codigo_form"].astype(str)

    # compute counts
    counts = df["__base_id"].value_counts().to_dict()
    # if count ==1 keep base, else create suffix -01 etc.
    # we will produce new column 'codigo_form_unico' then rename to 'codigo_form'
    new_codes = []
    seq_counters = {}
    for base in df["__base_id"]:
        if counts.get(base, 0) <= 1:
            new_codes.append(base)
        else:
            # generate sequential suffix
            seq = seq_counters.get(base, 0) + 1
            seq_counters[base] = seq
            new_codes.append(f"{base}-{seq:02d}")

    df["codigo_form"] = new_codes
    # drop helper
    df = df.drop(columns=["__base_id"])

    # Final guarantees
    df["codigo_form"] = df["codigo_form"].astype(str)
    df["nome_form"] = df["nome_form"].astype(str)
    df["observacao"] = df["observacao"].astype(str)
    df["dependencia_form"] = df["dependencia_form"].astype(str)

    return df

# -----------------------
# Preparar pareamento (UI)
# -----------------------
def preparar_pareamento(siga_df, form_df):
    """
    Prepara DataFrames usados pela UI:
      - pares_df: cópia do siga_df (cada linha representa um item SIGA) com coluna 'codigo_form' (None inicialmente)
      - somente_siga: cópia completa do siga_df (para export)
      - somente_form: cópia completa do form_df (para export)
    """
    pares_df = siga_df.copy().reset_index(drop=True)
    pares_df["codigo_form"] = None  # campo que a UI vai popular
    # garantir colunas mínimas
    if "nome" not in pares_df.columns:
        pares_df["nome"] = ""
    if "observacao" not in pares_df.columns:
        pares_df["observacao"] = ""
    if "dependencia" not in pares_df.columns:
        pares_df["dependencia"] = ""
    return pares_df, siga_df.copy().reset_index(drop=True), form_df.copy().reset_index(drop=True)

# -----------------------
# Exportação XLSX / ZIP
# -----------------------
def gerar_exportacao(pareados_df, somente_siga_df, somente_form_df, siga_df_full, form_df_full, nome_base="comparador_manual", compact=False):
    """
    Gera:
      - se compact=False -> BytesIO com XLSX contendo abas:
            'Pareados' (linhas combinando SIGA + FORM com prefixos SIGA__ / FORM__),
            'Somente_SIGA' (SIGA completo),
            'Somente_Formulário' (FORM completo)
      - se compact=True -> ZIP com 3 CSVs correspondentes
    """
    # Construir aba Pareados (cada linha do pareados_df)
    pareados_out = []
    for _, r in pareados_df.iterrows():
        codigo_siga = r.get("codigo_siga")
        # obter linha completa do SIGA
        siga_rows = []
        try:
            siga_rows = siga_df_full[siga_df_full["codigo"].astype(str) == str(codigo_siga)]
        except Exception:
            siga_rows = pd.DataFrame()
        siga_row = siga_rows.iloc[0].to_dict() if not siga_rows.empty else {}

        codigo_form = r.get("codigo_form")
        form_rows = pd.DataFrame()
        try:
            if codigo_form and str(codigo_form) != "None":
                form_rows = form_df_full[form_df_full["codigo_form"].astype(str) == str(codigo_form)]
        except Exception:
            form_rows = pd.DataFrame()
        form_row = form_rows.iloc[0].to_dict() if not form_rows.empty else {}

        combined = {}
        # prefix SIGA__
        for c in siga_df_full.columns:
            combined[f"SIGA__{c}"] = siga_row.get(c, "")
        # prefix FORM__
        for c in form_df_full.columns:
            combined[f"FORM__{c}"] = form_row.get(c, "")
        # meta
        combined["Status"] = "Pareado" if codigo_form and str(codigo_form) not in ["", "None"] else "Pendente"
        combined["Similaridade_%"] = r.get("similaridade", "") if "similaridade" in r else ""
        pareados_out.append(combined)

    pareados_out_df = pd.DataFrame(pareados_out)

    # Somente SIGA e Somente FORM já são cópias completas
    somente_siga_out = somente_siga_df.copy().reset_index(drop=True)
    somente_form_out = somente_form_df.copy().reset_index(drop=True)

    if not compact:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            # If pareados_out_df empty, create empty DF with at least one column
            if pareados_out_df.empty:
                pareados_out_df = pd.DataFrame(columns=["SIGA__codigo"])
            pareados_out_df.to_excel(writer, index=False, sheet_name="Pareados")
            somente_siga_out.to_excel(writer, index=False, sheet_name="Somente_SIGA")
            somente_form_out.to_excel(writer, index=False, sheet_name="Somente_Formulário")
        output.seek(0)
        return output
    else:
        mem = BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("pareados.csv", pareados_out_df.to_csv(index=False))
            z.writestr("somente_siga.csv", somente_siga_out.to_csv(index=False))
            z.writestr("somente_form.csv", somente_form_out.to_csv(index=False))
        mem.seek(0)
        return mem
