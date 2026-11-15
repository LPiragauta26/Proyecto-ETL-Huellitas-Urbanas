"""Transformacion BRONZE -> SILVER para Cali (CBA / Uaepa)."""
import re

import pandas as pd

from src.utils.helpers import get_logger, normalizar_texto

log = get_logger()

SIN_DATO = "Sin dato"

CORREGIMIENTOS = {
    "la buitrera": "La Buitrera",
    "montebello": "Montebello",
    "montebelllo": "Montebello",          # error de digitacion (3 L)
    "villacarmelo": "Villacarmelo",
    "pance": "Pance",
    "felidia": "Felidia",
    "los andes": "Los Andes",
    "navarro": "Navarro",
    "el hormiguero": "El Hormiguero",
    "golondrinas": "Las Golondrinas",
    "las golondrinas": "Las Golondrinas",
    "la paz": "La Paz",
    "la leonera": "La Leonera",
    "pichinde": "Pichinde",
    "pichinche": "Pichinde",              # error de digitacion
    "la elvira": "La Elvira",
    "la castilla": "La Castilla",
    "el saladito": "El Saladito",
}

CLASES = {
    "pqr": "PQR",
    "cita medica": "Cita médica",
    "esterilizaciones": "Esterilizaciones",
    "denuncia": "Denuncia",
    "urgencias": "Urgencias",
    "adopciones": "Adopciones",
    "solicitud de informacion general": "Solicitud de información general",
}
SIN_CLASIFICAR = "Sin clasificar"
NULOS = {"", "n/d", "nd", "n.d.", "na", "nan", "none", "null", "sin dato"}


def estandarizar_comuna(valor):
    """Devuelve (zona estandar, tipo_zona). Catalogo: Comuna 1..22 + corregimientos + categorias especiales."""
    t = normalizar_texto(valor)
    if t in NULOS:
        return SIN_DATO, "sin_dato"
    m = re.fullmatch(r"comuna\s*(\d{1,2})", t)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 22:
            return f"Comuna {n}", "urbana"
        return SIN_DATO, "sin_dato"
    if t in ("fuera de jurisdiccion", "municipio"):
        return "Fuera de jurisdicción", "fuera_jurisdiccion"
    if t == "area de expansion urbana":
        return "Área de expansión urbana", "expansion_urbana"
    if t == "zona rural":
        return "Zona rural (sin especificar)", "rural"
    if t == "corregimiento":
        return "Corregimiento (sin especificar)", "rural"
    nombre = re.sub(r"^corregimiento(\s+de(l)?)?\s+", "", t)
    if nombre in CORREGIMIENTOS:
        return CORREGIMIENTOS[nombre], "rural"
    return SIN_DATO, "sin_dato"  # valor no reconocido (ej. "Urgencias" digitado en Comuna)


def estandarizar_clase(valor) -> str:
    return CLASES.get(normalizar_texto(valor), SIN_CLASIFICAR)


def parsear_fecha(serie: pd.Series, corregir_225: bool, fecha_min, fecha_max):
    """Parsea fechas ISO. Devuelve (fecha, fecha_valida, fecha_corregida)."""
    texto = serie.astype(str).str.strip()
    corregida = pd.Series(False, index=serie.index)
    if corregir_225:
        mask = texto.str.startswith("0225-")
        texto = texto.where(~mask, "2025-" + texto.str[5:])
        corregida = mask
    fecha = pd.to_datetime(texto, errors="coerce")
    valida = fecha.notna() & (fecha >= pd.Timestamp(fecha_min)) & (fecha <= pd.Timestamp(fecha_max))
    fecha = fecha.where(valida)  # fuera de rango -> NaT (el registro NO se elimina)
    return fecha, valida, corregida


def estandarizar_barrio(serie: pd.Series) -> pd.DataFrame:
    """Devuelve barrio (grafia mas frecuente por clave normalizada) y barrio_clave."""
    clave = serie.map(normalizar_texto)
    limpio = serie.astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    es_nulo = clave.isin(NULOS)
    df = pd.DataFrame({"clave": clave, "original": limpio})
    df = df[~es_nulo]
    moda = df.groupby("clave")["original"].agg(lambda s: s.value_counts().index[0])
    barrio = clave.map(moda).where(~es_nulo, SIN_DATO).fillna(SIN_DATO)
    return pd.DataFrame({"barrio": barrio, "barrio_clave": clave.where(~es_nulo, "")})


def inferir_comuna_desde_barrio(df: pd.DataFrame, min_obs: int, min_acuerdo: float) -> pd.DataFrame:
    """Para registros SIN comuna pero CON barrio, asigna la comuna si ese barrio apunta
    (en los demas registros) a una sola comuna con alto acuerdo. Se marca comuna_imputada."""
    conocidos = df[(df["zona"] != SIN_DATO) & (df["barrio_clave"] != "") & (df["tipo_zona"].isin(["urbana", "rural"]))]
    if conocidos.empty:
        df["comuna_imputada"] = False
        return df
    conteo = conocidos.groupby(["barrio_clave", "zona"]).size().rename("n").reset_index()
    tot = conteo.groupby("barrio_clave")["n"].transform("sum")
    conteo["acuerdo"] = conteo["n"] / tot
    mejor = conteo.sort_values(["barrio_clave", "n"], ascending=[True, False]).drop_duplicates("barrio_clave")
    mejor = mejor.assign(total=mejor["barrio_clave"].map(conteo.groupby("barrio_clave")["n"].sum()))
    mejor = mejor[(mejor["total"] >= min_obs) & (mejor["acuerdo"] >= min_acuerdo)]
    mapa = mejor.set_index("barrio_clave")["zona"]
    candidatos = (df["zona"] == SIN_DATO) & (df["barrio_clave"] != "")
    nueva = df.loc[candidatos, "barrio_clave"].map(mapa)
    ok = nueva.notna()
    idx = nueva[ok].index
    df.loc[idx, "zona"] = nueva[ok]
    df.loc[idx, "tipo_zona"] = df.loc[idx, "zona"].map(lambda z: "urbana" if z.startswith("Comuna") else "rural")
    df["comuna_imputada"] = False
    df.loc[idx, "comuna_imputada"] = True
    return df


def limpiar_cali(df_bronze: pd.DataFrame, cfg_quality: dict) -> pd.DataFrame:
    df = df_bronze.copy()
    df = df.rename(columns={
        "_id": "id", "Fecha de reporte": "fecha_raw", "Clase de petición": "clase_raw",
        "Comuna": "comuna_raw", "Barrio": "barrio_raw",
    })
    n0 = len(df)

    # 1) Duplicados: se eliminan por id (llave del registro). Los registros identicos en
    #    los demas campos NO se eliminan: pueden ser solicitudes distintas el mismo dia.
    df = df.drop_duplicates(subset="id", keep="first")
    log.info("SILVER Cali: duplicados por id eliminados = %s", n0 - len(df))

    # 2) Tipos y fechas
    df["id"] = pd.to_numeric(df["id"], errors="coerce").astype("Int64")
    fecha_max = pd.Timestamp.today().normalize() if cfg_quality["fecha_max"] == "hoy" else pd.Timestamp(cfg_quality["fecha_max"])
    df["fecha"], df["fecha_valida"], df["fecha_corregida"] = parsear_fecha(
        df["fecha_raw"], cfg_quality["corregir_anio_225"], cfg_quality["fecha_min"], fecha_max
    )
    df["anio"] = df["fecha"].dt.year.astype("Int64")
    df["mes"] = df["fecha"].dt.month.astype("Int64")
    df["anio_mes"] = df["fecha"].dt.strftime("%Y-%m")

    # 3) Categorias
    df["clase"] = df["clase_raw"].map(estandarizar_clase)
    zonas = df["comuna_raw"].map(estandarizar_comuna)
    df["zona"] = zonas.map(lambda x: x[0])
    df["tipo_zona"] = zonas.map(lambda x: x[1])
    barrio = estandarizar_barrio(df["barrio_raw"])
    df["barrio"], df["barrio_clave"] = barrio["barrio"], barrio["barrio_clave"]

    # 4) Nulos geograficos: se intenta recuperar comuna desde el barrio
    df = inferir_comuna_desde_barrio(df, cfg_quality["barrio_min_obs"], cfg_quality["barrio_min_acuerdo"])
    log.info("SILVER Cali: comunas recuperadas desde barrio = %s", int(df["comuna_imputada"].sum()))

    cols = ["id", "fecha", "anio", "mes", "anio_mes", "fecha_valida", "fecha_corregida",
            "clase", "zona", "tipo_zona", "barrio", "comuna_imputada",
            "fecha_raw", "clase_raw", "comuna_raw", "barrio_raw"]
    df = df[cols].reset_index(drop=True)
    log.info("SILVER Cali: %s filas | zonas distintas %s -> %s", len(df), df["comuna_raw"].nunique(), df["zona"].nunique())
    return df
