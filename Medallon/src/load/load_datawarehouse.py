"""Carga: escribe silver/gold en CSV y publica las tablas en un 'datawarehouse' SQLite."""
import sqlite3

import pandas as pd

from src.utils.helpers import get_logger, ruta

log = get_logger()


def guardar_csv(df: pd.DataFrame, path: str) -> None:
    destino = ruta(path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(destino, index=False, encoding="utf-8-sig")  # utf-8-sig: se abre bien en Excel
    log.info("Archivo guardado: %s (%s filas)", path, len(df))


def cargar_datawarehouse(tablas: dict, db_path: str) -> None:
    destino = ruta(db_path)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(destino) as con:
        existentes = [
            r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        for t in existentes:
            if t not in tablas:
                con.execute(f'DROP TABLE IF EXISTS "{t}"')
        for nombre, df in tablas.items():
            df.to_sql(nombre, con, if_exists="replace", index=False)
            log.info("DW: tabla %s cargada (%s filas)", nombre, len(df))
