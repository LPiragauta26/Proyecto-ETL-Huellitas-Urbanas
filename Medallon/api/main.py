from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
from pydantic import BaseModel, Field
import yaml

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

###################################################
# Crear la ruta donde está el proyecto medallón
###################################################

BASE_DIR = Path(__file__).resolve().parent.parent

# Si api/ está dentro de Medallon/api, BASE_DIR ya es Medallon/.
# Si se ejecuta desde la carpeta superior, busca Medallon/ automáticamente.
if (BASE_DIR / "config" / "config.yaml").exists():
    MEDALLON_DIR = BASE_DIR
elif (BASE_DIR / "Medallon" / "config" / "config.yaml").exists():
    MEDALLON_DIR = BASE_DIR / "Medallon"
else:
    MEDALLON_DIR = BASE_DIR

print(MEDALLON_DIR)

CONFIG_FILE = (
    MEDALLON_DIR
    / "config"
    / "config.yaml"
)

print(CONFIG_FILE)

# Catálogo de los 13 KPIs de negocio disponibles en la capa Gold
CATALOGO_KPIS = {
    "kpi_calidad_datos": "Métricas de calidad antes (Bronze) vs después (Silver) para Cali y Bogotá",
    "kpi_casos_por_zona": "Solicitudes de Cali por zona, población 2020, tasa por 10k hab. y las 8 clases de servicio",
    "kpi_evolucion_mensual": "Serie mensual 2024-2025 de solicitudes totales y casos críticos en Cali",
    "kpi_priorizacion_territorial": "Ranking de priorización territorial (0-100) normalizado por tipo de zona (urbana/rural)",
    "kpi_comparativo_ciudades": "Comparativo estructural y operativo entre Cali (CBA/Uaepa) y Bogotá (IDPYBA)",
    "kpi_urgencias_por_zona": "Urgencias veterinarias por comuna/corregimiento (Cali) y localidad (Bogotá)",
    "kpi_bogota_detalle": "Distribución de diagnósticos, procedencia, especie y sexo en urgencias de Bogotá",
    "kpi_cambio_anual_servicios": "Cambio en el mix de servicios de Cali entre 2024 y 2025",
    "kpi_brecha_prevencion_zona": "Brecha entre prevención (esterilización + adopción) y casos críticos por zona en Cali",
    "kpi_top_barrios_cali": "Top 25 barrios más críticos de Cali y su concentración dentro de cada comuna",
    "kpi_calidad_por_clase": "Auditoría de completitud de barrio, comuna y fecha según clase de solicitud en Cali",
    "kpi_patron_semanal_cali": "Patrón operativo por día de la semana (lunes a domingo) en Cali",
    "kpi_bogota_engativa_vs_resto": "Análisis del efecto proximidad a la UCA (Engativá vs las otras 19 localidades de Bogotá)",
}

# Catálogo inicial de animales rescatados y rehabilitados en Cali (CBA/Uaepa) y Bogotá (IDPYBA/UCA),
# vinculados con las zonas, barrios y diagnósticos reales procesados en el ETL.
ANIMALES_SEMILLA = [
    {
        "id_animal": "CBA-CALI-001",
        "nombre": "Bruno",
        "especie": "Canino",
        "sexo": "Macho",
        "edad_aprox": "2 años",
        "talla": "Mediano",
        "ciudad": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "zona_rescate": "Comuna 20",
        "barrio_rescate": "Siloé",
        "historia_clinica_rescate": "Atendido por urgencia veterinaria en brigada de Comuna 20; rehabilitado, vacunado y esterilizado.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 2090,
    },
    {
        "id_animal": "CBA-CALI-002",
        "nombre": "Luna",
        "especie": "Canino",
        "sexo": "Hembra",
        "edad_aprox": "1 año",
        "talla": "Mediana",
        "ciudad": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "zona_rescate": "Comuna 18",
        "barrio_rescate": "Los Chorros",
        "historia_clinica_rescate": "Rescatada tras reporte ciudadano en Los Chorros (Comuna 18). Recuperada nutricionalmente y esterilizada.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 1816,
    },
    {
        "id_animal": "CBA-CALI-003",
        "nombre": "Simón",
        "especie": "Felino",
        "sexo": "Macho",
        "edad_aprox": "8 meses",
        "talla": "Pequeño",
        "ciudad": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "zona_rescate": "Comuna 1",
        "barrio_rescate": "Terrón Colorado",
        "historia_clinica_rescate": "Ingresó por atención médica en Terrón Colorado (Comuna 1). Dado de alta, desparasitado y esterilizado.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 9271,
    },
    {
        "id_animal": "CBA-CALI-004",
        "nombre": "Canela",
        "especie": "Canino",
        "sexo": "Hembra",
        "edad_aprox": "3 años",
        "talla": "Grande",
        "ciudad": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "zona_rescate": "Comuna 14",
        "barrio_rescate": "José Manuel Marroquín II",
        "historia_clinica_rescate": "Rescatada tras denuncia de abandono en Comuna 14. Muy dócil, sociable con niños y esterilizada.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 10206,
    },
    {
        "id_animal": "CBA-CALI-005",
        "nombre": "Milo",
        "especie": "Felino",
        "sexo": "Macho",
        "edad_aprox": "1.5 años",
        "talla": "Pequeño",
        "ciudad": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "zona_rescate": "Comuna 6",
        "barrio_rescate": "Ciudadela Floralia",
        "historia_clinica_rescate": "Valorado en jornada móvil en Ciudadela Floralia (Comuna 6). Negativo a virales, vacunado y castrado.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 17094,
    },
    {
        "id_animal": "UCA-BOG-001",
        "nombre": "Rocky",
        "especie": "Canino",
        "sexo": "Macho",
        "edad_aprox": "4 años",
        "talla": "Mediano",
        "ciudad": "Bogotá",
        "entidad": "IDPYBA - Unidad de Cuidado Animal (UCA)",
        "zona_rescate": "Engativá",
        "barrio_rescate": "Unidad de Cuidado Animal (UCA)",
        "historia_clinica_rescate": "Ingresó por urgencias a la UCA en Engativá con trauma ortopédico; cirugía exitosa y rehabilitación completa.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 10,
    },
    {
        "id_animal": "UCA-BOG-002",
        "nombre": "Kira",
        "especie": "Canino",
        "sexo": "Hembra",
        "edad_aprox": "2 años",
        "talla": "Mediana",
        "ciudad": "Bogotá",
        "entidad": "IDPYBA - Unidad de Cuidado Animal (UCA)",
        "zona_rescate": "Ciudad Bolívar",
        "barrio_rescate": "Reporte Ciudadano Directo",
        "historia_clinica_rescate": "Atendida por cuadro infeccioso tras reporte ciudadano en Ciudad Bolívar; 100% recuperada y esterilizada.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 19,
    },
    {
        "id_animal": "UCA-BOG-003",
        "nombre": "Nala",
        "especie": "Felino",
        "sexo": "Hembra",
        "edad_aprox": "1 año",
        "talla": "Pequeña",
        "ciudad": "Bogotá",
        "entidad": "IDPYBA - Unidad de Cuidado Animal (UCA)",
        "zona_rescate": "Suba",
        "barrio_rescate": "Escuadrón Anticrueldad",
        "historia_clinica_rescate": "Rescatada por el Escuadrón Anticrueldad en Suba. Rehabilitada física y comportamentalmente.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 11,
    },
    {
        "id_animal": "UCA-BOG-004",
        "nombre": "Toby",
        "especie": "Canino",
        "sexo": "Macho",
        "edad_aprox": "3 años",
        "talla": "Mediano",
        "ciudad": "Bogotá",
        "entidad": "IDPYBA - Unidad de Cuidado Animal (UCA)",
        "zona_rescate": "Usme",
        "barrio_rescate": "Brigada Médica IDPYBA",
        "historia_clinica_rescate": "Rescatado por politraumatismo vial en Usme; dado de alta con esquema completo de vacunación y microchip.",
        "esterilizado": "Sí",
        "vacunado": "Sí",
        "estado": "Disponible",
        "id_caso_origen_etl": 5,
    },
]


class SolicitudAdopcionInput(BaseModel):
    id_animal: str = Field(..., description="Código del animal a adoptar (ej. CBA-CALI-001 o UCA-BOG-001)")
    nombre_solicitante: str = Field(..., min_length=3, description="Nombre completo de la persona adoptante")
    documento: str = Field(..., min_length=5, description="Cédula o documento de identidad")
    telefono: str = Field(..., min_length=7, description="Teléfono o celular de contacto")
    correo: str = Field(..., min_length=5, description="Correo electrónico de contacto")
    ciudad_residencia: str = Field(..., description="Ciudad donde reside el adoptante (ej. Cali, Bogotá)")
    direccion_barrio: str = Field(..., description="Barrio o localidad de residencia")
    tipo_vivienda: str = Field("Casa / Apartamento con espacio seguro", description="Tipo de vivienda")
    motivacion: str = Field(..., min_length=5, description="Por qué desea adoptar y compromiso de tenencia responsable")


class CambioEstadoSolicitudInput(BaseModel):
    nuevo_estado: str = Field(..., description="Nuevo estado: 'Aceptada', 'En espera' o 'Negada'")
    observacion: Optional[str] = Field(None, description="Motivo o comentario del comité de bienestar animal")


SOLICITUDES_SEMILLA = [
    {
        "radicado": "ADOP-2026-0001",
        "fecha_solicitud": "2026-11-15 10:15:00",
        "id_animal": "CBA-CALI-005",
        "nombre_animal": "Milo",
        "especie": "Felino",
        "ciudad_animal": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "nombre_solicitante": "Camila Andrea Gómez",
        "documento": "1144098231",
        "telefono": "3157894512",
        "correo": "camila.gomez@correo.co",
        "ciudad_residencia": "Cali",
        "direccion_barrio": "Comuna 6 - Ciudadela Floralia",
        "tipo_vivienda": "Apartamento con mallas de protección y espacio seguro",
        "motivacion": "Contamos con mallas de seguridad en balcones, presupuesto veterinario y experiencia cuidando gatos rescatados.",
        "estado_solicitud": "Aceptada",
        "observacion_comite": "Evaluación Airflow/Comité: Cumple criterios de tenencia responsable, misma ciudad y vivienda segura con mallas.",
    },
    {
        "radicado": "ADOP-2026-0002",
        "fecha_solicitud": "2026-11-16 14:30:00",
        "id_animal": "UCA-BOG-004",
        "nombre_animal": "Toby",
        "especie": "Canino",
        "ciudad_animal": "Bogotá",
        "entidad": "IDPYBA - Unidad de Cuidado Animal (UCA)",
        "nombre_solicitante": "Carlos Eduardo Ramírez",
        "documento": "80123987",
        "telefono": "3104567890",
        "correo": "carlos.ramirez@correo.co",
        "ciudad_residencia": "Cali",
        "direccion_barrio": "Barrio El Ingenio",
        "tipo_vivienda": "Casa amplia con patio interno",
        "motivacion": "Deseo adoptarlo y asumir traslado, tengo patio seguro.",
        "estado_solicitud": "En espera",
        "observacion_comite": "Evaluación Airflow/Comité: En espera de entrevista virtual y verificación de traslado interurbano (Bogotá -> Cali).",
    },
    {
        "radicado": "ADOP-2026-0003",
        "fecha_solicitud": "2026-11-16 16:45:00",
        "id_animal": "CBA-CALI-001",
        "nombre_animal": "Bruno",
        "especie": "Canino",
        "ciudad_animal": "Cali",
        "entidad": "Centro de Bienestar Animal (CBA - UAEPA)",
        "nombre_solicitante": "Jorge Luis Pérez",
        "documento": "94512300",
        "telefono": "3001112233",
        "correo": "jorge.perez@correo.co",
        "ciudad_residencia": "Cali",
        "direccion_barrio": "Comuna 13",
        "tipo_vivienda": "Lote sin cerramiento en terraza abierta",
        "motivacion": "Para cuidar un lote abierto en las noches.",
        "estado_solicitud": "Negada",
        "observacion_comite": "Evaluación Airflow/Comité: Negada por condiciones sin cerramiento seguro; el animal Bruno regresa a estado Disponible.",
    },
]


######################################################
# Funciones
######################################################


def cargar_config():

    with CONFIG_FILE.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    return config


def obtener_ruta_gold():

    config = cargar_config()
    rutas_cfg = config.get("paths") or config.get("path") or {}

    ruta_gold = (
        MEDALLON_DIR
        / rutas_cfg["gold_final"]
    )

    print("RUTA GOLD:", ruta_gold)

    return ruta_gold


def obtener_directorio_kpis():

    config = cargar_config()
    rutas_cfg = config.get("paths") or config.get("path") or {}
    return MEDALLON_DIR / rutas_cfg.get("kpis_dir", "data/gold/kpis")


def obtener_ruta_validaciones():

    config = cargar_config()
    rutas_cfg = config.get("paths") or config.get("path") or {}
    return MEDALLON_DIR / rutas_cfg.get("evidencias_dir", "evidencias") / "validaciones_calidad.csv"


def obtener_ruta_catalogo_adopciones() -> Path:
    return MEDALLON_DIR / "data" / "gold" / "catalogo_adopciones.csv"


def obtener_ruta_solicitudes_adopcion() -> Path:
    return MEDALLON_DIR / "data" / "gold" / "solicitudes_adopcion.csv"


def asegurar_catalogo_adopciones() -> pd.DataFrame:
    """Garantiza que exista el catálogo de animales disponibles en data/gold/catalogo_adopciones.csv."""
    ruta_cat = obtener_ruta_catalogo_adopciones()
    ruta_cat.parent.mkdir(parents=True, exist_ok=True)
    if not ruta_cat.exists():
        df_init = pd.DataFrame(ANIMALES_SEMILLA)
        df_init.to_csv(ruta_cat, index=False, encoding="utf-8-sig")
        return df_init
    return pd.read_csv(ruta_cat)


def cargar_solicitudes_adopcion() -> pd.DataFrame:
    ruta_sol = obtener_ruta_solicitudes_adopcion()
    ruta_sol.parent.mkdir(parents=True, exist_ok=True)
    if not ruta_sol.exists():
        df_init = pd.DataFrame(SOLICITUDES_SEMILLA)
        df_init.to_csv(ruta_sol, index=False, encoding="utf-8-sig")
        return df_init
    df = pd.read_csv(ruta_sol)
    if "observacion_comite" not in df.columns:
        df["observacion_comite"] = "En evaluación por Comité de Bienestar Animal / Airflow"
    return df


def registrar_solicitud_adopcion(datos: SolicitudAdopcionInput) -> dict:
    df_cat = asegurar_catalogo_adopciones()
    id_buscado = datos.id_animal.strip().upper()
    mask = df_cat["id_animal"].str.upper() == id_buscado
    if not mask.any():
        raise HTTPException(
            status_code=404,
            detail=f"No existe el animal con código '{datos.id_animal}'. Consulta /adopciones/animales.",
        )

    fila_animal = df_cat.loc[mask].iloc[0]
    if str(fila_animal["estado"]).lower() != "disponible":
        raise HTTPException(
            status_code=400,
            detail=(
                f"El animal {fila_animal['nombre']} ({fila_animal['id_animal']}) "
                f"ya se encuentra en estado '{fila_animal['estado']}'."
            ),
        )

    df_sol = cargar_solicitudes_adopcion()
    consecutivo = len(df_sol) + 1
    radicado = f"ADOP-2026-{consecutivo:04d}"
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nueva_fila = {
        "radicado": radicado,
        "fecha_solicitud": fecha_actual,
        "id_animal": fila_animal["id_animal"],
        "nombre_animal": fila_animal["nombre"],
        "especie": fila_animal["especie"],
        "ciudad_animal": fila_animal["ciudad"],
        "entidad": fila_animal["entidad"],
        "nombre_solicitante": datos.nombre_solicitante.strip(),
        "documento": datos.documento.strip(),
        "telefono": datos.telefono.strip(),
        "correo": datos.correo.strip(),
        "ciudad_residencia": datos.ciudad_residencia.strip(),
        "direccion_barrio": datos.direccion_barrio.strip(),
        "tipo_vivienda": datos.tipo_vivienda.strip(),
        "motivacion": datos.motivacion.strip(),
        "estado_solicitud": "En revisión por bienestar animal",
        "observacion_comite": "Pendiente de evaluación (puedes usar los botones manuales o correr el DAG en Airflow)",
    }

    df_sol = pd.concat([df_sol, pd.DataFrame([nueva_fila])], ignore_index=True)
    df_sol.to_csv(obtener_ruta_solicitudes_adopcion(), index=False, encoding="utf-8-sig")

    # Actualizar estado del animal a 'En proceso de adopción'
    df_cat.loc[mask, "estado"] = "En proceso de adopción"
    df_cat.to_csv(obtener_ruta_catalogo_adopciones(), index=False, encoding="utf-8-sig")

    return nueva_fila


def actualizar_estado_solicitud_adopcion(
    radicado: str,
    nuevo_estado: str,
    observacion: Optional[str] = None,
) -> dict:
    """Actualiza el estado de una solicitud ('Aceptada', 'En espera' o 'Negada') y sincroniza el animal."""
    estados_validos = {
        "aceptada": "Aceptada",
        "aprobada": "Aceptada",
        "en espera": "En espera",
        "espera": "En espera",
        "negada": "Negada",
        "rechazada": "Negada",
    }
    clave = nuevo_estado.strip().lower()
    if clave not in estados_validos:
        raise HTTPException(
            status_code=400,
            detail="Estado inválido. Usa 'Aceptada', 'En espera' o 'Negada'.",
        )
    estado_canonico = estados_validos[clave]

    df_sol = cargar_solicitudes_adopcion()
    mask_sol = df_sol["radicado"].astype(str).str.upper() == radicado.strip().upper()
    if not mask_sol.any():
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró la solicitud con radicado '{radicado}'.",
        )

    idx = df_sol.index[mask_sol][0]
    id_animal = str(df_sol.loc[idx, "id_animal"])
    df_sol.loc[idx, "estado_solicitud"] = estado_canonico

    if observacion and observacion.strip():
        obs_texto = observacion.strip()
    else:
        mensajes_defecto = {
            "Aceptada": "Aprobada: cumple condiciones de tenencia responsable y espacio seguro.",
            "En espera": "En espera: pendiente de entrevista o visita domiciliaria de verificación.",
            "Negada": "Negada: no cumple requisitos de bienestar animal; el animal vuelve a estar Disponible.",
        }
        obs_texto = mensajes_defecto[estado_canonico]

    df_sol.loc[idx, "observacion_comite"] = obs_texto
    df_sol.to_csv(obtener_ruta_solicitudes_adopcion(), index=False, encoding="utf-8-sig")

    # Sincronizar el estado del animal en catalogo_adopciones.csv
    df_cat = asegurar_catalogo_adopciones()
    mask_cat = df_cat["id_animal"].astype(str).str.upper() == id_animal.upper()
    if mask_cat.any():
        if estado_canonico == "Aceptada":
            df_cat.loc[mask_cat, "estado"] = "Adoptado"
        elif estado_canonico == "En espera":
            df_cat.loc[mask_cat, "estado"] = "En espera"
        elif estado_canonico == "Negada":
            df_cat.loc[mask_cat, "estado"] = "Disponible"
        df_cat.to_csv(obtener_ruta_catalogo_adopciones(), index=False, encoding="utf-8-sig")

    fila_actualizada = preparar_dataframe_json(df_sol.loc[[idx]]).to_dict(orient="records")[0]
    return fila_actualizada


def evaluar_solicitudes_automatico_airflow() -> dict:
    """Motor automático invocado por Airflow (validate_gold) y main.py que clasifica las solicitudes
    pendientes en 'Aceptada', 'En espera' o 'Negada' según reglas de tenencia responsable.
    """
    df_sol = cargar_solicitudes_adopcion()
    df_cat = asegurar_catalogo_adopciones()
    evaluadas_nuevas = 0

    palabras_riesgo = [
        "sin cerramiento",
        "lote abierto",
        "amarrado",
        "cadena",
        "pelea",
        "azotea",
        "no tengo espacio",
        "calle",
    ]

    for idx, fila in df_sol.iterrows():
        estado_actual = str(fila.get("estado_solicitud", "")).strip()
        if estado_actual not in ("Aceptada", "En espera", "Negada"):
            evaluadas_nuevas += 1
            vivienda = str(fila.get("tipo_vivienda", "")).lower()
            motivacion = str(fila.get("motivacion", "")).strip()
            motivacion_low = motivacion.lower()
            ciudad_anim = str(fila.get("ciudad_animal", "")).strip().lower()
            ciudad_res = str(fila.get("ciudad_residencia", "")).strip().lower()

            if any(p in vivienda or p in motivacion_low for p in palabras_riesgo) or len(motivacion) < 12:
                nuevo_est = "Negada"
                obs = (
                    "Airflow Auto-Evaluación: Negada por condiciones de vivienda sin cerramiento "
                    "o motivación insuficiente de tenencia responsable."
                )
            elif ciudad_anim and ciudad_res and ciudad_anim != ciudad_res or len(motivacion) < 30:
                nuevo_est = "En espera"
                obs = (
                    "Airflow Auto-Evaluación: En espera de entrevista virtual y verificación "
                    "domiciliaria por comité de bienestar animal."
                )
            else:
                nuevo_est = "Aceptada"
                obs = (
                    "Airflow Auto-Evaluación: Aceptada automáticamente; cumple criterios de "
                    "vivienda segura, misma ciudad y compromiso de cuidado."
                )

            df_sol.loc[idx, "estado_solicitud"] = nuevo_est
            df_sol.loc[idx, "observacion_comite"] = obs

        # Sincronizar animal según estado final
        est_final = str(df_sol.loc[idx, "estado_solicitud"])
        id_anim = str(df_sol.loc[idx, "id_animal"]).upper()
        mask_cat = df_cat["id_animal"].astype(str).str.upper() == id_anim
        if mask_cat.any():
            if est_final == "Aceptada":
                df_cat.loc[mask_cat, "estado"] = "Adoptado"
            elif est_final == "En espera":
                df_cat.loc[mask_cat, "estado"] = "En espera"
            elif est_final == "Negada":
                df_cat.loc[mask_cat, "estado"] = "Disponible"

    df_sol.to_csv(obtener_ruta_solicitudes_adopcion(), index=False, encoding="utf-8-sig")
    df_cat.to_csv(obtener_ruta_catalogo_adopciones(), index=False, encoding="utf-8-sig")

    conteo = df_sol["estado_solicitud"].value_counts().to_dict() if not df_sol.empty else {}
    return {
        "total_solicitudes": int(len(df_sol)),
        "evaluadas_nuevas": int(evaluadas_nuevas),
        "aceptadas": int(conteo.get("Aceptada", 0)),
        "en_espera": int(conteo.get("En espera", 0)),
        "negadas": int(conteo.get("Negada", 0)),
        "en_revision": int(conteo.get("En revisión por bienestar animal", 0)),
    }


def cargar_gold():

    ruta_gold = obtener_ruta_gold()

    if not ruta_gold.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Disculpa, el archivo no existe: {ruta_gold}"
        )

    df = pd.read_csv(ruta_gold)

    return df


def cargar_kpi(nombre_kpi: str):

    limpio = nombre_kpi.replace(".csv", "").strip()
    ruta_kpi = obtener_directorio_kpis() / f"{limpio}.csv"

    if not ruta_kpi.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Disculpa, el KPI '{limpio}' no existe en {ruta_kpi}. "
                f"Consulta /kpis para ver los 13 KPIs disponibles."
            ),
        )

    return pd.read_csv(ruta_kpi), limpio, ruta_kpi


def preparar_dataframe_json(df):

    df = df.copy()

    df = df.astype(object).where(
        pd.notnull(df),
        None
    )

    return df


########################################################
# Creación de la API
########################################################

app = FastAPI(
    title="Bienestar Animal Medallon API (Cali CBA/Uaepa vs Bogotá IDPYBA)",
    description=(
        "API para prestar el servicio de consulta ciudadana de la capa Gold, los 13 KPIs de negocio, "
        "las validaciones de calidad y el Portal de Adopción Responsable de animales rescatados en Cali y Bogotá."
    ),
    version="1.1.0"
)

########################################################
# Endpoints
########################################################


@app.get("/")
def inicio():

    return {
        "mensaje": "Bienvenido a la API de Bienestar Animal Medallon (Cali CBA/Uaepa vs Bogotá IDPYBA)",
        "portal_ciudadano_y_adopcion": "/portal",
        "documentacion_swagger": "/docs",
        "gold": "/gold",
        "data": "/gold/data",
        "gold_por_ciudad": "/gold/ciudad/{ciudad}",
        "kpis": "/kpis",
        "kpi_detalle": "/kpis/{nombre_kpi}",
        "adopciones_gold_historico": "/adopciones/gold",
        "adopciones_animales_disponibles": "/adopciones/animales",
        "adopciones_postular": "/adopciones/solicitar (POST)",
        "adopciones_solicitudes_registradas": "/adopciones/solicitudes",
        "calidad": "/calidad",
        "health": "/health"
    }


@app.get("/gold")
def consultar_gold_completo(
    ciudad: Optional[str] = Query(None, description="Filtrar por ciudad (ej. Cali o Bogotá)"),
    tipo_zona: Optional[str] = Query(None, description="Filtrar por tipo_zona (urbana, rural, localidad, sin_dato)"),
    categoria: Optional[str] = Query(None, description="Filtrar por categoría (ej. Urgencias, PQR, Adopciones, Esterilizaciones)"),
    es_critico: Optional[bool] = Query(None, description="Filtrar solo servicios críticos (True/False)"),
):

    df = cargar_gold()

    if ciudad:
        df = df[df["ciudad"].str.lower() == ciudad.strip().lower()]
    if tipo_zona:
        df = df[df["tipo_zona"].str.lower() == tipo_zona.strip().lower()]
    if categoria:
        df = df[df["categoria"].str.lower() == categoria.strip().lower()]
    if es_critico is not None:
        df = df[df["es_critico"] == es_critico]

    df = preparar_dataframe_json(df)

    return {
        "total_registros": len(df),
        "total_columnas": len(df.columns),
        "Nombres_columnas": df.columns.tolist(),
        "Data": df.to_dict(orient="records")
    }


@app.get("/gold/data")
def consultar_solo_data():

    df = cargar_gold()

    df = preparar_dataframe_json(df)

    return {
        "Data": df.to_dict(orient="records")
    }


@app.get("/gold/ciudad/{ciudad}")
def consultar_gold_por_ciudad(ciudad: str):

    df = cargar_gold()
    c_norm = ciudad.strip().lower()
    if c_norm in ("bogota", "bogotá"):
        filtro = df["ciudad"] == "Bogotá"
    elif c_norm == "cali":
        filtro = df["ciudad"] == "Cali"
    else:
        raise HTTPException(
            status_code=400,
            detail="Ciudad no reconocida. Usa 'Cali' o 'Bogota'."
        )

    sub = preparar_dataframe_json(df[filtro])

    return {
        "ciudad": "Bogotá" if c_norm in ("bogota", "bogotá") else "Cali",
        "total_registros": len(sub),
        "total_casos": int(df.loc[filtro, "casos"].sum()),
        "Nombres_columnas": sub.columns.tolist(),
        "Data": sub.to_dict(orient="records"),
    }


@app.get("/kpis")
def listar_kpis():

    kpis_dir = obtener_directorio_kpis()
    disponibles = []

    for nombre, descripcion in CATALOGO_KPIS.items():
        archivo = kpis_dir / f"{nombre}.csv"
        disponibles.append({
            "kpi": nombre,
            "descripcion": descripcion,
            "existe": archivo.exists(),
            "endpoint": f"/kpis/{nombre}",
        })

    return {
        "total_kpis": len(disponibles),
        "directorio_kpis": str(kpis_dir),
        "kpis": disponibles,
    }


@app.get("/kpis/{nombre_kpi}")
def consultar_kpi(nombre_kpi: str):

    df, limpio, ruta_kpi = cargar_kpi(nombre_kpi)
    df = preparar_dataframe_json(df)

    return {
        "kpi": limpio,
        "descripcion": CATALOGO_KPIS.get(limpio, "Tabla KPI de la capa Gold"),
        "ruta": str(ruta_kpi),
        "total_registros": len(df),
        "total_columnas": len(df.columns),
        "Nombres_columnas": df.columns.tolist(),
        "Data": df.to_dict(orient="records"),
    }


########################################################
# Endpoints de Adopción Responsable + Datos Gold
########################################################


@app.get("/adopciones/gold", tags=["Adopciones"])
def consultar_adopciones_en_gold():
    """Muestra los datos reales de Adopciones en la capa Gold y por qué el ETL recomienda impulsar este canal."""
    df_gold = cargar_gold()
    adop_gold = df_gold[df_gold["categoria"].str.lower() == "adopciones"].sort_values("casos", ascending=False)
    adop_gold_json = preparar_dataframe_json(adop_gold)

    # Cruzar con el KPI de cambio anual para mostrar el hallazgo de negocio (2024 vs 2025)
    hallazgo_anual = {}
    try:
        df_cambio, _, _ = cargar_kpi("kpi_cambio_anual_servicios")
        fila_adop = df_cambio[df_cambio["clase"].str.lower() == "adopciones"]
        if not fila_adop.empty:
            r = fila_adop.iloc[0]
            hallazgo_anual = {
                "adopciones_2024": int(r["casos_2024"]),
                "adopciones_2025": int(r["casos_2025"]),
                "variacion_pct_2024_vs_2025": float(r["variacion_pct"]),
                "alerta_negocio": (
                    "Las solicitudes de adopción en Cali cayeron un -94.8% entre 2024 (58 casos) y 2025 (3 casos). "
                    "Por ello se habilita este módulo digital de adopción ciudadana conectado a la capa Gold."
                ),
            }
    except Exception:
        pass

    return {
        "total_casos_adopcion_historico_gold": int(adop_gold["casos"].sum()),
        "total_zonas_con_adopcion": len(adop_gold),
        "hallazgo_etl_2024_vs_2025": hallazgo_anual,
        "registros_gold_adopciones": adop_gold_json.to_dict(orient="records"),
    }


@app.get("/adopciones/animales", tags=["Adopciones"])
def listar_animales_en_adopcion(
    ciudad: Optional[str] = Query(None, description="Filtrar por ciudad (Cali o Bogotá)"),
    especie: Optional[str] = Query(None, description="Filtrar por especie (Canino o Felino)"),
    solo_disponibles: bool = Query(False, description="Si es True, muestra solo animales con estado 'Disponible'"),
):
    """Lista los animales rescatados y rehabilitados en Cali (CBA) y Bogotá (IDPYBA/UCA) para adopción."""
    df_cat = asegurar_catalogo_adopciones()

    if ciudad:
        c_norm = ciudad.strip().lower()
        if c_norm in ("bogota", "bogotá"):
            df_cat = df_cat[df_cat["ciudad"] == "Bogotá"]
        elif c_norm == "cali":
            df_cat = df_cat[df_cat["ciudad"] == "Cali"]
    if especie:
        df_cat = df_cat[df_cat["especie"].str.lower() == especie.strip().lower()]
    if solo_disponibles:
        df_cat = df_cat[df_cat["estado"].str.lower() == "disponible"]

    df_json = preparar_dataframe_json(df_cat)
    return {
        "total_animales": len(df_json),
        "disponibles": int((df_cat["estado"] == "Disponible").sum()),
        "en_proceso": int((df_cat["estado"] != "Disponible").sum()),
        "animales": df_json.to_dict(orient="records"),
    }


@app.post("/adopciones/solicitar", tags=["Adopciones"])
def postular_adopcion(solicitud: SolicitudAdopcionInput):
    """Registra una solicitud ciudadana de adopción responsable y actualiza el estado del animal."""
    registro = registrar_solicitud_adopcion(solicitud)
    return {
        "mensaje": (
            f"¡Solicitud registrada con éxito! Tu radicado es {registro['radicado']} "
            f"para adoptar a {registro['nombre_animal']} ({registro['id_animal']})."
        ),
        "solicitud": registro,
    }


@app.get("/adopciones/solicitudes", tags=["Adopciones"])
def listar_solicitudes_adopcion():
    """Consulta las solicitudes de adopción registradas a través de la API o la aplicación."""
    df_sol = cargar_solicitudes_adopcion()
    df_json = preparar_dataframe_json(df_sol)
    conteo = df_sol["estado_solicitud"].value_counts().to_dict() if not df_sol.empty else {}
    return {
        "total_solicitudes": len(df_json),
        "resumen_estados": {
            "Aceptada": int(conteo.get("Aceptada", 0)),
            "En espera": int(conteo.get("En espera", 0)),
            "Negada": int(conteo.get("Negada", 0)),
            "En revisión por bienestar animal": int(conteo.get("En revisión por bienestar animal", 0)),
        },
        "solicitudes": df_json.to_dict(orient="records"),
    }


@app.post("/adopciones/solicitudes/{radicado}/estado", tags=["Adopciones"])
def cambiar_estado_solicitud(radicado: str, datos: CambioEstadoSolicitudInput):
    """Permite aceptar, poner en espera o negar manualmente una solicitud de adopción."""
    actualizada = actualizar_estado_solicitud_adopcion(
        radicado=radicado,
        nuevo_estado=datos.nuevo_estado,
        observacion=datos.observacion,
    )
    return {
        "mensaje": f"Solicitud {radicado} actualizada a estado '{actualizada['estado_solicitud']}'.",
        "solicitud": actualizada,
    }


@app.post("/adopciones/evaluar-airflow", tags=["Adopciones"])
def ejecutar_evaluacion_airflow():
    """Ejecuta el motor de reglas de Airflow para clasificar solicitudes en Aceptada, En espera o Negada."""
    res = evaluar_solicitudes_automatico_airflow()
    return {
        "mensaje": (
            f"Evaluación automática completada: {res['aceptadas']} Aceptadas, "
            f"{res['en_espera']} En espera, {res['negadas']} Negadas."
        ),
        "resumen": res,
    }


@app.get("/portal", response_class=HTMLResponse, tags=["Portal Ciudadano"])
def portal_ciudadano_gold_y_adopcion():
    """Interfaz web interactiva dentro de la API para consultar datos Gold y adoptar animales rescatados."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Portal Ciudadano Gold y Adopción — Bienestar Animal (Cali & Bogotá)</title>
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f4f7f9; color: #1e293b; }
    header { background: linear-gradient(135deg, #0f766e, #1e3a8a); color: white; padding: 24px 32px; }
    header h1 { margin: 0 0 8px 0; font-size: 24px; }
    header p { margin: 0; opacity: 0.92; font-size: 14px; }
    .container { max-width: 1200px; margin: 24px auto; padding: 0 20px; }
    .tabs { display: flex; gap: 12px; margin-bottom: 20px; }
    .tab-btn { padding: 10px 20px; border: none; border-radius: 8px; cursor: pointer; font-weight: 600; background: #e2e8f0; color: #334155; }
    .tab-btn.active { background: #0f766e; color: white; }
    .panel { display: none; background: white; padding: 24px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); }
    .panel.active { display: block; }
    .grid-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-top: 16px; }
    .card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; background: #ffffff; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .badge-disp, .badge-aceptada { background: #dcfce7; color: #166534; }
    .badge-proc, .badge-espera { background: #fef3c7; color: #92400e; }
    .badge-negada { background: #fee2e2; color: #991b1b; }
    .badge-rev { background: #e0f2fe; color: #075985; }
    .filters { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
    select, input, textarea, button { padding: 8px 12px; border: 1px solid #cbd5e1; border-radius: 6px; font-size: 14px; }
    button.primary { background: #0f766e; color: white; border: none; font-weight: 600; cursor: pointer; }
    button.primary:hover { background: #115e59; }
    .btn-sm { padding: 5px 10px; font-size: 12px; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; margin-right: 4px; }
    .btn-ok { background: #16a34a; color: white; }
    .btn-wait { background: #d97706; color: white; }
    .btn-deny { background: #dc2626; color: white; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
    .alert { padding: 12px 16px; border-radius: 8px; margin-top: 14px; font-weight: 600; }
    .alert-ok { background: #dcfce7; color: #166534; }
    .alert-err { background: #fee2e2; color: #991b1b; }
    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 14px 0; }
    .kpi-box { padding: 12px 16px; border-radius: 10px; border: 1px solid #e2e8f0; background: #f8fafc; text-align: center; }
    .kpi-box strong { display: block; font-size: 22px; margin-top: 4px; }
  </style>
</head>
<body>
  <header>
    <h1>🐾 Portal Ciudadano: Datos Gold y Adopción Responsable (Cali CBA & Bogotá IDPYBA)</h1>
    <p>Conectado en vivo a la API FastAPI del Pipeline ETL Medallion | <a href="/docs" style="color:#99f6e4;">Ver Swagger (/docs)</a></p>
  </header>
  <div class="container">
    <div class="tabs">
      <button class="tab-btn active" onclick="mostrarTab('adopcion', this)">🐶 Animales para Adopción</button>
      <button class="tab-btn" onclick="mostrarTab('gold', this)">📊 Consultar Datos Gold y KPIs</button>
    </div>

    <!-- PANEL 1: ADOPCIONES (SOLO VISTA PÚBLICA CIUDADANA) -->
    <div id="panel-adopcion" class="panel active">
      <h2>Animales Rescatados y Rehabilitados listos para Adopción</h2>
      <p id="alerta-etl" style="background:#fffbeb; border-left:4px solid #f59e0b; padding:10px 14px; border-radius:6px;"></p>
      <div class="filters">
        <label>Ciudad:
          <select id="f-ciudad-adop" onchange="cargarAnimales()">
            <option value="">Todas (Cali y Bogotá)</option>
            <option value="Cali">Cali (CBA / UAEPA)</option>
            <option value="Bogotá">Bogotá (IDPYBA / UCA)</option>
          </select>
        </label>
        <label>Especie:
          <select id="f-especie-adop" onchange="cargarAnimales()">
            <option value="">Todas</option>
            <option value="Canino">Canino</option>
            <option value="Felino">Felino</option>
          </select>
        </label>
      </div>
      <div id="contenedor-animales" class="grid-cards"></div>

      <hr style="margin: 28px 0; border: none; border-top: 1px solid #e2e8f0;" />
      <h3>📝 Formulario de Postulación para Adopción Responsable</h3>
      <form id="form-adopcion" onsubmit="enviarAdopcion(event)">
        <div class="form-grid">
          <input type="text" id="id_animal" placeholder="Código del animal (ej. CBA-CALI-001)" required />
          <input type="text" id="nombre_solicitante" placeholder="Tu nombre completo" required />
          <input type="text" id="documento" placeholder="Documento de identidad" required />
          <input type="text" id="telefono" placeholder="Teléfono / Celular" required />
          <input type="email" id="correo" placeholder="Correo electrónico" required />
          <input type="text" id="ciudad_residencia" placeholder="Ciudad donde vives (Cali / Bogotá)" required />
          <input type="text" id="direccion_barrio" placeholder="Barrio / Localidad y dirección" required />
          <input type="text" id="tipo_vivienda" value="Casa / Apartamento con espacio seguro" required />
        </div>
        <textarea id="motivacion" rows="3" style="width:100%; margin-top:12px;" placeholder="Cuéntanos por qué deseas adoptarlo y tu compromiso de tenencia responsable..." required></textarea>
        <div style="margin-top:12px;">
          <button type="submit" class="primary">Enviar Solicitud de Adopción</button>
        </div>
      </form>
      <div id="mensaje-adopcion"></div>
    </div>

    <!-- PANEL 2: CONSULTA GOLD -->
    <div id="panel-gold" class="panel">
      <h2>Explorador Ciudadano de la Capa Gold (`gold_final.csv`)</h2>
      <div class="filters">
        <label>Ciudad:
          <select id="f-ciudad-gold" onchange="cargarGold()">
            <option value="">Todas</option>
            <option value="Cali">Cali</option>
            <option value="Bogotá">Bogotá</option>
          </select>
        </label>
        <label>Categoría:
          <select id="f-cat-gold" onchange="cargarGold()">
            <option value="">Todas</option>
            <option value="Urgencias">Urgencias</option>
            <option value="Denuncia">Denuncia</option>
            <option value="Esterilizaciones">Esterilizaciones</option>
            <option value="Adopciones">Adopciones</option>
            <option value="Cita médica">Cita médica</option>
            <option value="PQR">PQR</option>
          </select>
        </label>
      </div>
      <p id="resumen-gold"></p>
      <div style="max-height: 480px; overflow-y: auto;">
        <table id="tabla-gold">
          <thead>
            <tr><th>Ciudad</th><th>Zona / Localidad</th><th>Tipo Zona</th><th>Categoría</th><th>Homologada</th><th>Crítico</th><th>Periodo</th><th>Casos</th></tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    function mostrarTab(nombre, btn) {
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('panel-' + nombre).classList.add('active');
      btn.classList.add('active');
    }

    function seleccionarAnimal(id) {
      document.getElementById('id_animal').value = id;
      document.getElementById('form-adopcion').scrollIntoView({ behavior: 'smooth' });
    }

    function claseBadgeEstado(est) {
      if (est === 'Aceptada' || est === 'Disponible') return 'badge-aceptada';
      if (est === 'En espera' || est === 'En proceso de adopción') return 'badge-espera';
      if (est === 'Negada') return 'badge-negada';
      return 'badge-rev';
    }

    async function cargarAlertaGoldAdopciones() {
      const r = await fetch('/adopciones/gold');
      const d = await r.json();
      if (d.hallazgo_etl_2024_vs_2025 && d.hallazgo_etl_2024_vs_2025.alerta_negocio) {
        document.getElementById('alerta-etl').innerText = '📌 Hallazgo del ETL Medallion: ' + d.hallazgo_etl_2024_vs_2025.alerta_negocio;
      }
    }

    async function cargarAnimales() {
      const ciudad = document.getElementById('f-ciudad-adop').value;
      const especie = document.getElementById('f-especie-adop').value;
      const params = new URLSearchParams();
      if (ciudad) params.append('ciudad', ciudad);
      if (especie) params.append('especie', especie);
      const r = await fetch('/adopciones/animales?' + params.toString());
      const d = await r.json();
      const cont = document.getElementById('contenedor-animales');
      cont.innerHTML = d.animales.map(a => `
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0;">${a.especie === 'Canino' ? '🐶' : '🐱'} ${a.nombre}</h3>
            <span class="badge ${a.estado === 'Disponible' ? 'badge-disp' : 'badge-proc'}">${a.estado}</span>
          </div>
          <p style="margin:6px 0; font-size:13px; color:#475569;"><strong>Código:</strong> ${a.id_animal} | <strong>Edad:</strong> ${a.edad_aprox} | <strong>Sexo:</strong> ${a.sexo}</p>
          <p style="margin:6px 0; font-size:13px;"><strong>Ciudad y Zona:</strong> ${a.ciudad} — ${a.zona_rescate} (${a.barrio_rescate})</p>
          <p style="margin:6px 0; font-size:13px;"><strong>Entidad:</strong> ${a.entidad}</p>
          <p style="margin:8px 0; font-size:13px; color:#334155;">${a.historia_clinica_rescate}</p>
          ${a.estado === 'Disponible'
            ? `<button class="primary" onclick="seleccionarAnimal('${a.id_animal}')">Quiero adoptar a ${a.nombre}</button>`
            : `<button disabled>${a.estado}</button>`}
        </div>
      `).join('');
    }

    async function enviarAdopcion(e) {
      e.preventDefault();
      const payload = {
        id_animal: document.getElementById('id_animal').value,
        nombre_solicitante: document.getElementById('nombre_solicitante').value,
        documento: document.getElementById('documento').value,
        telefono: document.getElementById('telefono').value,
        correo: document.getElementById('correo').value,
        ciudad_residencia: document.getElementById('ciudad_residencia').value,
        direccion_barrio: document.getElementById('direccion_barrio').value,
        tipo_vivienda: document.getElementById('tipo_vivienda').value,
        motivacion: document.getElementById('motivacion').value,
      };
      const r = await fetch('/adopciones/solicitar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      const msg = document.getElementById('mensaje-adopcion');
      if (r.ok) {
        msg.innerHTML = `<div class="alert alert-ok">${d.mensaje}</div>`;
        document.getElementById('form-adopcion').reset();
        cargarAnimales();
      } else {
        msg.innerHTML = `<div class="alert alert-err">${d.detail || 'Error al registrar solicitud'}</div>`;
      }
    }

    async function cargarGold() {
      const ciudad = document.getElementById('f-ciudad-gold').value;
      const cat = document.getElementById('f-cat-gold').value;
      const params = new URLSearchParams();
      if (ciudad) params.append('ciudad', ciudad);
      if (cat) params.append('categoria', cat);
      const r = await fetch('/gold?' + params.toString());
      const d = await r.json();
      document.getElementById('resumen-gold').innerText = `Mostrando ${d.total_registros} registros de la capa Gold.`;
      const tbody = document.querySelector('#tabla-gold tbody');
      tbody.innerHTML = d.Data.map(f => `
        <tr>
          <td>${f.ciudad}</td><td>${f.zona}</td><td>${f.tipo_zona}</td>
          <td>${f.categoria}</td><td>${f.categoria_comparable}</td>
          <td>${f.es_critico ? 'Sí' : 'No'}</td><td>${f.periodo}</td><td><strong>${f.casos}</strong></td>
        </tr>
      `).join('');
    }

    cargarAlertaGoldAdopciones();
    cargarAnimales();
    cargarGold();
  </script>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse, tags=["Panel Privado Creadores"])
def panel_privado_creadores_comite():
    """Panel privado exclusivo para los creadores / Comité de Bienestar Animal (Aceptar, En espera, Negar + Airflow)."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>🔐 Panel Privado Creadores y Comité — Bienestar Animal</title>
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #0f172a; color: #1e293b; }
    header { background: linear-gradient(135deg, #1e293b, #0f766e); color: white; padding: 22px 32px; border-bottom: 3px solid #14b8a6; }
    header h1 { margin: 0 0 6px 0; font-size: 22px; }
    header p { margin: 0; opacity: 0.9; font-size: 13px; }
    .container { max-width: 1240px; margin: 24px auto; padding: 0 20px; }
    .panel { background: white; padding: 24px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.25); }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .badge-aceptada { background: #dcfce7; color: #166534; }
    .badge-espera { background: #fef3c7; color: #92400e; }
    .badge-negada { background: #fee2e2; color: #991b1b; }
    .badge-rev { background: #e0f2fe; color: #075985; }
    button.primary { padding: 9px 14px; background: #0f766e; color: white; border: none; border-radius: 6px; font-weight: 600; cursor: pointer; }
    .btn-sm { padding: 5px 10px; font-size: 12px; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; margin-right: 4px; }
    .btn-ok { background: #16a34a; color: white; }
    .btn-wait { background: #d97706; color: white; }
    .btn-deny { background: #dc2626; color: white; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .kpi-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 14px 0; }
    .kpi-box { padding: 12px 16px; border-radius: 10px; border: 1px solid #e2e8f0; background: #f8fafc; text-align: center; }
    .kpi-box strong { display: block; font-size: 22px; margin-top: 4px; }
    .alert { padding: 12px 16px; border-radius: 8px; margin-top: 12px; font-weight: 600; background: #dcfce7; color: #166534; }
  </style>
</head>
<body>
  <header>
    <h1>🔐 Panel Privado de Creadores — Comité de Bienestar Animal (Control Manual + Airflow)</h1>
    <p>Vista interna exclusiva para administradores | <a href="/portal" style="color:#99f6e4;">Ir al Portal Público (/portal)</a> | <a href="/docs" style="color:#99f6e4;">Swagger (/docs)</a></p>
  </header>
  <div class="container">
    <div class="panel">
      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <h2 style="margin:0;">📋 Bandeja de Solicitudes y Comité de Bienestar Animal (Control Manual + Airflow)</h2>
        <button class="primary" onclick="evaluarConAirflow()">⚙️ Evaluar Pendientes con Reglas Airflow</button>
      </div>
      <div id="mensaje-admin"></div>
      <div id="resumen-solicitudes" class="kpi-row"></div>
      <div style="overflow-x:auto;">
        <table id="tabla-solicitudes">
          <thead>
            <tr>
              <th>Radicado</th>
              <th>Fecha</th>
              <th>Animal</th>
              <th>Solicitante</th>
              <th>Ciudad / Vivienda</th>
              <th>Motivación</th>
              <th>Estado Actual</th>
              <th>Concepto Comité / Airflow</th>
              <th>Acciones Manuales</th>
            </tr>
          </thead>
          <tbody></tbody>
        </table>
      </div>
    </div>
  </div>
  <script>
    function claseBadgeEstado(est) {
      if (est === 'Aceptada') return 'badge-aceptada';
      if (est === 'En espera') return 'badge-espera';
      if (est === 'Negada') return 'badge-negada';
      return 'badge-rev';
    }
    async function cargarSolicitudes() {
      const r = await fetch('/adopciones/solicitudes');
      const d = await r.json();
      const res = d.resumen_estados || {};
      document.getElementById('resumen-solicitudes').innerHTML = `
        <div class="kpi-box"><span>Total Solicitudes</span><strong>${d.total_solicitudes}</strong></div>
        <div class="kpi-box" style="background:#f0fdf4;"><span>🟢 Aceptadas</span><strong style="color:#166534;">${res['Aceptada'] || 0}</strong></div>
        <div class="kpi-box" style="background:#fffbeb;"><span>🟡 En Espera</span><strong style="color:#92400e;">${res['En espera'] || 0}</strong></div>
        <div class="kpi-box" style="background:#fef2f2;"><span>🔴 Negadas</span><strong style="color:#991b1b;">${res['Negada'] || 0}</strong></div>
      `;
      const tbody = document.querySelector('#tabla-solicitudes tbody');
      tbody.innerHTML = d.solicitudes.map(s => `
        <tr>
          <td><strong>${s.radicado}</strong></td>
          <td>${s.fecha_solicitud}</td>
          <td>${s.nombre_animal} (${s.id_animal})<br><small>${s.ciudad_animal}</small></td>
          <td>${s.nombre_solicitante}<br><small>Tel: ${s.telefono}</small></td>
          <td>${s.ciudad_residencia} - ${s.direccion_barrio}<br><small>${s.tipo_vivienda}</small></td>
          <td>${s.motivacion}</td>
          <td><span class="badge ${claseBadgeEstado(s.estado_solicitud)}">${s.estado_solicitud}</span></td>
          <td><small>${s.observacion_comite || ''}</small></td>
          <td style="white-space:nowrap;">
            <button class="btn-sm btn-ok" onclick="cambiarEstado('${s.radicado}', 'Aceptada')">✅ Aceptar</button>
            <button class="btn-sm btn-wait" onclick="cambiarEstado('${s.radicado}', 'En espera')">⏳ En espera</button>
            <button class="btn-sm btn-deny" onclick="cambiarEstado('${s.radicado}', 'Negada')">❌ Negar</button>
          </td>
        </tr>
      `).join('');
    }
    async function cambiarEstado(radicado, nuevoEstado) {
      const r = await fetch(`/adopciones/solicitudes/${radicado}/estado`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nuevo_estado: nuevoEstado })
      });
      const d = await r.json();
      if (r.ok) {
        document.getElementById('mensaje-admin').innerHTML = `<div class="alert">${d.mensaje}</div>`;
        cargarSolicitudes();
      }
    }
    async function evaluarConAirflow() {
      const r = await fetch('/adopciones/evaluar-airflow', { method: 'POST' });
      const d = await r.json();
      if (r.ok) {
        document.getElementById('mensaje-admin').innerHTML = `<div class="alert">🤖 ${d.mensaje}</div>`;
        cargarSolicitudes();
      }
    }
    cargarSolicitudes();
  </script>
</body>
</html>"""


@app.get("/calidad")
def consultar_validaciones_calidad():

    ruta_val = obtener_ruta_validaciones()
    if not ruta_val.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Disculpa, el archivo de validaciones no existe: {ruta_val}"
        )

    df = pd.read_csv(ruta_val)
    resumen = df["estado"].value_counts().to_dict() if "estado" in df.columns else {}
    df = preparar_dataframe_json(df)

    return {
        "total_reglas": len(df),
        "resumen_estados": resumen,
        "Nombres_columnas": df.columns.tolist(),
        "Data": df.to_dict(orient="records"),
    }


@app.get("/health")
def health():

    ruta_gold = obtener_ruta_gold()
    kpis_dir = obtener_directorio_kpis()
    kpis_generados = len(list(kpis_dir.glob("kpi_*.csv"))) if kpis_dir.exists() else 0
    df_cat = asegurar_catalogo_adopciones()

    return {
        "api": "OK",
        "Archivo": ruta_gold.exists(),
        "ruta_gold": str(ruta_gold),
        "kpis_disponibles": kpis_generados,
        "animales_en_catalogo_adopcion": len(df_cat),
    }
