"""Carga de la fuente de idiomas y de la poblacion de esta seccion (personas con al menos una
evidencia de trayectoria; misma regla que Formacion, ya excluye defunciones, DEC-030).

Base: `data/processed/idiomas_personas.csv`. La limpieza descarto columnas que las reglas
necesitan, asi que se recuperan del raw `data/raw/idiomaspersonas.csv` uniendo por
IDIDIOMAPERSONA (unico en ambos; las demas columnas coinciden fila a fila):
- DESCRIPCION: nombre real del idioma cuando IDIOMA = 'OTRO'
- LENGUANATIVA: el processed convirtio el vacio en 0; aqui el vacio se conserva (desconocido)
- NIVELCOMPRESION y NAMEARCHDOC (archivo de respaldo)
"""
from __future__ import annotations

import pandas as pd

from evidencias.formacion.fuentes import cargar_poblacion  # noqa: F401 (misma poblacion)
from evidencias.trayectoria.fuentes import DATA_DIR

ARCHIVO_IDIOMAS = DATA_DIR / "processed" / "idiomas_personas.csv"
ARCHIVO_IDIOMAS_RAW = DATA_DIR / "raw" / "idiomaspersonas.csv"
SALIDA_DIR = DATA_DIR / "evidencias" / "idiomas"


def cargar_idiomas(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_IDIOMAS, low_memory=False).drop(columns=["LENGUANATIVA"])
    raw = pd.read_csv(ARCHIVO_IDIOMAS_RAW, low_memory=False)[
        ["IDIDIOMAPERSONA", "DESCRIPCION", "LENGUANATIVA", "NIVELCOMPRESION", "NAMEARCHDOC"]
    ]
    df = df.merge(raw, on="IDIDIOMAPERSONA", how="left", validate="one_to_one")
    for c in ("NIVELLECTURA", "NIVELESCRITURA", "NIVELCONVERSACION", "NIVELCOMPRESION", "NIVELMCER", "LENGUANATIVA"):
        df[c] = df[c].astype("string").str.strip()
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)
