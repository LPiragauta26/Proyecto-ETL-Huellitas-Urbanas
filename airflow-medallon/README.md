# Orquestación del Pipeline ETL Medallion con Apache Airflow 3.3.2

Esta carpeta contiene el entorno de **Apache Airflow 3.3.2** sobre **Docker Compose y WSL2** para orquestar el proyecto **ETL Bienestar Animal: Cali (CBA/Uaepa) vs. Bogotá (IDPYBA)** bajo una arquitectura **Medallion (Bronze → Silver → Gold → Validación, Evidencias Gráficas y Data Warehouse SQLite)**.

---

## 1. Estructura del Proyecto y la carpeta `airflow-medallon`

```text
ETL_Bienestar_animal/
├── airflow-medallon/                        # Entorno de orquestación con Docker + Airflow 3.3.2
│   ├── config/
│   │   └── airflow.cfg                      # Configuración de Apache Airflow 3.3.2
│   ├── dags/
│   │   └── etl_bienestar_animal_hourly.py   # DAG horario con las 5 tareas Medallion
│   ├── logs/                                # Logs generados por Airflow por DAG, tarea e intento
│   ├── plugins/                             # Plugins adicionales de Airflow
│   ├── .env                                 # AIRFLOW_UID=50000
│   ├── Dockerfile                           # Imagen apache/airflow:3.3.2 + dependencias del ETL
│   ├── requirements-airflow.txt             # pandas, numpy, PyYAML, requests, openpyxl, matplotlib
│   ├── docker-compose.yaml                  # Servicios de Airflow + volumen ../Medallon:/opt/airflow/medallon
│   └── README.md                            # Guía paso a paso de ejecución y pruebas P1–P5
│
└── Medallon/                                # Proyecto ETL Python montado en /opt/airflow/medallon
    ├── api/main.py                          # API FastAPI + Portal Ciudadano de Consulta Gold y Adopción
    ├── app/app.py                           # Tablero visual en Streamlit + Reporte Ejecutivo en Consola
    ├── config/config.yaml                   # Configuración centralizada de rutas, API CKAN, Excel, GeoJSON y SQLite
    ├── dags/etl_bienestar_animal_hourly.py  # Copia espejo del DAG para validación y pruebas locales
    ├── etl/                                 # Funciones run() modulares invocadas por cada @task
    │   ├── extract_api.py                   # Tarea 1: extract_api_bronze (API CKAN Población Cali + GeoJSON Bogotá)
    │   ├── extract_excel.py                 # Tarea 2: extract_excel_bronze (Excel Cali CBA/Uaepa + SHA-256)
    │   ├── transform_silver.py              # Tarea 3: transform_silver (Limpieza Cali/Bogotá + trazabilidad)
    │   ├── build_gold.py                    # Tarea 4: build_gold (JOIN dim_categoria + población + 13 KPIs)
    │   └── validate_gold.py                 # Tarea 5: validate_gold (Reglas calidad + 18 tablas SQLite + 8 gráficas)
    ├── src/                                 # Lógica de negocio (extract, transform, quality, load, utils)
    ├── data/                                # Capas bronze/, silver/, gold/ (gold_final.csv, kpis/*.csv, warehouse.db)
    ├── evidencias/                          # validaciones_calidad.csv, trazabilidad_fuentes.csv y 8 gráficas PNG
    ├── test/ y tests/                       # 23 pruebas automatizadas de arquitectura, ETL, KPIs, DAG y API
    └── main.py                              # Orquestador local independiente
```

---

## 2. Arquitectura del DAG (`etl_bienestar_animal_hourly`)

```text
          ┌───────────────────────────┐     ┌────────────────────────────┐
          │    extract_api_bronze     │     │    extract_excel_bronze    │
          │ (API CKAN Cali + GeoJSON) │     │ (Excel Solicitudes Cali)   │
          └─────────────┬─────────────┘     └──────────────┬─────────────┘
                        │                                  │
                        └────────────────┬─────────────────┘
                                         ▼
                                ┌──────────────────┐
                                │ transform_silver │
                                │(Limpieza+Catálogo│
                                │ + Trazabilidad)  │
                                └────────┬─────────┘
                                         ▼
                                ┌──────────────────┐
                                │    build_gold    │
                                │(JOIN + 13 KPIs de│
                                │Negocio y Calidad)│
                                └────────┬─────────┘
                                         ▼
                                ┌──────────────────┐
                                │  validate_gold   │
                                │(14 Reglas+SQLite │
                                │  + 8 Gráficas)   │
                                └──────────────────┘
```

### Parámetros configurados en el DAG:
- **`dag_id`**: `etl_bienestar_animal_hourly`
- **`schedule`**: `"0 * * * *"` (ejecución automática cada hora, al minuto `:00`, equivalente a `@hourly`)
- **`start_date`**: `datetime(2026, 10, 1)` (fecha fija)
- **`catchup`**: `False` (evita ejecuciones retroactivas masivas desde `start_date`)
- **`max_active_runs`**: `1` (garantiza que no se solapen dos corridas simultáneas)
- **`default_args`**: `{"owner": "bienestar_animal", "retries": 2, "retry_delay": timedelta(minutes=5)}`
- **`tags`**: `["ETL", "medallion", "bienestar-animal", "cali", "bogota"]`
- **Zona horaria**: `America/Bogota` (`UTC-5`), configurada en `docker-compose.yaml` mediante `AIRFLOW__CORE__DEFAULT_TIMEZONE: 'America/Bogota'` y `TZ: 'America/Bogota'`.

---

## 3. Pasos para levantar y ejecutar Airflow (con WSL2 y Docker Desktop)

Abra **Terminal** y sitúese dentro de la carpeta `airflow-medallon`:

```Terminal
cd C:\Users\Laura\Downloads\ETL_Bienestar_animal\airflow-medallon
```

### Paso 1: Construir la imagen personalizada con las librerías del ETL
```Terminal
docker compose build
```

### Paso 2: Inicializar la base de datos de Airflow (solo la primera vez)
```Terminal
docker compose up airflow-init
```
*(Espere hasta observar el mensaje `airflow-init exited with code 0`).*

### Paso 3: Levantar todos los contenedores de Airflow en segundo plano
```Terminal
docker compose up -d
```

### Paso 4: Verificar que los contenedores estén corriendo
```Terminal
docker ps
```

### Paso 5: Verificar que Airflow reconoce el DAG sin errores de importación
```Terminal
docker compose exec airflow-scheduler airflow dags list
docker compose exec airflow-scheduler airflow dags list-import-errors
```

### Paso 6: Acceder a la interfaz web de Airflow
- **URL**: `http://localhost:8080`
- **Usuario por defecto**: `airflow`
- **Contraseña por defecto**: `airflow`

---

## 4. Guía paso a paso para obtener las 5 Pruebas y Evidencias Exigidas (`P1` a `P5`)

### Prueba P1: DAG visible en Airflow sin errores de importación y con las 5 tareas
1. Ingrese a `http://localhost:8080` y busque el DAG **`etl_bienestar_animal_hourly`** (etiquetas: `ETL`, `medallion`, `bienestar-animal`, `cali`, `bogota`).
2. Haga clic sobre `etl_bienestar_animal_hourly` y abra la pestaña **Graph**.
3. **Captura P1**: Tome captura donde se observe que no hay alertas de importación y se visualicen las 5 tareas con sus dependencias:
   `[extract_api_bronze, extract_excel_bronze] >> transform_silver >> build_gold >> validate_gold`.

### Prueba P2: Ejecución manual exitosa con `gold_final.csv`, los 13 KPIs y SQLite validados
1. Active el interruptor (toggle) del DAG `etl_bienestar_animal_hourly` y presione el botón **Trigger DAG** (icono Play arriba a la derecha).
2. Observe cómo las 5 tareas pasan a verde (`success`).
3. Haga clic en la tarea `validate_gold` → pestaña **Logs** para ver el resumen impreso:
   - `gold_final.csv`: `404 filas x 9 columnas` (consolidando `17.642 casos de Cali` y `947 atenciones de Bogotá`)
   - `13 tablas de KPIs` en `data/gold/kpis/` (incluyendo priorización territorial, evolución mensual, cambio anual 2024 vs. 2025, brecha de prevención vs. casos críticos, top 25 barrios críticos, calidad por clase, patrón semanal y sesgo UCA en Bogotá)
   - Controles de calidad: `12 OK, 2 ADVERTENCIA, 0 ERROR` (`0 duplicados de llave`)
   - Carga en SQLite (`data/gold/warehouse.db`): `18 tablas` cargadas y `8 gráficas PNG` generadas en `evidencias/`.
4. **Captura P2**: Tome captura del Graph en estado `success` y del fragmento del log de `validate_gold`.

### Prueba P3: Evidencia de programación horaria (`0 * * * *`) y ejecución automática
1. Deje el interruptor (toggle) del DAG **activado (Unpaused)**.
2. En la barra superior del DAG se muestra `Schedule: 0 * * * *` y el próximo `Next Run` al minuto `:00` de la siguiente hora.
3. Al cumplirse el cierre del intervalo horario, el `airflow-scheduler` lanzará automáticamente una corrida con tipo `scheduled`.
4. **Captura P3**: Tome captura del historial de `Runs` mostrando tanto la corrida `manual` como la corrida `scheduled` disparada automáticamente por el scheduler.

### Prueba P4: Fallo inducido, log del error y evidencia de reintento o recuperación
El pipeline incluye un mecanismo seguro para inducir un fallo controlado sin dañar el código:
1. En PowerShell, cree el archivo disparador de fallo en Bronze:
   ```powershell
   New-Item -Path "..\Medallon\data\bronze\FORZAR_FALLO_API.txt" -ItemType File -Force
   ```
2. Ejecute manualmente el DAG (`Trigger DAG`) en Airflow.
3. Observe que `extract_api_bronze` entra en estado **`up_for_retry`** (amarillo/naranja) o **`failed`** (rojo) y que `transform_silver`, `build_gold` y `validate_gold` **no se ejecutan** (`upstream_failed`), respetando las dependencias del DAG.
4. Abra el **Log** de `extract_api_bronze` y tome captura del mensaje:
   `ConnectionError: Fallo simulado en extract_api_bronze: API de Datos Abiertos de Cali temporalmente inaccesible (FORZAR_FALLO_API.txt activo)`.
5. Ahora elimine el archivo disparador para simular que la API se recuperó:
   ```powershell
   Remove-Item -Path "..\Medallon\data\bronze\FORZAR_FALLO_API.txt" -Force
   ```
6. En Airflow, haga clic sobre la tarea `extract_api_bronze` → **Clear task** (o espere al reintento automático de los 5 minutos). La tarea se reejecutará y todo el flujo terminará en `success`.
7. **Captura P4**: Tome captura del estado `up_for_retry`/`failed`, del log del error y de la recuperación posterior en `success`.

### Prueba P5: Segunda ejecución sin duplicación de resultados (Idempotencia)
1. Dispare una segunda ejecución del DAG (`Trigger DAG`) o reejecute un intervalo existente (`Clear Dag Run`).
2. Compare el log de `build_gold` y `validate_gold` entre la primera y la segunda ejecución:
   - **Corrida 1**: `gold_final = 404 filas x 9 cols`, `casos_cali_total = 17642`, `atenciones_bogota_total = 947`, `duplicados_llave = 0`, `SQLite gold_final = 404 filas`, `zona_prioridad_1 = Comuna 20 (99.1)`, `barrio_critico_1 = Siloé (78 casos críticos)`.
   - **Corrida 2**: Exactamente `404 filas`, `17.642 casos de Cali`, `947 atenciones de Bogotá`, `0 duplicados` y los mismos valores de KPIs en las 18 tablas de `warehouse.db`.
3. **Captura P5**: Tome captura de las dos ejecuciones consecutivas en Airflow y de los logs mostrando que los conteos e indicadores permanecen idénticos.
