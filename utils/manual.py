import pandas as pd
from io import BytesIO
import zipfile
from rapidfuzz import process, fuzz

# --------------------------
# Leitura / normalização
# --------------------------
def _read_file(file):
    name = getattr(file, "name", str(file))
    if str(name).lower().endswith(".csv"):
        return pd.read_csv(file, dtype=str, keep_default_na=False).fillna("")
    else:
        return pd.read_excel(file, dtype=str).fillna("")

def _normalize_cols(df):
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    return df

def ler_planilha_siga(file):
    """
    Lê o CSV/XLSX do SIGA e renomeia colunas-chave para uso interno:
    - 'Código' -> 'codigo'
    - 'Nome' -> 'nome'
    - 'Dependência' -> 'dependencia'
    Mantém todas as outras colunas para exportação.
    """
    df = _read_file(file)
    df = _normalize_cols(df)
    # normalizar nomes para acesso sem erros (manter originais para export)
    cols = {c: c for c in df.columns}
    # mapeamentos esperados (se existirem)
    if "Código" in df.columns:
        df = df.rename(columns={"Código": "codigo"})
    elif "Código " in df.columns:
        df = df.rename(columns={"Código ": "codigo"})
    if "Nome" in df.columns:
        df = df.rename(columns={"Nome": "nome"})
    if "Dependência" in df.columns:
        df = df.rename(columns={"Dependência": "dependencia"})
    # garantir colunas mínimas
    if "codigo" not in df.columns:
        df = df.reset_index().rename(columns={"index": "codigo"})
    if "nome" not in df.columns:
        df["nome"] = ""
    if "dependencia" not in df.columns:
        df["dependencia"] = ""
    # padronizar nomes de coluna para acesso fácil
    return df

def ler_planilha_form(file):
    """
    Lê o CSV/XLSX do formulário (Tally) e renomeia colunas:
    - 'Submission ID' -> 'codigo_form'  (você pediu: usar Submission ID como codigo_form)
    - 'Nome / Tipo de Bens' -> 'nome_form'
    - 'Observações' -> 'observacao'
    - 'Dependência / Localização' -> 'dependencia_form'
    Mantém todas as outras colunas originais para export.
    """
    df = _read_file(file)
    df = _normalize_cols(df)

    # mapear colunas reais para internas (se existirem)
    rename_map = {}
    if "Submission ID" in df.columns:
        rename_map["Submission ID"] = "codigo_form"
    if "Nome / Tipo de Bens" in df.columns:
        rename_map["Nome / Tipo de Bens"] = "nome_form"
    if "Observações" in df.columns:
        rename_map["Observações"] = "observacao"
    if "Dependência / Localização" in df.columns:
        rename_map["Dependência / Localização"] = "dependencia_form"
    if "Respondent ID" in df.columns and "respondent_id" not in df.columns:
        rename_map["Respondent ID"] = "respondent_id"
    if "Submitted at" in df.columns:
        rename_map["Submitted at"] = "submitted_at"

    if rename_map:
        df = df.rename(columns=rename_map)

    # Garantias
    if "codigo_form" not in df.columns:
        # gerar codigo_form automático (F001...)
        df = df.reset_index().rename(columns={"index": "codigo_form"})
        df["codigo_form"] = df["codigo_form"].apply(lambda x: f"F{int(x)+1:03d}")
    if "nome_form" not in df.columns:
        # tentar mapear por outras colunas se existir
        possible = [c for c in df.columns if "nome" in c.lower() or "item" in c.lower() or "tipo" in c.lower()]
        if possible:
            df = df.rename(columns={possible[0]: "nome_form"})
        else:
            df["nome_form"] = ""
    if "observacao" not in df.columns:
        df["observacao"] = ""
    if "dependencia_form" not in df.columns:
        # tentar mapear por outras colunas
        possible = [c for c in df.columns if "depend" in c.lower() or "local" in c.lower()]
        if possible:
            df = df.rename(columns={possible[0]: "dependencia_form"})
        else:
            df["dependencia_form"] = ""
    return df

# --------------------------
# Preparar pareamento
# --------------------------
def preparar_pareamento(siga_df, form_df):
    """
    Retorna:
    - pares_df: DataFrame baseado em siga_df que terá coluna 'codigo_form' preenchida durante UI
    - somente_siga: copia completa do siga_df (todos os campos originais)
    - somente_form: copia completa do form_df (todos os campos originais)
    """
    pares_df = siga_df.copy().reset_index(drop=True)
    pares_df["codigo_form"] = None  # coluna para preenchimento manual na UI
    # garantir colunas mínimas
    if "nome" not in pares_df.columns:
        pares_df["nome"] = ""
    if "observacao" not in pares_df.columns:
        pares_df["observacao"] = ""
    if "dependencia" not in pares_df.columns:
        pares_df["dependencia"] = ""
    # só retornamos as cópias completas
    return pares_df, siga_df.copy().reset_index(drop=True), form_df.copy().reset_index(drop=True)

# --------------------------
# Sugestões fuzzy
# --------------------------
def sugerir_candidatos(pares_df, form_df, k=5):
    """
    Para cada item do pares_df (base SIGA), retorna top-k candidatos do form_df.
    Retorna DataFrame com colunas: best_code, best_name, score (melhor), e lista de candidatos (opcional).
    """
    # preparar lista de strings para match: "codigo_form | nome_form (obs)"
    choices = form_df.apply(lambda r: f"{r.get('codigo_form','')} | {r.get('nome_form','')} {('('+r.get('observacao','')+')') if r.get('observacao') else ''}", axis=1).tolist()

    rows = []
    for _, s in pares_df.iterrows():
        query = str(s.get("nome", ""))

        # process.extract retorna (match, score, index)
        matches = process.extract(query, choices, scorer=fuzz.token_set_ratio, limit=k)
        if matches:
            best_match = matches[0]
            best_idx = best_match[2]
            best_code = form_df.iloc[best_idx].get("codigo_form", "")
            best_name = form_df.iloc[best_idx].get("nome_form", "")
            best_score = int(best_match[1])
        else:
            best_code = ""
            best_name = ""
            best_score = 0

        rows.append({
            "codigo": s.get("codigo", ""),
            "nome": s.get("nome", ""),
            "dependencia": s.get("dependencia", ""),
            "best_code": best_code,
            "best_name": best_name,
            "score": best_score
        })
    return pd.DataFrame(rows)

# --------------------------
# Exportação
# --------------------------
def gerar_exportacao(pareados_df, somente_siga_df, somente_form_df, siga_df_full, form_df_full, nome_base="comparador_manual", compact=False):
    """
    Gera:
    - se compact=False -> BytesIO com XLSX contendo abas:
        Pareados, Somente_SIGA, Somente_Formulário
      Na aba 'Pareados' teremos colunas lado-a-lado com TODOS os campos originais de cada lado, além de Status e Similaridade.
    - se compact=True -> BytesIO com ZIP contendo 3 CSVs: pareados.csv, somente_siga.csv, somente_form.csv
    """
    # --- construir aba Pareados ---
    # Para cada registro em pareados_df, juntar todos os campos da linha SIGA original e do FORM original (quando houver)
    pareados_out_rows = []
    for _, r in pareados_df.iterrows():
        codigo_siga = r.get("codigo_siga")
        # buscar linha completa do SIGA
        siga_rows = siga_df_full[siga_df_full["codigo"].astype(str) == str(codigo_siga)]
        siga_row = siga_rows.iloc[0].to_dict() if not siga_rows.empty else {}
        codigo_form = r.get("codigo_form")
        form_rows = form_df_full[form_df_full["codigo_form"].astype(str) == str(codigo_form)] if pd.notna(codigo_form) and codigo_form not in [None, "None", ""] else pd.DataFrame()
        form_row = form_rows.iloc[0].to_dict() if not form_rows.empty else {}

        # construir um registro que combina colunas do SIGA com colunas do FORM (prefixando)
        combined = {}
        # todas as colunas do siga
        for c in siga_df_full.columns:
            combined[f"SIGA__{c}"] = siga_row.get(c, "")
        # todas as colunas do form
        for c in form_df_full.columns:
            combined[f"FORM__{c}"] = form_row.get(c, "")
        # meta
        combined["Status"] = ("Pareado" if codigo_form not in [None, "", "None"] else "Pendente")
        combined["Similaridade_%"] = r.get("similaridade", "")
        pareados_out_rows.append(combined)

    pareados_out = pd.DataFrame(pareados_out_rows)

    # --- somente_siga_df e somente_form_df já são cópias completas ---
    # renomear colunas para deixar claro na exportação (sem prefixo)
    somente_siga_out = somente_siga_df.copy()
    somente_form_out = somente_form_df.copy()

    # --- Exportar ---
    if not compact:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            pareados_out.to_excel(writer, index=False, sheet_name="Pareados")
            somente_siga_out.to_excel(writer, index=False, sheet_name="Somente_SIGA")
            somente_form_out.to_excel(writer, index=False, sheet_name="Somente_Formulário")
        output.seek(0)
        return output
    else:
        mem = BytesIO()
        with zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("pareados.csv", pareados_out.to_csv(index=False))
            z.writestr("somente_siga.csv", somente_siga_out.to_csv(index=False))
            z.writestr("somente_form.csv", somente_form_out.to_csv(index=False))
        mem.seek(0)
        return mem
