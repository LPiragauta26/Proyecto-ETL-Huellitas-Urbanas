"""Convierte Dataset_cali.csv a .xlsx sin modificar su contenido (todo como texto).
Uso (desde la carpeta raíz):  python scripts/convertir_csv_a_excel.py"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.getcwd())
from src.utils.helpers import cargar_config  # noqa: E402

cfg = cargar_config()
src = cfg["sources"]["cali"]
df = pd.read_csv(src["original_csv"], encoding=src["encoding"], dtype=str, keep_default_na=False)
df.to_excel(src["path"], sheet_name=src["sheet_name"], index=False, engine="openpyxl")
print(f"Convertido: {src['original_csv']} -> {src['path']} ({df.shape[0]} filas, {df.shape[1]} columnas)")