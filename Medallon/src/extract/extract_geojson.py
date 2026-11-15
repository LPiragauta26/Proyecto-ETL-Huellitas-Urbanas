"""Extraccion (capa BRONZE) de Bogota: lee el GeoJSON sin modificarlo."""
import json

from src.extract.extract_csv import sha256_archivo
from src.utils.helpers import get_logger, ruta

log = get_logger()


def extraer_bogota(path: str) -> dict:
    """Devuelve el GeoJSON completo (dict) tal cual esta en el archivo."""
    archivo = ruta(path)
    with open(archivo, "r", encoding="utf-8") as f:
        data = json.load(f)
    log.info("BRONZE Bogota: %s features | sha256=%s", len(data.get("features", [])), sha256_archivo(archivo)[:16])
    return data
