"""Pruebas del pipeline. Ejecutar con:  python -m pytest -q"""
import json

import pandas as pd
import pytest

import src.extract.extract_csv as extraer_csv
from src.transform.clean_bogota import LOCALIDADES, limpiar_bogota
from src.transform.clean_cali import (estandarizar_clase, estandarizar_comuna, limpiar_cali, parsear_fecha)
from src.transform.gold_data import (
    integrar_gold_final,
    kpi_bogota_engativa_vs_resto,
    kpi_brecha_prevencion_zona,
    kpi_calidad_por_clase,
    kpi_cambio_anual_servicios,
    kpi_casos_por_zona,
    kpi_evolucion_mensual,
    kpi_patron_semanal_cali,
    kpi_priorizacion,
    kpi_top_barrios_cali,
    poblacion_desde_api,
)
from src.utils.helpers import cargar_config, normalizar_texto, ruta

CFG = cargar_config()


@pytest.mark.parametrize("crudo,esperado", [
    ("Comuna 20", ("Comuna 20", "urbana")),
    ("COMUNA 20", ("Comuna 20", "urbana")),
    ("N/D", ("Sin dato", "sin_dato")),
    ("MONTEBELLLO", ("Montebello", "rural")),
    ("Corregimiento de Montebello", ("Montebello", "rural")),
    ("Corregimiento Pichinche", ("Pichinde", "rural")),
    ("FUERA DE JURISDICCION", ("Fuera de jurisdicción", "fuera_jurisdiccion")),
    ("Urgencias", ("Sin dato", "sin_dato")),   # error de digitacion en el campo Comuna
    ("Comuna 99", ("Sin dato", "sin_dato")),
])
def test_estandarizar_comuna(crudo, esperado):
    assert estandarizar_comuna(crudo) == esperado


def test_estandarizar_clase():
    assert estandarizar_clase("Pqr") == "PQR"
    assert estandarizar_clase("Cita médica") == "Cita médica"
    assert estandarizar_clase("N/D") == "Sin clasificar"
    assert estandarizar_clase("Sin respuesta") == "Sin clasificar"


def test_normalizar_texto():
    assert normalizar_texto("  ÁREA   de Expansión ") == "area de expansion"
    assert normalizar_texto(None) == ""


def test_fechas_invalidas_y_correccion():
    s = pd.Series(["2024-05-01T00:00:00", "0225-06-08T00:00:00", "2205-05-21T00:00:00", "2028-02-01T00:00:00", "2005-06-01T00:00:00"])
    fecha, valida, corregida = parsear_fecha(s, True, "2024-01-01", pd.Timestamp("2026-10-12"))
    assert valida.tolist() == [True, True, False, False, False]
    assert corregida.tolist() == [False, True, False, False, False]
    assert fecha.iloc[1] == pd.Timestamp("2025-06-08")
    assert fecha.iloc[2:].isna().all()


@pytest.fixture(scope="module")
def silver():
    sc = CFG["sources"]["cali"]
    if sc.get("file_type") == "excel":
        bronze = extraer_csv.extraer_cali_excel(sc["path"], sc["sheet_name"])
    else:
        bronze = extraer_csv.extraer_cali(sc["path"], sc["encoding"])
    with open(ruta(CFG["sources"]["bogota"]["path"]), encoding="utf-8") as f:
        geo = json.load(f)
    return bronze, limpiar_cali(bronze, CFG["quality"]), limpiar_bogota(geo)


def test_silver_cali_no_pierde_registros(silver):
    bronze, cali, _ = silver
    assert len(cali) == len(bronze) == 17642
    assert cali["id"].is_unique


def test_catalogo_de_zonas_reduce_valores(silver):
    bronze, cali, _ = silver
    assert cali["zona"].nunique() < bronze["Comuna"].nunique()
    assert not cali["zona"].str.contains("COMUNA").any()


def test_bogota_localidades_y_total(silver):
    _, _, bog = silver
    assert len(bog) == 20 and set(bog["cod_localidad"]) == set(LOCALIDADES)
    assert bog["atenciones"].sum() == 947
    assert bog.set_index("localidad").loc["Engativá", "atenciones"] == 656


def test_gold_cuadra_con_silver(silver):
    _, cali, bog = silver
    gold = integrar_gold_final(cali, bog)
    assert gold.loc[gold["ciudad"] == "Cali", "casos"].sum() == len(cali)
    assert gold.loc[gold["ciudad"] == "Bogotá", "casos"].sum() == bog["atenciones"].sum()
    assert set(gold["ciudad"]) == {"Cali", "Bogotá"}


def test_kpis_negocio_cuadran(silver):
    _, cali, bog = silver
    with open(ruta(CFG["api_poblacion"]["guardar_en"]), encoding="utf-8") as f:
        pob = poblacion_desde_api(pd.DataFrame(json.load(f)["result"]["records"]), CFG["api_poblacion"]["anio"])
    kz = kpi_casos_por_zona(cali, pob)
    cols_clases = ["denuncias", "urgencias", "esterilizaciones", "adopciones", "pqr", "citas_medicas", "solicitudes_info", "sin_clasificar"]
    assert (kz[cols_clases].sum(axis=1) == kz["casos_total"]).all()

    evol = kpi_evolucion_mensual(cali)
    assert evol["mes_con_registros"].all()  # sin meses fantasma en 2026

    prio = kpi_priorizacion(kz, CFG["gold"]["pesos_priorizacion"])
    assert prio.iloc[0]["zona"] == "Comuna 20"
    assert "ranking_en_tipo_zona" in prio.columns

    cambio = kpi_cambio_anual_servicios(cali)
    assert cambio["casos_2024"].sum() + cambio["casos_2025"].sum() == int(cali["fecha_valida"].sum())

    brecha = kpi_brecha_prevencion_zona(kz)
    assert not brecha.empty and "ratio_prevencion_criticos" in brecha.columns

    barrios = kpi_top_barrios_cali(cali)
    assert barrios.iloc[0]["barrio"] == "Siloé"

    cal_clase = kpi_calidad_por_clase(cali)
    assert cal_clase["casos_total"].sum() == len(cali)

    semanal = kpi_patron_semanal_cali(cali)
    assert len(semanal) == 7 and semanal["casos_total"].sum() == int(cali["fecha_valida"].sum())

    bog_sesgo = kpi_bogota_engativa_vs_resto(bog)
    assert not bog_sesgo.empty and set(bog_sesgo["dimension"]) == {"diagnostico", "procedencia", "especie", "sexo"}


def test_airflow_etl_fallo_controlado_p4(monkeypatch):
    from etl.extract_api import run
    monkeypatch.setenv("FORZAR_FALLO_API", "1")
    with pytest.raises(ConnectionError, match="Fallo simulado en extract_api_bronze"):
        run()


def test_airflow_dag_import_y_estructura():
    from dags.etl_bienestar_animal_hourly import PROJECT_DIR, etl_bienestar_animal_hourly
    assert (PROJECT_DIR / "config" / "config.yaml").exists()
    assert callable(etl_bienestar_animal_hourly)


def test_api_endpoints():
    from api.main import (
        consultar_adopciones_en_gold,
        consultar_gold_completo,
        consultar_gold_por_ciudad,
        consultar_kpi,
        consultar_solo_data,
        consultar_validaciones_calidad,
        health,
        inicio,
        listar_animales_en_adopcion,
        listar_kpis,
        portal_ciudadano_gold_y_adopcion,
    )
    assert inicio()["gold"] == "/gold"
    assert inicio()["portal_ciudadano_y_adopcion"] == "/portal"
    est = health()
    assert est["api"] == "OK" and est["Archivo"] is True and est["kpis_disponibles"] == 13

    gold_resp = consultar_gold_completo(ciudad=None, tipo_zona=None, categoria=None, es_critico=None)
    assert gold_resp["total_registros"] == 404
    assert len(consultar_solo_data()["Data"]) == 404

    cali_resp = consultar_gold_por_ciudad("Cali")
    assert cali_resp["total_casos"] == 17642

    kpis_resp = listar_kpis()
    assert kpis_resp["total_kpis"] == 13 and all(k["existe"] for k in kpis_resp["kpis"])

    prio_resp = consultar_kpi("kpi_priorizacion_territorial")
    assert prio_resp["total_registros"] == 37
    assert prio_resp["Data"][0]["zona"] == "Comuna 20"

    cal_resp = consultar_validaciones_calidad()
    assert cal_resp["total_reglas"] == 14

    adop_gold = consultar_adopciones_en_gold()
    assert adop_gold["total_casos_adopcion_historico_gold"] == 61

    animales = listar_animales_en_adopcion(ciudad=None, especie=None, solo_disponibles=False)
    assert animales["total_animales"] >= 9

    html_portal = portal_ciudadano_gold_y_adopcion()
    assert "Portal Ciudadano" in html_portal




