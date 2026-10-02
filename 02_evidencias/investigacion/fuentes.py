"""Carga de las fuentes YA DEPURADAS de investigacion (notebooks de 01_preprocesamiento) y de
la poblacion de esta seccion: personas con al menos una evidencia de trayectoria (misma regla
que Formacion; ya excluye a las identificadas en defuncion, DEC-030)."""
from __future__ import annotations

import pandas as pd

from evidencias.formacion.fuentes import cargar_poblacion  # noqa: F401 (misma poblacion)
from evidencias.trayectoria.fuentes import DATA_DIR, pc

ARCHIVO_PROYECTOS = DATA_DIR / "processed" / "proyectos_investigacion_disponible.csv"
ARCHIVO_REGISTRO_AUTORIDADES = DATA_DIR / "processed" / "registro_autoridades.csv"
SALIDA_DIR = DATA_DIR / "evidencias" / "investigacion"


def cargar_proyectos(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_PROYECTOS, low_memory=False)
    for c in ("FECHAINICIO", "FECHAFIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)


ARCHIVO_VINCULACION = DATA_DIR / "processed" / "proyectos_vinculacion_disponible.csv"


def cargar_vinculacion(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_VINCULACION, low_memory=False)
    for c in ("FECHAINICIO", "FECHAFIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)


ARCHIVO_PUBLICACIONES = DATA_DIR / "processed" / "publicaciones.csv"


def cargar_publicaciones(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_PUBLICACIONES, low_memory=False, dtype={
        "FACTORIMPACTOSJR": str, "FACTORIMPACTOCITESCORE": str, "NROISBN": str,
    })
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)


ARCHIVO_TESIS = DATA_DIR / "processed" / "proyecto_grado.csv"


def cargar_tesis(poblacion: set[int]) -> tuple[pd.DataFrame, int]:
    """Tesis dirigidas de la poblacion (la persona es IDDIRECTOR). Devuelve tambien cuantas
    filas de la fuente no tienen director (no se pueden asignar a nadie)."""
    df = pd.read_csv(ARCHIVO_TESIS, low_memory=False)
    sin_director = int(df["IDDIRECTOR"].isna().sum())
    df = df.dropna(subset=["IDDIRECTOR"]).assign(IDPERSONA=lambda d: d["IDDIRECTOR"].astype(int))
    df["FECHASUSTENTACION"] = pd.to_datetime(df["FECHASUSTENTACION"], format="mixed", errors="coerce")
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True), sin_director


ARCHIVO_PONENCIAS = DATA_DIR / "processed" / "ponentes_todos.csv"


def cargar_ponencias(poblacion: set[int]) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVO_PONENCIAS, low_memory=False)
    for c in ("FECHAINICIO", "FECHAFIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df[df["IDPERSONA"].isin(poblacion)].reset_index(drop=True)


def cargar_mapa_siglas() -> dict:
    return pc.construir_mapa_siglas_unidad(pd.read_csv(ARCHIVO_REGISTRO_AUTORIDADES, low_memory=False))
