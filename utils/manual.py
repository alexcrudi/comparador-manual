# utils/manual.py
import pandas as pd
from io import BytesIO
import zipfile
from pathlib import Path
from typing import Tuple, Dict, Any

# ---------------------
# Leitura e normalização
# ---------------------
def _read_file(file):
    """
    Lê CSV ou Excel (UploadedFile ou caminho) e retorna DataFrame com strings.
    Remove colunas 'Unnamed' e colunas completamente vazias.
    """
    name = getattr(file, "name", str(file))
    if str(name).lower().endswith(".csv"):
        df = pd.read_csv(file, dtype=str, keep_default_na=False).fillna("")
    else:
        df = pd.read_excel(file, dtype=str).fillna("")
    df = _normalize_columns(df)
    # remover colunas 'Unnamed' e colunas completamente vazias
    df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", na=False)]
    # remover colunas que são todas vazias
    non_empty_cols = [c for c in df.columns if not df[c].astype(str).str.strip().eq("").all()]
    df = df[non_empty_cols]
    return df

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip nos nomes das colunas e normalize espaços."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    # renomear colunas duplicadas (ex: se tiver duas colunas com mesmo nome, pandas já adiciona .1, .2)
    return df

# -----------------------------------
# Funções de leitura específicas (SIGA / Form)
# -----------------------------------
def ler_planilha_siga(file) -> pd.DataFrame:
    """
    Lê SIGA (CSV/XLSX) e renomeia colunas-chave para uso interno:
      'Código' -> 'codigo'
      'Nome'   -> 'nome'
      'Dependência' -> 'dependencia'
    Mantém todas as demais colunas (limpas) para exportação.
    """
    df = _read_file(file)
    rename_map = {}
    # mapeamentos comuns (respeita capitalização exata - já normalizamos)
    if "Código" in df.columns:
        rename_map["Código"] = "codigo"
    if "Código " in df.columns:
        rename_map["Código "] = "codigo"
    if "Nome" in df.columns:
        rename_map["Nome"] = "nome"
    if "Dependência" in df.columns:
        rename_map["Dependência"] = "dependencia"
    if rename_map:
        df = df.rename(columns=rename_map)
    # garantir colunas mínimas
    if "codigo" not in df.columns:
        # se não existir, usar índice como codigo
        df = df.reset_index().rename(columns={"index": "codigo"})
        df["codigo"] = df["codigo"].astype(str)
    if "nome" not in df.columns:
        # se não existir, tentar pegar a segunda coluna como nome
        cols = list(df.columns)
        if len(cols) > 1:
            df = df.rename(columns={cols[1]: "nome"})
        else:
            df["nome"] = ""
    if "dependencia" not in df.columns:
        # aceitar coluna vazia para dependência
        df["dependencia"] = ""
    # trim strings
    df["codigo"] = df["codigo"].astype(str).str.strip()
    df["nome"] = df["nome"].astype(str).str.strip()
    df["dependencia"] = df["dependencia"].astype(str).str.strip()
    # manter restante das colunas (já limpas)
    return df

def ler_planilha_form(file) -> pd.DataFrame:
    """
    Lê a planilha do formulário (Tally) e renomeia colunas para:
      'Submission ID' -> 'codigo_form'  (base)
      'Nome / Tipo de Bens' -> 'nome_form'
      'Observações' -> 'observacao'
      'Dependência / Localização' -> 'dependencia_form'
    Gera códigos únicos (Opção C):
      - se Submission ID é único -> mantém
      - se há duplicatas -> cria suffix '-01','-02',...
    Mantém todas as demais colunas originais.
    """
    df = _read_file(file)
    rename_map = {}
    if "Submission ID" in df.columns:
        rename_map["Submission ID"] = "codigo_form"
    if "Nome / Tipo de Bens" in df.columns:
        rename_map["Nome / Tipo de Bens"] = "nome_form"
    if "Observações" in df.columns:
        rename_map["Observações"] = "observacao"
    if "Dependência / Localização" in df.columns:
        rename_map["Dependência / Localização"] = "dependencia_form"
    if "Respondent ID" in df.columns:
        rename_map["Respondent ID"] = "respondent_id"
    if "Submitted at" in df.columns:
        rename_map["Submitted at"] = "submitted_at"
    if rename_map:
        df = df.rename(columns=rename_map)
    # garantias
    if "codigo_form" not in df.columns:
        # gerar codigo_form automático F001...
        df = df.reset_index().rename(columns={"index": "codigo_form"})
        df["codigo_form"] = df["codigo_form"].apply(lambda x: f"F{int(x)+1:03d}")
    if "nome_form" not in df.columns:
        possible = [c for c in df.columns if "nome" in c.lower() or "item" in c.lower() or "tipo" in c.lower()]
        if possible:
            df = df.rename(columns={possible[0]: "nome_form"})
        else:
            df["nome_form"] = ""
    if "observacao" not in df.columns:
        df["observacao"] = ""
    if "dependencia_form" not in df.columns:
        possible = [c for c in df.columns if "depend" in c.lower() or "local" in c.lower()]
        if possible:
            df = df.rename(columns={possible[0]: "dependencia_form"})
        else:
            df["dependencia_form"] = ""
    # padronizar e trim
    df = df.reset_index(drop=True)
    df["codigo_form"] = df["codigo_form"].astype(str).str.strip()
    df["nome_form"] = df["nome_form"].astype(str).str.strip()
    df["observacao"] = df["observacao"].astype(str).str.strip()
    df["dependencia_form"] = df["dependencia_form"].astype(str).str.strip()
    # gerar códigos únicos quando houver duplicates (Opção C)
    base_ids = df["codigo_form"].astype(str).tolist()
    counts = {}
    for bid in base_ids:
        counts[bid] = counts.get(bid, 0) + 1
    seq_counters = {}
    unique_codes = []
    for bid in base_ids:
        if counts.get(bid, 0) <= 1:
            unique_codes.append(bid)
        else:
            seq = seq_counters.get(bid, 0) + 1
            seq_counters[bid] = seq
            unique_codes.append(f"{bid}-{seq:02d}")
    df["codigo_form"] = unique_codes
    # garantir tipos
    df["codigo_form"] = df["codigo_form"].astype(str)
    df["nome_form"] = df["nome_form"].astype(str)
    df["observacao"] = df["observacao"].astype(str)
    df["dependencia_form"] = df["dependencia_form"].astype(str)
    return df

# -----------------------------------
# Preparar pareamento para UI
# -----------------------------------
def preparar_pareamento(siga_df: pd.DataFrame, form_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Prepara DataFrames usados pela UI:
      - pares_df: cópia do siga_df (cada linha representa um item SIGA) com coluna 'codigo_form' (None inicialmente)
      - somente_siga: cópia completa do siga_df (para export)
      - somente_form: cópia completa do form_df (para export)
    Observação: não realiza matching automático — modo 100% manual.
    """
    pares_df = siga_df.copy().reset_index(drop=True)
    pares_df["codigo_form"] = None
    # garantir colunas mínimas
    if "nome" not in pares_df.columns:
        pares_df["nome"] = ""
    if "observacao" not in pares_df.columns:
        pares_df["observacao"] = ""
    if "dependencia" not in pares_df.columns:
        pares_df["dependencia"] = ""
    return pares_df, siga_df.copy().reset_index(drop=True), form_df.copy().reset_index(drop=True)

# -----------------------------------
# Exportação (XLSX 3 abas) + CSV completo
# -----------------------------------
def gerar_exportacao(pareados_df: pd.DataFrame, somente_siga_df: pd.DataFrame, somente_form_df: pd.DataFrame,
                     siga_df_full: pd.DataFrame, form_df_full: pd.DataFrame, nome_base: str = "comparador_manual",
                     include_csv: bool = True) -> Dict[str, BytesIO]:
    """
    Gera:
      - XLSX com 3 abas: 'Pareados', 'Somente_SIGA', 'Somente_Formulário'
      - Opcionalmente um CSV 'tudo-em-um' contendo todas as linhas (pareados + somente_siga + somente_form)
    Retorna dicionário com chaves:
      {'xlsx': BytesIO, 'csv': BytesIO}  (csv presente apenas se include_csv=True)
    Observações:
      - Na aba 'Pareados' as colunas são prefixadas 'SIGA__' e 'FORM__' (com todas as colunas originais).
      - No CSV, cada linha possui as mesmas colunas prefixadas e coluna 'Status' indicando onde pertence.
    """
    # --- construir 'Pareados' ---
    pareados_out_rows = []
    # iterar sobre as linhas do pareados_df (cada linha corresponde a uma linha do SIGA)
    for _, r in pareados_df.iterrows():
        codigo_siga = r.get("codigo_siga") if isinstance(r, dict) else r.get("codigo_siga", "")
        # buscar linha completa do SIGA
        siga_rows = siga_df_full[siga_df_full["codigo"].astype(str) == str(codigo_siga)] if "codigo" in siga_df_full.columns else pd.DataFrame()
        siga_row = siga_rows.iloc[0].to_dict() if not siga_rows.empty else {}
        codigo_form = r.get("codigo_form", "") if isinstance(r, dict) else r.get("codigo_form", "")
        form_row = {}
        if codigo_form and "codigo_form" in form_df_full.columns:
            fr = form_df_full[form_df_full["codigo_form"].astype(str) == str(codigo_form)]
            if not fr.empty:
                form_row = fr.iloc[0].to_dict()
        # combinar colunas (prefix)
        combined = {}
        for c in siga_df_full.columns:
            combined[f"SIGA__{c}"] = siga_row.get(c, "")
        for c in form_df_full.columns:
            combined[f"FORM__{c}"] = form_row.get(c, "")
        combined["Status"] = "Pareado" if codigo_form and str(codigo_form) != "" else "Pendente"
        pareados_out_rows.append(combined)
    pareados_out_df = pd.DataFrame(pareados_out_rows)
    if pareados_out_df.empty:
        # manter coluna de referência se vazio
        pareados_out_df = pd.DataFrame(columns=["SIGA__codigo"])

    # --- Somente SIGA (copiar todas as colunas do siga_df_full e assinalar Status) ---
    somente_siga_out = []
    for _, r in somente_siga_df.iterrows():
        row = {}
        for c in siga_df_full.columns:
            row[f"SIGA__{c}"] = r.get(c, "")
        # preencher colunas FORM__* com vazio
        for c in form_df_full.columns:
            row[f"FORM__{c}"] = ""
        row["Status"] = "Somente_SIGA"
        somente_siga_out.append(row)
    somente_siga_out_df = pd.DataFrame(somente_siga_out)

    # --- Somente FORM (copiar todas as colunas do form_df_full e assinalar Status) ---
    somente_form_out = []
    for _, r in somente_form_df.iterrows():
        row = {}
        # preencher colunas SIGA__* com vazio
        for c in siga_df_full.columns:
            row[f"SIGA__{c}"] = ""
        for c in form_df_full.columns:
            row[f"FORM__{c}"] = r.get(c, "")
        row["Status"] = "Somente_Formulario"
        somente_form_out.append(row)
    somente_form_out_df = pd.DataFrame(somente_form_out)

    # --- Criar XLSX (3 abas) ---
    xlsx_io = BytesIO()
    with pd.ExcelWriter(xlsx_io, engine="xlsxwriter") as writer:
        # aba Pareados
        pareados_out_df.to_excel(writer, index=False, sheet_name="Pareados")
        # aba Somente_SIGA
        # se estiver vazia, salvar o DataFrame original (para manter colunas)
        if somente_siga_out_df.empty:
            # criar DF com colunas do siga para histórico
            tmp = somente_siga_df.copy().reset_index(drop=True)
            tmp.to_excel(writer, index=False, sheet_name="Somente_SIGA")
        else:
            somente_siga_out_df.to_excel(writer, index=False, sheet_name="Somente_SIGA")
        # aba Somente_Formulário
        if somente_form_out_df.empty:
            tmpf = somente_form_df.copy().reset_index(drop=True)
            tmpf.to_excel(writer, index=False, sheet_name="Somente_Formulário")
        else:
            somente_form_out_df.to_excel(writer, index=False, sheet_name="Somente_Formulário")
    xlsx_io.seek(0)

    result = {"xlsx": xlsx_io}

    # --- Criar CSV "tudo-em-um" se solicitado ---
    if include_csv:
        # concatenar: pareados, somente_siga, somente_form (todos já com as mesmas colunas prefixadas)
        # garantir que todos tenham as mesmas colunas (unir colunas)
        frames = []
        if not pareados_out_df.empty:
            frames.append(pareados_out_df)
        if not somente_siga_out_df.empty:
            frames.append(somente_siga_out_df)
        if not somente_form_out_df.empty:
            frames.append(somente_form_out_df)
        if frames:
            csv_all_df = pd.concat(frames, ignore_index=True, sort=False)
        else:
            # criar um CSV vazio com colunas mínimas
            cols = [f"SIGA__{c}" for c in siga_df_full.columns] + [f"FORM__{c}" for c in form_df_full.columns] + ["Status"]
            csv_all_df = pd.DataFrame(columns=cols)
        # ordenar colunas para ter sempre primeiro SIGA__..., depois FORM__..., depois Status
        siga_cols = [f"SIGA__{c}" for c in siga_df_full.columns]
        form_cols = [f"FORM__{c}" for c in form_df_full.columns]
        final_cols = [c for c in siga_cols if c in csv_all_df.columns] + [c for c in form_cols if c in csv_all_df.columns] + [c for c in ["Status"] if "Status" in csv_all_df.columns]
        csv_all_df = csv_all_df.reindex(columns=final_cols)
        # gerar CSV bytes (utf-8-sig para compatibilidade com Excel)
        csv_io = BytesIO()
        csv_text = csv_all_df.to_csv(index=False, encoding="utf-8-sig")
        csv_io.write(csv_text.encode("utf-8-sig"))
        csv_io.seek(0)
        result["csv"] = csv_io

    return result
