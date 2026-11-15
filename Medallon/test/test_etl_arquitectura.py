"""Pruebas de integridad de la estructura ETL Medallion (Extract, Transform, Load, API y App)."""
from pathlib import Path

from api.main import cargar_gold
from app.app import calcular_metricas_dataframe, resumen_capas_etl

MEDALLON_DIR = Path(__file__).resolve().parent.parent


def test_estructura_carpetas_medallon():
    """Verifica que todas las carpetas de la arquitectura Medallion y ETL existan."""
    carpetas_requeridas = [
        "api",
        "app",
        "config",
        "data/bronze",
        "data/silver",
        "data/gold",
        "data/gold/kpis",
        "etl",
        "evidencias",
        "logs",
        "notebooks",
        "src/extract",
        "src/transform",
        "src/quality",
        "src/load",
        "src/utils",
    ]
    for carpeta in carpetas_requeridas:
        assert (MEDALLON_DIR / carpeta).exists(), f"Falta la carpeta requerida: {carpeta}"


def test_resumen_capas_etl_completo():
    """Verifica que las etapas Extract (Bronze), Transform (Silver/Gold) y Load (SQLite) estén completas."""
    info = resumen_capas_etl()
    assert all(info["bronze"].values())
    assert info["silver"]["filas_cali"] == 17642
    assert info["silver"]["filas_bogota"] == 20
    assert info["gold"]["filas_gold_final"] == 404
    assert info["gold"]["total_kpis_csv"] == 13
    assert info["load_warehouse"]["total_tablas_sqlite"] == 18
    assert info["calidad_y_evidencias"]["graficas_png"] == 8


def test_metricas_streamlit_bienestar_animal():
    """Verifica el cálculo de métricas de Streamlit (categoría principal, total casos y gráfica) sobre gold_final."""
    df_gold = cargar_gold()
    res = calcular_metricas_dataframe(df_gold)
    assert res["columna_categoria"] == "categoria"
    assert res["columna_numerica"] == "casos"
    assert res["categoria_principal"] == "PQR"
    assert res["total_casos"] == 18589
    assert not res["serie_grafica"].empty

