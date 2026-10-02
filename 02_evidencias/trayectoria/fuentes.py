"""Carga de las fuentes YA DEPURADAS de trayectoria (salidas de 01_preprocesamiento y
04_trayectorias). No se lee nada de data/raw: la depuracion (categorias de cargo, ruido,
fechas efectivas, consolidacion de tramos) ya ocurrio en el pipeline y se reutiliza aqui.

Reutiliza `_preprocesamiento_comun` (pc) en vez de reimplementar sus reglas. La consolidacion
de tramos de cargo + unidad vive en `evidencias/trayectoria/tramos.py` (antes en
`notebooks/07_embeddings/_embeddings_comun.py`, eliminado en la limpieza del 2026-09-30).
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SALIDA_DIR = DATA_DIR / "evidencias" / "trayectoria"

_ruta = str(PROJECT_ROOT / "01_preprocesamiento_features" / "01_preprocesamiento")
if _ruta not in sys.path:
    sys.path.insert(0, _ruta)

import _preprocesamiento_comun as pc  # noqa: E402

ARCHIVOS = {
    "poblacion": DATA_DIR / "processed" / "datos_personales_ultimos_5anios.csv",
    "personas_excluidas": DATA_DIR / "processed" / "personas_excluidas.csv",
    "tramos_rol": DATA_DIR / "trayectorias" / "tramos_rol.csv",
    "eventos_puntuales": DATA_DIR / "trayectorias" / "eventos_puntuales_cargo.csv",
    "funciones_adicionales": DATA_DIR / "trayectorias" / "funciones_adicionales_persona.csv",
    "experiencia_externa": DATA_DIR / "processed" / "experiencia_externa.csv",
    "registro_autoridades": DATA_DIR / "processed" / "registro_autoridades.csv",
}


@dataclass
class FuentesTrayectoria:
    poblacion: set[int]
    personas_excluidas: pd.DataFrame  # IDPERSONA, MOTIVO (p.ej. identificada en defuncion)
    tramos_rol: pd.DataFrame
    eventos_puntuales: pd.DataFrame
    funciones_adicionales: pd.DataFrame
    experiencia_externa: pd.DataFrame
    mapa_siglas: dict


def _leer(clave: str, fechas: list[str] | None = None) -> pd.DataFrame:
    df = pd.read_csv(ARCHIVOS[clave], low_memory=False)
    for c in fechas or []:
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df


def _personas_excluidas(poblacion_archivo: set[int], defunciones: set[int]) -> pd.DataFrame:
    """Personas excluidas de todo analisis (DEC-030). Se leen de
    `personas_excluidas.csv` (salida del notebook 07); se agregan las defunciones que aun
    esten en el archivo de poblacion por si este quedo desactualizado."""
    archivo = ARCHIVOS["personas_excluidas"]
    excluidas = (
        pd.read_csv(archivo) if archivo.exists()
        else pd.DataFrame(columns=["IDPERSONA", "MOTIVO"])
    )
    faltantes = sorted((poblacion_archivo & defunciones) - set(excluidas["IDPERSONA"]))
    if faltantes:
        excluidas = pd.concat([excluidas, pd.DataFrame({"IDPERSONA": faltantes, "MOTIVO": pc.MOTIVO_DEFUNCION})])
    return excluidas.astype({"IDPERSONA": int}).reset_index(drop=True)


def cargar_fuentes() -> FuentesTrayectoria:
    poblacion_archivo = set(_leer("poblacion")["IDPERSONA"].astype(int))
    defunciones = pc.cargar_ids_defunciones()
    return FuentesTrayectoria(
        poblacion=poblacion_archivo - defunciones,
        personas_excluidas=_personas_excluidas(poblacion_archivo, defunciones),
        tramos_rol=_leer("tramos_rol", ["TRAMO_INICIO", "TRAMO_FIN"]),
        eventos_puntuales=_leer(
            "eventos_puntuales", ["FECHAINICIOCONTRATO", "FECHAFINCONTRATO", "FECHADESVINCULACION"]
        ),
        funciones_adicionales=_leer("funciones_adicionales", ["FECHA_DESDE", "FECHA_HASTA"]),
        experiencia_externa=_leer("experiencia_externa", ["FECHADESDE", "FECHAHASTA"]),
        mapa_siglas=pc.construir_mapa_siglas_unidad(_leer("registro_autoridades")),
    )


def sigla_unidad(unidad: str | None, mapa_siglas: dict) -> str | None:
    if not unidad:
        return None
    return mapa_siglas.get(unidad)


def unidad_para_texto(unidad: str | None, sigla: str | None) -> str | None:
    if not unidad:
        return None
    if not sigla or sigla.upper() in unidad.upper().split():
        return unidad
    return f"{unidad} ({sigla})"


# --- Texto de evidencias de trayectoria (2026-09-27): sin verbos ni "ESPOL"; solo el cargo,
# el lugar y los detalles disponibles, separados por coma. Lo que no se conoce se omite.

_NOMBRE_NIVEL = {"GRADO": "grado", "POSGRADO": "posgrado"}


def niveles_para_texto(niveles: list[str], base: str) -> str:
    """' (grado)', ' (posgrado)' o ' (grado y posgrado)' segun los niveles conocidos; vacio
    si no hay ninguno o si el texto base ya los menciona."""
    nombres = [_NOMBRE_NIVEL[n] for n in ("GRADO", "POSGRADO") if n in niveles]
    if not nombres or all(re.search(rf"\b{n.upper()}\b", base.upper()) for n in nombres):
        return ""
    return f" ({' y '.join(nombres)})"


def texto_cargo_lugar(descripcion: str, lugar: str | None) -> str:
    return f"{descripcion}, {lugar}" if lugar else descripcion
