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


def df_to_records(df: pd.DataFrame) -> list[dict]:
    return df.replace({np.nan: None}).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Carga de datos (cacheada en proceso, igual que @st.cache_data en Streamlit)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def get_personas() -> pd.DataFrame:
    return lib.load_personas_dashboard()


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
def get_eventos_trayectoria() -> pd.DataFrame:
    return lib.load_eventos_trayectoria()


@lru_cache(maxsize=1)
def get_corpus() -> pd.DataFrame:
    return lib.load_corpus_texto()


@lru_cache(maxsize=1)
def get_documento_semantico() -> pd.DataFrame:
    return lib.load_documento_semantico()


@lru_cache(maxsize=1)
def get_embeddings():
    return lib.load_embeddings()


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

    muestra_cols = ["IDPERSONA"] + [c for c in lib.METRICAS_CLAVE if c in personas.columns]
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
def mapa(tipo: str = Query("Todos"), perfiles: str = Query("")):
    personas = get_personas()
    pca_df = get_pca().merge(
        personas[["IDPERSONA", "CLUSTER", "PERFIL_NOMBRE", "TIPOEMPLEADO_ACTUAL_DESC",
                  "VIGENTE_MOSTRAR", "CARGO_ACTUAL"]],
        on="IDPERSONA", how="inner",
    )
    pca_df = pca_df[pca_df["CLUSTER"] != -1]
    if tipo == "Solo Administrativo":
        pca_df = pca_df[pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "ADMINISTRATIVO"]
    elif tipo == "Solo Docente":
        pca_df = pca_df[pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "DOCENTE"]
    if perfiles:
        ids_perfiles = {int(p) for p in perfiles.split(",") if p}
        pca_df = pca_df[pca_df["CLUSTER"].isin(ids_perfiles)]

    pca_df = pca_df.sort_values("CLUSTER")
    puntos = df_to_records(pca_df)
    for p in puntos:
        p["COLOR"] = cluster_color(p["CLUSTER"])
    return {"total_modelo": int(len(personas)), "n_mostrados": len(puntos), "puntos": puntos}


@app.get("/api/personas")
def listar_personas():
    personas = get_personas()
    return {"ids": personas["IDPERSONA"].sort_values().tolist()}


@app.get("/api/personas/{id_persona}")
def persona_ficha(id_persona: int):
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

    persona_dict = fila.replace({np.nan: None}).iloc[0].to_dict()

    return {
        "persona": persona_dict,
        "tiene_perfil": bool(tiene_perfil),
        "motivo_sin_perfil": motivo,
        "eventos_trayectoria": df_to_records(eventos_persona),
        "secciones": secciones,
        "radar": radar,
        "cluster_descripcion": cluster_descripcion,
        "corpus_muestra": corpus_muestra,
        "n_textos": int(n_textos) if pd.notna(n_textos) else 0,
        "color_tipo_evento": lib.COLOR_TIPO_EVENTO,
        "etiqueta_tipo_evento": lib.ETIQUETA_TIPO_EVENTO,
    }


@app.get("/api/equipos")
def equipos(
    perfiles: str = Query(""),
    vigencia: str = Query("Cualquiera"),
    tipo: str = Query(""),
    nivel: str = Query(""),
    min_publicaciones: int = Query(0),
    min_exp_admin: float = Query(0.0),
):
    personas = get_personas()
    resultado = personas
    if perfiles:
        ids_perfiles = {int(p) for p in perfiles.split(",") if p}
        resultado = resultado[resultado["CLUSTER"].isin(ids_perfiles)]
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

    cols_out = ["IDPERSONA"] + [c for c in lib.METRICAS_CLAVE if c in resultado.columns]
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


@app.post("/api/buscar")
def buscar(body: BusquedaSemantica):
    if not body.consulta.strip():
        raise HTTPException(400, "Consulta vacía")

    ids, matrix = get_embeddings()
    modelo = get_text_model()
    q = modelo.encode([f"query: {body.consulta}"], normalize_embeddings=True)[0]
    sims = matrix @ q
    top_idx = np.argsort(-sims)[: body.top_n]

    personas = get_personas()
    documentos = get_documento_semantico().set_index("IDPERSONA")["DOCUMENTO_TEXTO"]

    resultados = []
    for rango, idx in enumerate(top_idx, start=1):
        idp = int(ids[idx])
        fila = personas[personas["IDPERSONA"] == idp]
        if fila.empty:
            continue
        p = fila.iloc[0]
        resultados.append({
            "rango": rango,
            "id_persona": idp,
            "cluster": None if pd.isna(p.get("CLUSTER")) else int(p.get("CLUSTER")),
            "perfil_nombre": p.get("PERFIL_NOMBRE") if pd.notna(p.get("PERFIL_NOMBRE")) else None,
            "tipo_empleado": p.get("TIPOEMPLEADO_ACTUAL_DESC") if pd.notna(p.get("TIPOEMPLEADO_ACTUAL_DESC")) else None,
            "cargo_actual": p.get("CARGO_ACTUAL") if pd.notna(p.get("CARGO_ACTUAL")) else None,
            "evidencia": _mejor_evidencia(body.consulta, documentos.get(idp, "")),
        })

    return {"consulta": body.consulta, "resultados": resultados}


@app.get("/api/health")
def health():
    return {"status": "ok"}
