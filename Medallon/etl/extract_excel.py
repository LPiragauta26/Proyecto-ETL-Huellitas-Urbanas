"""Tarea 2 de Airflow (extract_excel_bronze):
Lee el archivo Excel de solicitudes de bienestar animal de Cali (CBA / Uaepa),
verifica su hash SHA-256 sin modificar el dato original y preserva copia en Bronze.
"""
from datetime import datetime
import shutil

import src.extract.extract_csv as extraer_csv
from src.utils.helpers import cargar_config, get_logger, ruta

log = get_logger()


def run() -> dict:
    cfg = cargar_config()
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fecha_ejec = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Iniciando tarea extract_excel_bronze (corrida: %s)...", run_ts)

    sc = cfg["sources"]["cali"]
    rel_path = sc["path"]
    archivo = ruta(rel_path)

    if sc.get("file_type") == "excel":
        df_cali = extraer_csv.extraer_cali_excel(rel_path, sc["sheet_name"])
    else:
        df_cali = extraer_csv.extraer_cali(rel_path, sc["encoding"])

    sha = extraer_csv.sha256_archivo(archivo)
    fecha_mod = datetime.fromtimestamp(archivo.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")

    carpeta_run_rel = f"data/bronze/runs/{run_ts}"
    carpeta_run = ruta(carpeta_run_rel)
    carpeta_run.mkdir(parents=True, exist_ok=True)
    copia_rel = f"{carpeta_run_rel}/{archivo.name}"
    shutil.copy2(archivo, ruta(copia_rel))

    resumen = {
        "etapa": "extract_excel_bronze",
        "run_timestamp": run_ts,
        "fecha_ejecucion": fecha_ejec,
        "excel_path": rel_path,
        "sheet_name": sc.get("sheet_name", "cali"),
        "bronze_copy_path": copia_rel,
        "filas_cali_bronze": int(len(df_cali)),
        "columnas_cali_bronze": int(df_cali.shape[1]),
        "fecha_modificacion_archivo": fecha_mod,
        "version_sha256": sha,
        "procedencia": sc.get("owner", "UAEPA / Centro de Bienestar Animal - Cali"),
    }
    print(
        f"[extract_excel_bronze] Filas={len(df_cali)} | Columnas={df_cali.shape[1]} | "
        f"SHA256={sha[:12]}... | Copia={copia_rel}"
    )
    log.info(
        "extract_excel_bronze completado: %s filas x %s columnas, sha256=%s, copia en %s",
        len(df_cali),
        df_cali.shape[1],
        sha[:12],
        copia_rel,
    )
    return resumen
