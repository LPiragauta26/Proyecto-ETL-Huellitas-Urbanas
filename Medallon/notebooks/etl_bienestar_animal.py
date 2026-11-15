
# # ETL con arquitectura medallón: bienestar animal en Cali (CBA/Uaepa) frente a Bogotá (IDPYBA)
#
# Este notebook ejecuta **todo el proceso** paso a paso y muestra, en orden:
#
# 1. Contexto y fuentes
# 2. Datos sin modificar (extracción, capa **bronze**)
# 3. EDA y problemas encontrados en el dato crudo
# 4. Limpieza (capa **silver**)
# 5. Integración con JOIN y KPIs (capa **gold**)
# 6. Validación y evidencias
# 7. Resumen y conclusiones

import os
import sys

if os.path.basename(os.getcwd()) == "notebooks":
    os.chdir("..")
sys.path.insert(0, os.getcwd())

import pandas as pd
from IPython.display import Image, display

import src.extract.extract_api as api
import src.extract.extract_csv as extraer_csv
import src.extract.extract_geojson as extraer_geo
import src.quality.quality_checks as calidad
import src.transform.clean_bogota as limpieza_bogota
import src.transform.clean_cali as limpieza_cali
import src.transform.gold_data as gold
import src.utils.graficos as graficos
from src.utils.helpers import cargar_config

pd.set_option("display.width", 200)
cfg = cargar_config()
p, s = cfg["paths"], cfg["sources"]
print("Carpeta de trabajo:", os.getcwd())
print("Proyecto:", cfg["project"]["name"])

# %% [markdown]
# ## 1. Contexto y fuentes
#
# En Cali, la Uaepa (a través del Centro de Bienestar Animal, CBA) gestiona solicitudes de abandono, maltrato, citas médicas, esterilizaciones, urgencias y adopciones, pero su registro tiene vacíos geográficos que dificultan la toma de decisiones. Además, se compara con Bogotá (IDPYBA).
#
# | Fuente | Formato | Qué contiene |
# |---|---|---|
# | **CBA / Uaepa, Cali** | Excel (convertido desde el CSV original de Datos Abiertos Cali) | 17.642 solicitudes, un registro por caso |
# | **IDPYBA, Bogotá** | GeoJSON | Atenciones veterinarias de urgencia por localidad (20 localidades, corte 30/06/2025) |
# | **Población de Cali por comuna y corregimiento** | **API REST** (Datos Abiertos de Cali, CKAN) | Proyecciones 2006-2020; se usa 2020 |

# %% [markdown]
# ## 2. EXTRACCIÓN (capa bronze)
#
# Los datos se leen **sin modificar**. El CSV original se conserva en `data/bronze/` y se registra el hash SHA-256 de cada archivo.
#
# ### 2.1 Cali (Excel)

# %%
bronze_cali = extraer_csv.extraer_cali_excel(s["cali"]["path"], s["cali"]["sheet_name"])
print("Cali (Excel):", bronze_cali.shape)
bronze_cali.head()

# %% [markdown]
# ### 2.2 Bogotá (GeoJSON)

# %%
bronze_bogota = extraer_geo.extraer_bogota(s["bogota"]["path"])
print("Bogotá (GeoJSON):", len(bronze_bogota["features"]), "localidades")
pd.DataFrame([f["properties"] for f in bronze_bogota["features"]]).iloc[:, :8].head()

# %% [markdown]
# ### 2.3 Población de Cali (API REST)
#
# Se consume el servicio `datastore_search` del portal de Datos Abiertos de Cali y la respuesta original se guarda en `data/bronze/poblacion_comunas_api.json`.

# %%
try:
    df_pob_api = api.extraer_poblacion_api(cfg["api_poblacion"])
    print("Registros recibidos:", len(df_pob_api))
    display(df_pob_api.iloc[:6, [1, -1]])   # descripción y último año (2020)
except Exception as e:
    df_pob_api = None
    print("API no disponible:", e)

# %% [markdown]
# ## 3. EDA y problemas del dato crudo

# %%
print("Registros Cali:", len(bronze_cali))
for c in bronze_cali.columns:
    vacios = int(bronze_cali[c].isin(["", "N/D"]).sum())
    print(f"{c}: {bronze_cali[c].nunique()} valores distintos | {vacios} vacíos o N/D")

# %%
# Verificación del número de valores distintos de comuna (el Avance 1 habla de 61)
col = next(c for c in bronze_cali.columns if c.lower().startswith("comuna"))
print("Valores distintos en", col, ":", bronze_cali[col].nunique())
print("Tras quitar espacios y pasar a minúsculas:", bronze_cali[col].str.strip().str.lower().nunique())

# %% [markdown]
# **Problemas encontrados**
#
# 1. **Comuna sin diligenciar:** 10,18 % de los registros. **Barrio sin diligenciar:** 44,13 %.
# 2. **Comunas escritas de muchas formas:** 83 valores distintos (tildes, mayúsculas, errores de digitación) que deben quedar en un catálogo único.
# 3. **Fechas con error:** 24 registros; 15 tienen el año `0225` (falta un cero) y 9 tienen la fecha vacía.
# 4. **24 registros sin clasificar** en el tipo de solicitud.
# 5. **Bogotá es un dato agregado:** 20 filas de un solo corte (30/06/2025), sin registro individual, y solo publica atenciones de urgencia.
# 6. **Bogotá concentra en Engativá el 69,3 % de las atenciones** porque allí está la infraestructura (UCA), no necesariamente porque allí ocurran más casos.
# 7. **La población de la API llega solo hasta 2020**, y los casos son de 2024-2026.

# %% [markdown]
# ## 4. LIMPIEZA (bronze → silver)
#
# - **Cali** (`clean_cali.py`): elimina duplicados por `id`, estandariza comunas y corregimientos en un catálogo único, recupera la comuna desde el barrio solo cuando es inequívoco (mínimo 3 observaciones y 95 % de acuerdo), corrige el año `0225` a 2025 (marcando la fila) y valida las fechas y las categorías.
# - **Bogotá** (`clean_bogota.py`): pasa el GeoJSON a una tabla con una fila por localidad (atenciones, especie, sexo, diagnóstico y procedencia).

# %%
silver_cali = limpieza_cali.limpiar_cali(bronze_cali, cfg["quality"])
silver_bogota = limpieza_bogota.limpiar_bogota(bronze_bogota)
print("Silver Cali:", silver_cali.shape, "| Silver Bogotá:", silver_bogota.shape)
silver_cali.head()

# %% [markdown]
# ### 4.1 Calidad antes y después (OKR 3)

# %%
metricas = calidad.metricas_calidad_cali(bronze_cali, silver_cali, cfg["quality"])
metricas

# %% [markdown]
# **Lectura de los resultados:** las metas del Avance 1 (98 % de comuna y 80 % de barrio) **no se alcanzan**: la comuna pasa de 89,81 % a 89,92 % y el barrio se queda en 55,87 %. El pipeline no inventa datos: solo infiere la comuna desde el barrio cuando es inequívoco, y eso recuperó 18 registros. Sí mejoran las fechas con error (27 a 12 tras corregir las 15 con año `0225` y acotar el cierre real a `2025-12-31` para excluir 5 registros de junio de 2025 mal digitados con año `2026`) y el catálogo de comunas (83 a 42 valores). La completitud real depende de que el dato se capture completo en origen.

# %% [markdown]
# ### 4.2 Reglas de validación

# %%
reglas = calidad.validar_pipeline(bronze_cali, silver_cali, silver_bogota, cfg["quality"])
reglas

# %% [markdown]
# Las dos advertencias son de la fuente de Bogotá: los diagnósticos y la procedencia no suman exactamente las atenciones en algunas localidades (diferencias de 1 o 2).

# %% [markdown]
# ## 5. INTEGRACIÓN Y KPIs (silver → gold)
#
# **Integración con JOIN:**
# - **JOIN 1:** los casos de Cali se unen a `dim_categoria` (muchos a uno) para llevar las categorías de las dos ciudades a una `categoria_comparable`. Solo "Urgencias" es comparable entre ambas.
# - **JOIN 2:** el comparativo de ciudades une ambas fuentes por `categoria_comparable`.
# - **JOIN 3:** los casos por zona se unen a la población de la API por zona, para calcular la tasa por 10.000 habitantes.

# %%
dim = gold.construir_dim_categoria(silver_cali)
dim

# %%
gold_final = gold.integrar_gold_final(silver_cali, silver_bogota)
print("gold_final:", gold_final.shape)
gold_final.head()

# %%
# Población: primero la API; si no está disponible, el archivo local
poblacion = None
cp = cfg.get("api_poblacion", {})
if cp.get("enabled"):
    try:
        poblacion = gold.poblacion_desde_api(api.extraer_poblacion_api(cp), cp["anio"])
    except Exception as e:
        print("API de población no disponible:", e)
if poblacion is None:
    poblacion = gold.cargar_poblacion(s["poblacion_cali"]["path"])
print("Zonas con población:", None if poblacion is None else len(poblacion))

# %%
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

k_zona.head(8)[["zona", "casos_total", "denuncias", "urgencias", "poblacion", "casos_por_10k_hab"]]

# %% [markdown]
# ### 5.1 Priorización territorial y evolución mensual

# %%
k_prio.head(10)[["ranking_prioridad", "ranking_en_tipo_zona", "zona", "tipo_zona", "casos_total",
                 "casos_criticos", "casos_por_10k_hab", "indice_priorizacion"]]

# %%
k_evol[["anio_mes", "casos_total", "variacion_pct_mensual"]]

# %% [markdown]
# ### 5.2 Cali frente a Bogotá

# %%
display(k_comp)
k_urg.head(10)

# %%
k_bog

# %% [markdown]
# ### 5.3 Nuevas Preguntas de Negocio y Hallazgos Accionables
#
# A partir de los datos procesados en la capa **Gold**, se formulan y responden 6 preguntas adicionales de negocio:
#
# 1. **¿Cómo cambió la composición de la demanda ciudadana y la oferta operativa del CBA entre 2024 y 2025?**
#    - **Hallazgo:** En 2024 predominaban las **PQR** (62,3 % del mix, 7.399 casos) y las jornadas de **Esterilizaciones** (15,4 %, 1.822 casos). En 2025 el modelo dio un giro hacia la atención clínica reactiva: **Citas médicas subió +81,3 %** (pasando al **49,8 %** de toda la operación) y **Urgencias creció +137,7 %** (de 260 a 618 casos, 10,7 % del total), mientras que las **Esterilizaciones cayeron un -91,8 %** (solo 149 en 2025) y las **Adopciones un -94,8 %** (de 58 a 3).
# 2. **¿En qué comunas existe un déficit de prevención (esterilizaciones) frente al volumen de casos críticos (denuncias + urgencias)?**
#    - **Hallazgo:** La demanda se divide en dos perfiles territoriales opuestos: en comunas de estratos medios/altos como **Comuna 17** (112 denuncias, la más alta de Cali; `ratio_prevencion_criticos = 0,31`), **Comuna 2** (73 denuncias, ratio `0,37`) y **Comuna 22** (41,8 % de sus casos son denuncias, ratio `0,17`), el ciudadano acude al CBA principalmente para **denunciar maltrato o tenencia irregular**, no para solicitar servicios gratuitos. En cambio, **Comuna 20** (Siloé) registra solo 2,2 % de denuncias pero lidera urgencias (106), citas médicas (824) y esterilizaciones (321, ratio `2,06`). También hay déficit preventivo en **Comuna 1** (ratio `0,69`), **Comuna 9** (`0,57`) y **Comuna 12** (`0,73`).
# 3. **¿Cuáles son los barrios específicos ("hotspots") que concentran más casos críticos en Cali para focalizar brigadas puerta a puerta?**
#    - **Hallazgo:** **Siloé (Comuna 20)** concentra por sí solo **662 solicitudes** (6,7 % de todos los registros con barrio de la ciudad) y **78 casos críticos** (53 urgencias + 25 denuncias), superando a 15 comunas completas. Le siguen **Terrón Colorado (Comuna 1)** con 53 casos críticos (34 urgencias + 19 denuncias), **Los Chorros (Comuna 18)** con 32 críticos, y en el oriente **Manuela Beltrán (Comuna 14)** y **Ciudad Córdoba (Comuna 15)** con 22 críticos cada uno. En el sur destaca **Valle del Lili (Comuna 17)** con 15 críticos (14 denuncias de 23 casos totales).
# 4. **¿En qué canales o tipos de solicitud se pierde más información geográfica (comuna y barrio) que impide cumplir el OKR 3?**
#    - **Hallazgo:** El **81,2 % de todos los registros sin comuna** (1.444 de 1.779) proviene de **PQR**. En **Esterilizaciones**, la comuna casi siempre se anota (solo 1,8 % sin comuna), pero **el 67,1 % carece de barrio** (1.322 casos sin barrio) porque en las jornadas masivas solo se registra la comuna del operativo. En cambio, **Urgencias** (2,3 % sin comuna, 14,3 % sin barrio) y **Cita médica** (3,0 % sin comuna, 20,2 % sin barrio) tienen alta completitud. Hacer obligatorio el barrio en formularios de PQR y planillas de esterilización resolvería el **80,2 % de los vacíos de barrio**.
# 5. **¿Cómo se comporta la carga operativa según el día de la semana?**
#    - **Hallazgo:** El **80,6 % de las solicitudes** ingresa de lunes a viernes (pico los **martes con 3.052 casos** y **miércoles con 2.886**). Los fines de semana baja el volumen total, pero el **sábado** alcanza la mayor proporción relativa de **Esterilizaciones (14,5 % de los casos del día)** por las brigadas comunitarias de fin de semana.
# 6. **Si aislamos el sesgo de infraestructura de Engativá (sede de la UCA) en Bogotá, ¿cuál es el verdadero perfil clínico y canal de ingreso en las otras 19 localidades?**
#    - **Hallazgo:** En **Engativá** (656 atenciones, 69,3 % de Bogotá), el **97,7 % ingresa por UCA** y el **79,7 % se registra con diagnóstico genérico "Otros"**. Al aislar las **otras 19 localidades (291 atenciones)**, se revela el perfil real de urgencias en territorio: el **84,9 % ingresa por reporte ciudadano directo**, el **7,2 % por Brigadas** y el **7,2 % por Escuadrón Anticrueldad**; clínicamente dominan las patologías **Infecciosas (47,1 %, 137 casos)** y el **Politraumatismo / atropellamiento (20,6 %, 60 casos)**, y la proporción de **felinos sube del 23,3 % al 33,0 %**.

# %%
display(k_cambio)
display(k_brecha.head(10))
display(k_barrios.head(10))
display(k_cal_clase)
display(k_semanal)
display(k_bog_sesgo.head(12))

# %% [markdown]
# ## 6. VALIDACIÓN Y EVIDENCIAS
#
# Las gráficas se guardan como evidencia en `evidencias/`, junto con `validaciones_calidad.csv`.

# %%
ev = p["evidencias_dir"]
graficos.grafica_casos_por_comuna(k_zona, ev)
graficos.grafica_evolucion_mensual(k_evol, ev)
graficos.grafica_urgencias_ciudades(k_urg, ev)
graficos.grafica_calidad(metricas, ev)
graficos.grafica_cambio_anual_servicios(k_cambio, ev)
graficos.grafica_brecha_prevencion(k_brecha, ev)
graficos.grafica_top_barrios(k_barrios, ev)
graficos.grafica_bogota_sesgo_uca(k_bog_sesgo, ev)
for f in sorted(os.listdir(ev)):
    if f.endswith(".png"):
        display(Image(os.path.join(ev, f)))

# %% [markdown]
# ## 7. Resumen y conclusiones

# %%
pd.DataFrame({
    "capa": ["bronze (Cali)", "bronze (Bogotá)", "silver (Cali)", "silver (Bogotá)", "gold"],
    "filas": [len(bronze_cali), len(bronze_bogota["features"]), len(silver_cali), len(silver_bogota), len(gold_final)],
})

# %%
# Conclusiones calculadas con los datos
sin = limpieza_cali.SIN_DATO
top3 = k_zona[k_zona["zona"] != sin].head(3)
print("Zonas con más casos registrados:", ", ".join(f"{r.zona} ({int(r.casos_total)})" for r in top3.itertuples()))
if k_zona["casos_por_10k_hab"].notna().any():
    t = k_zona.dropna(subset=["casos_por_10k_hab"]).sort_values("casos_por_10k_hab", ascending=False).head(3)
    print("Mayor tasa por 10.000 hab.:", ", ".join(f"{r.zona} ({r.casos_por_10k_hab})" for r in t.itertuples()))
pr = k_prio.head(3)
print("Prioridad territorial más alta:", ", ".join(f"{r.zona} ({r.indice_priorizacion})" for r in pr.itertuples()))
urg = k_comp[k_comp["comparable"] == True].iloc[0]
print("Urgencias: Cali", int(urg["casos_cali_total"]), "| Bogotá", int(urg["casos_bogota_corte_2025_06_30"]))

# %% [markdown]
# **Conclusiones**
#
# 1. **Dónde concentrar recursos:** el ranking de priorización combina casos, casos críticos (denuncias y urgencias) y la tasa por 10.000 habitantes normalizada por tipo de zona (urbana/rural), ubicando a las **Comunas 20, 18, 21, 13 y 14** en el top urbano y a **Villacarmelo y La Buitrera** en el top rural, con micro-focalización directa en los barrios **Siloé, Terrón Colorado y Los Chorros**.
# 2. **Alerta por caída de prevención en 2025:** entre 2024 y 2025 las esterilizaciones cayeron un **-91,8 %** (de 1.822 a 149) mientras las urgencias subieron **+137,7 %** y las citas médicas **+81,3 %**. Además, comunas como la **17, 2 y 22** demandan principalmente control de maltrato/denuncias, mientras **Comuna 20, 1 y 18** requieren brigadas clínicas y de esterilización.
# 3. **Calidad del dato accionable por canal:** el **81,2 % de los registros sin comuna** proviene de **PQR** y el **80,2 % de los registros sin barrio** se concentra entre **PQR (63,2 %) y Esterilizaciones (17,0 %)**. Exigir estos campos en esos dos canales permitirá alcanzar las metas del OKR 3 en origen.
# 4. **Cali y Bogotá (aislamiento del sesgo UCA):** solo "Urgencias" es comparable (Cali 879 en 2024-2025 vs. Bogotá 947 a corte 30/06/2025). Al separar el sesgo de la UCA en Engativá (79,7 % diagnóstico "Otros"), se observa que en las otras 19 localidades de Bogotá el **84,9 % proviene de reporte ciudadano** y predominan los casos **infecciosos (47,1 %) y politraumatismos (20,6 %)**.
