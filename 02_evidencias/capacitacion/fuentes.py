"""Carga de las fuentes YA DEPURADAS de capacitacion (notebooks 01_preprocesamiento de
capacitaciones y certificados) y de la poblacion de esta seccion: personas con al menos una
evidencia de trayectoria (misma regla que Formacion; ya excluye defunciones, DEC-030).

`capacitaciones_todas`, `certificados_todos` y `ponentes_todos` son tablas distintas del mismo
sistema (no comparten IDCAPACITACION)."""
from __future__ import annotations

import pandas as pd

from evidencias.formacion.fuentes import cargar_poblacion  # noqa: F401 (misma poblacion)
from evidencias.trayectoria.fuentes import DATA_DIR

ARCHIVO_CAPACITACIONES = DATA_DIR / "processed" / "capacitaciones_todas.csv"
ARCHIVO_CERTIFICADOS = DATA_DIR / "processed" / "certificados_todos.csv"
SALIDA_DIR = DATA_DIR / "evidencias"

# Columnas que usan las reglas; si la limpieza quito alguna por constante/vacia, queda en null
_COLUMNAS = ["IDCAPACITACION", "IDPERSONA", "NOMBRE", "FECHAINICIO", "FECHAFIN", "DURACION",
             "TIPOEVENTODESCRIPCION", "NOMBREPAIS", "TIPOMODALIDADDESCRIPCION", "CERTIFICADOPOR",
             "TIPODESCRIPCION", "TIPOCAPACITACION", "IDTIPOCONOCIMIEN"]


def _cargar(archivo, poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(archivo, low_memory=False)
    for c in _COLUMNAS:
        if c not in df.columns:
            df[c] = None
    for c in ("FECHAINICIO", "FECHAFIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df.loc[df["IDPERSONA"].isin(poblacion), _COLUMNAS].reset_index(drop=True)


def cargar_capacitaciones(poblacion: set[int]) -> pd.DataFrame:
    return _cargar(ARCHIVO_CAPACITACIONES, poblacion)


def cargar_certificados(poblacion: set[int]) -> pd.DataFrame:
    # Todas son TIPOEVENTO = CERTIFICACION (constante, la quito la limpieza): no aporta
    return _cargar(ARCHIVO_CERTIFICADOS, poblacion).assign(TIPOEVENTODESCRIPCION=None)
