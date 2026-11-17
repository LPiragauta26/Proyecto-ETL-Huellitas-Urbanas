"""Orquestador del pipeline Medallion: Bronze -> Silver -> Gold -> Validacion/Entrega.

Uso:  python main.py
"""
import sys
import pandas as pd

import src.extract.extract_api as api
import src.extract.extract_csv as extraer_csv
import src.extract.extract_geojson as extraer_geo
import src.load.load_datawarehouse as cargar
import src.quality.quality_checks as calidad
import src.transform.clean_bogota as limpieza_bogota
import src.transform.clean_cali as limpieza_cali
import src.transform.gold_data as gold
import src.utils.graficos as graficos
from src.utils.helpers import cargar_config, get_logger

log = get_logger()


def main() -> int:
    cfg = cargar_config()
    p, s = cfg["paths"], cfg["sources"]
    log.info("=== INICIO PIPELINE: %s v%s ===", cfg["project"]["name"], cfg["project"]["version"])

    # ---------------- 01 EXTRACCION / BRONZE (datos originales, sin modificar)
    bronze_cali = None
    if cfg["api"]["enabled"]:
        try:
            bronze_cali = api.extraer_cali_api(cfg["api"])
        except Exception as e:  # la API puede caerse: se usa el archivo local
            log.warning("API no disponible (%s). Se usa el archivo local de bronze.", e)
    if bronze_cali is None:
        if s["cali"].get("file_type") == "excel":
            bronze_cali = extraer_csv.extraer_cali_excel(s["cali"]["path"], s["cali"]["sheet_name"])
        else:
            bronze_cali = extraer_csv.extraer_cali(s["cali"]["path"], s["cali"]["encoding"])
    bronze_bogota = extraer_geo.extraer_bogota(s["bogota"]["path"])

    # ---------------- 02 TRANSFORMACION / SILVER
    silver_cali = limpieza_cali.limpiar_cali(bronze_cali, cfg["quality"])
    silver_bogota = limpieza_bogota.limpiar_bogota(bronze_bogota)
    cargar.guardar_csv(silver_cali, p["silver_cali"])
    cargar.guardar_csv(silver_bogota, p["silver_bogota"])

    # Validacion de calidad (OKR 3)
    metricas = calidad.metricas_calidad_cali(bronze_cali, silver_cali, cfg["quality"])

    # ---------------- 03 GOLD (integracion con JOIN + KPIs)
    gold_final = gold.integrar_gold_final(silver_cali, silver_bogota)
    dim = gold.construir_dim_categoria(silver_cali)
    reglas = calidad.validar_pipeline(bronze_cali, silver_cali, silver_bogota, cfg["quality"], gold_final=gold_final)

    poblacion = None
    cp = cfg.get("api_poblacion", {})
    if cp.get("enabled"):
        try:
            poblacion = gold.poblacion_desde_api(api.extraer_poblacion_api(cp), cp["anio"])
        except Exception as e:  # sin internet o API caída: se usa el archivo local
            log.warning("API de población no disponible (%s). Se usa el archivo local.", e)
    if poblacion is None:
        poblacion = gold.cargar_poblacion(s["poblacion_cali"]["path"])

    k_zona = gold.kpi_casos_por_zona(silver_cali, poblacion)
    k_evol = gold.kpi_evolucion_mensual(silver_cali)
    k_prio = gold.kpi_priorizacion(k_zona, cfg["gold"]["pesos_priorizacion"])
    k_comp = gold.kpi_comparativo_ciudades(silver_cali, silver_bogota, dim)
    k_urg = gold.kpi_urgencias_por_zona(silver_cali, silver_bogota)
    k_bog = gold.kpi_bogota_detalle(silver_bogota)

    # Nuevos KPIs para responder preguntas adicionales de negocio
    k_cambio = gold.kpi_cambio_anual_servicios(silver_cali)
    k_brecha = gold.kpi_brecha_prevencion_zona(k_zona)
    k_barrios = gold.kpi_top_barrios_cali(silver_cali)
    k_cal_clase = gold.kpi_calidad_por_clase(silver_cali)
    k_semanal = gold.kpi_patron_semanal_cali(silver_cali)
    k_bog_sesgo = gold.kpi_bogota_engativa_vs_resto(silver_bogota)

    kd = p["kpis_dir"]
    cargar.guardar_csv(gold_final, p["gold_final"])
    tablas_kpis = {
        "kpi_calidad_datos": metricas,
        "kpi_casos_por_zona": k_zona,
        "kpi_evolucion_mensual": k_evol,
        "kpi_priorizacion_territorial": k_prio,
        "kpi_comparativo_ciudades": k_comp,
        "kpi_urgencias_por_zona": k_urg,
        "kpi_bogota_detalle": k_bog,
        "kpi_cambio_anual_servicios": k_cambio,
        "kpi_brecha_prevencion_zona": k_brecha,
        "kpi_top_barrios_cali": k_barrios,
        "kpi_calidad_por_clase": k_cal_clase,
        "kpi_patron_semanal_cali": k_semanal,
        "kpi_bogota_engativa_vs_resto": k_bog_sesgo,
    }
    for nombre, df in tablas_kpis.items():
        cargar.guardar_csv(df, f"{kd}/{nombre}.csv")
    cargar.guardar_csv(reglas, f"{p['evidencias_dir']}/validaciones_calidad.csv")

    cargar.cargar_datawarehouse({
        "silver_cali": silver_cali.assign(fecha=silver_cali["fecha"].astype("string")),
        "silver_bogota": silver_bogota.assign(fecha_corte=silver_bogota["fecha_corte"].astype("string")),
        "gold_final": gold_final,
        "dim_categoria": dim,
        "validaciones_calidad": reglas,
        **tablas_kpis,
    }, p["warehouse_db"])

    # ---------------- 04 VALIDACION Y ENTREGA (evidencias)
    ev = p["evidencias_dir"]
    graficos.grafica_casos_por_comuna(k_zona, ev)
    graficos.grafica_evolucion_mensual(k_evol, ev)
    graficos.grafica_urgencias_ciudades(k_urg, ev)
    graficos.grafica_calidad(metricas, ev)
    graficos.grafica_cambio_anual_servicios(k_cambio, ev)
    graficos.grafica_brecha_prevencion(k_brecha, ev)
    graficos.grafica_top_barrios(k_barrios, ev)
    graficos.grafica_bogota_sesgo_uca(k_bog_sesgo, ev)

    fallas = reglas[reglas["estado"] == "FALLA"]
    from api.main import evaluar_solicitudes_automatico_airflow

    res_adop = evaluar_solicitudes_automatico_airflow()
    log.info(
        "Evaluación de solicitudes de adopción (Airflow/ETL): Total=%s | Aceptadas=%s | En espera=%s | Negadas=%s",
        res_adop["total_solicitudes"],
        res_adop["aceptadas"],
        res_adop["en_espera"],
        res_adop["negadas"],
    )
    log.info("=== FIN PIPELINE: %s reglas OK, %s advertencias, %s fallas ===",
             (reglas["estado"] == "OK").sum(), (reglas["estado"] == "ADVERTENCIA").sum(), len(fallas))
    return 1 if len(fallas) else 0


if __name__ == "__main__":
    sys.exit(main())
