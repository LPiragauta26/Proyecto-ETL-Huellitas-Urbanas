"""Extraccion (capa BRONZE) de Cali: lee el CSV tal cual, sin transformar."""
import hashlib

import pandas as pd

from src.utils.helpers import get_logger, ruta

log = get_logger()


def sha256_archivo(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def extraer_cali(path: str, encoding: str = "utf-8-sig") -> pd.DataFrame:
    """Lee Dataset_cali.csv como TEXTO (dtype=str, sin convertir N/D a nulos) para
    conservar los datos originales exactamente como llegaron."""
    archivo = ruta(path)
    df = pd.read_csv(archivo, encoding=encoding, dtype=str, keep_default_na=False)
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    log.info("BRONZE Cali: %s filas x %s columnas | sha256=%s", len(df), df.shape[1], sha256_archivo(archivo)[:16])
    return df

def extraer_cali_excel(path: str, sheet_name: str) -> pd.DataFrame:
    """Lee Dataset_cali.xlsx como TEXTO, igual que el CSV original, sin transformar nada."""
    archivo = ruta(path)
    df = pd.read_excel(archivo, sheet_name=sheet_name, dtype=str, keep_default_na=False, engine="openpyxl")
    df.columns = [c.replace("\ufeff", "").strip() for c in df.columns]
    log.info("BRONZE Cali (Excel): %s filas x %s columnas | sha256=%s", len(df), df.shape[1], sha256_archivo(archivo)[:16])
    return df