
from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

import pandas as pd
import requests

try:
    import streamlit as st
    _TIENE_STREAMLIT = True
except ImportError:
    st = None  # type: ignore[assignment]
    _TIENE_STREAMLIT = False

# Asegurar que la raíz de Medallon esté en sys.path
MEDALLON_DIR = Path(__file__).resolve().parent.parent
if str(MEDALLON_DIR) not in sys.path:
    sys.path.insert(0, str(MEDALLON_DIR))

from api.main import (  # noqa: E402
    CATALOGO_KPIS,
    SolicitudAdopcionInput,
    app,
    asegurar_catalogo_adopciones,
    cargar_config,
    cargar_gold,
    cargar_kpi,
    cargar_solicitudes_adopcion,
    obtener_directorio_kpis,
    obtener_ruta_gold,
    obtener_ruta_validaciones,
    registrar_solicitud_adopcion,
)


###############################################################################
# 1. FUNCIONES DEL PROYECTO ETL MEDALLION (CONSOLA Y RESUMEN DE CAPAS)
###############################################################################

def resumen_capas_etl() -> dict:
    """Consulta el estado real de las capas Bronze, Silver, Gold y SQLite del pipeline ETL."""
    cfg = cargar_config()
    rutas = cfg.get("paths", {})

    ruta_bronze_cali = MEDALLON_DIR / cfg["sources"]["cali"]["path"]
    ruta_bronze_bog = MEDALLON_DIR / cfg["sources"]["bogota"]["path"]
    ruta_bronze_pob = MEDALLON_DIR / cfg["api_poblacion"]["guardar_en"]

    ruta_silver_cali = MEDALLON_DIR / rutas.get("silver_cali", "data/silver/silver_cali.csv")
    ruta_silver_bog = MEDALLON_DIR / rutas.get("silver_bogota", "data/silver/silver_bogota.csv")
    ruta_gold = obtener_ruta_gold()
    ruta_db = MEDALLON_DIR / rutas.get("warehouse_db", "data/gold/warehouse.db")
    ruta_val = obtener_ruta_validaciones()
    kpis_dir = obtener_directorio_kpis()

    df_silver_cali = pd.read_csv(ruta_silver_cali) if ruta_silver_cali.exists() else pd.DataFrame()
    df_silver_bog = pd.read_csv(ruta_silver_bog) if ruta_silver_bog.exists() else pd.DataFrame()
    df_gold = cargar_gold() if ruta_gold.exists() else pd.DataFrame()
    df_val = pd.read_csv(ruta_val) if ruta_val.exists() else pd.DataFrame()

    tablas_sqlite = []
    if ruta_db.exists():
        with sqlite3.connect(ruta_db) as con:
            cur = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tablas_sqlite = [r[0] for r in cur.fetchall()]

    archivos_kpi = sorted(kpis_dir.glob("kpi_*.csv")) if kpis_dir.exists() else []
    evidencias_png = sorted((MEDALLON_DIR / rutas.get("evidencias_dir", "evidencias")).glob("*.png"))

    return {
        "proyecto": cfg["project"]["name"],
        "bronze": {
            "cali_excel_existe": ruta_bronze_cali.exists(),
            "bogota_geojson_existe": ruta_bronze_bog.exists(),
            "api_poblacion_json_existe": ruta_bronze_pob.exists(),
        },
        "silver": {
            "filas_cali": int(len(df_silver_cali)),
            "zonas_cali": int(df_silver_cali["zona"].nunique()) if "zona" in df_silver_cali.columns else 0,
            "filas_bogota": int(len(df_silver_bog)),
            "atenciones_bogota": int(df_silver_bog["atenciones"].sum()) if "atenciones" in df_silver_bog.columns else 0,
        },
        "gold": {
            "filas_gold_final": int(len(df_gold)),
            "casos_cali_gold": int(df_gold.loc[df_gold["ciudad"] == "Cali", "casos"].sum()) if not df_gold.empty else 0,
            "casos_bogota_gold": int(df_gold.loc[df_gold["ciudad"] == "Bogotá", "casos"].sum()) if not df_gold.empty else 0,
            "total_kpis_csv": len(archivos_kpi),
        },
        "load_warehouse": {
            "sqlite_path": str(ruta_db.relative_to(MEDALLON_DIR)),
            "total_tablas_sqlite": len(tablas_sqlite),
            "tablas": tablas_sqlite,
        },
        "calidad_y_evidencias": {
            "total_reglas": int(len(df_val)),
            "estados": df_val["estado"].value_counts().to_dict() if "estado" in df_val.columns else {},
            "graficas_png": len(evidencias_png),
        },
    }


def verificar_api_activa(url_base: str = "http://127.0.0.1:8000") -> dict:
    """Intenta consultar el endpoint /health de la API local si está encendida."""
    try:
        resp = requests.get(f"{url_base}/health", timeout=2)
        if resp.status_code == 200:
            return {"activa": True, "url": url_base, "respuesta": resp.json()}
    except Exception:
        pass
    return {"activa": False, "url": url_base}


def calcular_metricas_dataframe(df: pd.DataFrame) -> dict:
    """Adapta la lógica del profesor (producto más vendido / utilidad total / gráfica de barras)
    al esquema de Bienestar Animal (gold_final.csv, silver_cali.csv, silver_bogota.csv o cualquier KPI).
    """
    # Detectar columna de categoría/servicio (equivalente a 'Producto' del ejemplo del profesor)
    col_cat = None
    for candidata in ["categoria", "clase", "zona", "barrio", "localidad", "indicador", "regla"]:
        if candidata in df.columns:
            col_cat = candidata
            break
    if col_cat is None:
        cols_texto = df.select_dtypes(include=["object", "string"]).columns.tolist()
        col_cat = cols_texto[0] if cols_texto else df.columns[0]

    # Detectar columna numérica de volumen (equivalente a 'Utilidad' / 'Cantidad' del profesor)
    col_num = None
    for candidata in ["casos", "casos_total", "atenciones", "casos_criticos", "urgencias", "indice_priorizacion"]:
        if candidata in df.columns:
            col_num = candidata
            break
    if col_num is None:
        cols_num = df.select_dtypes(include=["number"]).columns.tolist()
        col_num = cols_num[0] if cols_num else None

    if col_num is not None:
        agrupado = df.groupby(col_cat)[col_num].sum().sort_values(ascending=False)
        categoria_principal = str(agrupado.index[0]) if not agrupado.empty else "Sin dato"
        total_casos = int(df[col_num].sum())
        serie_grafica = agrupado.head(10)
    else:
        conteo = df[col_cat].value_counts()
        categoria_principal = str(conteo.index[0]) if not conteo.empty else "Sin dato"
        total_casos = int(len(df))
        serie_grafica = conteo.head(10)

    # Si existe columna 'zona' además de 'categoria', calcular también el top por zona
    top_zonas = None
    if "zona" in df.columns and col_num is not None and col_cat != "zona":
        top_zonas = df.groupby("zona")[col_num].sum().sort_values(ascending=False).head(10)

    return {
        "columna_categoria": col_cat,
        "columna_numerica": col_num or "registros",
        "categoria_principal": categoria_principal,
        "total_casos": total_casos,
        "serie_grafica": serie_grafica,
        "top_zonas": top_zonas,
    }


def mostrar_reporte_consola() -> dict:
    """Imprime en consola el resumen de punta a punta del ETL Medallion y los principales hallazgos."""
    info = resumen_capas_etl()
    estado_api = verificar_api_activa()

    print("=" * 78)
    print(f" APLICACIÓN ETL MEDALLION — {info['proyecto']}")
    print("=" * 78)
    print(
        f"[1. EXTRACT / BRONZE] Cali Excel={info['bronze']['cali_excel_existe']} | "
        f"Bogotá GeoJSON={info['bronze']['bogota_geojson_existe']} | "
        f"API Población CKAN={info['bronze']['api_poblacion_json_existe']}"
    )
    print(
        f"[2. TRANSFORM / SILVER] Cali={info['silver']['filas_cali']:,} registros "
        f"({info['silver']['zonas_cali']} zonas estandarizadas) | "
        f"Bogotá={info['silver']['filas_bogota']} localidades ({info['silver']['atenciones_bogota']:,} atenciones)"
    )
    print(
        f"[3. TRANSFORM / GOLD] gold_final.csv={info['gold']['filas_gold_final']} filas "
        f"(Cali={info['gold']['casos_cali_gold']:,} | Bogotá={info['gold']['casos_bogota_gold']:,}) | "
        f"KPIs de negocio={info['gold']['total_kpis_csv']}/{len(CATALOGO_KPIS)}"
    )
    print(
        f"[4. LOAD / WAREHOUSE] SQLite ({info['load_warehouse']['sqlite_path']}): "
        f"{info['load_warehouse']['total_tablas_sqlite']} tablas cargadas"
    )
    print(
        f"[5. QUALITY & EVIDENCIAS] Reglas={info['calidad_y_evidencias']['total_reglas']} "
        f"{info['calidad_y_evidencias']['estados']} | "
        f"Gráficas PNG={info['calidad_y_evidencias']['graficas_png']}"
    )

    df_prio, _, _ = cargar_kpi("kpi_priorizacion_territorial")
    print("\n--- TOP 5 ZONAS PRIORITARIAS EN CALI (kpi_priorizacion_territorial) ---")
    cols_prio = [
        "ranking_prioridad",
        "zona",
        "tipo_zona",
        "casos_total",
        "casos_criticos",
        "casos_por_10k_hab",
        "indice_priorizacion",
    ]
    print(df_prio[cols_prio].head(5).to_string(index=False))

    df_barrios, _, _ = cargar_kpi("kpi_top_barrios_cali")
    print("\n--- TOP 5 BARRIOS CRÍTICOS EN CALI (kpi_top_barrios_cali) ---")
    cols_b = ["ranking_critico", "barrio", "zona", "casos_total", "casos_criticos", "urgencias", "denuncias"]
    print(df_barrios[cols_b].head(5).to_string(index=False))

    print("\n--- ESTADO DE LA API FASTAPI ---")
    if estado_api["activa"]:
        print(f"API ACTIVA en {estado_api['url']} -> {estado_api['respuesta']}")
    else:
        print("API apagada en este momento. Para levantarla ejecuta: uvicorn api.main:app --reload")
    print("=" * 78)
    return info


###############################################################################
# 2. APLICACIÓN STREAMLIT 
###############################################################################

def ejecutar_app_streamlit() -> None:
    """Interfaz visual en Streamlit que une el ejercicio del profesor con el proyecto Medallion."""
    st.set_page_config(
        page_title="Bienestar Animal Medallion — Cali vs Bogotá",
        layout="wide",
    )

    st.title("Tablero ETL Medallion: Bienestar Animal (Cali CBA/Uaepa vs Bogotá IDPYBA)")
    st.write(
        "Esta aplicación permite leer y graficar archivos CSV del pipeline Medallion "
        "(capa Silver, capa Gold y los 13 KPIs de negocio) o subir un archivo CSV propio."
    )

    # ---------------- Barra lateral (estructura del profesor + selector Medallion)
    st.sidebar.title("Configuraciones")
    st.sidebar.write("Aquí puedes configurar la aplicación y elegir la fuente de datos.")

    uploaded_file = st.sidebar.file_uploader("Elige un archivo CSV", type="csv")

    usar_datos_proyecto = st.sidebar.checkbox(
        "Usar datos del proyecto Medallion si no se sube un CSV",
        value=True,
    )
    opciones_proyecto = {
        "Capa Gold Consolidada (gold_final.csv)": obtener_ruta_gold(),
        "Capa Silver Cali (silver_cali.csv)": MEDALLON_DIR / "data/silver/silver_cali.csv",
        "Capa Silver Bogotá (silver_bogota.csv)": MEDALLON_DIR / "data/silver/silver_bogota.csv",
        **{
            f"KPI: {nombre} ({desc[:45]}...)": obtener_directorio_kpis() / f"{nombre}.csv"
            for nombre, desc in CATALOGO_KPIS.items()
        },
    }
    seleccion_archivo = st.sidebar.selectbox(
        "Archivo del proyecto Medallion:",
        list(opciones_proyecto.keys()),
    )

    
    df = None
    nombre_fuente = ""
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        nombre_fuente = f"Archivo subido: {uploaded_file.name}"
    elif usar_datos_proyecto:
        ruta_sel = opciones_proyecto[seleccion_archivo]
        if ruta_sel.exists():
            df = pd.read_csv(ruta_sel)
            nombre_fuente = f"{seleccion_archivo} ({ruta_sel.name})"

    if df is not None and not df.empty:
        st.subheader(f"Vista de datos — {nombre_fuente}")

        # Filtro opcional por ciudad si el CSV tiene la columna 'ciudad'
        if "ciudad" in df.columns:
            ciudades = ["Todas"] + sorted(df["ciudad"].dropna().unique().tolist())
            ciudad_sel = st.sidebar.radio("Filtrar por ciudad:", ciudades)
            if ciudad_sel != "Todas":
                df = df[df["ciudad"] == ciudad_sel]

        st.write(df)

      
        res_metricas = calcular_metricas_dataframe(df)
        categoria_mas_frecuente = res_metricas["categoria_principal"]
        casos_totales = res_metricas["total_casos"]
        col_cat = res_metricas["columna_categoria"]
        col_num = res_metricas["columna_numerica"]

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                label=f"Principal {col_cat} por volumen",
                value=categoria_mas_frecuente,
            )
        with col2:
            st.metric(
                label=f"Total de {col_num}",
                value=f"{casos_totales:,}",
            )
        with col3:
            st.metric(
                label="Registros en la tabla",
                value=f"{len(df):,}",
            )

        st.subheader(f"Distribución de {col_num} por {col_cat} (Top 10)")
        st.bar_chart(res_metricas["serie_grafica"])

        if res_metricas["top_zonas"] is not None:
            st.subheader(f"Top 10 zonas / localidades por {col_num}")
            st.bar_chart(res_metricas["top_zonas"])
    else:
        st.info("Por favor sube un archivo CSV en la barra lateral o activa los datos del proyecto para continuar.")

    st.markdown("---")
    st.header("Resumen Integral del Pipeline ETL Medallion")
    info = resumen_capas_etl()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solicitudes Cali (Silver)", f"{info['silver']['filas_cali']:,}")
    c2.metric("Atenciones Bogotá (Silver)", f"{info['silver']['atenciones_bogota']:,}")
    c3.metric("KPIs de Negocio (Gold)", f"{info['gold']['total_kpis_csv']}")
    c4.metric("Tablas en SQLite DW", f"{info['load_warehouse']['total_tablas_sqlite']}")

    tab_adop, tab_prio, tab_barrios, tab_graficas = st.tabs([
        "🐾 Adopción de Animales Rescatados",
        "Priorización Territorial (Cali)",
        "Top Barrios Críticos (Cali)",
        "Evidencias Gráficas (PNG)",
    ])
    with tab_adop:
        st.subheader("Portal de Adopción Responsable (Cali CBA/Uaepa & Bogotá IDPYBA)")
        st.info(
            "📌 **Hallazgo del ETL**: Las solicitudes de adopción en Cali cayeron un **-94,8 %** entre 2024 (58 casos) "
            "y 2025 (3 casos). Aquí puedes conocer los animales rescatados y rehabilitados en las zonas críticas "
            "del ETL y postularte para adoptarlos."
        )
        df_animales = asegurar_catalogo_adopciones()
        f1, f2 = st.columns(2)
        with f1:
            ciudad_adop = st.selectbox("Filtrar animales por ciudad:", ["Todas", "Cali", "Bogotá"])
        with f2:
            especie_adop = st.selectbox("Filtrar por especie:", ["Todas", "Canino", "Felino"])

        df_vista_anim = df_animales.copy()
        if ciudad_adop != "Todas":
            df_vista_anim = df_vista_anim[df_vista_anim["ciudad"] == ciudad_adop]
        if especie_adop != "Todas":
            df_vista_anim = df_vista_anim[df_vista_anim["especie"] == especie_adop]

        st.dataframe(df_vista_anim, width="stretch")

        disponibles_df = df_animales[df_animales["estado"] == "Disponible"]
        st.markdown("#### 📝 Formulario de Solicitud de Adopción")
        if disponibles_df.empty:
            st.success("¡Todos los animales del catálogo actual ya están en proceso de adopción!")
        else:
            opciones_anim = [
                f"{r['id_animal']} — {r['nombre']} ({r['especie']}, {r['ciudad']} - {r['zona_rescate']})"
                for _, r in disponibles_df.iterrows()
            ]
            with st.form("form_adopcion_streamlit"):
                seleccion_animal = st.selectbox("Selecciona el animal que deseas adoptar:", opciones_anim)
                col_a, col_b = st.columns(2)
                with col_a:
                    nombre_sol = st.text_input("Nombre completo del adoptante")
                    doc_sol = st.text_input("Documento de identidad")
                    tel_sol = st.text_input("Teléfono / Celular")
                with col_b:
                    correo_sol = st.text_input("Correo electrónico")
                    ciudad_res = st.selectbox("Ciudad de residencia", ["Cali", "Bogotá", "Otra"])
                    barrio_res = st.text_input("Barrio / Localidad y dirección")
                vivienda_sol = st.text_input("Tipo de vivienda", value="Casa / Apartamento con espacio seguro")
                motivacion_sol = st.text_area("¿Por qué deseas adoptar y cuál es tu compromiso de cuidado?")
                enviado = st.form_submit_button("Registrar Solicitud de Adopción")

                if enviado:
                    id_elegido = seleccion_animal.split(" — ")[0].strip()
                    try:
                        reg = registrar_solicitud_adopcion(
                            SolicitudAdopcionInput(
                                id_animal=id_elegido,
                                nombre_solicitante=nombre_sol,
                                documento=doc_sol,
                                telefono=tel_sol,
                                correo=correo_sol,
                                ciudad_residencia=ciudad_res,
                                direccion_barrio=barrio_res,
                                tipo_vivienda=vivienda_sol,
                                motivacion=motivacion_sol,
                            )
                        )
                        st.success(
                            f"¡Solicitud registrada! Radicado **{reg['radicado']}** para adoptar a "
                            f"**{reg['nombre_animal']}** ({reg['id_animal']})."
                        )
                    except Exception as exc:
                        st.error(f"Por favor completa todos los campos válidamente ({exc}).")

        df_sols = cargar_solicitudes_adopcion()
        if not df_sols.empty:
            st.markdown("#### Solicitudes de adopción registradas")
            st.dataframe(df_sols, width="stretch")

    with tab_prio:
        df_prio, _, _ = cargar_kpi("kpi_priorizacion_territorial")
        st.dataframe(df_prio, width="stretch")
    with tab_barrios:
        df_barrios, _, _ = cargar_kpi("kpi_top_barrios_cali")
        st.dataframe(df_barrios, width="stretch")
    with tab_graficas:
        rutas_png = sorted((MEDALLON_DIR / "evidencias").glob("*.png"))
        for ruta_img in rutas_png:
            st.image(str(ruta_img), caption=ruta_img.name, width="stretch")


def _ejecutando_en_streamlit() -> bool:
    """Detecta si el script fue lanzado mediante `streamlit run app/app.py`."""
    if not _TIENE_STREAMLIT:
        return False
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if _ejecutando_en_streamlit():
    ejecutar_app_streamlit()
elif __name__ == "__main__":
    if "--serve" in sys.argv:
        import uvicorn

        uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
    else:
        mostrar_reporte_consola()
