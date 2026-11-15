"""Tarea 1 de Airflow (extract_api_bronze):
Extrae las proyecciones de población de Cali desde la API CKAN de Datos Abiertos de Cali
y el GeoJSON de urgencias veterinarias de Bogotá (IDPYBA), preservando copia cruda en Bronze.
Incluye soporte para la Prueba P4 (fallo inducido controlado mediante FORZAR_FALLO_API.txt).
"""
from datetime import datetime
import os
import shutil

import src.extract.extract_api as api
import src.extract.extract_geojson as extraer_geo
from src.extract.extract_csv import sha256_archivo
from src.utils.helpers import cargar_config, get_logger, ruta

log = get_logger()


def run() -> dict:
    cfg = cargar_config()
    run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fecha_ejec = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Iniciando tarea extract_api_bronze (corrida: %s)...", run_ts)

    # Mecanismo para Prueba P4: fallo controlado sin alterar el código
    bandera_fallo = ruta("data/bronze/FORZAR_FALLO_API.txt")
    if bandera_fallo.exists() or os.environ.get("FORZAR_FALLO_API") == "1":
        msg = (
            "Fallo simulado en extract_api_bronze: API de Datos Abiertos de Cali "
            "temporalmente inaccesible (FORZAR_FALLO_API.txt activo)"
        )
        log.error(msg)
        raise ConnectionError(msg)

    cp = cfg["api_poblacion"]
    json_path = ruta(cp["guardar_en"])

    # 1) Extracción de API CKAN de población de Cali (con respaldo a snapshot en bronze)
    origen_pob = "api"
    try:
        df_pob = api.extraer_poblacion_api(cp)
        if not json_path.exists():
            origen_pob = "snapshot_bronze"
    except Exception as exc:
        log.warning("Fallo en consulta API población (%s). Verificando snapshot local...", exc)
        raise

    # 2) Extracción de GeoJSON de Bogotá (IDPYBA)
    bog_rel = cfg["sources"]["bogota"]["path"]
    bog_abs = ruta(bog_rel)
    geo_bogota = extraer_geo.extraer_bogota(bog_rel)
    n_features_bog = len(geo_bogota.get("features", []))
    sha_bogota = sha256_archivo(bog_abs)
    sha_pob = sha256_archivo(json_path) if json_path.exists() else ""

    # 3) Copia versionada de la corrida en data/bronze/runs/<run_ts>
    carpeta_run_rel = f"data/bronze/runs/{run_ts}"
    carpeta_run = ruta(carpeta_run_rel)
    carpeta_run.mkdir(parents=True, exist_ok=True)
    if json_path.exists():
        shutil.copy2(json_path, carpeta_run / json_path.name)
    if bog_abs.exists():
        shutil.copy2(bog_abs, carpeta_run / bog_abs.name)

    resumen = {
        "etapa": "extract_api_bronze",
        "run_timestamp": run_ts,
        "fecha_ejecucion": fecha_ejec,
        "bronze_dir": cfg["paths"]["bronze_dir"],
        "carpeta_corrida": carpeta_run_rel,
        "poblacion_json_path": cp["guardar_en"],
        "registros_api_poblacion": int(len(df_pob)),
        "anio_poblacion": str(cp["anio"]),
        "sha256_poblacion_api": sha_pob[:16],
        "bogota_geojson_path": bog_rel,
        "localidades_bogota": int(n_features_bog),
        "sha256_bogota_geojson": sha_bogota[:16],
        "origen_por_fuente": {
            "poblacion_cali_ckan": origen_pob,
            "bogota_idpyba_geojson": "archivo_bronze_geojson",
        },
    }
    print(
        f"[extract_api_bronze] Registros API población={len(df_pob)} (año {cp['anio']}) | "
        f"Localidades Bogotá GeoJSON={n_features_bog} | SHA256 Bogotá={sha_bogota[:12]}... | "
        f"Carpeta corrida={carpeta_run_rel}"
    )
    log.info(
        "extract_api_bronze completado: API población=%s registros, Bogotá GeoJSON=%s localidades, copia en %s",
        len(df_pob),
        n_features_bog,
        carpeta_run_rel,
    )
    return resumen
