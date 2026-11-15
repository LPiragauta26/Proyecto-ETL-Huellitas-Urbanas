# ETL Bienestar Animal: Cali (CBA/Uaepa) vs. Bogotá (IDPYBA)

Pipeline de ingeniería de datos con **arquitectura Medallion** (**Bronze → Silver → Gold → Data Warehouse SQLite → Validación y Evidencias**), orquestado con **Apache Airflow 3.3.2**, expuesto mediante una **API REST en FastAPI** (con Portal Ciudadano de Consulta Gold y Adopción Responsable) y visualizado en **Streamlit**.

**Autores:** Laura Fernanda Piragauta Pinzón, Omar Alejandro Yepez Ospino, Ana María Rivera Díaz y Thomas Marcos Flórez.

---

## 1. Estructura Completa del Proyecto

```text
ETL_Avance_2/
├── airflow-medallon/                        # Orquestación con Docker Compose + Apache Airflow 3.3.2
│   ├── config/airflow.cfg                   # Configuración de Apache Airflow
│   ├── dags/etl_bienestar_animal_hourly.py  # DAG horario (@hourly / 0 * * * *) con las 5 tareas Medallion
│   ├── logs/                                # Logs de ejecución por DAG, tarea e intento
│   ├── plugins/                             # Plugins de Airflow
│   ├── .env                                 # AIRFLOW_UID=50000
│   ├── Dockerfile                           # Imagen apache/airflow:3.3.2 + dependencias del ETL
│   ├── docker-compose.yaml                  # Servicios de Airflow + volumen ../Medallon:/opt/airflow/medallon
│   ├── README.md                            # Guía de despliegue de Airflow y pruebas P1–P5
│   └── requirements-airflow.txt             # Dependencias Python del contenedor
│
└── Medallon/                                # Proyecto principal ETL Medallion, API y App
    ├── api/                                 # Servicio REST en FastAPI + Portal Ciudadano de Adopción
    │   ├── __init__.py
    │   └── main.py
    ├── app/                                 # Tablero interactivo en Streamlit + Reporte de Consola
    │   ├── __init__.py
    │   └── app.py
    ├── config/                              # Configuración centralizada y catálogo de homologación
    │   ├── config.yaml
    │   └── dim_categoria.csv
    ├── dags/                                # Copia espejo del DAG para validación y pruebas locales
    │   └── etl_bienestar_animal_hourly.py
    ├── data/                                # Capas de datos de la arquitectura Medallion
    │   ├── bronze/                          # Datos crudos inmutables (Excel Cali, GeoJSON Bogotá, API CKAN Cali)
    │   ├── silver/                          # Datos limpios y estandarizados (silver_cali.csv, silver_bogota.csv)
    │   └── gold/                            # gold_final.csv, warehouse.db (SQLite), catálogo de adopción y kpis/
    │       └── kpis/                        # 13 tablas CSV de KPIs de negocio y calidad
    ├── etl/                                 # Módulos por tarea invocados desde Airflow y pruebas
    │   ├── __init__.py
    │   ├── extract_api.py                   # Tarea 1: extract_api_bronze (+ soporte de fallo controlado P4)
    │   ├── extract_excel.py                 # Tarea 2: extract_excel_bronze (control SHA-256 + copia de corrida)
    │   ├── transform_silver.py              # Tarea 3: transform_silver (limpieza Cali/Bogotá + trazabilidad)
    │   ├── build_gold.py                    # Tarea 4: build_gold (JOINs + gold_final.csv + 13 KPIs)
    │   └── validate_gold.py                 # Tarea 5: validate_gold (14 reglas + 18 tablas SQLite + 8 gráficas)
    ├── evidencias/                          # 8 gráficas PNG, validaciones_calidad.csv y trazabilidad_fuentes.csv
    ├── logs/                                # Registro detallado de ejecución (log.txt)
    ├── notebooks/                           # Notebook interactivo de análisis y exploración
    │   ├── etl_bienestar_animal.ipynb
    │   └── etl_bienestar_animal.py
    ├── scripts/                             # Utilidades auxiliares (conversión CSV a Excel)
    │   └── convertir_csv_a_excel.py
    ├── src/                                 # Núcleo modular del ETL separado por responsabilidades
    │   ├── extract/                         # extract_api.py, extract_csv.py, extract_geojson.py
    │   ├── transform/                       # clean_cali.py, clean_bogota.py, gold_data.py
    │   ├── quality/                         # quality_checks.py (métricas antes/después y 14 reglas de calidad)
    │   ├── load/                            # load_datawarehouse.py (exportación CSV y carga SQLite idempotente)
    │   └── utils/                           # helpers.py, graficos.py (generación de las 8 gráficas PNG)
    ├── test/                                # Pruebas de integridad de arquitectura ETL y métricas Streamlit
    │   └── test_etl_arquitectura.py
    ├── tests/                               # Pruebas unitarias de limpieza, JOINs, KPIs, DAG y API
    │   └── test_pipeline.py
    ├── .env
    ├── .gitignore
    ├── main.py                              # Orquestador local de punta a punta
    ├── README.md
    └── requirements.txt
```

---

## 2. Guía Rápida de Ejecución (Todos los Comandos)

Abre la **Terminal**, entra a la carpeta `Medallon` y activa el entorno virtual:

```Terminal
cd c:\Users\Laura\Downloads\ETL_Avance_2\Medallon
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2.1 Ejecutar el Pipeline ETL completo
Procesa las capas **Bronze → Silver → Gold**, genera los **13 KPIs**, pobla las **18 tablas en SQLite** (`data/gold/warehouse.db`), evalúa las **14 reglas de calidad** y exporta las **8 gráficas PNG** en `evidencias/`:
```powershell
python main.py
```

### 2.2 Ejecutar las 23 Pruebas Automatizadas (`pytest`)
Verifica las reglas de limpieza de comunas/clases/fechas, inferencia geográfica, cuadre entre Silver y Gold, cálculo de los 13 KPIs, fallo controlado de Airflow (`P4`), estructura de carpetas y endpoints de la API:
```Terminal
python -m pytest -v
```

### 2.3 Levantar la API FastAPI + Portal Ciudadano de Consulta Gold y Adopción
```Terminal
uvicorn api.main:app --reload
```
Rutas disponibles en el navegador una vez iniciado el servidor en `http://127.0.0.1:8000`:
* **🐾 Portal Web Ciudadano (Adopción + Consulta Gold interactiva)**: `http://127.0.0.1:8000/portal`
* **📘 Documentación interactiva Swagger UI**: `http://127.0.0.1:8000/docs`
* **🏠 Portada y catálogo de endpoints**: `http://127.0.0.1:8000/`
* **📊 Capa Gold completa (con filtros opcionales `?ciudad=`, `?tipo_zona=`, `?categoria=`, `?es_critico=`)**: `http://127.0.0.1:8000/gold`
* **📋 Solo arreglo `Data` de la capa Gold**: `http://127.0.0.1:8000/gold/data`
* **🌆 Capa Gold filtrada por ciudad (`Cali` o `Bogota`)**: `http://127.0.0.1:8000/gold/ciudad/Cali`
* **📈 Listado de los 13 KPIs de negocio**: `http://127.0.0.1:8000/kpis`
* **🔍 Detalle de cualquier KPI**: ej. `http://127.0.0.1:8000/kpis/kpi_priorizacion_territorial`
* **🐶 Animales rescatados disponibles para adopción**: `http://127.0.0.1:8000/adopciones/animales`
* **📉 Datos históricos de adopción en Gold y hallazgo 2024 vs. 2025**: `http://127.0.0.1:8000/adopciones/gold`
* **📝 Registrar postulación de adopción (`POST`)**: `http://127.0.0.1:8000/adopciones/solicitar`
* **📂 Ver solicitudes de adopción registradas**: `http://127.0.0.1:8000/adopciones/solicitudes`
* **✅ Reporte de las 14 reglas de validación de calidad**: `http://127.0.0.1:8000/calidad`
* **❤️ Estado de salud del servicio (`health`)**: `http://127.0.0.1:8000/health`

### 2.4 Ejecutar la Aplicación Visual en Streamlit o por Consola (`app/app.py`)
* **Interfaz gráfica web en Streamlit** (`http://localhost:8501`) — incluye el cargador de CSV y métricas dinámicas del profesor adaptadas a Bienestar Animal + pestañas de Adopción Responsable, Priorización Territorial, Top Barrios Críticos y las 8 Gráficas de Evidencia:
  ``Terminal
  python -m streamlit run app/app.py
  ```
* **Reporte ejecutivo en consola** (auditoría de las 5 etapas del ETL + Top 5 comunas y barrios + estado de la API):
  ```Terminal
  python app/app.py
  ```

### 2.5 Levantar la Orquestación con Apache Airflow 3.3.2 y Docker Compose
Desde la carpeta `airflow-medallon`:
```Terminal
cd c:\Users\Laura\Downloads\ETL_Avance_2\airflow-medallon
docker compose build
docker compose up airflow-init
docker compose up -d
```
* **Interfaz web de Airflow**: `http://localhost:8080` (usuario `airflow` / contraseña `airflow`)
* **DAG**: `etl_bienestar_animal_hourly` (`[extract_api_bronze, extract_excel_bronze] >> transform_silver >> build_gold >> validate_gold`)
* *(Consulta [`airflow-medallon/README.md`](../airflow-medallon/README.md) para el paso a paso de las pruebas **P1 a P5**).*

---

## 3. Arquitectura del Pipeline Medallion (Flujo de Datos)

| Capa | Módulos Principales | Qué hace | Salidas Generadas |
|---|---|---|---|
| **01 Bronze (Extract)** | `src/extract/`, `etl/extract_api.py`, `etl/extract_excel.py` | Extrae sin alterar `Dataset_cali.xlsx` (17.642 registros de solicitudes ciudadanas CBA/Uaepa), `dataset_bogota.geojson` (20 localidades con atenciones de urgencia IDPYBA) y la API CKAN de proyecciones de población de Cali (`poblacion_comunas_api.json`, con respaldo local automático). Calcula hash `SHA-256` y guarda copias por corrida. | `data/bronze/`, `evidencias/trazabilidad_fuentes.csv` |
| **02 Silver (Transform & Quality)** | `src/transform/clean_cali.py`, `src/transform/clean_bogota.py`, `src/quality/quality_checks.py` | Estandariza comunas y corregimientos de Cali (83 valores crudos → 42 zonas canónicas), recupera comunas faltantes por inferencia desde barrio, corrige errores de digitación en fechas (`0225` → `2025`), aplana el GeoJSON de Bogotá descartando geometría y evalúa métricas de calidad antes vs. después. | `data/silver/silver_cali.csv` (17.642 filas), `data/silver/silver_bogota.csv` (20 localidades) |
| **03 Gold (Integrate & KPIs)** | `src/transform/gold_data.py`, `etl/build_gold.py` | Ejecuta los 3 JOINs con `dim_categoria.csv` y con las proyecciones de población de Cali (año 2020, 37 zonas con población) para construir la tabla integrada `gold_final.csv` y las **13 tablas KPI de negocio y calidad**. | `data/gold/gold_final.csv` (404 filas), `data/gold/kpis/*.csv` (13 archivos) |
| **04 Load & Validación** | `src/load/load_datawarehouse.py`, `src/utils/graficos.py`, `etl/validate_gold.py` | Valida las **14 reglas de aceptación** (12 `OK`, 2 `ADVERTENCIA`, 0 `FALLA`), publica de forma idempotente **18 tablas** en SQLite (`warehouse.db`) y genera las **8 gráficas PNG de evidencia**. | `data/gold/warehouse.db`, `evidencias/validaciones_calidad.csv`, `evidencias/01_*.png` a `08_*.png`, `logs/log.txt` |

---

## 4. Reglas de Limpieza y Transformación (Capa Silver)

### 4.1 Cali (`clean_cali.py`)
1. **Homologación de Comunas y Corregimientos (`83 → 42` valores)**:
   * Unifica las 83 variantes crudas (mayúsculas, tildes, errores tipográficos como `MONTEBELLLO`, `Corregimiento Pichinche`, `Corregimiento de X`) en un catálogo único de **42 zonas**: las **22 comunas urbanas** (`Comuna 1` a `Comuna 22`), los **15 corregimientos rurales** (`La Buitrera`, `Villacarmelo`, `Pance`, `Montebello`, `Golondrinas`, `El Hormiguero`, `La Elvira`, `La Castilla`, `La Paz`, `La Leonera`, `Felidia`, `El Saladito`, `Pichinde`, `Los Andes`, `Navarro`), `"Fuera de jurisdicción"`, `"Área de expansión urbana"`, `"Zona rural (sin especificar)"`, `"Corregimiento (sin especificar)"` y `"Sin dato"`.
   * Valores inválidos digitados por error en la columna `Comuna` (como `"Urgencias"` o comunas inexistentes) se reubican en `"Sin dato"` sin eliminar el registro.
2. **Recuperación Geográfica por Inferencia (`Barrio → Comuna`)**:
   * Se construye un diccionario automático desde los propios datos: cuando un registro no tiene comuna pero su barrio aparece al menos **3 veces (`barrio_min_obs: 3`)** con **≥95 % de acuerdo (`barrio_min_acuerdo: 0.95`)** en una única comuna, se imputa la comuna y se marca `comuna_imputada = True` (**18 registros recuperados**).
3. **Tratamiento de Fechas (`parsear_fecha`)**:
   * Se corrigen automáticamente **15 registros** con año mal digitado `0225` → `2025` (marcados con `fecha_corregida = True`).
   * Se acota el rango válido al cierre real del corte **`2024-01-01` a `2025-12-31` (`fecha_max: "2025-12-31"`)**. Los **12 registros** con años fuera de rango (`2005`, `2205`, `20025`, `2026`, `2027`, `2028` —incluyendo 5 errores de digitación con año `2026` en medio de junio de 2025—) quedan con `fecha_valida = False` y `fecha = NaT`. **No se elimina ningún registro** (`17.642 → 17.642`), pero los registros sin fecha válida se excluyen de las series de tiempo para evitar meses fantasma en 2026.
4. **Clases de Petición (`9 → 8` categorías)**:
   * `"Pqr"` → `"PQR"`; `"N/D"` y `"Sin respuesta"` se unifican en `"Sin clasificar"`.
5. **Control de Duplicados**:
   * Duplicados exactos por llave `id`: **0 eliminados**. Existen **4.117 registros** idénticos en fecha, comuna, barrio y clase pero con distinto `id`; se conservan documentados porque representan múltiples solicitudes ciudadanas de un mismo operativo o barrio en el mismo día.

### 4.2 Bogotá (`clean_bogota.py`)
1. **Aplanado de GeoJSON a Tabla**:
   * Se procesan las **20 localidades de Bogotá** (`947 atenciones` de urgencia veterinaria), descartando la geometría poligonal.
2. **Renombrado Semántico y Agrupación por Prefijos**:
   * Los campos truncados del shapefile original se estandarizan en 4 dimensiones: diagnósticos (`dx_politraumatismo`, `dx_infeccioso`, `dx_ortopedico`, `dx_neurologico`, `dx_intoxicacion`, `dx_nefrourologico`, `dx_gastroenterico`, `dx_oncologico`, `dx_respiratorio`, `dx_otros`), canal de procedencia (`proc_ciudadania`, `proc_uca`, `proc_brigadas`, `proc_anticrueldad`, `proc_otros`), especie (`esp_canino`, `esp_felino`) y sexo (`sexo_macho`, `sexo_hembra`, `sexo_indeterminado`).
   * En localidades con `0` atenciones (`Sumapaz`), las proporciones (`pct_atenciones_uca`) se completan en `0.0` sin valores nulos.

---

## 5. Integración (JOINs) y Catálogo de las 13 Tablas KPI (Capa Gold)

* **JOIN 1 y 2 (`config/dim_categoria.csv`)**: Homologa las categorías de Cali (solicitudes por evento) y Bogotá (urgencias agregadas por localidad) hacia `categoria_comparable`, `grupo_servicio` y `es_critico`. La **única categoría directamente comparable entre ambas ciudades es `Urgencias`** (`879` en Cali vs. `947` en Bogotá).
* **JOIN 3 (Población API CKAN Cali)**: Cruza las zonas de Cali con las proyecciones oficiales de población del año 2020 (`37 zonas` con población: 22 comunas + 15 corregimientos) para calcular tasas por cada 10.000 habitantes. En `kpi_priorizacion_territorial`, la tasa poblacional se normaliza **dentro de cada `tipo_zona` (`urbana` vs. `rural`)** para que corregimientos de baja población (como Villacarmelo con 818 hab.) no distorsionen el ranking de las 22 comunas urbanas.

### Resumen de las 13 Tablas KPI en `data/gold/kpis/`:

| # | Archivo KPI | Filas | Pregunta de Negocio / Propósito |
|---|---|---|---|
| 1 | `kpi_calidad_datos.csv` | 14 | Comparativo de completitud y consistencia antes (Bronze) vs. después (Silver) para OKR 3. |
| 2 | `kpi_casos_por_zona.csv` | 42 | Volumen total, casos críticos, las 8 clases de servicio, población 2020 y tasas por 10k hab. en Cali. |
| 3 | `kpi_evolucion_mensual.csv` | 24 | Serie mensual continua `2024-01` a `2025-12` en Cali con variación porcentual y promedio móvil. |
| 4 | `kpi_priorizacion_territorial.csv` | 37 | Índice de priorización (0–100) ponderando volumen (40 %), críticos (30 %) y tasa 10k normalizada por tipo de zona (30 %). |
| 5 | `kpi_comparativo_ciudades.csv` | 8 | Comparativo por categoría homologada entre Cali (17.642 casos) y Bogotá (947 atenciones). |
| 6 | `kpi_urgencias_por_zona.csv` | 56 | Ranking intraciudad de urgencias veterinarias en las zonas de Cali y las 20 localidades de Bogotá. |
| 7 | `kpi_bogota_detalle.csv` | 28 | Distribución global de diagnósticos, procedencia, especie y sexo en las 947 atenciones de Bogotá. |
| 8 | `kpi_cambio_anual_servicios.csv` | 8 | Cambio en el portafolio de servicios de Cali entre 2024 y 2025 (giro de preventivo a clínico/reactivo). |
| 9 | `kpi_brecha_prevencion_zona.csv` | 37 | Razón entre acciones preventivas (`esterilizaciones + adopciones`) y casos críticos (`denuncias + urgencias`) por zona. |
| 10 | `kpi_top_barrios_cali.csv` | 25 | Top 25 barrios ("hotspots") con mayor volumen de casos críticos en Cali. |
| 11 | `kpi_calidad_por_clase.csv` | 8 | Auditoría de vacíos de comuna, barrio y fecha desagregada por clase de petición en Cali. |
| 12 | `kpi_patron_semanal_cali.csv` | 7 | Comportamiento operativo de lunes a domingo en Cali por tipo de solicitud. |
| 13 | `kpi_bogota_engativa_vs_resto.csv` | 22 | Contraste epidemiológico y de canal de ingreso entre Engativá (sede UCA) y el resto de las 19 localidades de Bogotá. |

---

## 6. Preguntas de Negocio y Hallazgos Principales

### 1. ¿Dónde concentrar recursos operativos y brigadas en Cali? (`kpi_casos_por_zona`, `kpi_priorizacion_territorial`)
* **Top 5 comunas por volumen total**: **Comuna 20** (2.310), **Comuna 18** (1.441), **Comuna 13** (1.146), **Comuna 14** (1.084) y **Comuna 21** (961).
* **Top 5 en el Índice de Priorización Territorial**: **Comuna 20** (`99,1`), **Comuna 18** (`61,9`), **Comuna 21** (`47,8`), **Comuna 13** (`47,5`) y **Comuna 14** (`46,5`). En zona rural lideran **Villacarmelo** (índice `35,7`; 118 casos; tasa de `1.442,54` por 10k hab.) y **La Buitrera** (213 casos).

### 2. ¿Cómo cambió el portafolio de demanda y servicios entre 2024 y 2025 en Cali? (`kpi_cambio_anual_servicios`)
* **Giro de modelo preventivo/administrativo a reactivo/clínico**:
  * En **2024** (11.873 casos con fecha válida), el **62,3 % eran PQR** (7.399) y el **15,4 % Esterilizaciones** (1.822).
  * En **2025** (5.757 casos), las **Citas médicas crecieron +81,3 %** (de 1.581 a 2.866, pasando a representar el **49,8 %** de toda la operación) y las **Urgencias crecieron +137,7 %** (de 260 a 618, subiendo al **10,7 %** del mix).
  * **Alerta crítica de negocio**: Las **Esterilizaciones cayeron un -91,8 %** en 2025 (de 1.822 a solo 149) y las **Adopciones cayeron un -94,8 %** (de 58 a solo 3 casos), lo que motivó la creación del **Portal Digital de Adopción Responsable** en la API y en Streamlit.

### 3. ¿En qué comunas hay déficit de prevención frente a casos críticos y dónde se concentra el maltrato? (`kpi_brecha_prevencion_zona`)
* **Comunas con foco en denuncias de maltrato/tenencia y baja solicitud de esterilización pública**: **Comuna 17** es la #1 en denuncias de toda Cali (**112 denuncias**, 27,0 % de sus casos) pero solo registra 37 esterilizaciones (`ratio_prevencion_criticos = 0,31`). Igual ocurre en **Comuna 2** (73 denuncias, ratio `0,37`), **Comuna 22** (51 denuncias = **41,8 %** de sus casos y **40,36 denuncias por 10k hab.**, ratio `0,17`) y el corregimiento de **Pance** (26,8 % denuncias, ratio `0,33`).
* **Comunas de alta demanda asistencial/clínica con déficit preventivo**: **Comuna 1** (104 casos críticos vs. 72 esterilizaciones, ratio `0,69`), **Comuna 9** (ratio `0,57`) y **Comuna 12** (ratio `0,73`), frente a **Comuna 20** que sí contó con mayor cobertura relativa de esterilización (321 esterilizaciones vs. 156 críticos, ratio `2,06`).

### 4. ¿Cuáles son los barrios específicos ("hotspots") más críticos de Cali? (`kpi_top_barrios_cali`)
* **Siloé (Comuna 20)** concentra **662 solicitudes** (6,7 % de todos los registros con barrio identificado en Cali) y **78 casos críticos** (53 urgencias + 25 denuncias), superando por sí solo a 15 comunas completas.
* Le siguen **Terrón Colorado (Comuna 1)** con 288 casos (53 críticos: 34 urgencias + 19 denuncias), **Los Chorros (Comuna 18)** con 236 casos (32 críticos), **Manuela Beltrán (Comuna 14)** con 121 casos (22 críticos) y **Ciudad Córdoba (Comuna 15)** con 101 casos (22 críticos: 15 denuncias + 7 urgencias). En el sur destaca **Valle del Lili (Comuna 17)** con 15 críticos (14 denuncias de 23 casos totales).

### 5. ¿En qué canales o servicios se pierde la información geográfica (OKR 3)? (`kpi_calidad_por_clase`)
* El **81,2 % de todos los registros sin comuna** (1.444 de 1.779) se origina en **PQR**.
* En **Esterilizaciones**, la comuna sí se captura (solo 1,8 % sin comuna), pero **el 67,1 % no tiene barrio** (1.322 casos) porque en las jornadas móviles masivas solo se registra la comuna del operativo.
* Entre **PQR (63,2 %) y Esterilizaciones (17,0 %) explican el 80,2 % de todos los vacíos de barrio**, mientras que **Urgencias** (2,3 % sin comuna) y **Cita médica** (3,0 % sin comuna) sí capturan la ubicación por requerimiento clínico.

### 6. ¿Cuál es el patrón operativo por día de la semana en Cali? (`kpi_patron_semanal_cali`)
* El **80,6 % de la demanda** ingresa de lunes a viernes (picos en **martes con 3.052 casos** y **miércoles con 2.886**).
* El **sábado** (1.856 casos) presenta la **mayor proporción relativa de Esterilizaciones (14,5 % del día)** por las jornadas comunitarias de fin de semana.

### 7. ¿Cuál es el verdadero perfil clínico de Bogotá al aislar el sesgo de la UCA en Engativá? (`kpi_bogota_engativa_vs_resto`)
* **Engativá** concentra el **69,3 % de las atenciones de Bogotá (656 de 947)** porque allí está ubicada físicamente la **Unidad de Cuidado Animal (UCA)**: el **97,7 %** ingresa por canal `UCA` y el **79,7 %** queda catalogado bajo el diagnóstico genérico `"Otros"`.
* Al aislar el **Resto de las 19 localidades (291 atenciones)**, emerge el perfil epidemiológico real en calle:
  * **Canal de ingreso**: **84,9 % reporte ciudadano directo** (247), **7,2 % Brigadas** (21) y **7,2 % Escuadrón Anticrueldad** (21).
  * **Diagnósticos reales**: lideran las enfermedades **Infecciosas (47,1 %, 137 casos)** —con focos en Ciudad Bolívar (34), Usme (18), Fontibón (16) y Bosa (11)—, seguidas de **Politraumatismo / atropellamientos (20,6 %, 60 casos)** y **Ortopédico (12,7 %, 37 casos)**, mientras que `"Otros"` cae a solo **1,7 %**.
  * **Especie**: la proporción de **felinos atendidos sube del 23,3 % en Engativá al 33,0 % en el resto de la ciudad**.

---

## 7. Evidencias Gráficas y Validaciones de Calidad (`evidencias/`)

El pipeline genera automáticamente **8 gráficas PNG** y el reporte `evidencias/validaciones_calidad.csv` con **14 reglas evaluadas (`12 OK`, `2 ADVERTENCIAS` documentadas de la fuente de Bogotá, `0 FALLAS`)**:

1. `01_casos_por_comuna.png` — Top 15 zonas de Cali por volumen y casos críticos.
2. `02_evolucion_mensual.png` — Evolución mensual 2024–2025 de solicitudes y casos críticos en Cali.
3. `03_urgencias_cali_vs_bogota.png` — Comparativo de urgencias por zona en Cali vs. localidades de Bogotá.
4. `04_calidad_antes_despues.png` — Impacto de la limpieza Bronze vs. Silver (OKR 3).
5. `05_cambio_mix_2024_vs_2025.png` — Transición del mix de servicios de Cali entre 2024 y 2025.
6. `06_brecha_prevencion_vs_criticos.png` — Mapa de brecha preventiva vs. casos críticos por comuna.
7. `07_top_barrios_criticos_cali.png` — Top 15 barrios críticos de Cali (desglose Urgencias vs. Denuncias).
8. `08_bogota_sesgo_uca_vs_resto.png` — Contraste de diagnósticos y canales entre Engativá (UCA) y el resto de Bogotá.
