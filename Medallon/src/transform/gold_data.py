"""Capa GOLD: integra Cali + Bogota (JOIN) y calcula los KPIs de negocio del Avance 1."""
import numpy as np
import pandas as pd

from src.transform.clean_cali import SIN_DATO, estandarizar_comuna
from src.utils.helpers import get_logger, ruta

log = get_logger()

SIN_FECHA = "Sin fecha válida"


# ---------------------------------------------------------------- dimension / JOIN
def construir_dim_categoria(silver_cali: pd.DataFrame) -> pd.DataFrame:
    """Catalogo que homologa las categorias de cada ciudad a una 'categoria_comparable'.
    Es la llave del JOIN entre las dos fuentes: Cali no tiene detalle clinico y Bogota solo
    publica atenciones de URGENCIA, por lo que la unica categoria realmente comparable es Urgencias."""
    filas = [("Cali", c, c) for c in sorted(silver_cali["clase"].unique())]
    filas.append(("Bogotá", "Atenciones de urgencia", "Urgencias"))
    dim = pd.DataFrame(filas, columns=["ciudad", "categoria_origen", "categoria_comparable"])
    dim["comparable"] = dim["categoria_comparable"].eq("Urgencias")
    return dim


def _cali_largo(silver_cali: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    base = silver_cali.merge(
        dim[dim["ciudad"] == "Cali"], left_on="clase", right_on="categoria_origen", how="left", validate="m:1"
    )
    base["periodo"] = base["anio"].astype("string").fillna(SIN_FECHA)
    g = (base.groupby(["zona", "tipo_zona", "categoria_comparable", "periodo", "comparable"], dropna=False)
             .size().rename("casos").reset_index())
    g.insert(0, "ciudad", "Cali")
    g.insert(1, "nivel_geografico", np.where(g["tipo_zona"].eq("urbana"), "comuna", "otra zona"))
    return g.rename(columns={"categoria_comparable": "categoria"})


def _bogota_largo(silver_bogota: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    d = dim[dim["ciudad"] == "Bogotá"].iloc[0]
    g = pd.DataFrame({
        "ciudad": "Bogotá", "nivel_geografico": "localidad",
        "zona": silver_bogota["localidad"], "tipo_zona": "localidad",
        "categoria": d["categoria_comparable"], "periodo": "2025 (corte 30/06)",
        "comparable": bool(d["comparable"]), "casos": silver_bogota["atenciones"],
    })
    return g


def integrar_gold_final(silver_cali: pd.DataFrame, silver_bogota: pd.DataFrame) -> pd.DataFrame:
    dim = construir_dim_categoria(silver_cali)
    gold = pd.concat([_cali_largo(silver_cali, dim), _bogota_largo(silver_bogota, dim)], ignore_index=True)
    gold["pct_casos_ciudad"] = (100 * gold["casos"] / gold.groupby("ciudad")["casos"].transform("sum")).round(3)
    cols = ["ciudad", "nivel_geografico", "zona", "tipo_zona", "categoria", "periodo", "casos", "pct_casos_ciudad", "comparable"]
    gold = gold[cols].sort_values(["ciudad", "zona", "categoria", "periodo"]).reset_index(drop=True)
    # Control: lo que entra == lo que sale
    assert gold.loc[gold["ciudad"] == "Cali", "casos"].sum() == len(silver_cali), "Gold Cali no cuadra con silver"
    assert gold.loc[gold["ciudad"] == "Bogotá", "casos"].sum() == silver_bogota["atenciones"].sum(), "Gold Bogota no cuadra con silver"
    log.info("GOLD final: %s filas (Cali %s casos | Bogota %s atenciones)", len(gold),
             int(gold.loc[gold.ciudad == "Cali", "casos"].sum()), int(gold.loc[gold.ciudad == "Bogotá", "casos"].sum()))
    return gold


# ---------------------------------------------------------------- poblacion (opcional)
def cargar_poblacion(path: str):
    """Lee poblacion por comuna. Acepta columnas (zona | comuna_num | comuna) + poblacion.
    Si el archivo no existe o no tiene valores diligenciados devuelve None (y se registra una advertencia)."""
    archivo = ruta(path)
    if not archivo.exists():
        log.warning("Sin archivo de poblacion (%s): tasa por 10.000 hab. y parte del indice quedan vacios", archivo.name)
        return None
    p = pd.read_csv(archivo, encoding="utf-8-sig")
    p.columns = [c.strip().lower() for c in p.columns]
    if "zona" in p:
        p["zona"] = p["zona"].map(lambda v: estandarizar_comuna(v)[0])
    elif "comuna_num" in p:
        p["zona"] = p["comuna_num"].map(lambda v: estandarizar_comuna(f"Comuna {v}")[0])
    elif "comuna" in p:
        p["zona"] = p["comuna"].map(lambda v: estandarizar_comuna(v)[0])
    else:
        log.warning("Archivo de poblacion sin columna zona/comuna_num/comuna: se ignora")
        return None
    p["poblacion"] = pd.to_numeric(p["poblacion"], errors="coerce")
    p = p.dropna(subset=["poblacion"])
    p = p[p["zona"] != SIN_DATO]
    if p.empty:
        log.warning("El archivo %s no tiene poblacion diligenciada: se ignora (tasa por 10.000 hab. queda vacia)", archivo.name)
        return None
    return p.groupby("zona", as_index=False)["poblacion"].sum()

def poblacion_desde_api(df_api: pd.DataFrame, anio: str):
    """Convierte la respuesta de la API (una fila por comuna o corregimiento, una columna por año)
    a la tabla (zona, poblacion) que usan los KPIs. Devuelve None si no se puede interpretar."""
    anio = str(anio)
    # El portal publica el nombre de la columna con la tilde dañada ("Descripci√≥n"): se busca por prefijo
    col_desc = next((c for c in df_api.columns if str(c).strip().lower().startswith("descripci")), None)
    if col_desc is None or anio not in df_api.columns:
        log.warning("API de población: columnas recibidas %s", list(df_api.columns))
        return None
    p = pd.DataFrame({
        "zona_original": df_api[col_desc].astype(str).str.strip(),
        "poblacion": pd.to_numeric(df_api[anio], errors="coerce"),
    })
    # Se omiten los totales ("TOTAL CALI", "Total Cabecera", ...)
    p = p[~p["zona_original"].str.lower().str.startswith("total")]

    def a_zona(v):
        z = estandarizar_comuna(v)[0]
        return z if z != SIN_DATO else estandarizar_comuna(f"Comuna {v}")[0]

    p["zona"] = p["zona_original"].map(a_zona)
    descartadas = p[p["zona"].eq(SIN_DATO) | p["poblacion"].isna()]
    if len(descartadas):
        log.info("API de población: %s filas descartadas (no son comuna o corregimiento): %s",
                 len(descartadas), descartadas["zona_original"].tolist()[:8])
    p = p[~p["zona"].eq(SIN_DATO)].dropna(subset=["poblacion"])
    if p.empty:
        log.warning("API de población: no quedó ninguna zona con población")
        return None
    log.info("API de población: %s zonas con población (año %s)", p["zona"].nunique(), anio)
    return p.groupby("zona", as_index=False)["poblacion"].sum()

# ---------------------------------------------------------------- KPIs
def kpi_casos_por_zona(silver_cali: pd.DataFrame, poblacion) -> pd.DataFrame:
    piv = silver_cali.pivot_table(index=["zona", "tipo_zona"], columns="clase", values="id", aggfunc="count", fill_value=0)
    piv.columns = [str(c) for c in piv.columns]
    piv = piv.reset_index()
    piv["casos_total"] = piv.drop(columns=["zona", "tipo_zona"]).sum(axis=1)
    mapa_cols = {
        "Denuncia": "denuncias",
        "Urgencias": "urgencias",
        "Esterilizaciones": "esterilizaciones",
        "Adopciones": "adopciones",
        "PQR": "pqr",
        "Cita médica": "citas_medicas",
        "Solicitud de información general": "solicitudes_info",
        "Sin clasificar": "sin_clasificar",
    }
    for c_orig in mapa_cols:
        if c_orig not in piv:
            piv[c_orig] = 0
    piv = piv.rename(columns=mapa_cols)
    piv["poblacion"] = np.nan
    if poblacion is not None:
        piv["poblacion"] = piv["zona"].map(poblacion.set_index("zona")["poblacion"])
    piv["casos_por_10k_hab"] = (piv["casos_total"] / piv["poblacion"] * 10000).round(2)
    ident = piv["zona"].ne(SIN_DATO)
    piv["ranking_casos"] = piv["casos_total"].where(ident).rank(ascending=False, method="min")
    cols = ["zona", "tipo_zona", "casos_total", "denuncias", "urgencias", "esterilizaciones", "adopciones",
            "pqr", "citas_medicas", "solicitudes_info", "sin_clasificar", "poblacion", "casos_por_10k_hab", "ranking_casos"]
    return piv[cols].sort_values("casos_total", ascending=False).reset_index(drop=True)


def kpi_evolucion_mensual(silver_cali: pd.DataFrame) -> pd.DataFrame:
    v = silver_cali[silver_cali["fecha_valida"]].copy()
    v["periodo_mes"] = v["fecha"].dt.to_period("M")
    piv = v.pivot_table(index="periodo_mes", columns="clase", values="id", aggfunc="count", fill_value=0)
    rango = pd.period_range(piv.index.min(), piv.index.max(), freq="M")
    con_datos = pd.Series(rango.isin(piv.index), index=rango)
    piv = piv.reindex(rango, fill_value=0)
    piv.columns = [str(c) for c in piv.columns]
    out = piv.copy()
    out["casos_total"] = piv.sum(axis=1)
    out["mes_con_registros"] = con_datos
    var = out["casos_total"].pct_change() * 100
    # La variacion solo es confiable entre meses consecutivos con registros
    previo_ok = out["mes_con_registros"].shift(1, fill_value=False)
    out["variacion_pct_mensual"] = var.where(out["mes_con_registros"] & previo_ok).round(2)
    out.index = out.index.astype(str)
    return out.rename_axis("anio_mes").reset_index()


def _minmax_por_grupo(serie: pd.Series, grupo: pd.Series) -> pd.Series:
    """Normaliza Min-Max dentro de cada tipo_zona (urbana vs rural) para que tasas extremas en
    corregimientos pequeños (ej. Villacarmelo con 818 hab.) no aplasten la escala de las 22 comunas."""
    res = pd.Series(0.0, index=serie.index)
    for _, idx in serie.groupby(grupo).groups.items():
        sub = serie.loc[idx]
        rango = sub.max() - sub.min()
        if rango > 0:
            res.loc[idx] = (sub - sub.min()) / rango
    return res


def kpi_priorizacion(kpi_zona: pd.DataFrame, pesos: dict) -> pd.DataFrame:
    """Indice de priorizacion territorial (0-100). Min-max por componente; tasa_10k se normaliza
    dentro de cada tipo_zona (urbana/rural) para evitar sesgo por tamaño poblacional de corregimientos."""
    d = kpi_zona[kpi_zona["tipo_zona"].isin(["urbana", "rural"]) & ~kpi_zona["zona"].str.contains("sin especificar")].copy()
    d["casos_criticos"] = d["denuncias"] + d["urgencias"]
    comp = {"casos_total": d["casos_total"], "casos_criticos": d["casos_criticos"], "tasa_10k": d["casos_por_10k_hab"]}
    activos = {k: s for k, s in comp.items() if s.notna().all() and s.max() > s.min()}
    peso_total = sum(pesos[k] for k in activos)
    d["indice_priorizacion"] = 0.0
    for k, s in activos.items():
        if k == "tasa_10k" and d["tipo_zona"].nunique() > 1:
            norm = _minmax_por_grupo(s, d["tipo_zona"])
        else:
            norm = (s - s.min()) / (s.max() - s.min())
        d["indice_priorizacion"] += norm * (pesos[k] / peso_total)
    d["indice_priorizacion"] = (100 * d["indice_priorizacion"]).round(1)
    d["componentes_usados"] = ", ".join(activos)
    d["ranking_prioridad"] = d["indice_priorizacion"].rank(ascending=False, method="min").astype(int)
    d["ranking_en_tipo_zona"] = d.groupby("tipo_zona")["indice_priorizacion"].rank(ascending=False, method="min").astype(int)
    cols = ["ranking_prioridad", "ranking_en_tipo_zona", "zona", "tipo_zona", "casos_total", "casos_criticos",
            "denuncias", "urgencias", "esterilizaciones", "adopciones", "casos_por_10k_hab",
            "indice_priorizacion", "componentes_usados"]
    return d[cols].sort_values(["ranking_prioridad", "casos_total"], ascending=[True, False]).reset_index(drop=True)


def kpi_comparativo_ciudades(silver_cali: pd.DataFrame, silver_bogota: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    """JOIN (outer) de ambas ciudades por categoria_comparable."""
    c = silver_cali.merge(dim[dim["ciudad"] == "Cali"], left_on="clase", right_on="categoria_origen", how="left")
    cali = c.groupby("categoria_comparable").agg(
        casos_cali_total=("id", "size"),
        casos_cali_hasta_corte_bogota=("fecha", lambda s: int((s <= pd.Timestamp("2025-06-30")).sum())),
    ).reset_index()
    bog = dim[dim["ciudad"] == "Bogotá"][["categoria_comparable"]].copy()
    bog["casos_bogota_corte_2025_06_30"] = int(silver_bogota["atenciones"].sum())
    out = cali.merge(bog, on="categoria_comparable", how="outer")
    out = out.merge(dim.groupby("categoria_comparable")["comparable"].max().reset_index(), on="categoria_comparable", how="left")
    out["nota"] = np.where(out["comparable"], "Unica categoria comparable. Periodos distintos: Cali 2024-2025 (registro individual) vs Bogota acumulado a 30/06/2025 (agregado por localidad)", "Solo Cali")
    return out.sort_values("comparable", ascending=False).reset_index(drop=True)


def kpi_urgencias_por_zona(silver_cali: pd.DataFrame, silver_bogota: pd.DataFrame) -> pd.DataFrame:
    cali = silver_cali[silver_cali["clase"] == "Urgencias"].groupby("zona").size().rename("urgencias").reset_index()
    cali.insert(0, "ciudad", "Cali")
    bog = silver_bogota[["localidad", "atenciones", "proc_uca"]].rename(columns={"localidad": "zona", "atenciones": "urgencias"})
    bog.insert(0, "ciudad", "Bogotá")
    out = pd.concat([cali, bog], ignore_index=True)
    out["pct_ciudad"] = (100 * out["urgencias"] / out.groupby("ciudad")["urgencias"].transform("sum")).round(2)
    pct_uca = (100 * out["proc_uca"] / out["urgencias"].where(out["urgencias"] > 0)).round(1)
    out["pct_atendidas_en_uca"] = np.where(out["ciudad"].eq("Bogotá"), pct_uca.fillna(0.0), np.nan)
    return out.drop(columns="proc_uca").sort_values(["ciudad", "urgencias"], ascending=[True, False]).reset_index(drop=True)


def kpi_bogota_detalle(silver_bogota: pd.DataFrame) -> pd.DataFrame:
    total = int(silver_bogota["atenciones"].sum())
    grupos = {"especie": "esp_", "sexo": "sexo_", "diagnostico": "dx_", "procedencia": "proc_"}
    filas = []
    for dim, pref in grupos.items():
        for c in [c for c in silver_bogota.columns if c.startswith(pref)]:
            casos = int(silver_bogota[c].sum())
            filas.append((dim, c[len(pref):], casos, round(100 * casos / total, 2)))
    out = pd.DataFrame(filas, columns=["dimension", "categoria", "casos", "pct_sobre_atenciones"])
    return out.sort_values(["dimension", "casos"], ascending=[True, False]).reset_index(drop=True)


# ---------------------------------------------------------------- Nuevos KPIs para Preguntas de Negocio
def kpi_cambio_anual_servicios(silver_cali: pd.DataFrame) -> pd.DataFrame:
    """Pregunta de negocio 1: ¿Cómo cambió el portafolio de demanda y servicios entre 2024 y 2025 en Cali?"""
    v = silver_cali[silver_cali["anio"].isin([2024, 2025])]
    piv = v.pivot_table(index="clase", columns="anio", values="id", aggfunc="count", fill_value=0)
    for a in (2024, 2025):
        if a not in piv:
            piv[a] = 0
    out = pd.DataFrame({
        "clase": piv.index,
        "casos_2024": piv[2024].values,
        "casos_2025": piv[2025].values,
    })
    tot_24 = max(int(out["casos_2024"].sum()), 1)
    tot_25 = max(int(out["casos_2025"].sum()), 1)
    out["pct_mix_2024"] = (100 * out["casos_2024"] / tot_24).round(2)
    out["pct_mix_2025"] = (100 * out["casos_2025"] / tot_25).round(2)
    out["cambio_puntos_mix"] = (out["pct_mix_2025"] - out["pct_mix_2024"]).round(2)
    out["variacion_abs"] = out["casos_2025"] - out["casos_2024"]
    out["variacion_pct"] = ((out["variacion_abs"] / out["casos_2024"].where(out["casos_2024"] > 0)) * 100).round(1)
    return out.sort_values("casos_2025", ascending=False).reset_index(drop=True)


def kpi_brecha_prevencion_zona(kpi_zona: pd.DataFrame) -> pd.DataFrame:
    """Pregunta de negocio 2: ¿En qué comunas/corregimientos hay déficit de prevención (esterilizaciones)
    frente a los casos críticos (denuncias + urgencias) y cuál es la vocación de demanda territorial?"""
    d = kpi_zona[kpi_zona["tipo_zona"].isin(["urbana", "rural"]) & ~kpi_zona["zona"].str.contains("sin especificar")].copy()
    d["casos_criticos"] = d["denuncias"] + d["urgencias"]
    d["pct_denuncias"] = (100 * d["denuncias"] / d["casos_total"].where(d["casos_total"] > 0)).round(1)
    d["pct_urgencias"] = (100 * d["urgencias"] / d["casos_total"].where(d["casos_total"] > 0)).round(1)
    d["pct_esterilizaciones"] = (100 * d["esterilizaciones"] / d["casos_total"].where(d["casos_total"] > 0)).round(1)
    d["denuncias_por_10k_hab"] = (d["denuncias"] / d["poblacion"] * 10000).round(2)
    d["urgencias_por_10k_hab"] = (d["urgencias"] / d["poblacion"] * 10000).round(2)
    d["ratio_prevencion_criticos"] = (d["esterilizaciones"] / d["casos_criticos"].where(d["casos_criticos"] > 0)).round(2)
    d["perfil_demanda"] = np.select(
        [
            (d["pct_denuncias"] >= 18.0).fillna(False).to_numpy(dtype=bool),
            (d["ratio_prevencion_criticos"] < 0.75).fillna(False).to_numpy(dtype=bool),
            (d["ratio_prevencion_criticos"] >= 1.25).fillna(False).to_numpy(dtype=bool),
        ],
        [
            "Foco en denuncias de maltrato/tenencia (baja esterilización)",
            "Déficit preventivo frente a casos críticos",
            "Alta cobertura relativa de esterilización",
        ],
        default="Balance intermedio prevención/criticidad",
    )
    cols = [
        "zona", "tipo_zona", "casos_total", "casos_criticos", "denuncias", "urgencias", "esterilizaciones",
        "citas_medicas", "pct_denuncias", "pct_urgencias", "pct_esterilizaciones",
        "denuncias_por_10k_hab", "urgencias_por_10k_hab", "ratio_prevencion_criticos", "perfil_demanda",
    ]
    return d[cols].sort_values(["casos_criticos", "denuncias"], ascending=[False, False]).reset_index(drop=True)


def kpi_top_barrios_cali(silver_cali: pd.DataFrame, top_n: int = 25) -> pd.DataFrame:
    """Pregunta de negocio 3: ¿Cuáles son los barrios críticos ('hotspots') que concentran más solicitudes
    y más emergencias/denuncias para micro-focalizar brigadas puerta a puerta?"""
    con_barrio = silver_cali[silver_cali["barrio"] != SIN_DATO]
    total_con_barrio = max(len(con_barrio), 1)
    g = con_barrio.groupby(["zona", "tipo_zona", "barrio"]).agg(
        casos_total=("id", "count"),
        denuncias=("clase", lambda s: int((s == "Denuncia").sum())),
        urgencias=("clase", lambda s: int((s == "Urgencias").sum())),
        esterilizaciones=("clase", lambda s: int((s == "Esterilizaciones").sum())),
        citas_medicas=("clase", lambda s: int((s == "Cita médica").sum())),
        pqr=("clase", lambda s: int((s == "PQR").sum())),
    ).reset_index()
    g["casos_criticos"] = g["denuncias"] + g["urgencias"]
    g["pct_sobre_barrios_identificados"] = (100 * g["casos_total"] / total_con_barrio).round(2)
    g = g.sort_values(["casos_criticos", "casos_total"], ascending=[False, False]).head(top_n).reset_index(drop=True)
    g.insert(0, "ranking_critico", range(1, len(g) + 1))
    return g


def kpi_calidad_por_clase(silver_cali: pd.DataFrame) -> pd.DataFrame:
    """Pregunta de negocio 4: ¿En qué canales o tipos de servicio se origina la pérdida de datos geográficos
    (comuna y barrio) que impide cumplir el OKR 3?"""
    total_sin_com = max(int((silver_cali["zona"] == SIN_DATO).sum()), 1)
    total_sin_bar = max(int((silver_cali["barrio"] == SIN_DATO).sum()), 1)
    g = silver_cali.groupby("clase").agg(
        casos_total=("id", "count"),
        sin_comuna=("zona", lambda s: int((s == SIN_DATO).sum())),
        sin_barrio=("barrio", lambda s: int((s == SIN_DATO).sum())),
        comunas_recuperadas=("comuna_imputada", lambda s: int(s.sum())),
    ).reset_index()
    g["pct_sin_comuna_en_clase"] = (100 * g["sin_comuna"] / g["casos_total"]).round(2)
    g["pct_sin_barrio_en_clase"] = (100 * g["sin_barrio"] / g["casos_total"]).round(2)
    g["aporte_al_total_sin_comuna_pct"] = (100 * g["sin_comuna"] / total_sin_com).round(2)
    g["aporte_al_total_sin_barrio_pct"] = (100 * g["sin_barrio"] / total_sin_bar).round(2)
    return g.sort_values("sin_barrio", ascending=False).reset_index(drop=True)


def kpi_patron_semanal_cali(silver_cali: pd.DataFrame) -> pd.DataFrame:
    """Pregunta de negocio 5: ¿Cómo varía la carga operativa según el día de la semana (hábil vs. fin de semana)?"""
    dias_orden = [
        (0, "Lunes", "Hábil"), (1, "Martes", "Hábil"), (2, "Miércoles", "Hábil"),
        (3, "Jueves", "Hábil"), (4, "Viernes", "Hábil"), (5, "Sábado", "Fin de semana"), (6, "Domingo", "Fin de semana"),
    ]
    v = silver_cali[silver_cali["fecha_valida"]].copy()
    v["dow"] = v["fecha"].dt.dayofweek
    piv = v.pivot_table(index="dow", columns="clase", values="id", aggfunc="count", fill_value=0)
    filas = []
    tot_general = max(len(v), 1)
    for dow, nombre, tipo_dia in dias_orden:
        row = piv.loc[dow] if dow in piv.index else pd.Series(dtype=int)
        tot = int(row.sum()) if len(row) else 0
        urg = int(row.get("Urgencias", 0))
        den = int(row.get("Denuncia", 0))
        est = int(row.get("Esterilizaciones", 0))
        cit = int(row.get("Cita médica", 0))
        pqr = int(row.get("PQR", 0))
        filas.append({
            "orden_dia": dow + 1,
            "dia_semana": nombre,
            "tipo_dia": tipo_dia,
            "casos_total": tot,
            "pct_total_semanal": round(100 * tot / tot_general, 2),
            "citas_medicas": cit,
            "pqr": pqr,
            "esterilizaciones": est,
            "denuncias": den,
            "urgencias": urg,
            "pct_esterilizaciones_en_dia": round(100 * est / tot, 2) if tot else 0.0,
        })
    return pd.DataFrame(filas)


def kpi_bogota_engativa_vs_resto(silver_bogota: pd.DataFrame) -> pd.DataFrame:
    """Pregunta de negocio 6: Al aislar el sesgo de infraestructura de Engativá (sede UCA),
    ¿cuál es el verdadero perfil clínico y canal de atención en las otras 19 localidades de Bogotá?"""
    eng = silver_bogota[silver_bogota["localidad"] == "Engativá"]
    res = silver_bogota[silver_bogota["localidad"] != "Engativá"]
    tot_eng = max(int(eng["atenciones"].sum()), 1)
    tot_res = max(int(res["atenciones"].sum()), 1)
    grupos = {"diagnostico": "dx_", "procedencia": "proc_", "especie": "esp_", "sexo": "sexo_"}
    filas = []
    for dim, pref in grupos.items():
        for c in [col for col in silver_bogota.columns if col.startswith(pref)]:
            c_eng = int(eng[c].sum())
            c_res = int(res[c].sum())
            if c_eng == 0 and c_res == 0:
                continue
            p_eng = round(100 * c_eng / tot_eng, 2)
            p_res = round(100 * c_res / tot_res, 2)
            filas.append({
                "dimension": dim,
                "categoria": c[len(pref):],
                "casos_engativa_uca": c_eng,
                "pct_engativa_uca": p_eng,
                "casos_resto_19_localidades": c_res,
                "pct_resto_19_localidades": p_res,
                "diferencia_puntos_pct": round(p_res - p_eng, 2),
            })
    out = pd.DataFrame(filas)
    return out.sort_values(["dimension", "casos_resto_19_localidades"], ascending=[True, False]).reset_index(drop=True)
