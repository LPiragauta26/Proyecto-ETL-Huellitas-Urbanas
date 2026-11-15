"""Tarea 4 de Airflow (build_gold):
Integra Silver Cali + Silver Bogotá mediante JOIN con dim_categoria y con la población de la API,
y construye de forma determinista e idempotente gold_final.csv y los 13 KPIs de negocio y calidad.
"""
from datetime import datetime
import json
import pandas as pd

import src.extract.extract_api as api
import src.extract.extract_csv as extraer_csv
import src.load.load_datawarehouse as cargar
import src.quality.quality_checks as calidad
import src.transform.gold_data as gold
from src.utils.helpers import cargar_config, get_logger, ruta

log = get_logger()


def _cargar_silver_cali(path_str: str) -> pd.DataFrame:
    df = pd.read_csv(ruta(path_str), encoding="utf-8-sig")
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
    df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")
    df["mes"] = pd.to_numeric(df["mes"], errors="coerce").astype("Int64")
    df["fecha_valida"] = df["fecha_valida"].astype(bool)
    df["fecha_corregida"] = df["fecha_corregida"].astype(bool)
    df["comuna_imputada"] = df["comuna_imputada"].astype(bool)
    for col_txt in ["clase", "zona", "tipo_zona", "barrio"]:
        df[col_txt] = df[col_txt].fillna("Sin dato").astype(str)
    return df


def _cargar_silver_bogota(path_str: str) -> pd.DataFrame:
    df = pd.read_csv(ruta(path_str), encoding="utf-8-sig")
    df["fecha_corte"] = pd.to_datetime(df["fecha_corte"], errors="coerce")
    return df


def run(silver_info: dict | None = None) -> dict:
    cfg = cargar_config()
    p, s = cfg["paths"], cfg["sources"]
    fecha_ejec = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info("Iniciando tarea build_gold...")

    silver_cali = _cargar_silver_cali(p["silver_cali"])
    silver_bogota = _cargar_silver_bogota(p["silver_bogota"])

    if s["cali"].get("file_type") == "excel":
        bronze_cali = extraer_csv.extraer_cali_excel(s["cali"]["path"], s["cali"]["sheet_name"])
    else:
        bronze_cali = extraer_csv.extraer_cali(s["cali"]["path"], s["cali"]["encoding"])

    # 1) Integración JOIN y catálogo homologado
    gold_final = gold.integrar_gold_final(silver_cali, silver_bogota)
    dim = gold.construir_dim_categoria(silver_cali)

    # 2) Población desde API CKAN (o snapshot local / CSV de respaldo)
    poblacion = None
    cp = cfg.get("api_poblacion", {})
    if cp.get("enabled"):
        try:
            json_snap = ruta(cp["guardar_en"])
            if json_snap.exists():
                datos = json.loads(json_snap.read_text(encoding="utf-8"))
                df_pob_api = pd.DataFrame(datos["result"]["records"])
            else:
                df_pob_api = api.extraer_poblacion_api(cp)
            poblacion = gold.poblacion_desde_api(df_pob_api, cp["anio"])
        except Exception as exc:
            log.warning("API/snapshot de población no disponible (%s). Se usa CSV local.", exc)
    if poblacion is None:
        poblacion = gold.cargar_poblacion(s["poblacion_cali"]["path"])

    # 3) Cálculo de los 13 KPIs de negocio y calidad
    metricas = calidad.metricas_calidad_cali(bronze_cali, silver_cali, cfg["quality"])
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

    # 4) Escritura determinista e idempotente en Gold
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

    top1_prio = k_prio.iloc[0]
    top1_barrio = k_barrios.iloc[0]
    urg_row = k_comp[k_comp["comparable"] == True].iloc[0]

    kpis_resumen = {
        "casos_cali_total": int(len(silver_cali)),
        "atenciones_bogota_total": int(silver_bogota["atenciones"].sum()),
        "urgencias_cali": int(urg_row["casos_cali_total"]),
        "urgencias_bogota": int(urg_row["casos_bogota_corte_2025_06_30"]),
        "zona_prioridad_1": str(top1_prio["zona"]),
        "indice_prioridad_1": float(top1_prio["indice_priorizacion"]),
        "barrio_critico_1": str(top1_barrio["barrio"]),
        "casos_criticos_barrio_1": int(top1_barrio["casos_criticos"]),
        "total_tablas_kpi": len(tablas_kpis),
    }

    resumen = {
        "etapa": "build_gold",
        "fecha_ejecucion": fecha_ejec,
        "gold_final_path": p["gold_final"],
        "kpis_dir": kd,
        "filas_gold_final": int(len(gold_final)),
        "columnas_gold_final": int(gold_final.shape[1]),
        "zonas_con_poblacion": 0 if poblacion is None else int(len(poblacion)),
        "kpis_resumen": kpis_resumen,
    }
    print(
        f"[build_gold] gold_final={len(gold_final)} filas x {gold_final.shape[1]} cols | "
        f"Tablas KPI={len(tablas_kpis)} | Resumen={kpis_resumen}"
    )
    log.info(
        "build_gold completado: gold_final=%s filas (%s), %s tablas KPI generadas",
        len(gold_final),
        p["gold_final"],
        len(tablas_kpis),
    )
    return resumen
