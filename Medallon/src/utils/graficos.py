"""Graficas de evidencia (se guardan en /evidencias)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.utils.helpers import get_logger, ruta

log = get_logger()
AZUL, NARANJA, ROJO, GRIS = "#2b6cb0", "#dd8b2f", "#c0392b", "#8a8f98"


def _guardar(fig, carpeta: str, nombre: str) -> None:
    destino = ruta(carpeta)
    destino.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(destino / nombre, dpi=140)
    plt.close(fig)
    log.info("Evidencia grafica: %s/%s", carpeta, nombre)


def grafica_casos_por_comuna(kpi_zona: pd.DataFrame, carpeta: str) -> None:
    d = kpi_zona[kpi_zona["tipo_zona"].eq("urbana")].sort_values("casos_total")
    top5 = set(d.nlargest(5, "casos_total")["zona"])
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(d["zona"], d["casos_total"], color=[ROJO if z in top5 else AZUL for z in d["zona"]])
    ax.set_title("Cali: casos por comuna (en rojo, las 5 con más casos)")
    ax.set_xlabel("Número de casos registrados")
    _guardar(fig, carpeta, "01_casos_por_comuna.png")


def grafica_evolucion_mensual(evol: pd.DataFrame, carpeta: str) -> None:
    # Se excluyen meses con muy pocos registros (ej. 2026-06 con 3 casos): no son una serie continua
    d = evol[evol["mes_con_registros"] & (evol["casos_total"] >= 10)]
    fig, ax = plt.subplots(figsize=(10, 5))
    for col, color in [("PQR", AZUL), ("Cita médica", NARANJA), ("Esterilizaciones", "#2f855a"),
                       ("Denuncia", ROJO), ("Urgencias", "#6b46c1")]:
        if col in d:
            ax.plot(d["anio_mes"], d[col], marker="o", ms=3, label=col, color=color)
    ax.plot(d["anio_mes"], d["casos_total"], color="black", lw=2, ls="--", label="Total")
    ax.set_xticks(range(0, len(d), 2))
    ax.set_xticklabels(d["anio_mes"].iloc[::2], rotation=60, ha="right", fontsize=8)
    ax.set_title("Cali: evolución mensual de solicitudes por tipo (2024-01 a 2025-12)")
    ax.set_ylabel("Casos")
    ax.legend(ncol=3, fontsize=8)
    _guardar(fig, carpeta, "02_evolucion_mensual.png")


def grafica_urgencias_ciudades(urg: pd.DataFrame, carpeta: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, ciudad, color in zip(axes, ["Cali", "Bogotá"], [AZUL, NARANJA]):
        d = urg[urg["ciudad"] == ciudad].sort_values("urgencias").tail(12)
        ax.barh(d["zona"], d["urgencias"], color=color)
        ax.set_title(f"{ciudad}: urgencias/atenciones por zona (top 12)")
        ax.set_xlabel("Casos")
    fig.suptitle("Distribución territorial de urgencias. Ojo: Bogotá es un corte acumulado a 30/06/2025", fontsize=10)
    _guardar(fig, carpeta, "03_urgencias_cali_vs_bogota.png")


def grafica_calidad(calidad: pd.DataFrame, carpeta: str) -> None:
    ind = ["pct_registros_sin_comuna", "pct_registros_sin_barrio", "pct_registros_con_error_de_fecha"]
    d = calidad[calidad["indicador"].isin(ind)].set_index("indicador").loc[ind]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = range(len(d))
    ax.bar([i - 0.2 for i in x], d["antes_bronze"], 0.4, label="Antes (bronze)", color=GRIS)
    ax.bar([i + 0.2 for i in x], d["despues_silver"], 0.4, label="Después (silver)", color=AZUL)
    ax.set_xticks(list(x))
    ax.set_xticklabels(["% sin comuna", "% sin barrio", "% error de fecha"])
    ax.set_ylabel("% de registros")
    ax.set_title("Calidad de datos de Cali: antes vs después")
    ax.legend()
    _guardar(fig, carpeta, "04_calidad_antes_despues.png")


def grafica_cambio_anual_servicios(cambio: pd.DataFrame, carpeta: str) -> None:
    principales = ["PQR", "Cita médica", "Esterilizaciones", "Denuncia", "Urgencias", "Adopciones"]
    d = cambio[cambio["clase"].isin(principales)].set_index("clase").reindex(principales).dropna(how="all")
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    x = range(len(d))
    axes[0].bar([i - 0.2 for i in x], d["casos_2024"], 0.4, label="2024", color=GRIS)
    axes[0].bar([i + 0.2 for i in x], d["casos_2025"], 0.4, label="2025", color=AZUL)
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(d.index, rotation=30, ha="right", fontsize=8.5)
    axes[0].set_ylabel("Número de casos")
    axes[0].set_title("Cali: volumen por tipo de solicitud (2024 vs 2025)")
    axes[0].legend()

    axes[1].bar([i - 0.2 for i in x], d["pct_mix_2024"], 0.4, label="% Mix 2024", color=GRIS)
    axes[1].bar([i + 0.2 for i in x], d["pct_mix_2025"], 0.4, label="% Mix 2025", color=NARANJA)
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(d.index, rotation=30, ha="right", fontsize=8.5)
    axes[1].set_ylabel("% sobre el total anual")
    axes[1].set_title("Transformación del mix: de PQR/Esterilización a Citas/Urgencias")
    axes[1].legend()
    _guardar(fig, carpeta, "05_cambio_mix_2024_vs_2025.png")


def grafica_brecha_prevencion(brecha: pd.DataFrame, carpeta: str) -> None:
    d = brecha[brecha["tipo_zona"].eq("urbana")].sort_values("casos_criticos").tail(12)
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    y = range(len(d))
    ax.barh([i - 0.2 for i in y], d["casos_criticos"], 0.4, label="Casos críticos (Denuncias + Urgencias)", color=ROJO)
    ax.barh([i + 0.2 for i in y], d["esterilizaciones"], 0.4, label="Esterilizaciones (Prevención)", color="#2f855a")
    ax.set_yticks(list(y))
    ax.set_yticklabels(d["zona"])
    ax.set_xlabel("Número de registros")
    ax.set_title("Cali: brecha entre casos críticos y esterilizaciones (Top 12 comunas críticas)")
    ax.legend()
    _guardar(fig, carpeta, "06_brecha_prevencion_vs_criticos.png")


def grafica_top_barrios(top_barrios: pd.DataFrame, carpeta: str) -> None:
    d = top_barrios.head(12).iloc[::-1].copy()
    etiquetas = [f"{r.barrio} ({r.zona})" for r in d.itertuples()]
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    ax.barh(etiquetas, d["denuncias"], label="Denuncias", color=ROJO)
    ax.barh(etiquetas, d["urgencias"], left=d["denuncias"], label="Urgencias", color=NARANJA)
    ax.set_xlabel("Casos críticos acumulados (Denuncias + Urgencias)")
    ax.set_title("Cali: Top 12 barrios ('hotspots') por volumen de casos críticos")
    ax.legend()
    _guardar(fig, carpeta, "07_top_barrios_criticos_cali.png")


def grafica_bogota_sesgo_uca(bog_comp: pd.DataFrame, carpeta: str) -> None:
    dx_all = bog_comp[bog_comp["dimension"] == "diagnostico"].copy()
    dx_all["total"] = dx_all["casos_engativa_uca"] + dx_all["casos_resto_19_localidades"]
    dx = dx_all.sort_values("total", ascending=False).head(6).iloc[::-1]
    pr = bog_comp[bog_comp["dimension"] == "procedencia"].iloc[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5))

    y1 = range(len(dx))
    axes[0].barh([i - 0.2 for i in y1], dx["pct_engativa_uca"], 0.4, label="Engativá (sede UCA)", color=GRIS)
    axes[0].barh([i + 0.2 for i in y1], dx["pct_resto_19_localidades"], 0.4, label="Resto 19 localidades", color=AZUL)
    axes[0].set_yticks(list(y1))
    axes[0].set_yticklabels(dx["categoria"])
    axes[0].set_xlabel("% de atenciones")
    axes[0].set_title("Diagnósticos: Engativá vs Resto de Bogotá")
    axes[0].legend(fontsize=8)

    y2 = range(len(pr))
    axes[1].barh([i - 0.2 for i in y2], pr["pct_engativa_uca"], 0.4, label="Engativá (sede UCA)", color=GRIS)
    axes[1].barh([i + 0.2 for i in y2], pr["pct_resto_19_localidades"], 0.4, label="Resto 19 localidades", color=NARANJA)
    axes[1].set_yticks(list(y2))
    axes[1].set_yticklabels(pr["categoria"])
    axes[1].set_xlabel("% de atenciones")
    axes[1].set_title("Canal de ingreso: Engativá vs Resto de Bogotá")
    axes[1].legend(fontsize=8)

    fig.suptitle("Bogotá: aislamiento del sesgo de infraestructura (UCA en Engativá vs operación en las demás localidades)", fontsize=10)
    _guardar(fig, carpeta, "08_bogota_sesgo_uca_vs_resto.png")
