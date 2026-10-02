"""Carga de la fuente de menciones de honor (`data/processed/mencion_honor.csv`) y de la
poblacion de esta seccion (personas con al menos una evidencia de trayectoria; misma regla
que Formacion, ya excluye defunciones, DEC-030).

La fuente trae el pais solo como IDPAIS, sin catalogo. El nombre se toma de la experiencia
externa (`data/raw/experenciaexterna.csv`), que trae IDPAIS y PAIS juntos: cada IDPAIS tiene
un unico nombre (verificado 2026-09-29) y cubre el 99 % de las menciones. Un IDPAIS que no
esta ahi (o 0) queda sin pais.
"""
from __future__ import annotations

import pandas as pd

from evidencias.formacion.fuentes import cargar_poblacion  # noqa: F401 (misma poblacion)
from evidencias.trayectoria.fuentes import DATA_DIR

ARCHIVO_MENCIONES = DATA_DIR / "processed" / "mencion_honor.csv"
ARCHIVO_PAISES = DATA_DIR / "raw" / "experenciaexterna.csv"
SALIDA_DIR = DATA_DIR / "evidencias" / "menciones_honor"


def cargar_paises() -> dict[int, str]:
    e = pd.read_csv(ARCHIVO_PAISES, low_memory=False, usecols=["IDPAIS", "PAIS"]).dropna()
    nombres = e.groupby("IDPAIS")["PAIS"].agg(lambda s: set(s.str.strip()))
    ambiguos = nombres[nombres.map(len) > 1]
    if len(ambiguos):
        raise ValueError(f"IDPAIS con mas de un nombre en {ARCHIVO_PAISES.name}: {ambiguos.to_dict()}")
    return {int(k): next(iter(v)) for k, v in nombres.items()}


def cargar_menciones(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_MENCIONES, low_memory=False)
    # Fechas imposibles en la fuente (anio 0024, 0199) quedan en null
    df["FECHA"] = pd.to_datetime(df["FECHA"], format="mixed", errors="coerce")
    df["PAIS"] = df["IDPAIS"].map(cargar_paises())
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)
