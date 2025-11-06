# utils/history.py
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS pareamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto TEXT,
    codigo_siga TEXT,
    nome_siga TEXT,
    observacao_siga TEXT,
    dependencia_siga TEXT,
    codigo_form TEXT,
    nome_form TEXT,
    observacao_form TEXT,
    dependencia_form TEXT,
    usuario TEXT,
    timestamp TEXT
);
"""

def ensure_db(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.executescript(DB_SCHEMA)
        conn.commit()
    finally:
        conn.close()

def insert_pareamentos(db_path: Path, projeto: str, rows: List[Dict[str, Any]], usuario: str = "local"):
    """
    rows: list of dicts, cada dict deve conter as chaves:
      codigo_siga, nome_siga, observacao_siga, dependencia_siga,
      codigo_form, nome_form, observacao_form, dependencia_form
    """
    ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat(timespec="seconds")
        for r in rows:
            cur.execute(
                "INSERT INTO pareamentos (projeto, codigo_siga, nome_siga, observacao_siga, dependencia_siga, codigo_form, nome_form, observacao_form, dependencia_form, usuario, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    projeto,
                    r.get("codigo_siga",""),
                    r.get("nome_siga",""),
                    r.get("observacao_siga",""),
                    r.get("dependencia_siga",""),
                    r.get("codigo_form",""),
                    r.get("nome_form",""),
                    r.get("observacao_form",""),
                    r.get("dependencia_form",""),
                    usuario,
                    now
                )
            )
        conn.commit()
    finally:
        conn.close()

def load_pareamentos(db_path: Path, projeto: str) -> List[Dict[str, Any]]:
    ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT codigo_siga, nome_siga, observacao_siga, dependencia_siga, codigo_form, nome_form, observacao_form, dependencia_form, usuario, timestamp FROM pareamentos WHERE projeto = ? ORDER BY id", (projeto,))
        rows = cur.fetchall()
        cols = ["codigo_siga","nome_siga","observacao_siga","dependencia_siga","codigo_form","nome_form","observacao_form","dependencia_form","usuario","timestamp"]
        return [dict(zip(cols, r)) for r in rows]
    finally:
        conn.close()

def list_projects(db_path: Path) -> List[str]:
    ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT projeto FROM pareamentos ORDER BY projeto")
        return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

def clear_project(db_path: Path, projeto: str):
    ensure_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM pareamentos WHERE projeto = ?", (projeto,))
        conn.commit()
    finally:
        conn.close()
