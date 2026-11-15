"""Transformacion BRONZE -> SILVER para Bogota (IDPYBA, GeoJSON agregado por localidad)."""
import pandas as pd

from src.utils.helpers import get_logger

log = get_logger()

# Codigo de localidad (CodLoc) -> nombre. Validado contra el Avance 1:
# 10 = Engativa (656 atenciones), 19 = Ciudad Bolivar (65), 5 = Usme (33).
LOCALIDADES = {
    1: "Usaquén", 2: "Chapinero", 3: "Santa Fe", 4: "San Cristóbal", 5: "Usme",
    6: "Tunjuelito", 7: "Bosa", 8: "Kennedy", 9: "Fontibón", 10: "Engativá",
    11: "Suba", 12: "Barrios Unidos", 13: "Teusaquillo", 14: "Los Mártires",
    15: "Antonio Nariño", 16: "Puente Aranda", 17: "La Candelaria",
    18: "Rafael Uribe Uribe", 19: "Ciudad Bolívar", 20: "Sumapaz",
}

# Nombres de campo truncados a 10 caracteres (formato shapefile) -> nombre claro
RENOMBRAR = {
    "Fecha": "fecha_corte", "CodLoc": "cod_localidad", "Atenciones": "atenciones",
    "Digestivo": "dx_digestivo", "Infeccioso": "dx_infeccioso", "Intoxicaci": "dx_intoxicacion",
    "Neonatolog": "dx_neonatologico", "Neoplasico": "dx_neoplasico", "Neurologic": "dx_neurologico",
    "Oftalmolog": "dx_oftalmologico", "Ortopedico": "dx_ortopedico", "Politrauma": "dx_politraumatismo",
    "Renal": "dx_renal", "Reproducti": "dx_reproductivo", "Respirator": "dx_respiratorio",
    "TraumaTeji": "dx_trauma_tejidos", "Cardiologi": "dx_cardiologico", "Dermatolog": "dx_dermatologico",
    "Nutriciona": "dx_nutricional", "Obstetrico": "dx_obstetrico", "Otros": "dx_otros",
    "RemiteBrig": "proc_remite_brigada", "CES": "proc_ces", "Ciudadano": "proc_ciudadano",
    "EscuadronA": "proc_escuadron_anticrueldad", "HogarPaso": "proc_hogar_de_paso", "UCA": "proc_uca",
    "Caninos": "esp_caninos", "Felinos": "esp_felinos", "Hembras": "sexo_hembras", "Machos": "sexo_machos",
    "Shape_Leng": "perimetro_m", "Shape_Area": "area_m2",
}


def aplanar_geojson(geojson: dict) -> pd.DataFrame:
    """Una fila por feature (localidad). La geometria se descarta; solo se conservan
    las propiedades (para el analisis tabular no se necesita el poligono)."""
    filas = [f["properties"] for f in geojson["features"]]
    return pd.DataFrame(filas)


def limpiar_bogota(geojson: dict) -> pd.DataFrame:
    df = aplanar_geojson(geojson)
    n0 = len(df)
    df = df.drop(columns=["Localidad"], errors="ignore")  # codigo duplicado en texto ("06"); se usa CodLoc entero
    df = df.rename(columns=RENOMBRAR)

    df = df.drop_duplicates(subset="cod_localidad", keep="first")
    df["cod_localidad"] = pd.to_numeric(df["cod_localidad"], errors="raise").astype(int)
    df["localidad"] = df["cod_localidad"].map(LOCALIDADES)
    if df["localidad"].isna().any():
        raise ValueError("CodLoc fuera del catalogo de 20 localidades de Bogota")
    df["fecha_corte"] = pd.to_datetime(df["fecha_corte"], errors="coerce")

    num = [c for c in df.columns if c.startswith(("dx_", "proc_", "esp_", "sexo_")) or c == "atenciones"]
    df[num] = df[num].fillna(0).astype(int)

    # Totales de control (para el reporte de calidad: las categorias deben sumar 'atenciones')
    cols_dx = [c for c in df.columns if c.startswith("dx_")]
    cols_proc = [c for c in df.columns if c.startswith("proc_")]
    cols_esp = [c for c in df.columns if c.startswith("esp_")]
    cols_sexo = [c for c in df.columns if c.startswith("sexo_")]

    df["suma_dx"] = df[cols_dx].sum(axis=1)
    df["suma_proc"] = df[cols_proc].sum(axis=1)
    df["suma_especie"] = df["esp_caninos"] + df["esp_felinos"]
    df["suma_sexo"] = df["sexo_hembras"] + df["sexo_machos"]

    # La concentracion en una localidad con infraestructura UCA infla la cifra (hallazgo del Avance 1)
    df["pct_atenciones_uca"] = (df["proc_uca"] / df["atenciones"].where(df["atenciones"] > 0)).fillna(0.0).round(4)

    base_cols = ["cod_localidad", "localidad", "fecha_corte", "atenciones"]
    ctrl_cols = ["suma_dx", "suma_proc", "suma_especie", "suma_sexo", "pct_atenciones_uca"]
    geo_cols = [c for c in ["perimetro_m", "area_m2"] if c in df.columns]
    agrupadas = base_cols + cols_dx + cols_proc + cols_esp + cols_sexo + ctrl_cols + geo_cols
    resto = [c for c in df.columns if c not in agrupadas]
    df = df[agrupadas + resto].sort_values("cod_localidad").reset_index(drop=True)
    log.info("SILVER Bogota: %s localidades | atenciones totales = %s", len(df), int(df["atenciones"].sum()))
    return df
