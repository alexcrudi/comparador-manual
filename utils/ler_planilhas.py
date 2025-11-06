import pandas as pd

def _read_file(file):
    # file may be an UploadedFile or path
    name = getattr(file, "name", str(file))
    if str(name).lower().endswith(".csv"):
        return pd.read_csv(file, dtype=str, keep_default_na=False)
    else:
        return pd.read_excel(file, dtype=str)

def _normalize_cols(df):
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    return df

def ler_planilha_siga(file):
    df = _read_file(file)
    df = _normalize_cols(df)
    cols = df.columns.tolist()
    # detect candidates
    codigo_candidates = [c for c in cols if "cod" in c or "codigo" in c or c=="id"]
    nome_candidates = [c for c in cols if "nome" in c or "descr" in c or "descricao" in c]
    if codigo_candidates:
        df = df.rename(columns={codigo_candidates[0]: "codigo_siga"})
    else:
        df = df.reset_index().rename(columns={"index":"codigo_siga"})
    if nome_candidates:
        df = df.rename(columns={nome_candidates[0]: "nome_siga"})
    else:
        # try second column, else fill empty
        if len(cols) > 1:
            df = df.rename(columns={cols[1]: "nome_siga"})
        else:
            df["nome_siga"] = ""
    # ensure columns exist
    if "codigo_siga" not in df.columns:
        df["codigo_siga"] = df.index.astype(str)
    if "nome_siga" not in df.columns:
        df["nome_siga"] = ""
    return df

def ler_planilha_form(file):
    df = _read_file(file)
    df = _normalize_cols(df)
    cols = df.columns.tolist()
    codigo_candidates = [c for c in cols if "response" in c or "id" in c or "codigo" in c]
    nome_candidates = [c for c in cols if "nome" in c or "item" in c or "descr" in c]
    obs_candidates = [c for c in cols if "obs" in c or "observ" in c or "nota" in c or "coment" in c]
    if codigo_candidates:
        df = df.rename(columns={codigo_candidates[0]: "codigo_tally"})
    else:
        df = df.reset_index().rename(columns={"index":"codigo_tally"})
        df["codigo_tally"] = df["codigo_tally"].apply(lambda x: f"F{int(x)+1:03d}")
    if nome_candidates:
        df = df.rename(columns={nome_candidates[0]: "nome_form"})
    else:
        # fallback: try other columns
        if len(cols) > 0:
            df = df.rename(columns={cols[0]: "nome_form"})
        else:
            df["nome_form"] = ""
    if obs_candidates:
        df = df.rename(columns={obs_candidates[0]: "observacao"})
    else:
        df["observacao"] = ""
    # ensure columns exist
    if "codigo_tally" not in df.columns:
        df["codigo_tally"] = df.index.astype(str)
    if "nome_form" not in df.columns:
        df["nome_form"] = ""
    return df
