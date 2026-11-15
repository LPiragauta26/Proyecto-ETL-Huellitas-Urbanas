"""Tarea 3 de Airflow (transform_silver):
Ejecuta la limpieza y estandarización Bronze -> Silver para Cali (CBA/Uaepa) y Bogotá (IDPYBA),
calcula métricas de calidad antes/después y genera el reporte de trazabilidad de fuentes.
"""
from datetime import datetime
import pandas as pd

import src.extract.extract_csv as extraer_csv
import src.extract.extract_geojson as extraer_geo
import src.load.load_datawarehouse as cargar
import src.quality.quality_checks as calidad
import src.transform.clean_bogota as limpieza_bogota
import src.transform.clean_cali as limpieza_cali
from src.utils.helpers import cargar_config, get_logger

log = get_logger()


def run(api_info: dict | None = None, excel_info: dict | None = None) -> dict:
    cfg = cargar_config()
    p, s = cfg["paths"], cfg["sources"]
    fecha_ejec = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Iniciando tarea transform_silver...")

    # 1) Lectura desde Bronze
    if s["cali"].get("file_type") == "excel":
        bronze_cali = extraer_csv.extraer_cali_excel(s["cali"]["path"], s["cali"]["sheet_name"])
    else:
        bronze_cali = extraer_csv.extraer_cali(s["cali"]["path"], s["cali"]["encoding"])
    bronze_bogota = extraer_geo.extraer_bogota(s["bogota"]["path"])

    # 2) Transformación Silver
    silver_cali = limpieza_cali.limpiar_cali(bronze_cali, cfg["quality"])
    silver_bogota = limpieza_bogota.limpiar_bogota(bronze_bogota)

    cargar.guardar_csv(silver_cali, p["silver_cali"])
    cargar.guardar_csv(silver_bogota, p["silver_bogota"])

    # 3) Reporte de trazabilidad de las 3 fuentes
    trazabilidad_path = f"{p['evidencias_dir']}/trazabilidad_fuentes.csv"
    df_traza = pd.DataFrame([
        {
            "fuente": "Cali - Solicitudes CBA / Uaepa",
            "formato": s["cali"].get("file_type", "excel"),
            "ruta_bronze": s["cali"]["path"],
            "filas_bronze": len(bronze_cali),
            "filas_silver": len(silver_cali),
            "sha256": (excel_info or {}).get("version_sha256", "")[:16],
            "fecha_ejecucion": fecha_ejec,
        },
        {
            "fuente": "Bogotá - Urgencias IDPYBA",
            "formato": "geojson",
            "ruta_bronze": s["bogota"]["path"],
            "filas_bronze": len(bronze_bogota.get("features", [])),
            "filas_silver": len(silver_bogota),
            "sha256": (api_info or {}).get("sha256_bogota_geojson", ""),
            "fecha_ejecucion": fecha_ejec,
        },
        {
            "fuente": "Cali - Proyecciones Población API CKAN",
            "formato": "json_api",
            "ruta_bronze": cfg["api_poblacion"]["guardar_en"],
            "filas_bronze": (api_info or {}).get("registros_api_poblacion", 41),
            "filas_silver": 37,
            "sha256": (api_info or {}).get("sha256_poblacion_api", ""),
            "fecha_ejecucion": fecha_ejec,
        },
    ])
    cargar.guardar_csv(df_traza, trazabilidad_path)

    # 4) Métricas de calidad antes y después
    metricas = calidad.metricas_calidad_cali(bronze_cali, silver_cali, cfg["quality"])
    cargar.guardar_csv(metricas, f"{p['kpis_dir']}/kpi_calidad_datos.csv")

    comunas_recup = int(silver_cali["comuna_imputada"].sum())
    fechas_corr = int(silver_cali["fecha_corregida"].sum())
    zonas_antes = int(bronze_cali["Comuna"].nunique())
    zonas_despues = int(silver_cali["zona"].nunique())

    resumen = {
        "etapa": "transform_silver",
        "fecha_ejecucion": fecha_ejec,
        "silver_cali_path": p["silver_cali"],
        "silver_bogota_path": p["silver_bogota"],
        "trazabilidad_path": trazabilidad_path,
        "filas_entrada_cali": int(len(bronze_cali)),
        "filas_salida_silver_cali": int(len(silver_cali)),
        "zonas_distintas_antes": zonas_antes,
        "zonas_distintas_despues": zonas_despues,
        "comunas_imputadas_desde_barrio": comunas_recup,
        "fechas_corregidas_0225": fechas_corr,
        "localidades_silver_bogota": int(len(silver_bogota)),
        "atenciones_totales_bogota": int(silver_bogota["atenciones"].sum()),
    }
    print(
        f"[transform_silver] Cali={len(silver_cali)} filas (zonas {zonas_antes}->{zonas_despues}, "
        f"comunas recuperadas={comunas_recup}, fechas 0225 corregidas={fechas_corr}) | "
        f"Bogotá={len(silver_bogota)} localidades ({int(silver_bogota['atenciones'].sum())} atenciones)"
    )
    log.info(
        "transform_silver completado: Cali=%s filas (%s), Bogotá=%s localidades (%s)",
        len(silver_cali),
        p["silver_cali"],
        len(silver_bogota),
        p["silver_bogota"],
    )
    return resumen
