"""Carga de la fuente YA DEPURADA de formacion (`data/processed/reporte_titulaciones_educacion.csv`,
notebook 01_preprocesamiento/18) y de la poblacion de esta seccion.

Poblacion (decision del usuario, 2026-09-28): solo las personas que tienen al menos una
evidencia de trayectoria (`data/evidencias/trayectoria/evidencias_trayectoria.csv`), que ya
excluye a las identificadas en defuncion (DEC-030) y a quienes no tienen trayectoria.
"""
from __future__ import annotations

import pandas as pd

from evidencias.trayectoria.fuentes import DATA_DIR, pc  # noqa: F401 (pc: configura sys.path)

ARCHIVO_TITULOS = DATA_DIR / "processed" / "reporte_titulaciones_educacion.csv"
ARCHIVO_EVIDENCIAS_TRAYECTORIA = DATA_DIR / "evidencias" / "trayectoria" / "evidencias_trayectoria.csv"
SALIDA_DIR = DATA_DIR / "evidencias" / "formacion"

# Datos personales o administrativos: se descartan al leer, nunca llegan a las evidencias.
_COLUMNAS_EXCLUIDAS = [
    "NumeroIdentificacion", "Apellidos", "Nombres", "CodEstudiante", "RefArchivo",
    "FechaSubidaArchivoTitulo", "ValidadoThMateriasAprobadas", "ValidadoThRankGraduado",
    "ValidadoThRankIes",
]


def cargar_poblacion() -> set[int]:
    personas = set(pd.read_csv(ARCHIVO_EVIDENCIAS_TRAYECTORIA, usecols=["persona_id"])["persona_id"].astype(int))
    return personas - pc.cargar_ids_defunciones()


def cargar_titulos(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_TITULOS, low_memory=False)
    df = df.drop(columns=[c for c in _COLUMNAS_EXCLUIDAS if c in df.columns]).rename(columns={"IdPersona": "IDPERSONA"})
    df["FechaGraduacion"] = pd.to_datetime(df["FechaGraduacion"], format="mixed", errors="coerce")
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)
