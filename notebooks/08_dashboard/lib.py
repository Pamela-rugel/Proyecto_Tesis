"""
Utilidades compartidas entre `08_dashboard.ipynb` (preparacion de datos) y
`app.py` (aplicacion Streamlit). No importa Streamlit: solo pandas/numpy, para
poder reutilizarse tambien desde el notebook sin esa dependencia.
"""

from __future__ import annotations

import sys
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
TRAYECTORIAS_DIR = DATA / "trayectorias"
PROCESSED_DIR = DATA / "processed"

sys.path.insert(0, str(ROOT / "notebooks" / "01_preprocesamiento"))
import _preprocesamiento_comun as pc  # noqa: E402 (import tras sys.path.insert, necesario)

# Nombres e interpretacion de perfiles: sintesis de la seccion 13 de
# `notebooks/06_clustering/06_clustering.ipynb` (DEC-009, reemplaza DEC-008). No son una
# categoria institucional oficial de ESPOL. IMPORTANTE: a diferencia de DEC-007/DEC-008,
# estos perfiles YA NO salen de K-Means - son la categoria de cargo real de cada persona
# (`CATEGORIA_CARGO_ACTUAL`, calculada por reglas en `04_trayectorias.ipynb`/DEC-004: Autoridad
# Academica, Docente Titular, Tecnico Docente, Profesional/Analista, etc.). Patrones de
# actividad como "movilidad de rol" ya NO son una categoria de grupo: viven en las variables
# (N_TRANSICIONES_ROL, TUVO_TRANSICION_AA_A_DD, ...) y se exploran por *cercania* en el mapa
# de puntos (pestaña "Mapa de perfiles"), no forzando una etiqueta nueva - asi, un docente
# con trayectoria parecida a la de un subdecano puede aparecer visualmente cerca de ese grupo
# sin dejar de estar etiquetado como lo que realmente es.
#
# GRUPO_PRINCIPAL (TIPOEMPLEADO_ACTUAL_DESC) y CLUSTER (categoria de cargo real) se calculan
# con logicas de "actual" ligeramente distintas y no siempre coinciden en la rama esperada
# (ver clusters_personas.csv, columnas GRUPO_PRINCIPAL/SUBGRUPO) - el caso mas notable son
# 74 personas TIPOEMPLEADO=ADMINISTRATIVO cuya categoria de cargo vigente es Tecnico Docente.
# Por eso NO hay un mapeo fijo cluster->rama unico: usar clusters_personas.csv/personas
# ("GRUPO_PRINCIPAL" es una columna aparte de "CLUSTER" para cada persona).
#
# Confirmado con el usuario: Rector/Vicerrector/Decano/Subdecano tienen TIPOEMPLEADO=DOCENTE
# en el dato institucional (se eligen desde el escalafon docente) y se mantienen ahi.
PERFIL_NOMBRES = {
    0: "Asistencia secretarial / oficina",
    1: "Autoridad académica (Rector/Vicerrector/Decano/Subdecano)",
    2: "Autoridad administrativa (Gerente/Director)",
    3: "Auxiliar / ayudante operativo",
    4: "Docente no titular / ocasional",
    5: "Docente titular de carrera",
    6: "Jefatura / supervisión operativa",
    7: "Otros (administrativo)",
    8: "Profesional / Analista",
    9: "Profesional especializado (abogado, psicólogo, etc.)",
    10: "Servicios generales / oficios",
    11: "Técnico docente / de investigación",
    12: "Técnico operativo / mantenimiento",
}

PERFIL_DESCRIPCIONES = {
    0: (
        "173 personas (7.8%). Titulación de bachillerato por sobre el promedio, ninguna "
        "facultad asociada de forma distintiva. 62% vigente."
    ),
    1: (
        "34 personas (1.5%). El cargo real más alto de la institución (Rector, Vicerrector, "
        "Decano, Subdecano). Máxima movilidad organizacional (mediana 4 unidades distintas) y "
        "mayor volumen contractual histórico (mediana 48.5 contratos). 97% vigente — casi "
        "todas las autoridades activas hoy están aquí."
    ),
    2: (
        "29 personas (1.3%). Máxima diversidad de categorías de rol y de unidades "
        "organizacionales dentro de administrativo — gerentes y directores de área. 76% "
        "vigente."
    ),
    3: (
        "30 personas (1.4%). Sin titulación de tercer nivel, titulación de bachillerato por "
        "sobre el promedio. 80% vigente."
    ),
    4: (
        "547 personas (24.7%). Actividad docente real (mediana 8 periodos, 2500 horas, 32 "
        "cursos) sin ser parte del escalafón de titulares. 60% vigente."
    ),
    5: (
        "268 personas (12.1%). El escalafón docente formal: mediana 14 periodos de docencia y "
        "la mayor actividad politécnica por término (T1/T2) de la población. 86% vigente."
    ),
    6: (
        "15 personas (0.7%). Heteroevaluación y cobertura de evaluación por debajo del "
        "promedio institucional — cargos de jefatura/supervisión con poca o ninguna actividad "
        "docente evaluada. 67% vigente."
    ),
    7: (
        "5 personas (0.2%), el grupo más pequeño — cargos administrativos que no encajaron en "
        "ninguna categoría de rol definida (ver `CATEGORIA_CARGO` en DEC-004). 80% vigente."
    ),
    8: (
        "294 personas (13.3%), uno de los grupos administrativos más numerosos. Baja "
        "diversidad de facultades/regímenes — perfil administrativo profesional estándar "
        "(analistas). 73% vigente."
    ),
    9: (
        "30 personas (1.4%). Profesionales con formación específica (abogacía, psicología, "
        "medicina, diseño, etc.) en funciones administrativas. 63% vigente."
    ),
    10: (
        "17 personas (0.8%). Oficios y servicios generales (chofer, guardián, jardinero, "
        "electricista, etc.), titulación de bachillerato por sobre el promedio. 76% vigente."
    ),
    11: (
        "755 personas (34.1%), el grupo más numeroso de toda la población. Apoyo técnico a "
        "docencia/investigación (técnico docente, de laboratorio, de investigación), con la "
        "menor vigencia de todos los perfiles (35%) — mucha rotación histórica en este tipo de "
        "cargo."
    ),
    12: (
        "11 personas (0.5%). Mantenimiento y operación técnica, alta carga horaria por "
        "actividad politécnica. 55% vigente."
    ),
}

# Colores por categoria de cargo: paleta calida para las de raiz administrativa, fria para
# las de raiz docente - referencial (algunas categorias mezclan ambas ramas, ver nota arriba),
# para que el mapa de puntos se lea de un vistazo sin ser una regla estricta de particion.
PERFIL_COLORES = {
    0: "#F4A261",   # asistencia secretarial/oficina
    1: "#1D3557",   # autoridad academica (docente)
    2: "#E76F51",   # autoridad administrativa
    3: "#BC6C25",   # auxiliar/ayudante operativo
    4: "#A8DADC",   # docente no titular/ocasional
    5: "#457B9D",   # docente titular de carrera
    6: "#9C6644",   # jefatura/supervision operativa
    7: "#B08968",   # otros (administrativo)
    8: "#F4A300",   # profesional/analista
    9: "#D4A373",   # profesional especializado
    10: "#8D6A4A",  # servicios generales/oficios
    11: "#2A9D8F",  # tecnico docente/investigacion
    12: "#8AB17D",  # tecnico operativo/mantenimiento
}

# Color fijo para personas "Mixto" (2+ cargos estructurales vigentes en paralelo, ver
# ES_MIXTO en construir_features_trayectoria, correccion 2026-09-15, caso IDPERSONA 3519) -
# violeta, no usado en PERFIL_COLORES (paletas calida/administrativa vs fria/docente), para
# que se distinga a simple vista de las 13 categorias reales. Usado por el mapa de puntos
# del dashboard React (dashboard_react/backend/main.py); el dashboard Streamlit no muestra
# esta categoria por ahora.
COLOR_MIXTO = "#7B2CBF"

# Paleta para el clustering SEMANTICO (en espacio de embeddings, ver
# notebooks/07b_clustering_semantico) - deliberadamente distinta de PERFIL_COLORES (que usa
# calido=administrativo/frio=docente) para que nunca se confunda visualmente con el
# clustering estructural: ambos clusterings pueden mostrarse lado a lado en el dashboard y
# usan IDs de cluster que no son comparables entre si (mismo numero de cluster no significa
# el mismo grupo de personas). Paleta categorica neutra (tonos teal/purpura), largo 12 (el
# clustering semantico selecciona K entre 8 y 25 candidatos - ver notebook seccion 4 - asi
# que debe cubrir mas de 8 sin repetir color por wraparound, caso real: K=9 repetia el color
# del cluster 0 en el cluster 8).
PERFIL_COLORES_SEMANTICO = [
    "#118AB2", "#EF476F", "#06D6A0", "#FFD166", "#7209B7", "#F3722C", "#4361EE", "#843B62",
    "#2A9D8F", "#E76F51", "#8338EC", "#3A86FF",
]

# Subconjunto curado de `dataset_personas_features.csv` para tarjetas de
# persona / comparaciones rapidas (evita saturar la UI con las 85 columnas).
METRICAS_CLAVE = [
    "TIPOEMPLEADO_ACTUAL_DESC",
    "CARGO_ACTUAL",
    "UNIDAD_ACTUAL_NOMBRE",
    "VIGENTE_MOSTRAR",
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
    # Movilidad de carrera (DEC-027): visibles en la tabla de resultados/CSV de "Formar
    # equipos" para que el filtro de estabilidad (max_turbulencia/min_duracion_mediana en
    # /api/equipos) sea verificable a simple vista, no solo un criterio ciego.
    "DURACION_MEDIANA_TRAMO_ANIOS",
    "TURBULENCIA_TRAMOS",
    "ANIOS_EN_UNIDAD_ACTUAL",
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
            "de 08_dashboard.ipynb (o, si faltan insumos, los notebooks 06_clustering / "
            "07_embeddings)."
        )
    return pd.read_csv(path, **kwargs)


def load_personas_dashboard() -> pd.DataFrame:
    df = _read_csv(DASHBOARD_DIR / "personas_dashboard.csv")
    # DEC-024: VIGENTE_ACTUALMENTE (vinculación general, calcular_periodos_continuos) puede
    # quedar en False para autoridades académicas superiores cuyo último acto administrativo
    # (FF corto, tipo "encargo de despacho") ya tiene fecha de cierre, aunque su nombramiento
    # estructural (VIGENTE_TRAMO_ESTRUCTURAL, protegido por ESTADOCONTRATO abierto) siga
    # activo — caso real: persona 1216, rectora. VIGENTE_MOSTRAR es la señal que debe usar
    # cualquier vista del dashboard (ficha, filtros, mapa) para no contradecir "Cargo actual".
    df["VIGENTE_MOSTRAR"] = (
        df["VIGENTE_ACTUALMENTE"].fillna(False) | df["VIGENTE_TRAMO_ESTRUCTURAL"].fillna(False)
    )
    return df


def load_cluster_resumen() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "cluster_perfiles_resumen.csv")


def load_cluster_top_features() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "cluster_top_features.csv")


def load_dendrograma_centroides() -> np.ndarray:
    """Matriz de enlace (formato `scipy.cluster.hierarchy.linkage`) entre los centroides de
    los 9 sub-perfiles finales (DEC-008: 4 administrativos + 5 docentes), calculada en
    `06_clustering.ipynb` con enlace `ward` sobre el mismo espacio de `X_modelado` usado
    para el clustering. No se recalcula aqui para no depender de `X_modelado.csv` (mas
    pesado) desde el dashboard."""
    df = _read_csv(CLUSTERING_DIR / "dendrograma_centroides.csv")
    return df[["CLUSTER_A", "CLUSTER_B", "DISTANCIA", "N_OBSERVACIONES"]].to_numpy()


def load_pca_personas() -> pd.DataFrame:
    """Proyeccion PCA de 2 componentes por persona (`IDPERSONA`, `PC1`, `PC2`), calculada una
    sola vez en `06_clustering.ipynb` sobre las 141 columnas de `X_modelado` (DEC-008), para
    que el dashboard dibuje un punto por persona sin cargar `X_modelado.csv` completo."""
    return _read_csv(CLUSTERING_DIR / "pca_personas.csv")


# ---------------------------------------------------------------------------
# Clustering SEMANTICO (en espacio de embeddings) - capa de comparacion/validacion nueva,
# ver notebooks/07b_clustering_semantico/07b_clustering_semantico.ipynb. Independiente del
# clustering estructural de arriba: distinto espacio (embeddings de 768 dim del documento
# semantico general, no X_modelado), distinto numero de clusters (K propio, no forzado a 13),
# y sin nombres de perfil interpretados a mano todavia (PERFIL_NOMBRE_SEMANTICO es generico,
# "Perfil semantico N" + descripcion automatica por variables estructuradas).
# ---------------------------------------------------------------------------

def load_cluster_resumen_semantico() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "cluster_perfiles_resumen_semantico.csv")


def load_cluster_top_features_semantico() -> pd.DataFrame:
    return _read_csv(DASHBOARD_DIR / "cluster_top_features_semantico.csv")


def load_clusters_personas_semantico() -> pd.DataFrame:
    return _read_csv(CLUSTERING_DIR / "clusters_personas_semantico.csv")


def load_pca_personas_semantico() -> pd.DataFrame:
    """Proyeccion PCA de 2 componentes por persona en el espacio de EMBEDDINGS (no
    X_modelado) - PC1/PC2 aqui no son comparables con los de `load_pca_personas()` (distinto
    espacio de origen, distinta escala)."""
    return _read_csv(CLUSTERING_DIR / "pca_personas_semantico.csv")


def load_feature_dictionary() -> pd.DataFrame:
    return _read_csv(FEATURES_DIR / "feature_dictionary.csv")


@lru_cache(maxsize=1)
def feature_label_map() -> dict:
    """FEATURE -> descripcion legible (feature_dictionary.csv), con fallback al nombre crudo."""
    fd = load_feature_dictionary()
    return dict(zip(fd["FEATURE"], fd["DESCRIPTION"]))


def load_embeddings() -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (ids, matriz normalizada L2) desde embeddings_personas.csv (embedding
    GENERAL: trayectoria + formacion + docencia + investigacion + etc., ver DEC-014)."""
    df = _read_csv(EMBEDDINGS_DIR / "embeddings_personas.csv")
    ids = df["IDPERSONA"].to_numpy()
    matrix = df.drop(columns=["IDPERSONA"]).to_numpy(dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return ids, matrix / norms


def load_embeddings_trayectoria() -> tuple[np.ndarray, np.ndarray]:
    """Devuelve (ids, matriz normalizada L2) desde embeddings_trayectoria.csv - capa nueva
    e INDEPENDIENTE del embedding general (ver notebooks/07_embeddings/07_embeddings.ipynb,
    seccion 7): calculada solo sobre el documento de trayectoria (cargo/unidad/permanencia/
    estabilidad/movilidad), no sobre formacion/docencia/investigacion/etc. Cubre solo a las
    personas con al menos un tramo de rol estructural (ver CATEGORIAS_PUNTUALES/DEC-004),
    un subconjunto mas chico que `load_embeddings()`."""
    df = _read_csv(EMBEDDINGS_DIR / "embeddings_trayectoria.csv")
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


# ---------------------------------------------------------------------------
# Vista de trayectoria de persona (DEC-015): fuentes reutilizadas de 04_trayectorias
# y data/processed - la MISMA informacion que alimenta el documento semantico
# (07_embeddings/_embeddings_comun.py), pero devuelta como datos estructurados
# (no texto ya ensamblado) para que app.py la presente como timeline/tarjetas.
# ---------------------------------------------------------------------------

NOMBRES_CATEGORIA_CARGO = pc.NOMBRES_CATEGORIA_CARGO

# Colores por TIPO_EVENTO para la timeline de trayectoria (ver render_timeline_trayectoria
# en app.py) - cargo estructural en la paleta de PERFIL_COLORES (rama), funciones
# adicionales/subrogaciones en tonos distintos para diferenciarlas visualmente del
# contrato, experiencia externa en gris (fuera de ESPOL).
#
# 2026-09-10 (decision confirmada por el usuario, con correccion posterior el mismo dia):
# - CARGO_ESPOL se separa en variantes GRADO/POSGRADO (ver
#   `pc.construir_eventos_trayectoria`) - misma familia de color (tono base) para que siga
#   leyendose como "la misma categoria amplia".
# - Ya NO existe una lane separada "Contrato puntual (ESPOL)": se fusiono en CARGO_ESPOL
#   (cualquier vinculo dentro de ESPOL sin nivel de docencia conocido se presenta igual,
#   sea tramo estructural o contrato puntual).
# - Una funcion/subrogacion de coordinacion academica (GRADO/POSGRADO poblado, o el
#   nombre del cargo lo dice explicitamente) se considera CARGO, no funcion adicional:
#   nunca genera FUNCION_ADICIONAL_GRADO/POSGRADO ni SUBROGACION_GRADO/POSGRADO, cae
#   directo en CARGO_ESPOL_GRADO/POSGRADO. FUNCION_ADICIONAL/SUBROGACION genericas (sin
#   nivel conocido) no tienen variante de nivel.
# - EXPERIENCIA_EXTERNA se separa en Ecuador/exterior.
COLOR_TIPO_EVENTO = {
    "CARGO_ESPOL": "#457B9D",
    "CARGO_ESPOL_GRADO": "#1D3557",
    "CARGO_ESPOL_POSGRADO": "#6D9DC5",
    "FUNCION_ADICIONAL": "#E9C46A",
    "SUBROGACION": "#F4A261",
    "EXPERIENCIA_EXTERNA": "#ADB5BD",
    "EXPERIENCIA_EXTERNA_ECUADOR": "#6C757D",
    "EXPERIENCIA_EXTERNA_EXTERIOR": "#CED4DA",
}

ETIQUETA_TIPO_EVENTO = {
    "CARGO_ESPOL": "Cargo en ESPOL",
    "CARGO_ESPOL_GRADO": "Cargo en ESPOL — Grado",
    "CARGO_ESPOL_POSGRADO": "Cargo en ESPOL — Posgrado",
    "FUNCION_ADICIONAL": "Función adicional",
    "SUBROGACION": "Subrogación",
    "EXPERIENCIA_EXTERNA": "Experiencia externa",
    "EXPERIENCIA_EXTERNA_ECUADOR": "Experiencia externa — Ecuador",
    "EXPERIENCIA_EXTERNA_EXTERIOR": "Experiencia externa — Exterior",
}


def load_eventos_trayectoria() -> pd.DataFrame:
    """Linea de tiempo unificada por persona (`pc.construir_eventos_trayectoria`,
    DEC-014): cargo estructural en ESPOL, funciones adicionales/subrogaciones (DEC-012) y
    experiencia externa, todo con fecha real - insumo tanto del documento semantico como
    de esta vista de dashboard."""
    df = _read_csv(TRAYECTORIAS_DIR / "eventos_trayectoria_persona.csv")
    # pd.to_datetime explicito, no parse_dates de read_csv: una sola fecha mal formada en
    # una fuente cruda puede hacer que pandas descarte el parseo de toda la columna y la
    # deje como texto plano, sin avisar (visto con experiencia_externa.csv esta sesion).
    for c in ("FECHA_INICIO", "FECHA_FIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    df["ES_VIGENTE"] = df["ES_VIGENTE"].astype(bool)
    return df


def load_documento_semantico() -> pd.DataFrame:
    return _read_csv(EMBEDDINGS_DIR / "documento_semantico_persona.csv")


def load_documento_trayectoria() -> pd.DataFrame:
    """Documento de TRAYECTORIA por persona (DOCUMENTO_TRAYECTORIA_TEXTO + variables
    objetivas: N_CARGOS_TOTAL, N_CARGOS_SIGNIFICATIVOS, N_CAMBIOS_CARGO, N_CAMBIOS_UNIDAD,
    duraciones, unidades), usado como fuente de "evidencia" de la busqueda de trayectoria -
    analogo a `load_documento_semantico()` pero con el texto de cargo/unidad/permanencia/
    movilidad en vez del documento general."""
    return _read_csv(EMBEDDINGS_DIR / "documento_trayectoria_persona.csv")


def load_tramos_cargo_unidad() -> pd.DataFrame:
    """Tramos consolidados por cargo+unidad (una fila por tramo, con deteccion de cargos
    paralelos) - ver notebooks/07_embeddings/_embeddings_comun.py::
    construir_tramos_cargo_unidad_persona. Misma consolidacion (cargo+unidad+receso corto)
    que ya usa el documento de trayectoria, expuesta como tabla para la ficha del
    dashboard."""
    df = _read_csv(EMBEDDINGS_DIR / "tramos_cargo_unidad_persona.csv")
    for c in ("INICIO", "FIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df


@lru_cache(maxsize=1)
def _titulaciones_graduadas() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "reporte_titulaciones_educacion.csv", low_memory=False)
    df["FechaGraduacion"] = pd.to_datetime(df["FechaGraduacion"], format="mixed", errors="coerce")
    df = df.rename(columns={"IdPersona": "IDPERSONA"})
    return df[(df["Estado"] == "Graduado") & df["Titulo"].notna()]


def formacion_persona(id_persona: int) -> pd.DataFrame:
    orden_nivel = {"CUARTO NIVEL": 0, "TERCER NIVEL": 1, "BACHILLERATO": 2, "PRIMARIA": 3}
    df = _titulaciones_graduadas()
    df = df[df["IDPERSONA"] == id_persona][["Titulo", "Nivel", "Institucion", "Pais", "FechaGraduacion"]]
    return df.assign(_ORDEN=df["Nivel"].map(orden_nivel).fillna(9)).sort_values("_ORDEN").drop(columns="_ORDEN")


@lru_cache(maxsize=1)
def _carga_academica_todas() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "carga_academica_disponible.csv", low_memory=False)


def docencia_persona(id_persona: int) -> pd.DataFrame:
    df = _carga_academica_todas()
    df = df[(df["IDPERSONA"] == id_persona) & df["NOMMATERIA"].notna()]
    return (
        df.groupby("NOMMATERIA")
        .agg(ANIO_MIN=("ANIO", "min"), ANIO_MAX=("ANIO", "max"), N_PERIODOS=("ANIO", "size"),
             UNIDAD=("NOMBREUNIDAD", "first"))
        .reset_index().sort_values("ANIO_MAX", ascending=False)
    )


@lru_cache(maxsize=1)
def _proyectos_investigacion_todos() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "proyectos_investigacion_disponible.csv", low_memory=False)


@lru_cache(maxsize=1)
def _publicaciones_todas() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "publicaciones.csv", low_memory=False)


@lru_cache(maxsize=1)
def _proyecto_grado_todos() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "proyecto_grado.csv", low_memory=False).rename(columns={"IDDIRECTOR": "IDPERSONA"})


@lru_cache(maxsize=1)
def _ponentes_todos() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "ponentes_todos.csv", low_memory=False)


@lru_cache(maxsize=1)
def _proyectos_vinculacion_todos() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "proyectos_vinculacion_disponible.csv", low_memory=False)


def investigacion_persona(id_persona: int) -> dict[str, pd.DataFrame]:
    proy = _proyectos_investigacion_todos()
    proy = proy[proy["IDPERSONA"] == id_persona][["NOMBRE", "STRAREACAMPOAMPLIO", "FECHAINICIO", "FECHAFIN", "ESTADO_PROYECTO"]]
    pub = _publicaciones_todas()
    pub = pub[pub["IDPERSONA"] == id_persona][["TITULO", "ANIO", "TIPOPUBLICACION", "CUARTIL"]]
    tesis = _proyecto_grado_todos()
    tesis = tesis[tesis["IDPERSONA"] == id_persona][["NOMBRETRABAJOTITULACION", "FECHASUSTENTACION", "NIVELFORMACION"]]
    pon = _ponentes_todos()
    pon = pon[pon["IDPERSONA"] == id_persona][["NOMBRE", "FECHAINICIO", "NOMBREPAIS"]]
    return {"proyectos": proy, "publicaciones": pub, "tesis_dirigidas": tesis, "ponencias": pon}


def vinculacion_persona(id_persona: int) -> pd.DataFrame:
    df = _proyectos_vinculacion_todos()
    return df[df["IDPERSONA"] == id_persona][["NOMBREPROYECTO", "NOMBREPROGRAMA", "FECHAINICIO", "FECHAFIN"]]


@lru_cache(maxsize=1)
def _capacitaciones_todas() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "capacitaciones_todas.csv", low_memory=False)


@lru_cache(maxsize=1)
def _certificados_todos() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "certificados_todos.csv", low_memory=False)


def capacitacion_persona(id_persona: int) -> dict[str, pd.DataFrame]:
    cap = _capacitaciones_todas()
    cap = cap[cap["IDPERSONA"] == id_persona][["NOMBRE", "FECHAINICIO", "TIPOCAPACITACION", "NOMBREPAIS"]]
    cert = _certificados_todos()
    cert = cert[cert["IDPERSONA"] == id_persona][["NOMBRE", "FECHAINICIO", "CERTIFICADOPOR"]]
    return {"capacitaciones": cap, "certificaciones": cert}


@lru_cache(maxsize=1)
def _idiomas_todos() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "idiomas_personas.csv", low_memory=False)


def idiomas_persona(id_persona: int) -> pd.DataFrame:
    df = _idiomas_todos()
    df = df[df["IDPERSONA"] == id_persona]
    if "LENGUANATIVA" in df.columns:
        df = df[df["LENGUANATIVA"] != 1]
    return df[["IDIOMA", "NIVELLECTURA", "NIVELESCRITURA", "NIVELCONVERSACION", "NIVELMCER"]]


@lru_cache(maxsize=1)
def _mencion_honor_todas() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "mencion_honor.csv", low_memory=False)
    df["FECHA"] = pd.to_datetime(df["FECHA"], format="mixed", errors="coerce")
    return df


def reconocimientos_persona(id_persona: int) -> pd.DataFrame:
    df = _mencion_honor_todas()
    return df[df["IDPERSONA"] == id_persona][["NOMBREMENCION", "INSTITUCION", "FECHA"]]


# ---------------------------------------------------------------------------
# Motivo de "sin perfil" (CLUSTER=-1, DEC-012): explica con el dato real, no con un
# mensaje generico, por que una persona puede tener un CARGO_ACTUAL visible y aun asi no
# tener cargo estructural - la razon exacta es la categoria de su contrato mas reciente en
# historial_laboral_categoria_cargo.csv (las mismas categorias que construir_tramos_rol
# excluye: CATEGORIAS_PUNTUALES, SIN_DATO, SIN_TIPOEMPLEADO).
# ---------------------------------------------------------------------------

_ETIQUETAS_CATEGORIAS_PUNTUALES = {
    "CONTRATO_SERVICIOS_PROFESIONALES_PROYECTO": "contrato de servicios profesionales por proyecto",
    "DOCENTE_CONTRATADO_SERVICIOS_CIVILES": "contrato docente de servicios civiles",
    "ACTIVIDAD_ACADEMICA_DESDE_ADMINISTRATIVO": "actividad académica puntual (personal administrativo)",
    "TRIBUNAL_COMISION_ACADEMICA": "participación en tribunal/comisión académica",
    "DOCENTE_HONORARIO_ESPECIAL": "docente honorario/invitado",
}


@lru_cache(maxsize=1)
def _historial_categoria_cargo() -> pd.DataFrame:
    df = pd.read_csv(TRAYECTORIAS_DIR / "historial_laboral_categoria_cargo.csv", low_memory=False)
    for c in ("FECHAINICIOCONTRATO", "FECHAFINCONTRATO"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df


def motivo_sin_perfil(id_persona: int) -> str | None:
    """Para personas con `CLUSTER=-1`: por que, con el dato real (no un mensaje generico).
    Devuelve None si no se encuentra una explicacion clara (no deberia pasar para alguien
    realmente sin cargo estructural, pero se evita inventar una razon si los datos no la
    respaldan)."""
    df = _historial_categoria_cargo()
    sub = df[(df["IDPERSONA"] == id_persona) & (~df["ES_RUIDO_CALIDAD_DATOS"])].sort_values("FECHAINICIOCONTRATO")
    if sub.empty:
        return "No tiene ningún contrato registrado en el historial laboral."
    ultima = sub.iloc[-1]
    cat, cargo = ultima["CATEGORIA_CARGO"], ultima["CARGO"]
    if cat in pc.CATEGORIAS_PUNTUALES:
        etiqueta = _ETIQUETAS_CATEGORIAS_PUNTUALES.get(cat, cat.replace("_", " ").lower())
        return (f"Su contrato más reciente (\"{cargo}\") es de tipo **{etiqueta}** — por diseño "
                "(ver DEC-004), este tipo de contrato puntual/por proyecto no se considera un cargo "
                "estructural continuo, aunque esté vigente.")
    if cat == "SIN_TIPOEMPLEADO":
        return (f"Su contrato más reciente (\"{cargo}\") es de tipo **contrato civil** (sin relación "
                "de dependencia, ver DEC-012) — no corresponde a personal docente ni administrativo "
                "en el sentido institucional.")
    if cat == "SIN_DATO":
        return "Su contrato más reciente no tiene un cargo (`CARGO`) registrado en el sistema origen."
    return None
