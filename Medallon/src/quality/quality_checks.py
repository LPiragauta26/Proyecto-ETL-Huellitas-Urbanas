"""Validacion de calidad (OKR 3): metricas antes/despues y reglas de aceptacion."""
import pandas as pd

from src.utils.helpers import get_logger, normalizar_texto
from src.transform.clean_cali import NULOS, SIN_DATO, estandarizar_comuna

log = get_logger()


def _pct(parte, total) -> float:
    return round(100 * parte / total, 2) if total else 0.0


def metricas_calidad_cali(bronze: pd.DataFrame, silver: pd.DataFrame, cfg_quality: dict) -> pd.DataFrame:
    n_b, n_s = len(bronze), len(silver)
    # En bronze se cuenta sin comuna tanto vacíos/N/D como valores inválidos (ej. "Urgencias" en Comuna)
    b_sin_comuna = int(bronze["Comuna"].map(lambda v: estandarizar_comuna(v)[0] == SIN_DATO).sum())
    b_sin_barrio = int(bronze["Barrio"].map(normalizar_texto).isin(NULOS).sum())
    s_sin_comuna = int((silver["zona"] == SIN_DATO).sum())
    s_sin_barrio = int((silver["barrio"] == SIN_DATO).sum())
    # Registros identicos en todos los campos salvo el id: informativo, NO se eliminan
    identicos = bronze.drop(columns=bronze.columns[0]).duplicated().sum()
    filas = [
        ("registros_totales", n_b, n_s, ""),
        ("registros_duplicados_por_id", int(bronze.iloc[:, 0].duplicated().sum()), int(silver["id"].duplicated().sum()), "se eliminan"),
        ("registros_identicos_sin_id", int(identicos), int(identicos), "informativo: pueden ser solicitudes distintas; no se eliminan"),
        ("pct_registros_con_comuna", _pct(n_b - b_sin_comuna, n_b), _pct(n_s - s_sin_comuna, n_s), f"meta Avance 1: {cfg_quality['meta_comuna_pct']}%"),
        ("pct_registros_sin_comuna", _pct(b_sin_comuna, n_b), _pct(s_sin_comuna, n_s), ""),
        ("pct_registros_con_barrio", _pct(n_b - b_sin_barrio, n_b), _pct(n_s - s_sin_barrio, n_s), f"meta Avance 1: {cfg_quality['meta_barrio_pct']}%"),
        ("pct_registros_sin_barrio", _pct(b_sin_barrio, n_b), _pct(s_sin_barrio, n_s), ""),
        ("valores_distintos_comuna", int(bronze["Comuna"].nunique()), int(silver["zona"].nunique()), "catalogo unico de comunas/corregimientos"),
        ("valores_distintos_clase_peticion", int(bronze["Clase de petición"].nunique()), int(silver["clase"].nunique()), ""),
        ("registros_con_error_de_fecha", int((~silver["fecha_valida"]).sum() + silver["fecha_corregida"].sum()),
         int((~silver["fecha_valida"]).sum()), "antes: invalidas + corregibles; despues: invalidas (fecha vacia)"),
        ("pct_registros_con_error_de_fecha", _pct((~silver["fecha_valida"]).sum() + silver["fecha_corregida"].sum(), n_s),
         _pct((~silver["fecha_valida"]).sum(), n_s), ""),
        ("fechas_corregidas_anio_0225", 0, int(silver["fecha_corregida"].sum()), "0225 -> 2025"),
        ("comunas_recuperadas_desde_barrio", 0, int(silver["comuna_imputada"].sum()), "inferencia barrio -> comuna"),
        ("registros_clase_sin_clasificar", int(bronze["Clase de petición"].map(normalizar_texto).isin(NULOS | {"sin respuesta"}).sum()),
         int((silver["clase"] == "Sin clasificar").sum()), ""),
    ]
    return pd.DataFrame(filas, columns=["indicador", "antes_bronze", "despues_silver", "nota"])


def validar_pipeline(
    bronze,
    silver_cali,
    silver_bogota,
    cfg_quality: dict | None = None,
    gold_final: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Reglas de aceptacion. Devuelve tabla con estado OK / ADVERTENCIA / FALLA."""
    r = []
    f_min = pd.Timestamp(cfg_quality["fecha_min"]) if cfg_quality and "fecha_min" in cfg_quality else pd.Timestamp("2024-01-01")
    if cfg_quality and "fecha_max" in cfg_quality and cfg_quality["fecha_max"] != "hoy":
        f_max = pd.Timestamp(cfg_quality["fecha_max"])
    else:
        f_max = pd.Timestamp.today().normalize()

    def regla(nombre, ok, detalle="", severidad="FALLA"):
        r.append((nombre, "OK" if ok else severidad, detalle))

    regla("Cali: no se pierden registros bronze->silver", len(bronze) == len(silver_cali), f"{len(bronze)} -> {len(silver_cali)}")
    regla("Cali: id unico", silver_cali["id"].is_unique)
    regla("Cali: clase sin valores fuera del catalogo", silver_cali["clase"].notna().all())
    regla("Cali: fechas validas dentro del rango", bool(silver_cali.loc[silver_cali["fecha_valida"], "fecha"].between(f_min, f_max).all()))
    pct_fecha = 100 * (~silver_cali["fecha_valida"]).mean()
    regla("Cali: fechas invalidas < 1%", pct_fecha < 1, f"{pct_fecha:.3f}%", "ADVERTENCIA")
    regla("Bogota: 20 localidades", len(silver_bogota) == 20, f"{len(silver_bogota)} localidades")
    regla("Bogota: sin nulos en atenciones", silver_bogota["atenciones"].notna().all())
    for col, nombre in [("suma_especie", "especie"), ("suma_sexo", "sexo")]:
        regla(f"Bogota: {nombre} suma atenciones", bool((silver_bogota[col] == silver_bogota["atenciones"]).all()))
    for col, nombre in [("suma_dx", "diagnosticos"), ("suma_proc", "procedencia")]:
        dif = silver_bogota[silver_bogota[col] != silver_bogota["atenciones"]]
        regla(f"Bogota: {nombre} suman atenciones", dif.empty,
              "" if dif.empty else "diferencias en " + ", ".join(f"{l} ({int(d):+d})" for l, d in zip(dif["localidad"], dif[col] - dif["atenciones"])),
              "ADVERTENCIA")
    if gold_final is not None:
        duplicados_gold = int(gold_final.duplicated(subset=["ciudad", "zona", "categoria", "periodo"]).sum())
        casos_cali_gold = int(gold_final.loc[gold_final["ciudad"] == "Cali", "casos"].sum())
        casos_bog_gold = int(gold_final.loc[gold_final["ciudad"] == "Bogotá", "casos"].sum())
        regla("Gold: sin duplicados en llave (ciudad, zona, categoria, periodo)", duplicados_gold == 0, f"duplicados={duplicados_gold}")
        regla("Gold: casos Cali cuadran con Silver", casos_cali_gold == len(silver_cali), f"{casos_cali_gold} == {len(silver_cali)}")
        regla("Gold: atenciones Bogotá cuadran con Silver", casos_bog_gold == int(silver_bogota["atenciones"].sum()), f"{casos_bog_gold} == {int(silver_bogota['atenciones'].sum())}")
    out = pd.DataFrame(r, columns=["regla", "estado", "detalle"])
    for _, f in out.iterrows():
        nivel = log.info if f["estado"] == "OK" else log.warning
        nivel("CALIDAD [%s] %s %s", f["estado"], f["regla"], f["detalle"])
    return out
