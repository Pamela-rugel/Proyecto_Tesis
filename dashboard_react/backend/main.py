"""
API FastAPI para el dashboard React de perfiles de personal ESPOL.

Reutiliza `notebooks/08_dashboard/lib.py` (misma logica de carga de datos ya validada por
el dashboard Streamlit) - esta API NO reimplementa la preparacion de datos, solo la expone
como JSON y agrega el endpoint de busqueda semantica (que necesita ejecutar el modelo de
embeddings sobre la consulta del usuario, algo que un frontend estatico no puede hacer).

Ejecutar con:
    d:\\Proyecto_Tesis\\.venv\\Scripts\\python -m uvicorn main:app --reload --port 8001
    (desde dashboard_react/backend/)
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "notebooks" / "08_dashboard"))
sys.path.insert(0, str(ROOT / "notebooks" / "01_preprocesamiento"))
import lib  # noqa: E402

app = FastAPI(title="Perfiles ESPOL API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

CLUSTER_COLORS_FALLBACK = [
    "#66C2A5", "#FC8D62", "#8DA0CB", "#E78AC3", "#A6D854",
    "#FFD92F", "#E5C494", "#B3B3B3",
]


def cluster_color(cluster: int) -> str:
    return lib.PERFIL_COLORES.get(int(cluster), CLUSTER_COLORS_FALLBACK[int(cluster) % len(CLUSTER_COLORS_FALLBACK)])


def cluster_color_semantico(cluster: int) -> str:
    paleta = lib.PERFIL_COLORES_SEMANTICO
    return paleta[int(cluster) % len(paleta)]


def color_por_texto(texto: str) -> str:
    """Color determinístico (mismo texto -> siempre el mismo color) para el modo "cargo
    real" del mapa (~239 valores distintos de CARGO_ACTUAL, demasiados para una paleta
    fija como PERFIL_COLORES). Usa un hash estable del texto para elegir un hue en HSL
    (en vez de un color RGB directo del hash, que tiende a verse sucio/repetido) -
    saturación y luminosidad fijas para que todos los colores tengan contraste similar."""
    import colorsys
    import hashlib
    h = int(hashlib.md5(texto.encode("utf-8")).hexdigest(), 16)
    hue = (h % 360) / 360.0
    r, g, b = colorsys.hls_to_rgb(hue, 0.45, 0.55)
    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


def df_to_records(df: pd.DataFrame) -> list[dict]:
    return df.replace({np.nan: None}).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Carga de datos (cacheada en proceso, igual que @st.cache_data en Streamlit)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_nombres_persona() -> pd.Series:
    """Mapeo IDPERSONA -> nombre completo, cargado directo del CSV crudo (data/raw/
    historialaboralpersonas.csv) porque ningún archivo procesado del pipeline (features,
    embeddings, personas_dashboard.csv) incluye nombre - el pipeline trabaja
    intencionalmente con IDPERSONA como identificador. Pedido explícito del usuario
    2026-09-16 ("ya no uses idpersona, usa los nombres que estan en hstorial laboral"),
    confirmando que quiere nombres visibles en todo el dashboard (no anonimizado) -
    IDPERSONA se mantiene internamente (URLs, joins) pero no se muestra en ninguna
    pantalla. Cacheado en memoria, igual patrón que los demás get_*() de este archivo."""
    df = pd.read_csv(
        ROOT / "data" / "raw" / "historialaboralpersonas.csv",
        usecols=["IDPERSONA", "NOMBRES", "APELLIDOS"], low_memory=False,
    ).drop_duplicates("IDPERSONA")
    nombre = (df["NOMBRES"].str.strip() + " " + df["APELLIDOS"].str.strip()).str.title()
    return pd.Series(nombre.values, index=df["IDPERSONA"], name="NOMBRE_COMPLETO")


@lru_cache(maxsize=1)
def get_personas() -> pd.DataFrame:
    personas = lib.load_personas_dashboard()
    nombres = get_nombres_persona()
    personas["NOMBRE_COMPLETO"] = personas["IDPERSONA"].map(nombres).fillna(
        "Persona " + personas["IDPERSONA"].astype(str)
    )
    return personas


@lru_cache(maxsize=1)
def get_resumen() -> pd.DataFrame:
    return lib.load_cluster_resumen()


@lru_cache(maxsize=1)
def get_top_features() -> pd.DataFrame:
    return lib.load_cluster_top_features()


@lru_cache(maxsize=1)
def get_feature_labels() -> dict:
    return lib.feature_label_map()


@lru_cache(maxsize=1)
def get_pca() -> pd.DataFrame:
    return lib.load_pca_personas()


@lru_cache(maxsize=1)
def get_resumen_semantico() -> pd.DataFrame:
    return lib.load_cluster_resumen_semantico()


@lru_cache(maxsize=1)
def get_top_features_semantico() -> pd.DataFrame:
    return lib.load_cluster_top_features_semantico()


@lru_cache(maxsize=1)
def get_clusters_semantico() -> pd.DataFrame:
    return lib.load_clusters_personas_semantico()


@lru_cache(maxsize=1)
def get_pca_semantico() -> pd.DataFrame:
    return lib.load_pca_personas_semantico()


@lru_cache(maxsize=1)
def get_eventos_trayectoria() -> pd.DataFrame:
    return lib.load_eventos_trayectoria()


@lru_cache(maxsize=1)
def get_tramos_rol() -> pd.DataFrame:
    """Tramos de rol (`pc.construir_tramos_rol`): rachas de contratos consecutivos del
    mismo cargo ya colapsadas en una sola fila, con roles administrativos/docentes
    paralelos ya resueltos correctamente (DEC-011: solo se colapsa un rol corto solapado
    si hay una subrogación real detrás, si no ambos quedan como tramos separados). Solo
    cubre ADMINISTRATIVO/DOCENTE (excluye por diseño los contratos puntuales/"servicios
    profesionales" sin tipo, ver `CATEGORIAS_PUNTUALES` en `_preprocesamiento_comun.py`)."""
    df = pd.read_csv(ROOT / "data" / "trayectorias" / "tramos_rol.csv", low_memory=False)
    for c in ("TRAMO_INICIO", "TRAMO_FIN"):
        df[c] = pd.to_datetime(df[c], format="mixed", errors="coerce")
    return df


@lru_cache(maxsize=1)
def get_corpus() -> pd.DataFrame:
    return lib.load_corpus_texto()


@lru_cache(maxsize=1)
def get_documento_semantico() -> pd.DataFrame:
    return lib.load_documento_semantico()


@lru_cache(maxsize=1)
def get_embeddings():
    return lib.load_embeddings()


@lru_cache(maxsize=1)
def get_embeddings_trayectoria():
    return lib.load_embeddings_trayectoria()


@lru_cache(maxsize=1)
def get_documento_trayectoria() -> pd.DataFrame:
    return lib.load_documento_trayectoria()


@lru_cache(maxsize=1)
def get_tramos_cargo_unidad() -> pd.DataFrame:
    return lib.load_tramos_cargo_unidad()


_text_model = None


def get_text_model():
    global _text_model
    if _text_model is None:
        from sentence_transformers import SentenceTransformer

        _text_model = SentenceTransformer("intfloat/multilingual-e5-base")
    return _text_model


_STOPWORDS_ES = {
    "de", "la", "el", "en", "que", "y", "a", "los", "las", "un", "una", "con", "para",
    "por", "su", "es", "se", "del", "al", "lo", "como", "más", "o", "sin", "sobre",
}


def _mejor_evidencia(consulta: str, documento: str, max_oraciones: int = 2) -> str:
    """Misma heuristica que app.py (Streamlit) - ver docstring alli. No es lo que "vio" el
    embedding internamente, es una guia de solapamiento lexico transparente y verificable."""
    if not documento or not isinstance(documento, str):
        return ""
    palabras_consulta = {w for w in consulta.lower().split() if w not in _STOPWORDS_ES and len(w) > 2}
    if not palabras_consulta:
        return documento[:220] + ("…" if len(documento) > 220 else "")

    oraciones = [o.strip() for o in documento.replace("\n", " ").split(". ") if o.strip()]
    puntajes = []
    for o in oraciones:
        palabras_oracion = {w.strip(".,;:()") for w in o.lower().split()}
        solape = len(palabras_consulta & palabras_oracion)
        if solape:
            puntajes.append((solape, o))
    if not puntajes:
        return documento[:220] + ("…" if len(documento) > 220 else "")
    puntajes.sort(key=lambda t: -t[0])
    mejores = [o for _, o in puntajes[:max_oraciones]]
    return " (…) ".join(mejores)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/resumen")
def resumen():
    personas = get_personas()
    resumen_df = get_resumen()
    return {
        "n_personas": int(len(personas)),
        "n_perfiles": int(resumen_df["CLUSTER"].nunique()),
        "n_con_texto": int((personas["N_REGISTROS_TEXTO"] > 0).sum()),
        "perfiles": [
            {**rec, "COLOR": cluster_color(rec["CLUSTER"])}
            for rec in df_to_records(resumen_df.sort_values("CLUSTER"))
        ],
    }


@app.get("/api/perfiles/{cluster_id}")
def perfil_detalle(cluster_id: int):
    resumen_df = get_resumen()
    fila = resumen_df[resumen_df["CLUSTER"] == cluster_id]
    if fila.empty:
        raise HTTPException(404, "Perfil no encontrado")
    fila = fila.iloc[0]

    labels = get_feature_labels()
    feats = get_top_features()
    feats = feats[feats["CLUSTER"] == cluster_id].copy()
    feats["FEATURE_LABEL"] = feats["FEATURE"].map(lambda f: labels.get(f, f))

    personas = get_personas()
    cargos_cluster = personas.loc[personas["CLUSTER"] == cluster_id, "CARGO_ACTUAL"].dropna()
    conteo_cargos = cargos_cluster.value_counts().reset_index()
    conteo_cargos.columns = ["CARGO_ACTUAL", "N_PERSONAS"]

    muestra_cols = ["IDPERSONA", "NOMBRE_COMPLETO"] + [c for c in lib.METRICAS_CLAVE if c in personas.columns]
    muestra = personas[personas["CLUSTER"] == cluster_id][muestra_cols].head(50)

    return {
        "cluster": int(cluster_id),
        "nombre": fila["PERFIL_NOMBRE"],
        "n_personas": int(fila["N_PERSONAS"]),
        "pct_poblacion": float(fila["PCT_POBLACION"]),
        "descripcion": fila["DESCRIPCION"],
        "color": cluster_color(cluster_id),
        "top_features": df_to_records(feats[["FEATURE", "FEATURE_LABEL", "VALUE_CLUSTER", "VALUE_GLOBAL"]]),
        "cargos": df_to_records(conteo_cargos),
        "n_cargos_distintos": int(cargos_cluster.nunique()),
        "n_con_cargo": int(len(cargos_cluster)),
        "muestra_personas": df_to_records(muestra),
    }


@app.get("/api/mapa")
def mapa(tipo: str = Query("Todos"), perfiles: str = Query(""), modo: str = Query("rama")):
    personas = get_personas()
    pca_df = get_pca().merge(
        personas[["IDPERSONA", "NOMBRE_COMPLETO", "CLUSTER", "PERFIL_NOMBRE", "TIPOEMPLEADO_ACTUAL_DESC",
                  "VIGENTE_MOSTRAR", "CARGO_ACTUAL", "ES_MIXTO", "CARGOS_ACTUALES_MIXTO",
                  "CATEGORIAS_ACTUALES_MIXTO"]],
        on="IDPERSONA", how="inner",
    )
    pca_df = pca_df[pca_df["CLUSTER"] != -1]
    pca_df["ES_MIXTO"] = pca_df["ES_MIXTO"].fillna(False)

    if tipo == "Solo Administrativo":
        pca_df = pca_df[(pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "ADMINISTRATIVO") & (~pca_df["ES_MIXTO"])]
    elif tipo == "Solo Docente":
        pca_df = pca_df[(pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "DOCENTE") & (~pca_df["ES_MIXTO"])]
    elif tipo == "Solo Mixto":
        pca_df = pca_df[pca_df["ES_MIXTO"]]

    if perfiles:
        ids_perfiles = {int(p) for p in perfiles.split(",") if p}
        if modo == "cargo":
            # Modo "por cargo": un filtro de perfil especifico tambien incluye a las
            # personas Mixto que tengan ese cargo entre sus roles vigentes concurrentes
            # (decision confirmada por el usuario) - CATEGORIAS_ACTUALES_MIXTO trae los
            # codigos CATEGORIA_CARGO reales, no el nombre de presentacion, asi que se
            # compara contra SUBGRUPO (la categoria cruda de cluster_perfiles_resumen).
            categorias_por_cluster = dict(zip(get_resumen()["CLUSTER"], get_resumen()["SUBGRUPO"]))
            categorias_filtro = {categorias_por_cluster[c] for c in ids_perfiles if c in categorias_por_cluster}
            mixto_con_ese_cargo = pca_df["ES_MIXTO"] & pca_df["CATEGORIAS_ACTUALES_MIXTO"].fillna("").apply(
                lambda s: any(cat in s.split(";") for cat in categorias_filtro)
            )
            pca_df = pca_df[pca_df["CLUSTER"].isin(ids_perfiles) | mixto_con_ese_cargo]
        else:
            pca_df = pca_df[pca_df["CLUSTER"].isin(ids_perfiles)]

    pca_df = pca_df.sort_values("CLUSTER")
    puntos = df_to_records(pca_df)
    for p in puntos:
        if p["ES_MIXTO"]:
            p["COLOR"] = lib.COLOR_MIXTO
            p["GRUPO_COLOR"] = "MIXTO"
        elif modo == "rama":
            p["COLOR"] = "#457B9D" if p["TIPOEMPLEADO_ACTUAL_DESC"] == "DOCENTE" else "#E76F51"
            p["GRUPO_COLOR"] = p["TIPOEMPLEADO_ACTUAL_DESC"]
        elif modo == "cargo_real":
            cargo = p["CARGO_ACTUAL"] or "SIN CARGO"
            p["COLOR"] = color_por_texto(cargo)
            p["GRUPO_COLOR"] = cargo
        else:
            p["COLOR"] = cluster_color(p["CLUSTER"])
            p["GRUPO_COLOR"] = str(p["CLUSTER"])
    return {"total_modelo": int(len(personas)), "n_mostrados": len(puntos), "puntos": puntos, "modo": modo}


# ---------------------------------------------------------------------------
# Clustering SEMANTICO (en espacio de embeddings) - endpoints paralelos a resumen/perfiles/
# mapa de arriba, pero sobre el clustering de notebooks/07b_clustering_semantico (distinto
# espacio, distinto K, sin relacion 1:1 de IDs de cluster con el clustering estructural).
# Deliberadamente separados de los endpoints existentes (no un parametro "modo" en los
# mismos) para no arriesgar el comportamiento ya validado del clustering estructural.
# ---------------------------------------------------------------------------

@app.get("/api/resumen_semantico")
def resumen_semantico():
    resumen_df = get_resumen_semantico()
    clusters_df = get_clusters_semantico()
    return {
        "n_personas": int(len(clusters_df)),
        "n_perfiles": int(resumen_df["CLUSTER_SEMANTICO"].nunique()),
        "perfiles": [
            {**rec, "COLOR": cluster_color_semantico(rec["CLUSTER_SEMANTICO"])}
            for rec in df_to_records(resumen_df.sort_values("CLUSTER_SEMANTICO"))
        ],
    }


@app.get("/api/perfiles_semantico/{cluster_id}")
def perfil_detalle_semantico(cluster_id: int):
    resumen_df = get_resumen_semantico()
    fila = resumen_df[resumen_df["CLUSTER_SEMANTICO"] == cluster_id]
    if fila.empty:
        raise HTTPException(404, "Perfil semántico no encontrado")
    fila = fila.iloc[0]

    labels = get_feature_labels()
    feats = get_top_features_semantico()
    feats = feats[feats["CLUSTER_SEMANTICO"] == cluster_id].copy()
    feats["FEATURE_LABEL"] = feats["FEATURE"].map(lambda f: labels.get(f, f))

    personas = get_personas()
    clusters_df = get_clusters_semantico()
    ids_cluster = set(clusters_df.loc[clusters_df["CLUSTER_SEMANTICO"] == cluster_id, "IDPERSONA"])
    personas_cluster = personas[personas["IDPERSONA"].isin(ids_cluster)]

    cargos_cluster = personas_cluster["CARGO_ACTUAL"].dropna()
    conteo_cargos = cargos_cluster.value_counts().reset_index()
    conteo_cargos.columns = ["CARGO_ACTUAL", "N_PERSONAS"]

    muestra_cols = ["IDPERSONA", "NOMBRE_COMPLETO"] + [c for c in lib.METRICAS_CLAVE if c in personas_cluster.columns]
    muestra = personas_cluster[muestra_cols].head(50)

    return {
        "cluster": int(cluster_id),
        "nombre": fila["PERFIL_NOMBRE_SEMANTICO"],
        "n_personas": int(fila["N_PERSONAS"]),
        "pct_poblacion": float(fila["PCT_POBLACION"]),
        "descripcion": fila["DESCRIPCION"],
        "color": cluster_color_semantico(cluster_id),
        "top_features": df_to_records(feats[["FEATURE", "FEATURE_LABEL", "VALUE_CLUSTER", "VALUE_GLOBAL"]]),
        "cargos": df_to_records(conteo_cargos),
        "n_cargos_distintos": int(cargos_cluster.nunique()),
        "n_con_cargo": int(len(cargos_cluster)),
        "muestra_personas": df_to_records(muestra),
    }


@app.get("/api/mapa_semantico")
def mapa_semantico(perfiles: str = Query(""), modo: str = Query("cluster_semantico"), tipo: str = Query("Todos")):
    """Mismo mapa PCA que /api/mapa pero en el espacio de EMBEDDINGS (ver
    notebooks/07b_clustering_semantico) - `modo` decide COMO se colorea, igual patron que
    /api/mapa: "cluster_semantico" (default) usa los clusters de este notebook,
    "rama" usa TIPOEMPLEADO_ACTUAL_DESC/Mixto (igual regla que el mapa estructural, para
    comparar administrativo/docente/mixto en ambos espacios), "cargo_real" usa el cargo
    textual exacto (color_por_texto, mismo criterio que el mapa estructural)."""
    personas = get_personas()
    clusters_df = get_clusters_semantico()
    pca_df = get_pca_semantico().merge(clusters_df, on="IDPERSONA", how="inner").merge(
        personas[["IDPERSONA", "NOMBRE_COMPLETO", "TIPOEMPLEADO_ACTUAL_DESC", "VIGENTE_MOSTRAR", "CARGO_ACTUAL",
                  "ES_MIXTO", "CARGOS_ACTUALES_MIXTO"]],
        on="IDPERSONA", how="inner",
    )
    pca_df["ES_MIXTO"] = pca_df["ES_MIXTO"].fillna(False)

    if tipo == "Solo Administrativo":
        pca_df = pca_df[(pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "ADMINISTRATIVO") & (~pca_df["ES_MIXTO"])]
    elif tipo == "Solo Docente":
        pca_df = pca_df[(pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "DOCENTE") & (~pca_df["ES_MIXTO"])]
    elif tipo == "Solo Mixto":
        pca_df = pca_df[pca_df["ES_MIXTO"]]

    if perfiles and modo == "cluster_semantico":
        ids_perfiles = {int(p) for p in perfiles.split(",") if p}
        pca_df = pca_df[pca_df["CLUSTER_SEMANTICO"].isin(ids_perfiles)]

    resumen_df = get_resumen_semantico().set_index("CLUSTER_SEMANTICO")["PERFIL_NOMBRE_SEMANTICO"]
    pca_df = pca_df.sort_values("CLUSTER_SEMANTICO")
    puntos = df_to_records(pca_df)
    for p in puntos:
        p["PERFIL_NOMBRE_SEMANTICO"] = resumen_df.get(p["CLUSTER_SEMANTICO"])
        # El color/agrupacion por Mixto solo tiene sentido en modo "rama" (2+ cargos
        # estructurales vigentes en paralelo es un concepto de la rama admin/docente) - en
        # modo "cluster_semantico" no debe tapar el cluster real de la persona (bug real:
        # aparecia un 10mo grupo "MIXTO" ademas de los 9 clusters, aunque el usuario pidiera
        # ver los clusters puros).
        if p["ES_MIXTO"] and modo == "rama":
            p["COLOR"] = lib.COLOR_MIXTO
            p["GRUPO_COLOR"] = "MIXTO"
        elif modo == "rama":
            # El clustering semantico cubre a TODA la poblacion con embedding (incluye
            # personas sin tramo de rol estructural vigente, ver DEC en 07b_clustering_
            # semantico), a diferencia del mapa estructural que ya filtra CLUSTER != -1 -
            # ~22% no tiene TIPOEMPLEADO_ACTUAL_DESC. Sin este caso quedaban silenciosamente
            # coloreados como "administrativo" (el else original) y agrupados bajo el
            # nombre de grupo "None" crudo.
            if p["TIPOEMPLEADO_ACTUAL_DESC"] == "DOCENTE":
                p["COLOR"] = "#457B9D"
                p["GRUPO_COLOR"] = "DOCENTE"
            elif p["TIPOEMPLEADO_ACTUAL_DESC"] == "ADMINISTRATIVO":
                p["COLOR"] = "#E76F51"
                p["GRUPO_COLOR"] = "ADMINISTRATIVO"
            else:
                p["COLOR"] = "#94A3B8"
                p["GRUPO_COLOR"] = "SIN CARGO ACTUAL"
        elif modo == "cargo_real":
            cargo = p["CARGO_ACTUAL"] or "SIN CARGO"
            p["COLOR"] = color_por_texto(cargo)
            p["GRUPO_COLOR"] = cargo
        else:
            p["COLOR"] = cluster_color_semantico(p["CLUSTER_SEMANTICO"])
            p["GRUPO_COLOR"] = str(p["CLUSTER_SEMANTICO"])
    return {"total_modelo": int(len(clusters_df)), "n_mostrados": len(puntos), "puntos": puntos, "modo": modo}


_TOLERANCIA_RECESO_ACADEMICO = pd.Timedelta(days=90)


def _contar_tramos_por_categoria(tramos_persona: pd.DataFrame, tipo_empleado: str) -> int:
    """Cuenta cargos de un tipo (ADMINISTRATIVO/DOCENTE) fusionando tramos consecutivos de
    la MISMA CATEGORIA_CARGO separados por un receso corto (<= 90 días) - cubre el patrón
    real de contratación docente por periodo académico/semestral, donde `tramos_rol.csv`
    trae un tramo nuevo por cada semestre aunque sea el mismo cargo repetido con brechas de
    vacaciones entre medio (ej. persona 3519: 22 tramos "PROFESOR PREGRADO" 2001-2011, uno
    por semestre). Sin esto, alguien con muchos años de docencia por periodo se ve con una
    cifra de "cargos" artificialmente alta comparado con alguien de contrato anual
    continuo. Se agrupa por CATEGORIA_CARGO (no por CARGO_TRAMO textual) porque es la
    identidad estable de "mismo tipo de cargo" ya usada en el resto del pipeline."""
    del_tipo = tramos_persona[tramos_persona["TIPOEMPLEADO_DESC"] == tipo_empleado]
    n_tramos = 0
    for _, grupo in del_tipo.groupby("CATEGORIA_CARGO"):
        grupo = grupo.sort_values("TRAMO_INICIO")
        fin_anterior = None
        for _, fila in grupo.iterrows():
            inicio = fila["TRAMO_INICIO"]
            if fin_anterior is None or pd.isna(fin_anterior) or (inicio - fin_anterior) > _TOLERANCIA_RECESO_ACADEMICO:
                n_tramos += 1
            fin_actual = fila["TRAMO_FIN"]
            fin_anterior = fin_actual if pd.notna(fin_actual) else fin_anterior
    return n_tramos


def _contar_tramos_servicios_profesionales(eventos_sin_tipo: pd.DataFrame) -> list[dict]:
    """Cuenta tramos entre los eventos CARGO_ESPOL* sin TIPOEMPLEADO ("servicios
    profesionales"/contratos puntuales, excluidos de tramos_rol.csv por diseño): dos
    eventos con la MISMA DESCRIPCION se fusionan en un solo tramo si el segundo empieza
    dentro de un receso corto (<= 90 días, mismo criterio que `_contar_tramos_por_categoria`
    para el patrón de contrato puntual por periodo/semestre) de terminar el primero - no se
    cruzan con los tramos administrativo/docente de tramos_rol.csv (ese cruce causaba
    fusiones indebidas con cargos paralelos reales, ver persona 3519: un cargo docente
    vigente desde 2011 o un rol de Director solapado con "servicios profesionales" sueltos
    no deben absorberlos)."""
    n_tramos = 0
    descripciones: list[str] = []
    for descripcion, grupo in eventos_sin_tipo.groupby("DESCRIPCION"):
        grupo = grupo.sort_values("FECHA_INICIO")
        fin_anterior = None
        for _, fila in grupo.iterrows():
            inicio = fila["FECHA_INICIO"]
            if fin_anterior is None or pd.isna(fin_anterior) or (inicio - fin_anterior) > _TOLERANCIA_RECESO_ACADEMICO:
                n_tramos += 1
                descripciones.append(descripcion)
            fin_actual = fila["FECHA_FIN"]
            fin_anterior = fin_actual if pd.notna(fin_actual) else fin_anterior
    if not n_tramos:
        return []
    if len(set(descripciones)) == 1:
        return [{"etiqueta": descripciones[0], "cantidad": n_tramos}]
    return [{"etiqueta": "Otros", "cantidad": n_tramos}]


def _resumen_cargos_espol(id_persona: int, eventos_persona: pd.DataFrame) -> dict:
    """Cuenta cargos en ESPOL por TRAMO, no por evento/contrato individual - alguien que
    renueva el mismo contrato varias veces (incluyendo renovaciones separadas por un receso
    académico corto, ej. vacaciones entre semestres) cuenta como 1 cargo, no como N.
    Administrativo/Docente parten de `tramos_rol.csv` (que ya maneja roles paralelos
    correctamente, DEC-011) pero se fusionan aquí por CATEGORIA_CARGO + receso corto; los
    contratos "servicios profesionales" sin tipo se cuentan aparte con el mismo criterio de
    receso, sin cruzarse con los tramos con tipo."""
    tramos = get_tramos_rol()
    tramos_persona = tramos[tramos["IDPERSONA"] == id_persona]
    n_administrativo = _contar_tramos_por_categoria(tramos_persona, "ADMINISTRATIVO")
    n_docente = _contar_tramos_por_categoria(tramos_persona, "DOCENTE")

    cargos_espol = eventos_persona[eventos_persona["TIPO_EVENTO"].str.startswith("CARGO_ESPOL")]
    sin_tipo = cargos_espol[cargos_espol["TIPOEMPLEADO"].isna()]
    otras_categorias = _contar_tramos_servicios_profesionales(sin_tipo) if len(sin_tipo) else []

    total = n_administrativo + n_docente + sum(o["cantidad"] for o in otras_categorias)
    return {
        "total": total,
        "administrativo": n_administrativo,
        "docente": n_docente,
        "otras_categorias": otras_categorias,
    }


def _contar_tramos_vectorizado(df: pd.DataFrame, clave_grupo: list[str], col_inicio: str, col_fin: str) -> pd.Series:
    """Misma regla de fusión que `_contar_tramos_por_categoria`/
    `_contar_tramos_servicios_profesionales` (nuevo tramo si el gap con el evento anterior
    del mismo grupo supera `_TOLERANCIA_RECESO_ACADEMICO`), pero vectorizada con
    operaciones de pandas sobre TODAS las personas a la vez en vez de un loop Python +
    `.iterrows()` por persona - con ~5000 personas, el overhead fijo de pandas por llamada
    de función hacía que la versión con loop tardara ~9s incluso después de evitar el
    escaneo lineal repetido (reportado por el usuario 2026-09-16: "empieza filtrando y se
    demora, ni siquiera he colocado los filtros"). `clave_grupo` debe incluir "IDPERSONA"
    como primer elemento. Devuelve una Serie IDPERSONA -> cantidad de tramos."""
    d = df.sort_values(clave_grupo + [col_inicio]).copy()
    # ffill antes de cummax: un tramo abierto (FECHA_FIN/TRAMO_FIN nulo) debe mantener el
    # ÚLTIMO fin conocido dentro de su grupo, no "resetear" el máximo a NaT (que es lo que
    # haría cummax solo) - misma semántica que `fin_anterior` en la versión con loop, que
    # nunca sobrescribe con un valor nulo.
    fin_maximo_visto = d.groupby(clave_grupo)[col_fin].apply(lambda s: s.ffill().cummax()).reset_index(drop=True)
    fin_maximo_visto.index = d.index
    fin_anterior = fin_maximo_visto.groupby([d[c] for c in clave_grupo]).shift(1)
    primero_del_grupo = d.groupby(clave_grupo).cumcount().eq(0)
    gap = d[col_inicio] - fin_anterior
    nuevo_tramo = primero_del_grupo | gap.isna() | (gap > _TOLERANCIA_RECESO_ACADEMICO)
    return d.assign(_NUEVO=nuevo_tramo).groupby("IDPERSONA")["_NUEVO"].sum()


@lru_cache(maxsize=1)
def get_n_cargos_espol_por_persona() -> pd.Series:
    """Precalcula `resumen_cargos_espol()["total"]` para TODAS las personas (no solo
    on-demand como en la ficha individual), para poder usarlo como filtro en "Formar
    equipos" - ej. "mínimo de cargos distintos en ESPOL" para la necesidad real de
    selección de Director de Talento Humano (2026-09-16): cantidad de cargos + estabilidad,
    no solo un puesto único en toda la carrera. Cacheado en memoria (igual patrón que los
    demás get_*() de este archivo) - vive solo en el backend del dashboard, no se
    materializa en personas_dashboard.csv ni en el pipeline de notebooks. Usa la versión
    vectorizada (`_contar_tramos_vectorizado`), no el loop por persona de
    `_contar_tramos_por_categoria`/`_contar_tramos_servicios_profesionales` (esas dos
    siguen usándose para la ficha individual, donde el volumen es 1 persona y sí hace
    falta el desglose admin/docente/etiquetas de "Otros")."""
    tramos = get_tramos_rol()
    eventos = get_eventos_trayectoria()
    cargos_espol_todos = eventos[eventos["TIPO_EVENTO"].str.startswith("CARGO_ESPOL")]
    sin_tipo_todos = cargos_espol_todos[cargos_espol_todos["TIPOEMPLEADO"].isna()]

    n_admin_docente = _contar_tramos_vectorizado(
        tramos, ["IDPERSONA", "TIPOEMPLEADO_DESC", "CATEGORIA_CARGO"], "TRAMO_INICIO", "TRAMO_FIN"
    )
    n_sin_tipo = _contar_tramos_vectorizado(
        sin_tipo_todos, ["IDPERSONA", "DESCRIPCION"], "FECHA_INICIO", "FECHA_FIN"
    )
    return n_admin_docente.add(n_sin_tipo, fill_value=0).rename("N_CARGOS_ESPOL")


def _duraciones_tramos_fusionados(df: pd.DataFrame, clave_grupo: list[str], col_inicio: str, col_fin: str) -> pd.DataFrame:
    """Como `_contar_tramos_vectorizado`, pero en vez de solo contar, calcula la duración
    (en años) de cada tramo YA FUSIONADO por receso académico - necesario para
    DURACION_MEDIANA_TRAMO_ANIOS/TURBULENCIA_TRAMOS, que hoy vienen del pipeline de
    notebooks calculadas sobre tramos_rol.csv SIN esa fusión: alguien con muchos tramos
    cortos por periodo académico (ej. persona 3519, 22 tramos semestrales de "Profesor
    Pregrado" 2001-2011) sale con una mediana artificialmente baja (0.36 años) aunque en
    la práctica esos tramos son un solo cargo continuo - la misma distorsión que ya se
    corrigió para N_CARGOS_ESPOL, aplicada aquí a duración en vez de conteo. Devuelve un
    DataFrame con IDPERSONA y DURACION_ANIOS, una fila por tramo fusionado."""
    d = df.sort_values(clave_grupo + [col_inicio]).copy()
    fin_maximo_visto = d.groupby(clave_grupo)[col_fin].apply(lambda s: s.ffill().cummax()).reset_index(drop=True)
    fin_maximo_visto.index = d.index
    fin_anterior = fin_maximo_visto.groupby([d[c] for c in clave_grupo]).shift(1)
    primero_del_grupo = d.groupby(clave_grupo).cumcount().eq(0)
    gap = d[col_inicio] - fin_anterior
    nuevo_tramo = primero_del_grupo | gap.isna() | (gap > _TOLERANCIA_RECESO_ACADEMICO)
    d["_ID_TRAMO"] = nuevo_tramo.cumsum()

    hoy = pd.Timestamp.today()
    d["_FIN_EFECTIVO"] = d[col_fin].fillna(hoy)
    agregado = d.groupby("_ID_TRAMO").agg(
        IDPERSONA=("IDPERSONA", "first"),
        INICIO=(col_inicio, "min"),
        FIN=("_FIN_EFECTIVO", "max"),
    )
    agregado["DURACION_ANIOS"] = (agregado["FIN"] - agregado["INICIO"]).dt.days / 365.25
    return agregado[["IDPERSONA", "DURACION_ANIOS"]]


@lru_cache(maxsize=1)
def get_estabilidad_carrera_por_persona() -> pd.DataFrame:
    """Recalcula DURACION_MEDIANA_TRAMO_ANIOS y TURBULENCIA_TRAMOS sobre tramos YA
    FUSIONADOS por receso académico (ver `_duraciones_tramos_fusionados`), para usar en
    los filtros de "Formar equipos"/"Búsqueda combinada" en vez de las columnas originales
    de `personas_dashboard.csv` (que vienen del pipeline de notebooks sin esa fusión) -
    pedido explícito del usuario 2026-09-16 tras detectar que 3519 (Director de Talento
    Humano y Profesor) quedaba excluida de un filtro "mínimo 1 año de permanencia típica"
    por una mediana de 0.36 años calculada sobre sus 22 tramos semestrales sin fusionar.
    Solo cubre tramos con TIPOEMPLEADO (ADMINISTRATIVO/DOCENTE, de tramos_rol.csv) - los
    contratos "servicios profesionales" sin tipo no formaban parte del cálculo original
    tampoco. Cacheado en memoria, igual patrón que get_n_cargos_espol_por_persona."""
    tramos = get_tramos_rol()
    duraciones = _duraciones_tramos_fusionados(
        tramos, ["IDPERSONA", "TIPOEMPLEADO_DESC", "CATEGORIA_CARGO"], "TRAMO_INICIO", "TRAMO_FIN"
    )
    resumen = duraciones.groupby("IDPERSONA")["DURACION_ANIOS"].agg(
        DURACION_MEDIANA_TRAMO_ANIOS_FUSIONADA="median",
        _MEDIA="mean",
        _STD="std",
        _N="size",
    )
    turbulencia = (resumen["_STD"] / resumen["_MEDIA"]).where(resumen["_N"] >= 2)
    resumen["TURBULENCIA_TRAMOS_FUSIONADA"] = turbulencia
    return resumen[["DURACION_MEDIANA_TRAMO_ANIOS_FUSIONADA", "TURBULENCIA_TRAMOS_FUSIONADA"]]


@app.get("/api/personas")
def listar_personas():
    personas = get_personas().sort_values("NOMBRE_COMPLETO")
    return {
        "ids": personas["IDPERSONA"].tolist(),
        "personas": df_to_records(personas[["IDPERSONA", "NOMBRE_COMPLETO"]]),
    }


def _evidencia_trayectoria(id_persona: int) -> dict:
    """Arma el bloque de evidencia para la ficha de persona cuando la coincidencia viene de
    la busqueda por TRAYECTORIA (`origen_busqueda=trayectoria`) - a diferencia del corpus
    generico (`corpus_muestra`, pensado para el embedding general de temas/conocimiento),
    aqui se muestra: el documento de trayectoria completo (el mismo texto que se embebio,
    ver notebooks/07_embeddings/07_embeddings.ipynb seccion 7), sus variables objetivas
    (N_CARGOS_TOTAL, N_CAMBIOS_CARGO, N_CAMBIOS_UNIDAD, duraciones...), y el detalle de
    periodos/cargos/unidades consolidados con marca de cargo paralelo (ES_PARALELO) cuando
    la persona ejercio 2+ cargos en unidades distintas al mismo tiempo."""
    documentos_trayectoria = get_documento_trayectoria()
    fila_doc = documentos_trayectoria[documentos_trayectoria["IDPERSONA"] == id_persona]
    if fila_doc.empty:
        return {"disponible": False, "motivo": "Sin tramo de rol estructural (sin embedding de trayectoria)."}

    d = fila_doc.iloc[0]
    variables = {
        "n_cargos_total": int(d["N_CARGOS_TOTAL"]),
        "n_cargos_significativos": int(d["N_CARGOS_SIGNIFICATIVOS"]),
        "n_cambios_cargo": int(d["N_CAMBIOS_CARGO"]),
        "n_cambios_unidad": int(d["N_CAMBIOS_UNIDAD"]),
        "duracion_media_cargo_anios": None if pd.isna(d["DURACION_MEDIA_CARGO_ANIOS"]) else float(d["DURACION_MEDIA_CARGO_ANIOS"]),
        "duracion_mediana_cargo_anios": None if pd.isna(d["DURACION_MEDIANA_CARGO_ANIOS"]) else float(d["DURACION_MEDIANA_CARGO_ANIOS"]),
        "duracion_max_cargo_anios": None if pd.isna(d["DURACION_MAX_CARGO_ANIOS"]) else float(d["DURACION_MAX_CARGO_ANIOS"]),
        "n_unidades_total": int(d["N_UNIDADES_TOTAL"]),
        "n_unidades_significativas": int(d["N_UNIDADES_SIGNIFICATIVAS"]),
        "proporcion_cargos_significativos": None if pd.isna(d["PROPORCION_CARGOS_SIGNIFICATIVOS"]) else float(d["PROPORCION_CARGOS_SIGNIFICATIVOS"]),
    }

    tramos = get_tramos_cargo_unidad()
    tramos_persona = tramos[tramos["IDPERSONA"] == id_persona].sort_values("INICIO").reset_index(drop=True)

    # Fin efectivo (hoy si vigente) para comparar solapes de fecha - mismo criterio que
    # `construir_tramos_cargo_unidad_persona` en _embeddings_comun.py, recalculado aqui
    # (no en el notebook) porque solo se necesita el DETALLE de con qué otro periodo se
    # solapa cada uno, no el booleano ES_PARALELO en si (ese ya viene calculado).
    hoy = pd.Timestamp.today().normalize()
    fin_cmp = tramos_persona["FIN"].fillna(hoy)

    periodos = []
    for i, r in tramos_persona.iterrows():
        paralelo_con = []
        if bool(r["ES_PARALELO"]):
            for j, r2 in tramos_persona.iterrows():
                if i == j:
                    continue
                solapan = r["INICIO"] <= fin_cmp.iloc[j] and r2["INICIO"] <= fin_cmp.iloc[i]
                if solapan:
                    paralelo_con.append({
                        "cargo": r2["CARGO"] or None,
                        "unidad": r2["UNIDAD"] or None,
                        "inicio": r2["INICIO"].strftime("%Y-%m-%d") if pd.notna(r2["INICIO"]) else None,
                        "fin": r2["FIN"].strftime("%Y-%m-%d") if pd.notna(r2["FIN"]) else None,
                    })

        periodos.append({
            "cargo": r["CARGO"] or None,
            "unidad": r["UNIDAD"] or None,
            "inicio": r["INICIO"].strftime("%Y-%m-%d") if pd.notna(r["INICIO"]) else None,
            "fin": r["FIN"].strftime("%Y-%m-%d") if pd.notna(r["FIN"]) else None,
            "vigente": bool(pd.isna(r["FIN"])),
            "duracion_anios": None if pd.isna(r["DURACION_ANIOS"]) else float(r["DURACION_ANIOS"]),
            "es_significativo": bool(r["ES_SIGNIFICATIVO"]),
            "es_paralelo": bool(r["ES_PARALELO"]),
            "paralelo_con": paralelo_con,
        })

    # Secuencia de cambios de CARGO (ignora cambios que son solo de unidad) y de UNIDAD
    # (ignora cambios que son solo de cargo), cada una como lista de transiciones
    # consecutivas EN ORDEN CRONOLOGICO - separado del conteo simple N_CAMBIOS_CARGO/
    # N_CAMBIOS_UNIDAD (ya en `variables`) para responder "como fue la secuencia" con
    # fechas y valores concretos, no solo el numero.
    secuencia_cambios_cargo = []
    secuencia_cambios_unidad = []
    for i in range(1, len(tramos_persona)):
        anterior, actual = tramos_persona.iloc[i - 1], tramos_persona.iloc[i]
        fecha_cambio = actual["INICIO"].strftime("%Y-%m-%d") if pd.notna(actual["INICIO"]) else None
        if anterior["CARGO"] != actual["CARGO"]:
            secuencia_cambios_cargo.append({
                "fecha": fecha_cambio, "de": anterior["CARGO"] or None, "a": actual["CARGO"] or None,
            })
        if anterior["UNIDAD"] != actual["UNIDAD"]:
            secuencia_cambios_unidad.append({
                "fecha": fecha_cambio, "de": anterior["UNIDAD"] or None, "a": actual["UNIDAD"] or None,
            })

    return {
        "disponible": True,
        "documento_texto": d["DOCUMENTO_TRAYECTORIA_TEXTO"],
        "variables": variables,
        "periodos": periodos,
        "secuencia_cambios_cargo": secuencia_cambios_cargo,
        "secuencia_cambios_unidad": secuencia_cambios_unidad,
        "tiene_cargos_paralelos": any(p["es_paralelo"] for p in periodos),
    }


@app.get("/api/personas/{id_persona}")
def persona_ficha(id_persona: int, origen_busqueda: str = Query("")):
    personas = get_personas()
    fila = personas[personas["IDPERSONA"] == id_persona]
    if fila.empty:
        raise HTTPException(404, "Persona no encontrada")
    persona = fila.iloc[0]
    resumen_df = get_resumen()

    cluster_val = persona.get("CLUSTER")
    tiene_perfil = pd.notna(cluster_val) and int(cluster_val) != -1

    motivo = None
    if not tiene_perfil:
        motivo = lib.motivo_sin_perfil(id_persona)

    eventos = get_eventos_trayectoria()
    eventos_persona = eventos[eventos["IDPERSONA"] == id_persona].sort_values("FECHA_INICIO").copy()

    resumen_cargos_espol = _resumen_cargos_espol(id_persona, eventos_persona)

    eventos_persona["FECHA_INICIO"] = eventos_persona["FECHA_INICIO"].dt.strftime("%Y-%m-%d")
    eventos_persona["FECHA_FIN"] = eventos_persona["FECHA_FIN"].dt.strftime("%Y-%m-%d")

    secciones = {}
    formacion = lib.formacion_persona(id_persona)
    if len(formacion):
        secciones["formacion"] = df_to_records(formacion)
    docencia = lib.docencia_persona(id_persona)
    if len(docencia):
        secciones["docencia"] = df_to_records(docencia)
    investigacion = lib.investigacion_persona(id_persona)
    if any(len(v) for v in investigacion.values()):
        secciones["investigacion"] = {k: df_to_records(v) for k, v in investigacion.items()}
    vinculacion = lib.vinculacion_persona(id_persona)
    if len(vinculacion):
        secciones["vinculacion"] = df_to_records(vinculacion)
    capacitacion = lib.capacitacion_persona(id_persona)
    if any(len(v) for v in capacitacion.values()):
        secciones["capacitacion"] = {k: df_to_records(v) for k, v in capacitacion.items()}
    idiomas = lib.idiomas_persona(id_persona)
    if len(idiomas):
        secciones["idiomas"] = df_to_records(idiomas)
    reconocimientos = lib.reconocimientos_persona(id_persona)
    if len(reconocimientos):
        secciones["reconocimientos"] = df_to_records(reconocimientos)

    radar = None
    cluster_descripcion = None
    if tiene_perfil:
        fila_cluster = resumen_df[resumen_df["CLUSTER"] == int(cluster_val)]
        if len(fila_cluster):
            cluster_descripcion = fila_cluster.iloc[0]["DESCRIPCION"]
        disponibles = [f for f in lib.RADAR_FEATURES if f in persona.index]
        radar_vals = []
        for f in disponibles:
            serie = personas[f]
            val = persona[f]
            pct = float((serie < val).mean()) if pd.notna(val) else 0.0
            radar_vals.append(round(pct, 4))
        radar = {"features": disponibles, "valores": radar_vals}

    n_textos = persona.get("N_REGISTROS_TEXTO")
    corpus_muestra = []
    if pd.notna(n_textos) and n_textos and n_textos > 0:
        corpus = get_corpus()
        corpus_muestra = df_to_records(corpus[corpus["IDPERSONA"] == id_persona].head(10)[["FUENTE", "TEXTO"]])

    # DEC (2026-09-16): "Por qué coincide" debe reflejar la fuente REAL que se comparo en
    # la busqueda de origen, no siempre el corpus generico del embedding general - el
    # frontend indica el origen via `origen_busqueda` (ver BusquedaTrayectoriaPage.tsx).
    evidencia_trayectoria = None
    if origen_busqueda == "trayectoria":
        evidencia_trayectoria = _evidencia_trayectoria(id_persona)

    persona_dict = fila.replace({np.nan: None}).iloc[0].to_dict()

    return {
        "persona": persona_dict,
        "tiene_perfil": bool(tiene_perfil),
        "motivo_sin_perfil": motivo,
        "eventos_trayectoria": df_to_records(eventos_persona),
        "resumen_cargos_espol": resumen_cargos_espol,
        "secciones": secciones,
        "radar": radar,
        "cluster_descripcion": cluster_descripcion,
        "corpus_muestra": corpus_muestra,
        "n_textos": int(n_textos) if pd.notna(n_textos) else 0,
        "evidencia_trayectoria": evidencia_trayectoria,
        "color_tipo_evento": lib.COLOR_TIPO_EVENTO,
        "etiqueta_tipo_evento": lib.ETIQUETA_TIPO_EVENTO,
    }


def _aplicar_filtros_estructurados(
    personas: pd.DataFrame,
    vigencia: str = "Cualquiera",
    tipo: str = "",
    nivel: str = "",
    min_publicaciones: int = 0,
    min_exp_admin: float = 0.0,
    max_turbulencia: float = 0.0,
    min_duracion_mediana: float = 0.0,
    min_cargos_espol: int = 0,
    max_cargos_espol: int = 0,
) -> pd.DataFrame:
    """Filtros estructurados compartidos entre "Formar equipos" (`/api/equipos`) y
    "Búsqueda combinada" (`/api/buscar_avanzado`) - misma lógica, un solo lugar para
    mantenerla consistente entre ambas pantallas. Sin filtro de perfil/cluster (quitado a
    pedido explícito del usuario 2026-09-16, "no quiero que en formacion de comisiones ni
    en el tab combinado se filtre por perfiles")."""
    resultado = personas.merge(
        get_n_cargos_espol_por_persona().rename("N_CARGOS_ESPOL"),
        left_on="IDPERSONA", right_index=True, how="left",
    ).merge(
        get_estabilidad_carrera_por_persona(), left_on="IDPERSONA", right_index=True, how="left",
    )
    # DURACION_MEDIANA_TRAMO_ANIOS/TURBULENCIA_TRAMOS originales (de personas_dashboard.csv,
    # calculadas sobre tramos SIN fusionar) se reemplazan por la versión fusionada por
    # receso académico en toda la tabla, no solo en el filtro - así "Formar equipos" y la
    # ficha muestran el mismo criterio consistente. Ver `get_estabilidad_carrera_por_persona`.
    resultado["DURACION_MEDIANA_TRAMO_ANIOS"] = resultado["DURACION_MEDIANA_TRAMO_ANIOS_FUSIONADA"]
    resultado["TURBULENCIA_TRAMOS"] = resultado["TURBULENCIA_TRAMOS_FUSIONADA"]
    if vigencia == "Solo vigentes":
        resultado = resultado[resultado["VIGENTE_MOSTRAR"] == True]  # noqa: E712
    elif vigencia == "Solo no vigentes":
        resultado = resultado[resultado["VIGENTE_MOSTRAR"] == False]  # noqa: E712
    if tipo:
        tipos = set(tipo.split(","))
        resultado = resultado[resultado["TIPOEMPLEADO_ACTUAL_DESC"].isin(tipos)]
    if nivel:
        niveles = set(nivel.split(","))
        resultado = resultado[resultado["NIVEL_ACADEMICO_MAXIMO"].isin(niveles)]
    if min_publicaciones:
        resultado = resultado[resultado["NUM_PUBLICACIONES"].fillna(0) >= min_publicaciones]
    if min_exp_admin:
        resultado = resultado[resultado["ANIOS_EXPERIENCIA_ADMINISTRATIVO"].fillna(0) >= min_exp_admin]
    if max_turbulencia:
        # TURBULENCIA_TRAMOS es NA real para personas con un solo tramo fusionado (ver
        # DEC-027) - no hay rotacion que medir con un unico tramo, asi que por definicion
        # son personas MUY estables y no deben excluirse por tener el dato nulo (fillna con
        # 0, el minimo posible de turbulencia, no con un valor alto que las descartaria
        # injustamente).
        resultado = resultado[resultado["TURBULENCIA_TRAMOS"].fillna(0) <= max_turbulencia]
    if min_duracion_mediana:
        resultado = resultado[resultado["DURACION_MEDIANA_TRAMO_ANIOS"].fillna(0) >= min_duracion_mediana]
    if min_cargos_espol:
        resultado = resultado[resultado["N_CARGOS_ESPOL"].fillna(0) >= min_cargos_espol]
    if max_cargos_espol:
        # Alguien con un solo cargo en toda su carrera (N_CARGOS_ESPOL=1) siempre pasa
        # cualquier máximo >= 1, tal como pidió el usuario (2026-09-16): "personas con un
        # cargo pasan cualquier filtro" - de "cuántas veces se mueve de cargo".
        resultado = resultado[resultado["N_CARGOS_ESPOL"].fillna(0) <= max_cargos_espol]
    return resultado


@app.get("/api/equipos")
def equipos(
    vigencia: str = Query("Cualquiera"),
    tipo: str = Query(""),
    nivel: str = Query(""),
    min_publicaciones: int = Query(0),
    min_exp_admin: float = Query(0.0),
    max_turbulencia: float = Query(0.0),
    min_duracion_mediana: float = Query(0.0),
    min_cargos_espol: int = Query(0),
    max_cargos_espol: int = Query(0),
):
    personas = get_personas()
    resultado = _aplicar_filtros_estructurados(
        personas, vigencia, tipo, nivel, min_publicaciones, min_exp_admin,
        max_turbulencia, min_duracion_mediana, min_cargos_espol, max_cargos_espol,
    )

    cols_out = ["IDPERSONA", "NOMBRE_COMPLETO"] + [c for c in lib.METRICAS_CLAVE if c in resultado.columns]
    if "N_CARGOS_ESPOL" not in cols_out:
        cols_out.append("N_CARGOS_ESPOL")
    return {
        "n_resultados": int(len(resultado)),
        "candidatos": df_to_records(resultado[cols_out]),
        "opciones": {
            "tipo_empleado": sorted(personas["TIPOEMPLEADO_ACTUAL_DESC"].dropna().unique().tolist()),
            "nivel_academico": sorted(personas["NIVEL_ACADEMICO_MAXIMO"].dropna().unique().tolist()),
        },
    }


class BusquedaSemantica(BaseModel):
    consulta: str
    top_n: int = 10
    vigencia: str = "Cualquiera"


@app.post("/api/buscar")
def buscar(body: BusquedaSemantica):
    if not body.consulta.strip():
        raise HTTPException(400, "Consulta vacía")

    ids, matrix = get_embeddings()
    modelo = get_text_model()
    q = modelo.encode([f"query: {body.consulta}"], normalize_embeddings=True)[0]
    sims = matrix @ q
    orden = np.argsort(-sims)

    personas = get_personas()
    documentos = get_documento_semantico().set_index("IDPERSONA")["DOCUMENTO_TEXTO"]

    resultados = []
    rango = 0
    for idx in orden:
        idp = int(ids[idx])
        fila = personas[personas["IDPERSONA"] == idp]
        if fila.empty:
            continue
        p = fila.iloc[0]
        vigente = bool(p.get("VIGENTE_MOSTRAR")) if pd.notna(p.get("VIGENTE_MOSTRAR")) else False

        if body.vigencia == "Solo vigentes" and not vigente:
            continue
        if body.vigencia == "Solo no vigentes" and vigente:
            continue

        rango += 1
        resultados.append({
            "rango": rango,
            "id_persona": idp,
            "nombre_completo": p.get("NOMBRE_COMPLETO"),
            "cluster": None if pd.isna(p.get("CLUSTER")) else int(p.get("CLUSTER")),
            "perfil_nombre": p.get("PERFIL_NOMBRE") if pd.notna(p.get("PERFIL_NOMBRE")) else None,
            "vigente": vigente,
            "tipo_empleado": p.get("TIPOEMPLEADO_ACTUAL_DESC") if pd.notna(p.get("TIPOEMPLEADO_ACTUAL_DESC")) else None,
            "cargo_actual": p.get("CARGO_ACTUAL") if pd.notna(p.get("CARGO_ACTUAL")) else None,
            "evidencia": _mejor_evidencia(body.consulta, documentos.get(idp, "")),
        })
        if rango >= body.top_n:
            break

    return {"consulta": body.consulta, "resultados": resultados}


class BusquedaAvanzada(BaseModel):
    consulta: str
    top_n: int = 10
    vigencia: str = "Cualquiera"
    tipo: str = ""
    nivel: str = ""
    min_publicaciones: int = 0
    min_exp_admin: float = 0.0
    max_turbulencia: float = 0.0
    min_duracion_mediana: float = 0.0
    min_cargos_espol: int = 0
    max_cargos_espol: int = 0


@app.post("/api/buscar_avanzado")
def buscar_avanzado(body: BusquedaAvanzada):
    """Combina texto libre (afinidad semántica) con los mismos filtros estructurados de
    "Formar equipos" - pedido explícito del usuario 2026-09-16 ("con esos filtros ahora si
    puedo buscar por transicion pero no alguien que tenga conocimeintos en th"): los
    filtros numéricos por sí solos no capturan conocimiento/experiencia temática, y la
    búsqueda semántica por sí sola no puede aplicar umbrales duros (DEC-019, similitud
    coseno sin punto de corte interpretable) - se necesitan ambos a la vez, no uno u otro.
    Orden de combinación (confirmado por el usuario): primero se filtra la población
    completa por los criterios estructurales, y SOLO DESPUÉS se ordena por afinidad al
    texto dentro de quienes ya pasaron el filtro - así nadie que cumple los filtros se
    pierde por haber quedado fuera de un top-N calculado antes de filtrar."""
    if not body.consulta.strip():
        raise HTTPException(400, "Consulta vacía")

    personas = get_personas()
    filtrados = _aplicar_filtros_estructurados(
        personas, body.vigencia, body.tipo, body.nivel, body.min_publicaciones,
        body.min_exp_admin, body.max_turbulencia, body.min_duracion_mediana,
        body.min_cargos_espol, body.max_cargos_espol,
    )
    ids_filtrados = set(filtrados["IDPERSONA"])

    ids, matrix = get_embeddings()
    modelo = get_text_model()
    q = modelo.encode([f"query: {body.consulta}"], normalize_embeddings=True)[0]
    sims = matrix @ q
    orden = np.argsort(-sims)

    documentos = get_documento_semantico().set_index("IDPERSONA")["DOCUMENTO_TEXTO"]
    personas_por_id = filtrados.set_index("IDPERSONA")

    resultados = []
    rango = 0
    for idx in orden:
        idp = int(ids[idx])
        if idp not in ids_filtrados:
            continue
        p = personas_por_id.loc[idp]
        rango += 1
        resultados.append({
            "rango": rango,
            "id_persona": idp,
            "nombre_completo": p.get("NOMBRE_COMPLETO"),
            "cluster": None if pd.isna(p.get("CLUSTER")) else int(p.get("CLUSTER")),
            "perfil_nombre": p.get("PERFIL_NOMBRE") if pd.notna(p.get("PERFIL_NOMBRE")) else None,
            "vigente": bool(p.get("VIGENTE_MOSTRAR")) if pd.notna(p.get("VIGENTE_MOSTRAR")) else False,
            "tipo_empleado": p.get("TIPOEMPLEADO_ACTUAL_DESC") if pd.notna(p.get("TIPOEMPLEADO_ACTUAL_DESC")) else None,
            "cargo_actual": p.get("CARGO_ACTUAL") if pd.notna(p.get("CARGO_ACTUAL")) else None,
            "n_cargos_espol": None if pd.isna(p.get("N_CARGOS_ESPOL")) else float(p.get("N_CARGOS_ESPOL")),
            "duracion_mediana_tramo_anios": None if pd.isna(p.get("DURACION_MEDIANA_TRAMO_ANIOS")) else float(p.get("DURACION_MEDIANA_TRAMO_ANIOS")),
            "evidencia": _mejor_evidencia(body.consulta, documentos.get(idp, "")),
        })
        if rango >= body.top_n:
            break

    return {"consulta": body.consulta, "n_candidatos_tras_filtros": int(len(ids_filtrados)), "resultados": resultados}


@app.post("/api/buscar_avanzado_trayectoria")
def buscar_avanzado_trayectoria(body: BusquedaAvanzada):
    """Igual que `/api/buscar_avanzado` (mismos filtros estructurados, mismo cuerpo de
    request `BusquedaAvanzada`, mismo orden de combinacion: primero se filtra la poblacion
    por los criterios estructurales, y SOLO DESPUES se ordena por afinidad al texto dentro
    de quienes ya pasaron el filtro), pero el ranking semantico usa el embedding de
    TRAYECTORIA (`embeddings_trayectoria.csv`, ver notebooks/07_embeddings/07_embeddings.ipynb
    seccion 7) en vez del embedding general - permite comparar como cambia el orden de
    resultados cuando la afinidad se mide solo por patron de carrera (cargo/unidad/
    permanencia/estabilidad/movilidad) en vez de por conocimiento/tema. Capa exploratoria
    para comparacion, no reemplaza `/api/buscar_avanzado` ni se mezcla con el.

    La "evidencia" de por que coincide usa `documento_trayectoria_persona.csv` (el texto de
    trayectoria), no el documento semantico general - asi el fragmento resaltado es
    coherente con lo que efectivamente se comparo semanticamente.

    Solo cubre a las personas con embedding de trayectoria (las que tienen al menos un tramo
    de rol estructural, ver CATEGORIAS_PUNTUALES/DEC-004) - un subconjunto mas chico que el
    embedding general."""
    if not body.consulta.strip():
        raise HTTPException(400, "Consulta vacía")

    personas = get_personas()
    filtrados = _aplicar_filtros_estructurados(
        personas, body.vigencia, body.tipo, body.nivel, body.min_publicaciones,
        body.min_exp_admin, body.max_turbulencia, body.min_duracion_mediana,
        body.min_cargos_espol, body.max_cargos_espol,
    )
    ids_filtrados = set(filtrados["IDPERSONA"])

    ids, matrix = get_embeddings_trayectoria()
    modelo = get_text_model()
    q = modelo.encode([f"query: {body.consulta}"], normalize_embeddings=True)[0]
    sims = matrix @ q
    orden = np.argsort(-sims)

    documentos_trayectoria = get_documento_trayectoria().set_index("IDPERSONA")["DOCUMENTO_TRAYECTORIA_TEXTO"]
    personas_por_id = filtrados.set_index("IDPERSONA")

    resultados = []
    rango = 0
    for idx in orden:
        idp = int(ids[idx])
        if idp not in ids_filtrados:
            continue
        p = personas_por_id.loc[idp]
        rango += 1
        resultados.append({
            "rango": rango,
            "id_persona": idp,
            "nombre_completo": p.get("NOMBRE_COMPLETO"),
            "cluster": None if pd.isna(p.get("CLUSTER")) else int(p.get("CLUSTER")),
            "perfil_nombre": p.get("PERFIL_NOMBRE") if pd.notna(p.get("PERFIL_NOMBRE")) else None,
            "vigente": bool(p.get("VIGENTE_MOSTRAR")) if pd.notna(p.get("VIGENTE_MOSTRAR")) else False,
            "tipo_empleado": p.get("TIPOEMPLEADO_ACTUAL_DESC") if pd.notna(p.get("TIPOEMPLEADO_ACTUAL_DESC")) else None,
            "cargo_actual": p.get("CARGO_ACTUAL") if pd.notna(p.get("CARGO_ACTUAL")) else None,
            "n_cargos_espol": None if pd.isna(p.get("N_CARGOS_ESPOL")) else float(p.get("N_CARGOS_ESPOL")),
            "duracion_mediana_tramo_anios": None if pd.isna(p.get("DURACION_MEDIANA_TRAMO_ANIOS")) else float(p.get("DURACION_MEDIANA_TRAMO_ANIOS")),
            "evidencia": _mejor_evidencia(body.consulta, documentos_trayectoria.get(idp, "")),
        })
        if rango >= body.top_n:
            break

    return {"consulta": body.consulta, "n_candidatos_tras_filtros": int(len(ids_filtrados)), "resultados": resultados}


@app.get("/api/health")
def health():
    return {"status": "ok"}
