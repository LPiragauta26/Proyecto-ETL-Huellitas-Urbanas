"""Extraccion desde API del portal de Datos Abiertos de Cali (CKAN datastore_search).

IMPORTANTE: esta funcion solo se usa si config.api.enabled = true y se define resource_id.
Si la API falla (o esta deshabilitada) el pipeline usa el archivo local de bronze.
Nota: no se pudo probar contra el portal real desde el entorno de desarrollo; verificar
base_url y resource_id con el recurso publicado por la Uaepa.
"""
import pandas as pd
import json
from src.utils.helpers import get_logger, ruta

log = get_logger()


def extraer_cali_api(cfg_api: dict) -> pd.DataFrame:
    import requests  # import local: solo se necesita si se usa la API

    if not cfg_api.get("resource_id"):
        raise ValueError("api.resource_id vacio en config.yaml")
    filas, offset = [], 0
    while True:
        resp = requests.get(
            cfg_api["base_url"],
            params={"resource_id": cfg_api["resource_id"], "limit": cfg_api["page_size"], "offset": offset},
            timeout=cfg_api["timeout"],
        )
        resp.raise_for_status()
        lote = resp.json()["result"]["records"]
        if not lote:
            break
        filas.extend(lote)
        offset += len(lote)
    df = pd.DataFrame(filas).astype(str)
    destino = ruta(cfg_api["guardar_en"])
    df.to_csv(destino, index=False, encoding="utf-8")
    log.info("BRONZE API: %s registros descargados -> %s", len(df), destino.name)
    return df

def extraer_poblacion_api(cfg_pob: dict) -> pd.DataFrame:
    """Consume la API (CKAN datastore_search) del portal de Datos Abiertos de Cali:
    proyecciones de población por comuna y corregimiento. Guarda la respuesta original en bronze.
    Si la red falla pero ya existe el snapshot en bronze, lo carga para garantizar reproducibilidad."""
    import requests

    destino = ruta(cfg_pob["guardar_en"])
    try:
        resp = requests.get(
            cfg_pob["base_url"],
            params={"resource_id": cfg_pob["resource_id"], "limit": cfg_pob.get("limit", 500)},
            timeout=cfg_pob["timeout"],
        )
        resp.raise_for_status()
        datos = resp.json()
        if not datos.get("success"):
            raise ValueError("La API de población respondió con success=false")
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
        df = pd.DataFrame(datos["result"]["records"])
        log.info("BRONZE API población: %s registros -> %s", len(df), destino.name)
        return df
    except Exception as e:
        if destino.exists():
            log.warning("API de población sin conexión (%s). Se usa snapshot local de bronze: %s", e, destino.name)
            datos = json.loads(destino.read_text(encoding="utf-8"))
            return pd.DataFrame(datos["result"]["records"])
        raise