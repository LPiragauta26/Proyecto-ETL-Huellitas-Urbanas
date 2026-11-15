"""Tarea 5 de Airflow (validate_gold):
Ejecuta las reglas de validación de calidad (OKR 3 y consistencia de Gold),
actualiza de forma idempotente el Data Warehouse SQLite (warehouse.db) y genera las 8 gráficas de evidencia.
"""
from datetime import datetime
import pandas as pd

import src.extract.extract_csv as extraer_csv
import src.load.load_datawarehouse as cargar
import src.quality.quality_checks as calidad
import src.transform.gold_data as gold
import src.utils.graficos as graficos
from etl.build_gold import _cargar_silver_bogota, _cargar_silver_cali
from src.utils.helpers import cargar_config, get_logger, ruta

log = get_logger()


def run(gold_info: dict | None = None) -> dict:
    cfg = cargar_config()
    p, s = cfg["paths"], cfg["sources"]
    fecha_ejec = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Iniciando tarea validate_gold...")

    if s["cali"].get("file_type") == "excel":
        bronze_cali = extraer_csv.extraer_cali_excel(s["cali"]["path"], s["cali"]["sheet_name"])
    else:
        bronze_cali = extraer_csv.extraer_cali(s["cali"]["path"], s["cali"]["encoding"])

    silver_cali = _cargar_silver_cali(p["silver_cali"])
    silver_bogota = _cargar_silver_bogota(p["silver_bogota"])
    gold_final = pd.read_csv(ruta(p["gold_final"]), encoding="utf-8-sig")
    dim = gold.construir_dim_categoria(silver_cali)

    # 1) Validación de reglas de calidad y consistencia de Gold
    duplicados_gold = int(gold_final.duplicated(subset=["ciudad", "zona", "categoria", "periodo"]).sum())
    reglas_totales = calidad.validar_pipeline(
        bronze_cali, silver_cali, silver_bogota, cfg["quality"], gold_final=gold_final
    )

    validaciones_path = f"{p['evidencias_dir']}/validaciones_calidad.csv"
    cargar.guardar_csv(reglas_totales, validaciones_path)

    # 2) Lectura de las 13 tablas KPI generadas en Gold
    kd = p["kpis_dir"]
    nombres_kpis = [
        "kpi_calidad_datos",
        "kpi_casos_por_zona",
        "kpi_evolucion_mensual",
        "kpi_priorizacion_territorial",
        "kpi_comparativo_ciudades",
        "kpi_urgencias_por_zona",
        "kpi_bogota_detalle",
        "kpi_cambio_anual_servicios",
        "kpi_brecha_prevencion_zona",
        "kpi_top_barrios_cali",
        "kpi_calidad_por_clase",
        "kpi_patron_semanal_cali",
        "kpi_bogota_engativa_vs_resto",
    ]
    tablas_kpis = {nombre: pd.read_csv(ruta(f"{kd}/{nombre}.csv"), encoding="utf-8-sig") for nombre in nombres_kpis}

    # 3) Carga idempotente en SQLite (warehouse.db)
    tablas_dw = {
        "silver_cali": silver_cali.assign(fecha=silver_cali["fecha"].astype("string")),
        "silver_bogota": silver_bogota.assign(fecha_corte=silver_bogota["fecha_corte"].astype("string")),
        "gold_final": gold_final,
        "dim_categoria": dim,
        "validaciones_calidad": reglas_totales,
        **tablas_kpis,
    }
    cargar.cargar_datawarehouse(tablas_dw, p["warehouse_db"])

    # 4) Generación de las 8 gráficas de evidencia
    ev = p["evidencias_dir"]
    graficos.grafica_casos_por_comuna(tablas_kpis["kpi_casos_por_zona"], ev)
    graficos.grafica_evolucion_mensual(tablas_kpis["kpi_evolucion_mensual"], ev)
    graficos.grafica_urgencias_ciudades(tablas_kpis["kpi_urgencias_por_zona"], ev)
    graficos.grafica_calidad(tablas_kpis["kpi_calidad_datos"], ev)
    graficos.grafica_cambio_anual_servicios(tablas_kpis["kpi_cambio_anual_servicios"], ev)
    graficos.grafica_brecha_prevencion(tablas_kpis["kpi_brecha_prevencion_zona"], ev)
    graficos.grafica_top_barrios(tablas_kpis["kpi_top_barrios_cali"], ev)
    graficos.grafica_bogota_sesgo_uca(tablas_kpis["kpi_bogota_engativa_vs_resto"], ev)

    n_ok = int((reglas_totales["estado"] == "OK").sum())
    n_adv = int((reglas_totales["estado"] == "ADVERTENCIA").sum())
    n_err = int((reglas_totales["estado"] == "FALLA").sum())

    if n_err > 0:
        raise ValueError(f"validate_gold falló con {n_err} reglas en estado FALLA")

    resumen = {
        "etapa": "validate_gold",
        "fecha_ejecucion": fecha_ejec,
        "validaciones_path": validaciones_path,
        "warehouse_path": p["warehouse_db"],
        "filas_validadas_gold": int(len(gold_final)),
        "duplicados_llave": duplicados_gold,
        "controles_ok": n_ok,
        "controles_advertencia": n_adv,
        "controles_error": n_err,
        "tablas_cargadas_sqlite": len(tablas_dw),
        "filas_insertadas_sqlite_gold": int(len(gold_final)),
        "graficas_generadas": 8,
    }
    print(
        f"[validate_gold] Validaciones OK={n_ok} | ADVERTENCIAS={n_adv} | ERRORES={n_err} | "
        f"Duplicados llave={duplicados_gold} | SQLite ({len(tablas_dw)} tablas, gold_final={len(gold_final)} filas) | "
        f"Gráficas PNG=8"
    )
    log.info("validate_gold completado exitosamente: %s", resumen)
    return resumen
