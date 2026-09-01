"""
Utilidades compartidas entre `07_dashboard.ipynb` (preparacion de datos) y
`app.py` (aplicacion Streamlit). No importa Streamlit: solo pandas/numpy, para
poder reutilizarse tambien desde el notebook sin esa dependencia.
"""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
FEATURES_DIR = DATA / "features"
CLUSTERING_DIR = DATA / "clustering"
EMBEDDINGS_DIR = DATA / "embeddings"
DASHBOARD_DIR = DATA / "dashboard"

# Nombres e interpretacion de perfiles: sintesis de la seccion 8 de
# `notebooks/05_clustering/05_clustering.ipynb` (DEC-001). No son una
# categoria institucional oficial de ESPOL.
PERFIL_NOMBRES = {
    0: "Docente de trayectoria historica moderada (mayormente no vigente)",
    1: "Administrativo",
    2: "Alta produccion academica e investigativa / liderazgo integral",
    3: "Alta carga docente",
    4: "Ingreso reciente / trayectoria corta",
}

PERFIL_DESCRIPCIONES = {
    0: (
        "Personas con actividad docente historica moderada (mediana ~1233 horas, 4 periodos, "
        "17 cursos), casi siempre con un solo regimen contractual y nivel academico de cuarto "
        "nivel, pero cuya relacion laboral docente ya no esta vigente en su mayoria "
        "(3.7% vigentes vs 30.9% a nivel institucional)."
    ),
    1: (
        "95.7% de personal administrativo, con la mayor experiencia administrativa "
        "(mediana 11.15 anios vs 0.84 institucional), regimen LOSEP predominante y la mayor "
        "proporcion actualmente vigente (67.3% vs 30.9% institucional)."
    ),
    2: (
        "El grupo con mas actividad en casi todas las dimensiones: maximo de periodos de "
        "docencia, mas horas y actividades politecnicas, mas proyectos de investigacion "
        "(incl. como director), mas publicaciones, alta proporcion de roles docente-"
        "administrativo mixtos (72.5%) y de multiples cargos en un mismo anio (95.4%). "
        "Todas las personas tienen nivel academico de cuarto nivel."
    ),
    3: (
        "El grupo con mayor carga de docencia pura: maximo de horas de docencia "
        "(mediana 5082 h), mas cursos (63) y mas estudiantes atendidos (1406), con actividad "
        "politecnica alta pero sin el mismo nivel de produccion investigativa que el perfil 2."
    ),
    4: (
        "Antiguedad efectiva y de calendario muy bajas (mediana ~1.2-1.4 anios), pocos "
        "registros historicos (mediana 4 vs 20.5 institucional), un solo cargo distinto, pocas "
        "capacitaciones, nivel academico predominante de tercer nivel y practicamente nadie "
        "vigente actualmente (0.5%)."
    ),
}

# Subconjunto curado de `dataset_personas_features.csv` para tarjetas de
# persona / comparaciones rapidas (evita saturar la UI con las 85 columnas).
METRICAS_CLAVE = [
    "TIPOEMPLEADO_ACTUAL_DESC",
    "CARGO_ACTUAL",
    "UNIDAD_ACTUAL_NOMBRE",
    "VIGENTE_ACTUALMENTE",
    "NIVEL_ACADEMICO_MAXIMO",
    "ANTIGUEDAD_EFECTIVA_ANIOS",
    "NUM_PERIODOS_DOCENCIA",
    "TOTAL_HORAS_DOCENCIA",
    "NUM_PUBLICACIONES",
    "NUM_PROYECTOS_INVESTIGACION",
    "NUM_PROYECTOS_VINCULACION",
    "ANIOS_EXPERIENCIA_ADMINISTRATIVO",
    "NUM_CAPACITACIONES",
    "NUM_IDIOMAS",
    "NUM_RECONOCIMIENTOS",
]

# Variables numericas usadas para el grafico radar / comparacion de perfil
# (todas presentes en `dataset_personas_features.csv`, escalas heterogeneas
# por lo que se normalizan 0-1 por percentil antes de graficar).
RADAR_FEATURES = [
    "TOTAL_HORAS_DOCENCIA",
    "NUM_PUBLICACIONES",
    "NUM_PROYECTOS_INVESTIGACION",
    "NUM_PROYECTOS_VINCULACION",
    "ANIOS_EXPERIENCIA_ADMINISTRATIVO",
    "NUM_CAPACITACIONES",
]

DISCLAIMER = (
    "Los perfiles son una sintesis analitica basada en patrones de los datos historicos "
    "disponibles, no una categoria institucional oficial de ESPOL ni un juicio de valor sobre "
    "las personas. Esta herramienta es un apoyo a la decision: no debe usarse como criterio "
    "automatico de contratacion, promocion o asignacion sin la intervencion y el criterio de "
    "las unidades institucionales correspondientes."
)


def _read_csv(path: Path, **kwargs) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"No se encontro {path}. Ejecuta primero las secciones de preparacion de datos "
            "de 07_dashboard.ipynb (o, si faltan insumos, los notebooks 05_clustering / "
            "06_embeddings)."
        )
    return pd.read_csv(path, **kwargs)


def load_personas_dashboard() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "personas_dashboard.csv")


def load_cluster_resumen() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "cluster_perfiles_resumen.csv")


def load_cluster_top_features() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "cluster_top_features.csv")


def load_feature_dictionary() -> pd.DataFrame:
    return _read_csv(FEATURES_DIR / "feature_dictionary.csv")


@lru_cache(maxsize=1)
def feature_label_map() -> dict:
    """FEATURE -> descripcion legible (feature_dictionary.csv), con fallback al nombre crudo."""
    fd = load_feature_dictionary()
    return dict(zip(fd["FEATURE"], fd["DESCRIPTION"]))


def load_embeddings() -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (ids, matriz normalizada L2) desde embeddings_personas.csv."""
    df = _read_csv(EMBEDDINGS_DIR / "embeddings_personas.csv")
    ids = df["IDPERSONA"].to_numpy()
    matrix = df.drop(columns=["IDPERSONA"]).to_numpy(dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return ids, matrix / norms


def load_corpus_texto() -> pd.DataFrame:
    return _read_csv(EMBEDDINGS_DIR / "corpus_texto_detalle.csv")


def load_cobertura_texto() -> pd.DataFrame:
    return _read_csv(EMBEDDINGS_DIR / "cobertura_texto_personas.csv")


def percentile_normalize(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """Normaliza columnas numericas a percentil [0,1] dentro de la poblacion dada."""
    out = pd.DataFrame(index=df.index)
    for c in cols:
        out[c] = df[c].rank(pct=True)
    return out
