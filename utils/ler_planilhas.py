import pandas as pd

def _read_file(file):
    if hasattr(file, "read"):
        name = getattr(file, "name", "")
    else:
        name = str(file)
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
    # tentar detectar colunas de codigo e nome
    cols = df.columns.tolist()
    codigo_candidates = [c for c in cols if "cod" in c or "codigo" in c or "id" in c]
    nome_candidates = [c for c in cols if "nome" in c or "descr" in c or "descrição" in c]
    if not codigo_candidates:
        raise ValueError("Não foi possível detectar coluna de código no SIGA. Renomeie a coluna para conter 'cod' ou 'codigo'.")
    if not nome_candidates:
        # fallback: criar coluna nome com concat de outras colunas
        df["nome_siga"] = df[codigo_candidates[0]].astype(str)
    else:
        df = df.rename(columns={codigo_candidates[0]: "codigo_siga", nome_candidates[0]: "nome_siga"})
    # garantir colunas existam
    if "codigo_siga" not in df.columns:
        df["codigo_siga"] = df.index.astype(str)
    if "nome_siga" not in df.columns:
        df["nome_siga"] = ""
    return df

def ler_planilha_form(file):
    df = _read_file(file)
    df = _normalize_cols(df)
    cols = df.columns.tolist()
    # Tally geralmente exporta um id/response id ou similar
    codigo_candidates = [c for c in cols if "response" in c or "id" in c or "codigo" in c]
    nome_candidates = [c for c in cols if "nome" in c or "item" in c or "descr" in c]
    obs_candidates = [c for c in cols if "obs" in c or "observ" in c or "nota" in c]
    if not codigo_candidates:
        # criar codigo_tally automático
        df = df.reset_index().rename(columns={"index": "codigo_tally"})
        df["codigo_tally"] = df["codigo_tally"].apply(lambda x: f\"F{int(x)+1:03d}\")
    else:
        df = df.rename(columns={codigo_candidates[0]: "codigo_tally"})
    if not nome_candidates:
        df["nome_form"] = ""
    else:
        df = df.rename(columns={nome_candidates[0]: "nome_form"})
    if obs_candidates:
        df = df.rename(columns={obs_candidates[0]: "observacao"})
    else:
        df["observacao"] = ""
    return df
