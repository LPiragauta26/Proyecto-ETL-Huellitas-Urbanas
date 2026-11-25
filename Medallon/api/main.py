from datetime import datetime
from pathlib import Path
from typing import Optional
import pandas as pd
from pydantic import BaseModel, Field
import yaml

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse

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


class AdminLoginInput(BaseModel):
    usuario: str = Field(..., description="Usuario administrador (Admin)")
    password: str = Field(..., description="Contraseña administrador (admin123)")


class CambioEstadoAnimalInput(BaseModel):
    nuevo_estado: str = Field(..., description="Estado del animal: 'Disponible', 'En espera' o 'Adoptado'")


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
        "observacion_comite": "Cumple criterios de tenencia responsable, misma ciudad y vivienda segura con mallas.",
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
        "observacion_comite": "En espera de entrevista virtual y verificación de traslado interurbano (Bogotá -> Cali).",
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
        "observacion_comite": "Negada por condiciones sin cerramiento seguro; el animal Bruno regresa a estado Disponible.",
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
        "observacion_comite": "Solicitud en revisión por el Comité de Bienestar Animal.",
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
                    "Negada por condiciones de vivienda sin cerramiento "
                    "o motivación insuficiente de tenencia responsable."
                )
            elif ciudad_anim and ciudad_res and ciudad_anim != ciudad_res or len(motivacion) < 30:
                nuevo_est = "En espera"
                obs = (
                    "En espera de entrevista virtual y verificación "
                    "domiciliaria por comité de bienestar animal."
                )
            else:
                nuevo_est = "Aceptada"
                obs = (
                    "Aceptada; cumple criterios de "
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
                    "Las solicitudes de adopción en Cali disminuyeron un 94,8 %, pasando de 58 casos en 2024 a 3 casos en 2025. "
                    "Ante esta reducción significativa, se habilita este módulo digital de adopción ciudadana, con el objetivo de "
                    "facilitar la adopción responsable de animales y brindarles una segunda oportunidad para disfrutar de una vida "
                    "digna, segura y llena de bienestar."
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


@app.get("/adopciones/consultar-mi-solicitud", tags=["Adopciones"])
def consultar_mi_solicitud_ciudadano(
    q: str = Query(..., description="Número de radicado (ej. ADOP-2026-0001) o documento de identidad"),
):
    """Permite a un ciudadano consultar únicamente el estado de su propia solicitud por radicado o cédula."""
    df_sol = cargar_solicitudes_adopcion()
    buscado = q.strip().upper()
    if df_sol.empty or not buscado:
        return {"encontrado": False, "resultados": []}

    mask = (df_sol["radicado"].astype(str).str.upper() == buscado) | (
        df_sol["documento"].astype(str).str.upper() == buscado
    )
    sub = preparar_dataframe_json(df_sol[mask])
    campos_publicos = [
        "radicado",
        "fecha_solicitud",
        "id_animal",
        "nombre_animal",
        "especie",
        "ciudad_animal",
        "estado_solicitud",
        "observacion_comite",
    ]
    cols = [c for c in campos_publicos if c in sub.columns]
    return {
        "encontrado": bool(len(sub) > 0),
        "resultados": sub[cols].to_dict(orient="records"),
    }


@app.post("/adopciones/animales/{id_animal}/estado", tags=["Panel Privado Creadores"])
def cambiar_estado_animal_admin(id_animal: str, datos: CambioEstadoAnimalInput):
    """Permite a los administradores actualizar el estado de disponibilidad de un animal."""
    df_cat = asegurar_catalogo_adopciones()
    mask = df_cat["id_animal"].astype(str).str.upper() == id_animal.strip().upper()
    if not mask.any():
        raise HTTPException(status_code=404, detail=f"No existe el animal '{id_animal}'.")
    df_cat.loc[mask, "estado"] = datos.nuevo_estado.strip()
    df_cat.to_csv(obtener_ruta_catalogo_adopciones(), index=False, encoding="utf-8-sig")
    return {
        "mensaje": f"Estado del animal {id_animal} actualizado a '{datos.nuevo_estado}'.",
        "animal": preparar_dataframe_json(df_cat[mask]).to_dict(orient="records")[0],
    }


@app.post("/admin/login", tags=["Panel Privado Creadores"])
def login_administrador(credenciales: AdminLoginInput):
    """Valida las credenciales del Panel Privado de Creadores (Usuario: Admin | Contraseña: admin123)."""
    usr = credenciales.usuario.strip()
    pwd = credenciales.password.strip()
    if usr.lower() == "admin" and pwd == "admin123":
        return {
            "autenticado": True,
            "usuario": "Admin",
            "rol": "Creador / Comité de Bienestar Animal",
            "mensaje": "Acceso concedido al Panel Privado de Administración.",
        }
    raise HTTPException(
        status_code=401,
        detail="Credenciales incorrectas. Verifica el usuario y la contraseña de administrador.",
    )


@app.get("/evidencias/{nombre_archivo}", tags=["Evidencias Gráficas"])
def obtener_grafica_evidencia(nombre_archivo: str):
    """Sirve las 8 gráficas PNG generadas por el pipeline ETL para visualización en el portal web y admin."""
    config = cargar_config()
    rutas_cfg = config.get("paths") or {}
    ev_dir = MEDALLON_DIR / rutas_cfg.get("evidencias_dir", "evidencias")
    seguro = Path(nombre_archivo).name
    ruta_img = ev_dir / seguro
    if not ruta_img.exists() or ruta_img.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail=f"La gráfica '{seguro}' no existe en evidencias/.")
    return FileResponse(ruta_img, media_type="image/png")


@app.get("/portal", response_class=HTMLResponse, tags=["Portal Ciudadano"])
def portal_ciudadano_gold_y_adopcion():
    """Interfaz web interactiva dentro de la API para consultar datos Gold, preguntas de negocio y adoptar animales."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>Portal Ciudadano Gold y Adopción — Bienestar Animal (Cali & Bogotá)</title>
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f1f5f9; color: #1e293b; }
    header { background: linear-gradient(135deg, #0f766e, #1e3a8a); color: white; padding: 24px 32px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
    header h1 { margin: 0 0 6px 0; font-size: 24px; }
    header p { margin: 0; opacity: 0.92; font-size: 14px; }
    .btn-admin-link { background: rgba(255,255,255,0.16); color: #ffffff; text-decoration: none; padding: 10px 16px; border-radius: 8px; font-weight: 600; font-size: 13px; border: 1px solid rgba(255,255,255,0.35); transition: 0.2s; }
    .btn-admin-link:hover { background: rgba(255,255,255,0.28); }
    .container { max-width: 1240px; margin: 24px auto; padding: 0 20px; }
    .tabs { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
    .tab-btn { padding: 11px 22px; border: none; border-radius: 10px; cursor: pointer; font-weight: 700; font-size: 14px; background: #e2e8f0; color: #334155; transition: 0.2s; }
    .tab-btn.active { background: #0f766e; color: white; box-shadow: 0 4px 12px rgba(15,118,110,0.25); }
    .panel { display: none; background: white; padding: 26px; border-radius: 14px; box-shadow: 0 4px 16px rgba(0,0,0,0.06); }
    .panel.active { display: block; }
    .grid-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin-top: 16px; }
    .card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; background: #ffffff; transition: transform 0.15s; }
    .card:hover { transform: translateY(-2px); box-shadow: 0 6px 14px rgba(0,0,0,0.06); }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .badge-disp, .badge-aceptada { background: #dcfce7; color: #166534; }
    .badge-proc, .badge-espera { background: #fef3c7; color: #92400e; }
    .badge-negada { background: #fee2e2; color: #991b1b; }
    .badge-rev { background: #e0f2fe; color: #075985; }
    .filters { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; align-items: center; }
    select, input, textarea, button { padding: 9px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }
    button.primary { background: #0f766e; color: white; border: none; font-weight: 600; cursor: pointer; }
    button.primary:hover { background: #115e59; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 9px 10px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
    .alert { padding: 12px 16px; border-radius: 8px; margin-top: 14px; font-weight: 600; }
    .alert-ok { background: #dcfce7; color: #166534; }
    .alert-err { background: #fee2e2; color: #991b1b; }
    /* Estilos para Preguntas de Negocio en Gráficas y FAQ */
    .hero-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 24px; }
    .stat-card { background: linear-gradient(135deg, #f8fafc, #f0fdfa); border: 1px solid #ccfbf1; border-radius: 12px; padding: 16px; text-align: center; }
    .stat-card .num { font-size: 26px; font-weight: 800; color: #0f766e; display: block; }
    .stat-card .lbl { font-size: 13px; color: #475569; font-weight: 600; }
    .charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(520px, 1fr)); gap: 22px; margin-top: 16px; }
    .chart-box { border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; background: #ffffff; box-shadow: 0 2px 8px rgba(0,0,0,0.03); }
    .chart-box h3 { margin: 0 0 8px 0; color: #0f172a; font-size: 17px; }
    .chart-box p.explain { margin: 0 0 14px 0; font-size: 13.5px; color: #475569; line-height: 1.5; }
    .bar-row { margin-bottom: 10px; }
    .bar-label { display: flex; justify-content: space-between; font-size: 12.5px; font-weight: 600; margin-bottom: 4px; color: #334155; }
    .bar-track { width: 100%; background: #f1f5f9; height: 12px; border-radius: 999px; overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 999px; }
    .img-evidencia { width: 100%; border-radius: 8px; border: 1px solid #e2e8f0; margin-top: 12px; }
    .faq-section { margin-top: 32px; }
    details.faq-item { border: 1px solid #cbd5e1; border-radius: 10px; padding: 14px 18px; margin-bottom: 12px; background: #f8fafc; transition: 0.2s; }
    details.faq-item[open] { background: #ffffff; border-color: #0f766e; box-shadow: 0 4px 12px rgba(15,118,110,0.08); }
    details.faq-item summary { font-weight: 700; font-size: 15px; color: #0f172a; cursor: pointer; list-style: none; display: flex; justify-content: space-between; align-items: center; }
    details.faq-item summary::after { content: '➕'; font-size: 14px; color: #0f766e; }
    details.faq-item[open] summary::after { content: '➖'; }
    details.faq-item .faq-body { margin-top: 12px; font-size: 14px; color: #334155; line-height: 1.6; border-top: 1px solid #e2e8f0; padding-top: 10px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>🐾 Huellitas urbanas</h1>
      <p>🐾 Portal Ciudadano: Bienestar Animal, Preguntas de Negocio y Adopción (Cali & Bogotá)</p>
    </div>
    <div>
      <a href="/admin" class="btn-admin-link">🔐 Acceso Admin / Creadores</a>
    </div>
  </header>

  <div class="container">
    <div class="tabs">
      <button class="tab-btn active" onclick="mostrarTab('negocio', this)">📈 Preguntas de Negocio (Gráficas y Preguntas Frecuentes)</button>
      <button class="tab-btn" onclick="mostrarTab('adopcion', this)">🐶 Adoptar un Animal Rescatado</button>
      <button class="tab-btn" onclick="mostrarTab('gold', this)">📊 Explorador de Datos Abiertos (Gold)</button>
    </div>

    <!-- PANEL 1: PREGUNTAS DE NEGOCIO (GRÁFICAS + FAQ CIUDADANO) -->
    <div id="panel-negocio" class="panel active">
      <h2 style="margin-top:0;">📈 Hallazgos y Preguntas de Negocio del Proyecto Bienestar Animal</h2>
      <p style="color:#475569; font-size:14.5px; margin-bottom:20px;">
        Descubre de forma visual qué revelaron los <strong>17.642 reportes de Cali</strong> y las <strong>947 urgencias veterinarias de Bogotá</strong> tras pasar por nuestro pipeline de datos Medallion:
      </p>

      <div class="hero-stats">
        <div class="stat-card"><span class="num">17.642</span><span class="lbl">Solicitudes Procesadas en Cali (100% conservadas)</span></div>
        <div class="stat-card"><span class="num">947</span><span class="lbl">Urgencias Veterinarias en 20 Localidades de Bogotá</span></div>
        <div class="stat-card"><span class="num">-94,8%</span><span class="lbl">Caída de Adopciones en Cali (2024 vs 2025)</span></div>
        <div class="stat-card"><span class="num">42 Zonas</span><span class="lbl">Comunas y Corregimientos Homologados (de 83 crudos)</span></div>
      </div>

      <h3 style="color:#0f766e; border-bottom:2px solid #ccfbf1; padding-bottom:8px;">📊 Parte 1: Preguntas de Negocio Explicadas con Gráficas</h3>
      <div class="charts-grid">

        <!-- PREGUNTA GRÁFICA 1 -->
        <div class="chart-box">
          <h3>1. ¿Dónde se concentran más casos y urgencias de animales en Cali?</h3>
          <p class="explain">
            Al cruzar los casos con la población oficial de cada comuna, creamos un <strong>Índice de Priorización (0 a 100)</strong>. La <strong>Comuna 20 (Siloé)</strong> lidera con <strong>2.310 solicitudes y puntaje 99,1</strong>, seguida de la Comuna 18 y Comuna 13. En zona rural lideran <strong>La Buitrera (213 casos)</strong> y <strong>Villacarmelo</strong>.
          </p>
          <div class="bar-row">
            <div class="bar-label"><span>🥇 Comuna 20 (Urbana - Prioridad #1: 99,1 pts)</span><span>2.310 casos (156 críticos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:100%; background:#0f766e;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🥈 Comuna 18 (Urbana - Prioridad #2: 61,9 pts)</span><span>1.441 casos (96 críticos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:62.4%; background:#14b8a6;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🥉 Comuna 13 (Urbana - Prioridad #4: 47,5 pts)</span><span>1.146 casos (75 críticos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:49.6%; background:#0284c7;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>4️⃣ Comuna 14 (Urbana - Prioridad #5: 46,5 pts)</span><span>1.084 casos (74 críticos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:46.9%; background:#38bdf8;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>5️⃣ Comuna 21 (Urbana - Prioridad #3: 47,8 pts)</span><span>961 casos (90 críticos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:41.6%; background:#6366f1;"></div></div>
          </div>
          <img class="img-evidencia" src="/evidencias/01_casos_por_comuna.png" alt="Gráfica Top Comunas Cali" />
        </div>

        <!-- PREGUNTA GRÁFICA 2 -->
        <div class="chart-box">
          <h3>2. ¿Cómo cambió la atención entre 2024 y 2025 y por qué es urgente adoptar?</h3>
          <p class="explain">
            Entre 2024 y 2025 la atención en Cali pasó de preventiva a clínica de emergencia: las <strong>Urgencias subieron +137,7%</strong> y las <strong>Citas médicas +81,3%</strong>, pero las <strong>Esterilizaciones cayeron -91,8%</strong> y las <strong>Adopciones cayeron -94,8% (de 58 a solo 3 casos)</strong>. Por eso creamos este Portal Digital de Adopción.
          </p>
          <div class="bar-row">
            <div class="bar-label"><span>🚨 Urgencias Veterinarias (2024: 260 → 2025: 618)</span><span style="color:#dc2626;">+137,7% incremento</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:92%; background:#dc2626;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🩺 Citas Médicas (2024: 1.581 → 2025: 2.866)</span><span style="color:#0284c7;">+81,3% incremento</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:78%; background:#0284c7;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>✂️ Esterilizaciones (2024: 1.822 → 2025: 149)</span><span style="color:#d97706;">-91,8% caída</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:15%; background:#d97706;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🐾 Adopciones (2024: 58 → 2025: 3 casos)</span><span style="color:#991b1b;">-94,8% caída crítica</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:8%; background:#991b1b;"></div></div>
          </div>
          <img class="img-evidencia" src="/evidencias/05_cambio_mix_2024_vs_2025.png" alt="Gráfica Cambio Mix 2024 vs 2025" />
        </div>

        <!-- PREGUNTA GRÁFICA 3 -->
        <div class="chart-box">
          <h3>3. ¿Cuáles son los barrios más críticos ("Hotspots") de Cali?</h3>
          <p class="explain">
            Al bajar al nivel de barrio, descubrimos que un solo barrio —<strong>Siloé (Comuna 20)</strong>— concentra <strong>662 solicitudes y 78 casos críticos</strong> (53 urgencias + 25 denuncias), superando por sí solo a 15 comunas completas de la ciudad.
          </p>
          <div class="bar-row">
            <div class="bar-label"><span>🔥 1. Siloé (Comuna 20)</span><span>662 casos | 78 críticos (53 urg / 25 den)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:100%; background:#b91c1c;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🔥 2. Terrón Colorado (Comuna 1)</span><span>288 casos | 53 críticos (34 urg / 19 den)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:68%; background:#ea580c;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🔥 3. Los Chorros (Comuna 18)</span><span>236 casos | 32 críticos (25 urg / 7 den)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:41%; background:#d97706;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🔥 4. Manuela Beltrán (Comuna 14)</span><span>121 casos | 22 críticos (18 urg / 4 den)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:28%; background:#0f766e;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🔥 5. Ciudad Córdoba (Comuna 15)</span><span>101 casos | 22 críticos (7 urg / 15 den)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:28%; background:#0284c7;"></div></div>
          </div>
          <img class="img-evidencia" src="/evidencias/07_top_barrios_criticos_cali.png" alt="Gráfica Top Barrios Críticos Cali" />
        </div>

        <!-- PREGUNTA GRÁFICA 4 -->
        <div class="chart-box">
          <h3>4. ¿Qué ocurre en Bogotá al separar la sede UCA (Engativá) del resto de la ciudad?</h3>
          <p class="explain">
            <strong>Engativá concentra el 69,3% de las atenciones de Bogotá (656 de 947)</strong> porque allí está ubicada físicamente la <strong>Unidad de Cuidado Animal (UCA)</strong>. Al aislar las otras <strong>19 localidades (291 urgencias en calle)</strong>, emerge el perfil real: <strong>84,9% ingresa por reporte ciudadano</strong> y lideran las <strong>enfermedades infecciosas (47,1%)</strong> y <strong>atropellamientos/politraumatismos (20,6%)</strong>.
          </p>
          <div class="bar-row">
            <div class="bar-label"><span>🏥 Engativá (Sede física UCA - 656 atenciones)</span><span>69,3% del total Bogotá</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:69.3%; background:#1e3a8a;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🌆 Resto de las 19 Localidades (Ciudad Bolívar, Suba, Usme, Bosa...)</span><span>30,7% (291 en calle)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:30.7%; background:#0f766e;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🦠 Diagnóstico #1 en las 19 localidades: Infeccioso</span><span>47,1% (137 casos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:47.1%; background:#d97706;"></div></div>
          </div>
          <div class="bar-row">
            <div class="bar-label"><span>🚑 Diagnóstico #2 en las 19 localidades: Politraumatismo vial</span><span>20,6% (60 casos)</span></div>
            <div class="bar-track"><div class="bar-fill" style="width:20.6%; background:#dc2626;"></div></div>
          </div>
          <img class="img-evidencia" src="/evidencias/08_bogota_sesgo_uca_vs_resto.png" alt="Gráfica Bogotá Engativá vs Resto" />
        </div>

      </div>

      <!-- PARTE 2: PREGUNTAS FRECUENTES (FAQ SIN GRÁFICAS) -->
      <div class="faq-section">
        <h3 style="color:#1e3a8a; border-bottom:2px solid #dbeafe; padding-bottom:8px;">❓ Parte 2: Preguntas Frecuentes de Negocio y Ciudadanía (Haz clic en cada pregunta)</h3>

        <details class="faq-item" open>
          <summary>1. ¿En qué zonas de Cali hay más denuncias de maltrato animal frente a baja esterilización?</summary>
          <div class="faq-body">
            Nuestro indicador de <strong>Brecha de Prevención (`kpi_brecha_prevencion_zona`)</strong> reveló dos perfiles distintos en Cali:<br>
            • <strong>Comunas con alta denuncia de maltrato y baja esterilización pública:</strong> La <strong>Comuna 17</strong> es la #1 en denuncias de toda Cali (<strong>112 denuncias</strong>, 27% de sus reportes) con solo 37 esterilizaciones (ratio preventivo de <code>0,31</code>). Igual sucede en la <strong>Comuna 22</strong> (donde el <strong>41,8%</strong> de todos sus casos son denuncias de maltrato y tiene la tasa más alta: <strong>40,36 denuncias por cada 10.000 habitantes</strong>) y el corregimiento de <strong>Pance</strong> (26,8% denuncias). En estas zonas la prioridad es inspección de tenencia responsable y control policivo.<br>
            • <strong>Comunas vulnerables con déficit de jornadas preventivas:</strong> <strong>Comuna 1 (Terrón Colorado)</strong> tiene 104 casos críticos frente a solo 72 esterilizaciones (ratio <code>0,69</code>), por lo que requiere brigadas móviles gratuitas de esterilización.
          </div>
        </details>

        <details class="faq-item">
          <summary>2. ¿Qué días de la semana se atienden más animales y cuándo se hacen las jornadas de esterilización?</summary>
          <div class="faq-body">
            Según el análisis de <strong>Patrón Semanal Operativo (`kpi_patron_semanal_cali`)</strong>:<br>
            • El <strong>80,6% de la demanda</strong> ingresa en días hábiles (lunes a viernes), alcanzando el pico máximo los <strong>martes (3.052 casos)</strong> y <strong>miércoles (2.886 casos)</strong>.<br>
            • Los <strong>sábados (1.856 casos)</strong> destacan porque concentran la <strong>mayor proporción relativa de Esterilizaciones de toda la semana (14,5% de los servicios del día)</strong> gracias a las jornadas comunitarias de fin de semana en barrios.
          </div>
        </details>

        <details class="faq-item">
          <summary>3. ¿Por qué faltaban datos de barrio o comuna en algunos registros y cómo lo corrigió el proyecto (OKR 3)?</summary>
          <div class="faq-body">
            La auditoría de <strong>Calidad por Clase (`kpi_calidad_por_clase`)</strong> demostró que los vacíos geográficos no son al azar:<br>
            • El <strong>81,2% de los registros sin comuna</strong> proviene del canal administrativo de <strong>PQR</strong>.<br>
            • En <strong>Esterilizaciones</strong> sí se registra la comuna (98,2% completas), pero el <strong>67,1% no tiene barrio</strong> porque en los operativos móviles masivos solo se anota la comuna del evento.<br>
            • <strong>Solución de Ingeniería de Datos:</strong> Sin eliminar ni un solo registro (<strong>17.642 → 17.642</strong>), estandarizamos <strong>83 variantes mal escritas de comunas en 42 zonas oficiales</strong>, recuperamos comunas faltantes inferidas automáticamente desde el nombre del barrio (con ≥95% de acuerdo) y corregimos 15 fechas con año mal digitado (<code>0225 → 2025</code>).
          </div>
        </details>

        <details class="faq-item">
          <summary>4. ¿Se pueden comparar directamente todos los números de Cali (17.642) con los de Bogotá (947)?</summary>
          <div class="faq-body">
            No directamente en su totalidad, y por eso construimos una <strong>tabla de homologación (`dim_categoria.csv`)</strong>:<br>
            • El dataset de <strong>Cali (CBA/Uaepa)</strong> registra <em>todas</em> las interacciones ciudadanas individuales (PQR, citas médicas, esterilizaciones, denuncias, urgencias y adopciones).<br>
            • El dataset abierto de <strong>Bogotá (IDPYBA)</strong> reporta exclusivamente <strong>atenciones clínicas de urgencia veterinaria agregadas en las 20 localidades</strong>.<br>
            • Al homologar ambas fuentes en la capa Gold, la categoría directamente comparable 1 a 1 es <strong>Urgencias Veterinarias</strong>: <strong>879 urgencias en Cali vs. 947 urgencias en Bogotá</strong>.
          </div>
        </details>

        <details class="faq-item">
          <summary>5. ¿Cómo funciona la postulación para adoptar un perro o gato rescatado en este portal?</summary>
          <div class="faq-body">
            1. Ve a la pestaña <strong>🐶 Adoptar un Animal Rescatado</strong> y elige uno de los animales rehabilitados por el CBA (Cali) o la UCA/IDPYBA (Bogotá).<br>
            2. Completa el formulario con tus datos de contacto, tipo de vivienda y motivación de tenencia responsable. Recibirás un <strong>número de radicado único</strong> (ej. <code>ADOP-2026-0001</code>).<br>
            3. Nuestro sistema automatizado en <strong>Apache Airflow</strong> y el <strong>Comité de Bienestar Animal</strong> evalúan la solicitud y la clasifican en:<br>
            &nbsp;&nbsp;• 🟢 <strong>Aceptada:</strong> Cumple condiciones de vivienda con cerramiento seguro y tenencia responsable (el animal pasa a estado <em>Adoptado</em>).<br>
            &nbsp;&nbsp;• 🟡 <strong>En espera:</strong> Pendiente de entrevista virtual o verificación domiciliaria/traslado.<br>
            &nbsp;&nbsp;• 🔴 <strong>Negada:</strong> Si la vivienda no cuenta con condiciones seguras; el animal vuelve automáticamente a estar <em>Disponible</em> para otra familia.<br>
            4. Puedes consultar el estado de tu propio trámite en cualquier momento ingresando tu radicado o cédula en la pestaña de Adopción.
          </div>
        </details>
      </div>
    </div>

    <!-- PANEL 2: ADOPCIONES (VISTA PÚBLICA CIUDADANA) -->
    <div id="panel-adopcion" class="panel">
      <h2>🐾 Animales Rescatados y Rehabilitados listos para Adopción</h2>
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

      <hr style="margin: 28px 0; border: none; border-top: 1px solid #e2e8f0;" />
      <h3>🔍 Consultar el Estado de mi Solicitud (Por Radicado o Documento)</h3>
      <p style="font-size:13.5px; color:#475569; margin-top:0;">Ingresa tu número de radicado (ej. <code>ADOP-2026-0001</code>) o tu documento de identidad para conocer si tu solicitud fue <strong>Aceptada</strong>, está <strong>En espera</strong> o fue <strong>Negada</strong>:</p>
      <div class="filters">
        <input type="text" id="q-radicado" placeholder="Ej. ADOP-2026-0001 o tu cédula" style="min-width:260px;" />
        <button type="button" class="primary" onclick="consultarMiSolicitud()">Consultar mi estado</button>
      </div>
      <div id="resultado-mi-solicitud"></div>
    </div>

    <!-- PANEL 3: CONSULTA GOLD -->
    <div id="panel-gold" class="panel">
      <h2>📊 Explorador Ciudadano de la Capa Gold (`gold_final.csv`)</h2>
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
        document.getElementById('alerta-etl').innerText = '📌 Hallazgo identificado: ' + d.hallazgo_etl_2024_vs_2025.alerta_negocio;
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

    async function consultarMiSolicitud() {
      const q = document.getElementById('q-radicado').value.trim();
      const cont = document.getElementById('resultado-mi-solicitud');
      if (!q) {
        cont.innerHTML = `<div class="alert alert-err">Por favor escribe tu número de radicado o documento.</div>`;
        return;
      }
      const r = await fetch('/adopciones/consultar-mi-solicitud?q=' + encodeURIComponent(q));
      const d = await r.json();
      if (!d.encontrado) {
        cont.innerHTML = `<div class="alert alert-err">No encontramos ninguna solicitud con el radicado o documento "${q}".</div>`;
        return;
      }
      cont.innerHTML = d.resultados.map(s => `
        <div class="card" style="margin-top:10px; border-left:4px solid #0f766e;">
          <strong>Radicado: ${s.radicado}</strong> (${s.fecha_solicitud}) — Animal: <strong>${s.nombre_animal} (${s.id_animal})</strong><br>
          <div style="margin-top:6px;">Estado actual: <span class="badge ${claseBadgeEstado(s.estado_solicitud)}">${s.estado_solicitud}</span></div>
          <p style="margin:6px 0 0 0; font-size:13px; color:#334155;"><strong>Observación del Comité:</strong> ${s.observacion_comite || 'En evaluación'}</p>
        </div>
      `).join('');
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
    """Panel privado exclusivo para los creadores / Comité de Bienestar Animal protegido con contraseña (Admin / admin123)."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <title>🔐 Panel Privado Creadores y Comité — Bienestar Animal</title>
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #0f172a; color: #1e293b; }
    header { background: linear-gradient(135deg, #1e293b, #0f766e); color: white; padding: 20px 32px; border-bottom: 3px solid #14b8a6; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; }
    header h1 { margin: 0 0 4px 0; font-size: 22px; }
    header p { margin: 0; opacity: 0.9; font-size: 13px; }
    .container { max-width: 1280px; margin: 24px auto; padding: 0 20px; }
    .panel { background: white; padding: 24px; border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.25); margin-bottom: 20px; }
    .login-box { max-width: 420px; margin: 60px auto; background: white; padding: 32px; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,0.4); text-align: center; }
    .login-box h2 { margin-top: 0; color: #0f172a; }
    .login-box input { width: 100%; box-sizing: border-box; margin-bottom: 14px; padding: 10px 12px; border: 1px solid #cbd5e1; border-radius: 8px; font-size: 14px; }
    .admin-tabs { display: flex; gap: 10px; margin-bottom: 18px; flex-wrap: wrap; }
    .admin-tab-btn { padding: 10px 18px; border: none; border-radius: 8px; cursor: pointer; font-weight: 700; background: #334155; color: #e2e8f0; }
    .admin-tab-btn.active { background: #14b8a6; color: #0f172a; }
    .admin-section { display: none; }
    .admin-section.active { display: block; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
    .badge-aceptada, .badge-ok { background: #dcfce7; color: #166534; }
    .badge-espera, .badge-adv { background: #fef3c7; color: #92400e; }
    .badge-negada, .badge-err { background: #fee2e2; color: #991b1b; }
    .badge-rev { background: #e0f2fe; color: #075985; }
    button.primary { padding: 9px 16px; background: #0f766e; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
    button.danger { padding: 8px 14px; background: #dc2626; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
    .btn-sm { padding: 5px 10px; font-size: 12px; font-weight: 600; border: none; border-radius: 6px; cursor: pointer; margin-right: 4px; }
    .btn-ok { background: #16a34a; color: white; }
    .btn-wait { background: #d97706; color: white; }
    .btn-deny { background: #dc2626; color: white; }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }
    th, td { border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }
    th { background: #f8fafc; font-weight: 600; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin: 14px 0; }
    .kpi-box { padding: 14px 16px; border-radius: 10px; border: 1px solid #e2e8f0; background: #f8fafc; text-align: center; }
    .kpi-box strong { display: block; font-size: 22px; margin-top: 4px; }
    .alert { padding: 12px 16px; border-radius: 8px; margin-top: 12px; font-weight: 600; background: #dcfce7; color: #166534; }
    .alert-err { background: #fee2e2; color: #991b1b; }
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr)); gap: 16px; margin-top: 16px; }
    .gallery-card { border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; background: #f8fafc; }
    .gallery-card img { width: 100%; border-radius: 6px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>🔐 Panel Privado de Creadores y Comité de Bienestar Animal</h1>
      <p>Control de Adopciones | <a href="/portal" style="color:#99f6e4;">Ir al Portal Público (/portal)</a> | <a href="/docs" style="color:#99f6e4;">Swagger (/docs)</a></p>
    </div>
    <div id="zona-logout" style="display:none;">
      <span style="margin-right:12px; font-size:13px;">👤 Sesión activa: <strong>Admin</strong></span>
      <button class="danger" onclick="cerrarSesion()">🚪 Cerrar Sesión</button>
    </div>
  </header>

  <!-- PANTALLA DE LOGIN CON CONTRASEÑA -->
  <div id="vista-login" class="login-box">
    <div style="font-size:42px; margin-bottom:8px;">🔒</div>
    <h2>Ingreso Exclusivo Creadores</h2>
    <p style="font-size:13.5px; color:#64748b; margin-bottom:20px;">
      Ingresa las credenciales de administrador para acceder a la Bandeja del Comité de Adopciones, Airflow y Auditoría ETL.
    </p>
    <form onsubmit="iniciarSesion(event)">
      <input type="text" id="usr-admin" placeholder="Usuario (Admin)" required />
      <input type="password" id="pwd-admin" placeholder="Contraseña" required />
      <button type="submit" class="primary" style="width:100%; padding:11px;">Ingresar al Panel de Administración</button>
    </form>
    <div id="msg-login"></div>
  </div>

  <!-- CONTENIDO PRIVADO DE ADMINISTRACIÓN (OCULTO HASTA INICIAR SESIÓN) -->
  <div id="vista-admin" class="container" style="display:none;">
    <div class="admin-tabs">
      <button class="admin-tab-btn active" onclick="mostrarSeccionAdmin('solicitudes', this)">📋 1. Comité de Solicitudes (Aceptar / En espera / Negar + Airflow)</button>
      <button class="admin-tab-btn" onclick="mostrarSeccionAdmin('animales', this)">🐾 2. Gestión de Animales Rescatados</button>
      <button class="admin-tab-btn" onclick="mostrarSeccionAdmin('calidad', this)">🏛️ 3. Monitor ETL Medallion & 14 Reglas de Calidad</button>
      <button class="admin-tab-btn" onclick="mostrarSeccionAdmin('kpis', this)">📊 4. Explorador de los 13 KPIs y 8 Gráficas PNG</button>
    </div>

    <!-- SECCIÓN 1: BANDEJA DE SOLICITUDES -->
    <div id="sec-solicitudes" class="admin-section active">
      <div class="panel">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
          <h2 style="margin:0;">📋 Bandeja de Solicitudes y Comité de Bienestar Animal (Control Manual + Airflow)</h2>
          <button class="primary" onclick="evaluarConAirflow()">⚙️ Evaluar Pendientes con Reglas Airflow</button>
        </div>
        <div id="mensaje-admin"></div>
        <div id="resumen-solicitudes" class="kpi-row"></div>
        <div style="margin:10px 0;">
          <input type="text" id="obs-personalizada" placeholder="Observación opcional del Comité antes de hacer clic en Aceptar / En espera / Negar..." style="width:100%; box-sizing:border-box; padding:8px 12px; border:1px solid #cbd5e1; border-radius:6px;" />
        </div>
        <div style="overflow-x:auto;">
          <table id="tabla-solicitudes">
            <thead>
              <tr>
                <th>Radicado</th>
                <th>Fecha</th>
                <th>Animal</th>
                <th>Solicitante y Contacto</th>
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

    <!-- SECCIÓN 2: GESTIÓN DE ANIMALES -->
    <div id="sec-animales" class="admin-section">
      <div class="panel">
        <h2 style="margin-top:0;">🐾 Inventario de Animales Rescatados (Cali CBA & Bogotá IDPYBA)</h2>
        <p style="font-size:13.5px; color:#475569;">Desde aquí los creadores pueden cambiar o liberar manualmente el estado de cualquier animal en el catálogo:</p>
        <div style="overflow-x:auto;">
          <table id="tabla-admin-animales">
            <thead>
              <tr>
                <th>Código</th>
                <th>Nombre / Especie</th>
                <th>Ciudad y Zona Rescate</th>
                <th>Entidad</th>
                <th>Caso Origen ETL</th>
                <th>Estado Actual</th>
                <th>Cambiar Estado</th>
              </tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- SECCIÓN 3: MONITOR ETL Y 14 REGLAS DE CALIDAD -->
    <div id="sec-calidad" class="admin-section">
      <div class="panel">
        <h2 style="margin-top:0;">🏛️ Estado de la Arquitectura Medallion y Data Warehouse SQLite</h2>
        <div class="kpi-row">
          <div class="kpi-box"><span>🥉 Bronze (Cali + Bogotá + API)</span><strong>17.642 + 20 loc.</strong><small>SHA-256 verificado</small></div>
          <div class="kpi-box"><span>🥈 Silver (Zonas Homologadas)</span><strong>83 → 42 zonas</strong><small>0 registros perdidos</small></div>
          <div class="kpi-box"><span>🥇 Gold (`gold_final.csv`)</span><strong>404 filas | 13 KPIs</strong><small>0 duplicados de llave</small></div>
          <div class="kpi-box"><span>🗄️ Data Warehouse (`warehouse.db`)</span><strong>18 Tablas SQLite</strong><small>Carga idempotente</small></div>
        </div>
        <h3>✅ Auditoría de las 14 Reglas de Validación de Calidad (`validaciones_calidad.csv`)</h3>
        <div style="overflow-x:auto;">
          <table id="tabla-admin-calidad">
            <thead>
              <tr><th>Etapa</th><th>Regla de Calidad</th><th>Valor Observado</th><th>Umbral / Esperado</th><th>Estado</th><th>Detalle</th></tr>
            </thead>
            <tbody></tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- SECCIÓN 4: EXPLORADOR DE LOS 13 KPIS Y 8 GRÁFICAS -->
    <div id="sec-kpis" class="admin-section">
      <div class="panel">
        <h2 style="margin-top:0;">📊 Explorador Interno de las 13 Tablas KPI de Negocio</h2>
        <div style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:12px;">
          <label><strong>Seleccionar KPI:</strong></label>
          <select id="sel-kpi-admin" onchange="cargarKpiAdmin()" style="min-width:340px; padding:8px;"></select>
        </div>
        <p id="desc-kpi-admin" style="font-size:13.5px; color:#0f766e; font-weight:600;"></p>
        <div style="max-height:380px; overflow:auto;">
          <table id="tabla-kpi-admin"><thead></thead><tbody></tbody></table>
        </div>

        <hr style="margin:28px 0; border:none; border-top:1px solid #e2e8f0;" />
        <h3>🖼️ Galería Completa de las 8 Gráficas PNG de Evidencia (`evidencias/`)</h3>
        <div class="gallery-grid">
          <div class="gallery-card"><strong>01. Casos por Comuna (Cali)</strong><img src="/evidencias/01_casos_por_comuna.png" /></div>
          <div class="gallery-card"><strong>02. Evolución Mensual 2024–2025</strong><img src="/evidencias/02_evolucion_mensual.png" /></div>
          <div class="gallery-card"><strong>03. Urgencias Cali vs Bogotá</strong><img src="/evidencias/03_urgencias_cali_vs_bogota.png" /></div>
          <div class="gallery-card"><strong>04. Calidad Antes vs Después (OKR 3)</strong><img src="/evidencias/04_calidad_antes_despues.png" /></div>
          <div class="gallery-card"><strong>05. Cambio Mix 2024 vs 2025</strong><img src="/evidencias/05_cambio_mix_2024_vs_2025.png" /></div>
          <div class="gallery-card"><strong>06. Brecha Prevención vs Críticos</strong><img src="/evidencias/06_brecha_prevencion_vs_criticos.png" /></div>
          <div class="gallery-card"><strong>07. Top Barrios Críticos Cali</strong><img src="/evidencias/07_top_barrios_criticos_cali.png" /></div>
          <div class="gallery-card"><strong>08. Bogotá Sesgo UCA vs Resto</strong><img src="/evidencias/08_bogota_sesgo_uca_vs_resto.png" /></div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function mostrarSeccionAdmin(id, btn) {
      document.querySelectorAll('.admin-section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.admin-tab-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('sec-' + id).classList.add('active');
      btn.classList.add('active');
    }

    async function iniciarSesion(e) {
      e.preventDefault();
      const usuario = document.getElementById('usr-admin').value;
      const password = document.getElementById('pwd-admin').value;
      const r = await fetch('/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario, password })
      });
      const d = await r.json();
      if (r.ok && d.autenticado) {
        sessionStorage.setItem('admin_autenticado', '1');
        activarVistaAdmin();
      } else {
        document.getElementById('msg-login').innerHTML = `<div class="alert alert-err">${d.detail || 'Usuario o contraseña incorrectos'}</div>`;
      }
    }

    function cerrarSesion() {
      sessionStorage.removeItem('admin_autenticado');
      document.getElementById('vista-admin').style.display = 'none';
      document.getElementById('zona-logout').style.display = 'none';
      document.getElementById('vista-login').style.display = 'block';
      document.getElementById('pwd-admin').value = '';
    }

    function activarVistaAdmin() {
      document.getElementById('vista-login').style.display = 'none';
      document.getElementById('vista-admin').style.display = 'block';
      document.getElementById('zona-logout').style.display = 'block';
      cargarSolicitudes();
      cargarAnimalesAdmin();
      cargarCalidadAdmin();
      inicializarSelectorKpis();
    }

    function claseBadgeEstado(est) {
      if (est === 'Aceptada' || est === 'Disponible' || est === 'OK') return 'badge-aceptada';
      if (est === 'En espera' || est === 'ADVERTENCIA') return 'badge-espera';
      if (est === 'Negada' || est === 'FALLA') return 'badge-negada';
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
          <td><strong>${s.nombre_animal}</strong> (${s.id_animal})<br><small>${s.especie} - ${s.ciudad_animal}</small></td>
          <td><strong>${s.nombre_solicitante}</strong><br><small>CC: ${s.documento} | Tel: ${s.telefono}<br>${s.correo}</small></td>
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
      const obs = document.getElementById('obs-personalizada').value.trim();
      const payload = { nuevo_estado: nuevoEstado };
      if (obs) payload.observacion = obs;
      const r = await fetch(`/adopciones/solicitudes/${radicado}/estado`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const d = await r.json();
      if (r.ok) {
        document.getElementById('mensaje-admin').innerHTML = `<div class="alert">${d.mensaje}</div>`;
        document.getElementById('obs-personalizada').value = '';
        cargarSolicitudes();
        cargarAnimalesAdmin();
      }
    }

    async function evaluarConAirflow() {
      const r = await fetch('/adopciones/evaluar-airflow', { method: 'POST' });
      const d = await r.json();
      if (r.ok) {
        document.getElementById('mensaje-admin').innerHTML = `<div class="alert">🤖 ${d.mensaje}</div>`;
        cargarSolicitudes();
        cargarAnimalesAdmin();
      }
    }

    async function cargarAnimalesAdmin() {
      const r = await fetch('/adopciones/animales');
      const d = await r.json();
      const tbody = document.querySelector('#tabla-admin-animales tbody');
      tbody.innerHTML = d.animales.map(a => `
        <tr>
          <td><strong>${a.id_animal}</strong></td>
          <td>${a.especie === 'Canino' ? '🐶' : '🐱'} <strong>${a.nombre}</strong> (${a.edad_aprox}, ${a.sexo})</td>
          <td>${a.ciudad} — ${a.zona_rescate} (${a.barrio_rescate})</td>
          <td>${a.entidad}</td>
          <td>ID #${a.id_caso_origen_etl}</td>
          <td><span class="badge ${claseBadgeEstado(a.estado)}">${a.estado}</span></td>
          <td style="white-space:nowrap;">
            <button class="btn-sm btn-ok" onclick="cambiarEstadoAnimal('${a.id_animal}', 'Disponible')">Disponible</button>
            <button class="btn-sm btn-wait" onclick="cambiarEstadoAnimal('${a.id_animal}', 'En espera')">En espera</button>
            <button class="btn-sm btn-deny" onclick="cambiarEstadoAnimal('${a.id_animal}', 'Adoptado')">Adoptado</button>
          </td>
        </tr>
      `).join('');
    }

    async function cambiarEstadoAnimal(idAnimal, nuevoEstado) {
      const r = await fetch(`/adopciones/animales/${idAnimal}/estado`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nuevo_estado: nuevoEstado })
      });
      if (r.ok) cargarAnimalesAdmin();
    }

    async function cargarCalidadAdmin() {
      const r = await fetch('/calidad');
      const d = await r.json();
      const tbody = document.querySelector('#tabla-admin-calidad tbody');
      tbody.innerHTML = (d.Data || []).map(f => `
        <tr>
          <td><strong>${f.etapa || 'ETL'}</strong></td>
          <td>${f.regla || ''}</td>
          <td>${f.valor_actual ?? f.valor ?? ''}</td>
          <td>${f.umbral ?? f.esperado ?? ''}</td>
          <td><span class="badge ${claseBadgeEstado(f.estado)}">${f.estado}</span></td>
          <td><small>${f.detalle || ''}</small></td>
        </tr>
      `).join('');
    }

    async function inicializarSelectorKpis() {
      const r = await fetch('/kpis');
      const d = await r.json();
      const sel = document.getElementById('sel-kpi-admin');
      sel.innerHTML = (d.kpis || []).map(k => `<option value="${k.kpi}">${k.kpi} — ${k.descripcion}</option>`).join('');
      cargarKpiAdmin();
    }

    async function cargarKpiAdmin() {
      const nombre = document.getElementById('sel-kpi-admin').value;
      if (!nombre) return;
      const r = await fetch('/kpis/' + nombre);
      const d = await r.json();
      document.getElementById('desc-kpi-admin').innerText = `${d.descripcion} (${d.total_registros} registros)`;
      const cols = d.Nombres_columnas || [];
      document.querySelector('#tabla-kpi-admin thead').innerHTML = '<tr>' + cols.map(c => `<th>${c}</th>`).join('') + '</tr>';
      document.querySelector('#tabla-kpi-admin tbody').innerHTML = (d.Data || []).map(row =>
        '<tr>' + cols.map(c => `<td>${row[c] ?? ''}</td>`).join('') + '</tr>'
      ).join('');
    }

    if (sessionStorage.getItem('admin_autenticado') === '1') {
      activarVistaAdmin();
    }
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
