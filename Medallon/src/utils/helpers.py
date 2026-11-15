"""Utilidades compartidas: configuracion, logging y normalizacion de texto."""
import logging
import re
import unicodedata
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def ruta(relativa: str) -> Path:
    """Convierte una ruta relativa del config en ruta absoluta dentro del proyecto."""
    return ROOT / relativa


def cargar_config() -> dict:
    with open(ROOT / "config" / "config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_logger(nombre: str = "etl", log_file: str = "logs/log.txt") -> logging.Logger:
    logger = logging.getLogger(nombre)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    archivo = ruta(log_file)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(archivo, mode="a", encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def normalizar_texto(valor) -> str:
    """Minusculas, sin tildes, sin espacios repetidos. Valores nulos -> ''."""
    if valor is None:
        return ""
    texto = str(valor)
    if texto.lower() == "nan":
        return ""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto).strip().lower()
    return texto
