from __future__ import annotations

from datetime import datetime, timedelta
import os
from pathlib import Path
import sys

try:
    from airflow.sdk import dag, task
    _EN_AIRFLOW = True
except ImportError:
    _EN_AIRFLOW = False

    class _NodoLocal(dict):
        """Envoltorio de dict que soporta el operador >> en pruebas locales sin Airflow."""
        def __rshift__(self, other):
            return other

        def __rrshift__(self, other):
            return self

    def dag(**_kwargs):
        def _decorador(fn):
            return fn
        return _decorador

    def task(fn):
        def _wrapper(*args, **kwargs):
            res = fn(*args, **kwargs)
            return _NodoLocal(res) if isinstance(res, dict) else res
        return _wrapper


def _resolver_project_dir() -> Path:
    """Resuelve la ruta del proyecto ETL dentro del contenedor Docker (/opt/airflow/medallon) o en local."""
    rutas_docker = [
        Path("/opt/airflow/medallon"),
        Path("/opt/airflow/Medallon"),
    ]
    for ruta in rutas_docker:
        if ruta.exists() and (ruta / "config" / "config.yaml").exists():
            return ruta

    # Ruta local relativa cuando se ejecuta desde airflow-medallon/dags o Medallon/dags
    actual = Path(__file__).resolve().parent.parent
    if (actual / "config" / "config.yaml").exists():
        return actual
    alternativa = actual.parent / "Medallon"
    if (alternativa / "config" / "config.yaml").exists():
        return alternativa
    return actual


PROJECT_DIR = _resolver_project_dir()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))


@dag(
    dag_id="etl_bienestar_animal_hourly",
    description=(
        "Pipeline ETL Medallion (Bienestar Animal Cali CBA/Uaepa vs Bogotá IDPYBA): "
        "Bronze (API CKAN + Excel + GeoJSON) -> Silver -> Gold (JOIN + 13 KPIs) -> Validación, Gráficas y SQLite"
    ),
    start_date=datetime(2026, 10, 1),
    schedule="0 * * * *",  # cada hora, al minuto 00 (equivalente a @hourly)
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "bienestar_animal",
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["ETL", "medallion", "bienestar-animal", "cali", "bogota"],
)
def etl_bienestar_animal_hourly():
    @task
    def extract_api_bronze():
        """Extrae proyecciones de población de Cali (API CKAN) y GeoJSON de Bogotá (IDPYBA) hacia Bronze."""
        os.chdir(PROJECT_DIR)
        from etl.extract_api import run

        return run()

    @task
    def extract_excel_bronze():
        """Lee el archivo Excel de solicitudes de Cali (CBA/Uaepa), verifica SHA-256 y conserva copia en Bronze."""
        os.chdir(PROJECT_DIR)
        from etl.extract_excel import run

        return run()

    @task
    def transform_silver(api_path: dict, excel_path: dict):
        """Limpia, estandariza comunas/barrios/fechas de Cali, aplana el GeoJSON de Bogotá y genera trazabilidad."""
        os.chdir(PROJECT_DIR)
        from etl.transform_silver import run

        return run(api_path, excel_path)

    @task
    def build_gold(silver_path: dict):
        """Ejecuta los JOINs (dim_categoria + población) y construye gold_final.csv y los 13 KPIs de negocio."""
        os.chdir(PROJECT_DIR)
        from etl.build_gold import run

        return run(silver_path)

    @task
    def validate_gold(gold_path: dict):
        """Valida reglas de calidad (OKR 3 + consistencia Gold), carga 18 tablas en SQLite y genera 8 gráficas PNG."""
        os.chdir(PROJECT_DIR)
        from etl.validate_gold import run

        return run(gold_path)

    api = extract_api_bronze()
    excel = extract_excel_bronze()
    silver = transform_silver(api, excel)
    gold = build_gold(silver)
    validate = validate_gold(gold)

    [api, excel] >> silver >> gold >> validate
    return {
        "extract_api_bronze": api,
        "extract_excel_bronze": excel,
        "transform_silver": silver,
        "build_gold": gold,
        "validate_gold": validate,
    }


if _EN_AIRFLOW:
    dag_instance = etl_bienestar_animal_hourly()
