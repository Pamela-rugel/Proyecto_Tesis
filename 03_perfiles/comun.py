"""Rutas, carga de evidencias y utilidades compartidas del paquete `perfiles`."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
EVIDENCIAS_DIR = DATA_DIR / "evidencias"
PERFILES_DIR = DATA_DIR / "perfiles"
EMBEDDINGS_DIR = PERFILES_DIR / "embeddings"
EMBEDDINGS_TEMA_DIR = PERFILES_DIR / "embeddings_tema"
CLUSTERING_DIR = PERFILES_DIR / "clustering"

# Fuentes ya corregidas para filtrar (no son variables del clustering): DEC-023 dejo la
# vigencia correcta en historial_laboral_features (VIGENTE_ACTUALMENTE); el atributo `vigente`
# de las evidencias de trayectoria esta inflado (tramos sin fecha de fin), no se usa aqui.
ARCHIVO_HISTORIAL_FEATURES = DATA_DIR / "processed" / "historial_laboral_features.csv"

AMBITOS = {"todos": "Todo el personal", "administrativos": "Personal administrativo", "docentes": "Personal docente"}

# Vistas semanticas: que tipos de evidencia alimentan cada una
TIPOS_V1_TRAYECTORIA = [
    "TRAYECTORIA_CARGO_ESTRUCTURAL", "TRAYECTORIA_CONTRATO_PUNTUAL", "TRAYECTORIA_FUNCION_ADICIONAL",
    "TRAYECTORIA_EXPERIENCIA_EXTERNA", "ACTIVIDAD_CARGA",
]
TIPOS_V2_ACADEMICO = [
    "FORMACION_TITULO", "FORMACION_EN_CURSO", "PROYECTO_INVESTIGACION", "PROYECTO_VINCULACION", "PUBLICACION",
    "TESIS_DIRIGIDA", "PONENCIA", "DOCENCIA_MATERIA", "CAPACITACION", "CERTIFICACION", "MENCION_HONOR",
]


def archivos_evidencias() -> list[Path]:
    return sorted(EVIDENCIAS_DIR.glob("*/evidencias_*.csv"))


def cargar_evidencias(con_atributos: bool = True) -> pd.DataFrame:
    columnas = None if con_atributos else ["evidencia_id", "persona_id", "tipo_id", "texto"]
    return pd.concat([pd.read_csv(f, usecols=columnas) for f in archivos_evidencias()], ignore_index=True)


def huella_archivos(archivos: list[Path]) -> dict[str, str]:
    """SHA-256 (16 primeros caracteres) de cada archivo: identifica la version de los datos."""
    salida = {}
    for f in archivos:
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for bloque in iter(lambda: fh.read(1 << 20), b""):
                h.update(bloque)
        salida[str(f.relative_to(PROJECT_ROOT)).replace("\\", "/")] = h.hexdigest()[:16]
    return salida


def huella_texto(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def cargar_estado_personas() -> pd.DataFrame:
    """Tipo de empleado actual y vigencia de cada persona (fuente corregida en DEC-023). El tipo
    puede ser "ADMINISTRATIVO / DOCENTE" si tiene hoy contratos activos de ambos (DEC-054): esa
    persona entra en los dos ámbitos (ver `en_ambito`)."""
    f = pd.read_csv(ARCHIVO_HISTORIAL_FEATURES, low_memory=False,
                    usecols=["IDPERSONA", "TIPOS_EMPLEADO_ACTUALES", "VIGENTE_ACTUALMENTE", "CARGO_ACTUAL",
                             "UNIDAD_ACTUAL_NOMBRE"])
    return f.rename(columns={"IDPERSONA": "persona_id", "TIPOS_EMPLEADO_ACTUALES": "tipo_empleado",
                             "VIGENTE_ACTUALMENTE": "vigente", "CARGO_ACTUAL": "cargo_actual",
                             "UNIDAD_ACTUAL_NOMBRE": "unidad_actual"})


def en_ambito(tipo_empleado: pd.Series, ambito: str) -> pd.Series:
    """Máscara de pertenencia a un ámbito. Quien es "ADMINISTRATIVO / DOCENTE" está en ambos."""
    if ambito == "todos":
        return pd.Series(True, index=tipo_empleado.index)
    clave = {"administrativos": "ADMINISTRATIVO", "docentes": "DOCENTE"}[ambito]
    return tipo_empleado.fillna("").str.split(" / ").map(lambda tipos: clave in tipos)
