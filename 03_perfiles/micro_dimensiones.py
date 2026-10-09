"""Microarquetipos DENTRO de cada dimensión de evidencia (capa 2, DEC-055).

Nada está predefinido (decisión de la usuaria): ni temas, ni roles, ni su número. En cada ámbito y
dimensión se descubren dos facetas, cada una con su método:

1. **Temas** (de qué trata la evidencia). Se agrupan las EVIDENCIAS, no las personas, porque una
   persona trabaja varios temas y promediarlos los diluye. Procedimiento tipo BERTopic:
   - texto de tema = título/nombre/materia de la evidencia, sin metadatos (`dimensiones.texto_tema`),
     embebido con bge-m3 (`data/perfiles/embeddings_tema/`);
   - UMAP a 5 dimensiones (coseno) y HDBSCAN, que decide cuántos temas hay; tamaño mínimo de tema
     = 0,5 % de los textos (al menos 10);
   - las evidencias que HDBSCAN deja como ruido se asignan al tema de centroide más cercano (coseno
     en el espacio original) y quedan marcadas;
   - nombre del tema = términos distintivos (c-TF-IDF) de sus textos.
   La persona recibe la proporción de sus evidencias de la dimensión en cada tema (suma 1).
2. **Patrones de actividad** (cómo participa). Se agrupan las PERSONAS con los componentes de la
   dimensión (`dimensiones.DIMENSIONES`) y proporciones que no dependen del volumen
   (`PROPORCIONES`, p. ej. qué parte de sus proyectos dirige), estandarizados entre quienes tienen
   evidencias: KMeans, k entre 3 y 6 por mayor silueta. La etiqueta sale del centroide (rasgos muy
   altos, altos y bajos frente al resto de la dimensión). Sobre estas variables (pocas, continuas o
   discretas) KMeans separa roles mejor que el clustering espectral, que dejaba un grupo "típico"
   con el 75 % de las personas.

Con menos de `MIN_PERSONAS` personas con evidencias (o `MIN_TEXTOS` textos) no se subdivide.
"""
from __future__ import annotations

import json
import warnings

import numpy as np
import pandas as pd

from perfiles import clustering as cl
from perfiles import snf
from perfiles.dimensiones import DIMENSIONES
from perfiles.embeddings import clave_texto
from perfiles.interpretacion import terminos_distintivos

MIN_PERSONAS = 40
MIN_TEXTOS = 60
FRACCION_TEMA = 0.005
UMAP_DIM, UMAP_VECINOS = 5, 15
HDBSCAN_MIN_SAMPLES = 5
K_MIN_PATRON, K_MAX_PATRON = 3, 6
UMBRAL_Z = 0.4            # componente distintivo del patrón frente a la dimensión
SEMILLA = cl.SEMILLA

# Proporciones que describen CÓMO participa la persona sin depender del volumen (p. ej. qué parte
# de sus proyectos dirige). Solo son variables de entrada: los patrones los forma el clustering.
# dimensión -> [(numerador, denominador, descripción)] sobre los conteos de `componentes_crudos`.
PROPORCIONES = {
    "investigacion": [("proyectos_dirigidos", "proyectos", "Proporción de sus proyectos que dirige o codirige"),
                      ("publicaciones_q1q2", "publicaciones", "Proporción de sus publicaciones en Q1–Q2"),
                      ("publicaciones_autor", "publicaciones", "Proporción de sus publicaciones como autor (no coautor)")],
    "ponencias": [("ponencias_exterior", "ponencias", "Proporción de ponencias en el exterior")],
    "vinculacion": [("proyectos_dirigidos", "proyectos", "Proporción de proyectos o programas que dirige")],
    "tesis_dirigidas": [("tesis_investigacion_doctorado", "tesis", "Proporción de tesis de investigación o doctorado"),
                        ("estudiantes", "tesis", "Estudiantes por tesis")],
    "capacitacion": [("cursos_exterior", "cursos", "Proporción de capacitaciones en el exterior"),
                     ("horas", "cursos", "Horas por capacitación")],
    "certificaciones": [("vigentes", "certificaciones", "Proporción de certificaciones vigentes")],
    "reconocimientos": [("menciones_exterior", "menciones", "Proporción de menciones del exterior")],
    "experiencia_externa": [("exterior", "experiencias", "Proporción de experiencias en el exterior"),
                            ("academica", "experiencias", "Proporción de experiencias académicas")],
    "trayectoria_espol": [("funciones_adicionales", "cargos", "Funciones adicionales por cargo")],
    "docencia": [("estudiantes", "materias", "Estudiantes por materia")],
}


def variables_patron(dimension: str, comp: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Componentes de la dimensión + sus proporciones (conteos reales, no log). Devuelve las
    variables y {variable: descripción}."""
    cfg = DIMENSIONES[dimension]
    cols = [f"{dimension}__{c}" for c in cfg["componentes"]]
    x = comp[cols].copy()
    desc = {c: cfg["componentes"][c.split("__", 1)[1]][1] for c in cols}
    for num, den, texto in PROPORCIONES.get(dimension, []):
        n_ = np.expm1(comp[f"{dimension}__{num}"])
        d_ = np.expm1(comp[f"{dimension}__{den}"])
        col = f"{dimension}__prop_{num}_{den}"
        x[col] = np.where(d_ > 0, n_ / np.where(d_ > 0, d_, 1), 0.0)
        if texto.startswith(("Horas por", "Estudiantes por", "Funciones adicionales por")):
            x[col] = np.log1p(x[col])
            texto += " (log)"
        desc[col] = texto
    return x, desc


def _frase(desc: str) -> str:
    return desc.split(" (")[0].split(":")[0].lower()


def mapa_tsne(x: np.ndarray) -> np.ndarray:
    """Coordenadas 2D t-SNE SOLO para visualizar (no es el espacio donde se agrupa). Con más de 50
    columnas se reduce antes con PCA a 50."""
    from sklearn.decomposition import PCA
    from sklearn.manifold import TSNE

    x = np.asarray(x, dtype=np.float32)
    if x.shape[1] > 50:
        x = PCA(50, random_state=SEMILLA).fit_transform(x)
    perplejidad = float(min(30, max(5, (len(x) - 1) / 3)))
    return TSNE(n_components=2, perplexity=perplejidad, init="pca", learning_rate="auto",
                random_state=SEMILLA).fit_transform(x)


# ------------------------------------------------------------------ temas
def descubrir_temas(textos: np.ndarray, vectores: np.ndarray) -> dict | None:
    """Temas de un conjunto de textos únicos. Devuelve etiqueta por texto (todas asignadas), si fue
    asignada por cercanía, términos y tamaños; None si hay pocos textos."""
    import umap
    from sklearn.cluster import HDBSCAN

    n = len(textos)
    if n < MIN_TEXTOS:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        reducido = umap.UMAP(n_components=UMAP_DIM, n_neighbors=min(UMAP_VECINOS, n - 1), min_dist=0.0, metric="cosine",
                             random_state=SEMILLA).fit_transform(vectores)
    tam_min = max(10, int(round(n * FRACCION_TEMA)))
    lab = HDBSCAN(min_cluster_size=tam_min, min_samples=HDBSCAN_MIN_SAMPLES).fit_predict(reducido)
    k = int(lab.max()) + 1
    if k < 2:
        return None
    centroides = cl.centroides(vectores[lab >= 0], lab[lab >= 0], k)
    ruido = lab < 0
    if ruido.any():
        lab = lab.copy()
        lab[ruido] = np.argmax(vectores[ruido] @ centroides.T, axis=1)
    # orden por tamaño: Tema 1 = el más grande
    orden = np.argsort(-np.bincount(lab, minlength=k))
    nuevo = np.empty(k, dtype=int)
    nuevo[orden] = np.arange(k)
    lab = nuevo[lab]
    terminos = terminos_distintivos({j: list(textos[lab == j]) for j in range(k)}, n=8)
    return {"etiquetas": lab, "por_cercania": ruido, "k": k, "terminos": terminos, "tamano_minimo": tam_min,
            "proporcion_ruido": round(float(ruido.mean()), 3)}


def temas_dimension(e: pd.DataFrame, pos_tema: dict, vec_tema: np.ndarray, vigentes: set) -> tuple[pd.DataFrame, dict, pd.DataFrame] | None:
    """`e`: evidencias de UNA dimensión de las personas del ámbito (columna `tema`)."""
    e = e.dropna(subset=["tema"])
    textos = np.array(sorted(e["tema"].unique()))
    res = descubrir_temas(textos, vec_tema[[pos_tema[clave_texto(t)] for t in textos]])
    if res is None:
        return None
    tema_de = dict(zip(textos, res["etiquetas"]))
    e = e.assign(tema_id=e["tema"].map(tema_de))
    prop = (e.groupby(["persona_id", "tema_id"]).size() / e.groupby("persona_id").size()).rename("proporcion").reset_index()
    prop["dominante"] = prop["proporcion"] == prop.groupby("persona_id")["proporcion"].transform("max")
    # mapa: embedding de tema de cada persona = promedio de los de sus evidencias de la dimensión
    vec_texto = vec_tema[[pos_tema[clave_texto(t)] for t in textos]]
    fila_texto = {t: i for i, t in enumerate(textos)}
    personas_mapa = np.array(sorted(e["persona_id"].unique()))
    emb_persona = np.vstack([vec_texto[[fila_texto[t] for t in g]].mean(axis=0)
                             for _, g in e.groupby("persona_id")["tema"]])
    xy = mapa_tsne(emb_persona / np.linalg.norm(emb_persona, axis=1, keepdims=True))
    mapa = pd.DataFrame({"persona_id": personas_mapa, "x": xy[:, 0], "y": xy[:, 1]})
    fichas = []
    for j in range(res["k"]):
        ej = e[e["tema_id"] == j]
        personas = ej["persona_id"].unique()
        ejemplos = ej.groupby("tema")["persona_id"].nunique().sort_values(ascending=False).head(5)
        terms = res["terminos"].get(j, [])
        fichas.append({
            "id": j, "etiqueta": ", ".join(terms[:4]) if terms else f"Tema {j + 1}", "terminos_distintivos": terms,
            "n_textos": int((res["etiquetas"] == j).sum()), "n_evidencias": int(len(ej)), "n_personas": int(len(personas)),
            "n_personas_vigentes": int(sum(p in vigentes for p in personas)),
            "personas_dominante": int(prop[(prop["tema_id"] == j) & prop["dominante"]]["persona_id"].nunique()),
            "ejemplos": [{"texto": t, "personas": int(m)} for t, m in ejemplos.items()],
        })
    resumen = {"n_textos": len(textos), "k": res["k"], "tamano_minimo": res["tamano_minimo"],
               "proporcion_asignada_por_cercania": res["proporcion_ruido"], "temas": fichas}
    return prop, resumen, mapa


# ------------------------------------------------------------------ patrones de actividad
def _etiqueta_patron(componentes: list[dict], maximo: int = 2) -> str:
    """Rasgos del centroide frente al resto de la dimensión (z): muy alto (>= 1,5), alto
    (>= UMBRAL_Z) y bajo (<= -UMBRAL_Z), a lo sumo `maximo` por nivel, los más marcados primero."""
    niveles = {"Muy alto": [], "Alto": [], "Bajo": []}
    for x in sorted(componentes, key=lambda x: -abs(x["z"])):
        nivel = "Muy alto" if x["z"] >= 1.5 else "Alto" if x["z"] >= UMBRAL_Z else "Bajo" if x["z"] <= -UMBRAL_Z else None
        if nivel and len(niveles[nivel]) < maximo:
            niveles[nivel].append(_frase(x["descripcion"]))
    partes = [f"{n}: {', '.join(v)}" for n, v in niveles.items() if v]
    return " · ".join(partes) if partes else "Nivel típico en todo"


def _kmeans(z: np.ndarray, k: int, semilla: int = SEMILLA):
    from sklearn.cluster import KMeans
    return KMeans(k, n_init=10, random_state=semilla).fit(z)


def _seleccionar_k_patron(z: np.ndarray) -> tuple[int, dict]:
    """k entre K_MIN_PATRON y K_MAX_PATRON con mayor silueta, sin grupos de menos del 3 % (>= 10)."""
    from sklearn.metrics import silhouette_score
    minimo = max(10, int(0.03 * len(z)))
    tabla = []
    for k in range(K_MIN_PATRON, min(K_MAX_PATRON, len(z) // minimo) + 1):
        lab = _kmeans(z, k).labels_
        tabla.append({"k": k, "silueta": round(float(silhouette_score(z, lab)), 4), "tamano_minimo": int(np.bincount(lab).min())})
    validos = [t for t in tabla if t["tamano_minimo"] >= minimo] or tabla
    k = max(validos, key=lambda t: t["silueta"])["k"]
    return k, {"k_elegido": k, "criterio": f"mayor silueta (KMeans) con grupos de al menos {minimo} personas", "tabla": tabla}


def _estabilidad_kmeans(z: np.ndarray, lab: np.ndarray, k: int) -> float:
    from sklearn.metrics import adjusted_rand_score
    rng = np.random.default_rng(SEMILLA)
    aris = []
    for i in range(cl.N_SUBMUESTRAS):
        idx = np.sort(rng.choice(len(z), size=int(len(z) * cl.FRACCION_SUBMUESTRA), replace=False))
        aris.append(adjusted_rand_score(lab[idx], _kmeans(z[idx], k, SEMILLA + i + 1).labels_))
    return float(np.mean(aris))


def patrones_dimension(dimension: str, ids: np.ndarray, comp_todo: pd.DataFrame, vigente: np.ndarray) -> tuple[pd.DataFrame, dict] | None:
    """KMeans sobre los componentes y proporciones estandarizados. Afinidad derivada con cada patrón
    = inverso del cuadrado de la distancia al centroide, normalizado (no es probabilidad)."""
    comp, descripciones = variables_patron(dimension, comp_todo)
    desv = comp.std()
    z = ((comp - comp.mean()) / desv.where(desv > 0, 1)).loc[:, desv > 0]
    if len(ids) < MIN_PERSONAS or z.shape[1] == 0:
        return None
    zz = z.to_numpy()
    k, seleccion = _seleccionar_k_patron(zz)
    modelo = _kmeans(zz, k)
    # numeración por tamaño: Patrón 1 = el más grande
    renum = np.empty(k, dtype=int)
    renum[np.argsort(-np.bincount(modelo.labels_, minlength=k))] = np.arange(k)
    lab = renum[modelo.labels_]
    centros = np.empty_like(modelo.cluster_centers_)
    centros[renum] = modelo.cluster_centers_
    dist2 = ((zz[:, None, :] - centros[None, :, :]) ** 2).sum(axis=2)
    inv = 1.0 / np.maximum(dist2, 1e-6)
    memb = inv / inv.sum(axis=1, keepdims=True)
    cl.validar_afinidades(memb)
    fila = np.arange(len(ids))
    orden = np.argsort(-memb, axis=1)
    segunda = memb[fila, orden[:, 1]]
    # representante: el vigente más cercano al centroide de su patrón
    reps = np.full(k, -1)
    for c in range(k):
        cand = np.flatnonzero((lab == c) & vigente)
        if len(cand):
            reps[c] = cand[np.argmin(dist2[cand, c])]
    # similitud con el representante: 1 - distancia / distancia máxima dentro del patrón (1 = él mismo)
    similitud = np.full(len(ids), np.nan)
    for c in range(k):
        if reps[c] < 0:
            continue
        miembros = np.flatnonzero(lab == c)
        dd = np.linalg.norm(zz[miembros] - zz[reps[c]], axis=1)
        similitud[miembros] = 1.0 - dd / dd.max() if dd.max() > 0 else 1.0
    personas = pd.DataFrame({
        "persona_id": ids, "patron": lab, "afinidad_1": memb[fila, lab], "patron_2": orden[:, 1], "afinidad_2": segunda,
        "similitud_representante": similitud,
        "mixto": segunda >= cl.UMBRAL_MIXTO * memb[fila, orden[:, 0]], "es_representante": np.isin(fila, reps),
        "afinidades": [json.dumps([round(float(v), 4) for v in fila_m]) for fila_m in memb],
    })
    fichas = []
    for c in range(k):
        m = lab == c
        componentes = []
        for j, col in enumerate(z.columns):
            desc = descripciones[col]
            media = comp.loc[m, col].mean()
            componentes.append({"componente": col.split("__", 1)[1], "descripcion": desc, "z": round(float(centros[c, j]), 2),
                                "media_grupo": round(float(np.expm1(media) if "(log" in desc else media), 2)})
        componentes.sort(key=lambda x: -x["z"])
        fichas.append({"id": c, "etiqueta": _etiqueta_patron(componentes), "tamano": int(m.sum()),
                       "tamano_vigentes": int(vigente[m].sum()), "proporcion": round(float(m.mean()), 3),
                       "representante_id": int(ids[reps[c]]) if reps[c] >= 0 else None, "componentes": componentes})
    xy = mapa_tsne(zz)
    personas["x"], personas["y"] = xy[:, 0], xy[:, 1]
    return personas, {"k": k, "metodo": "KMeans sobre variables estandarizadas", "seleccion_k": seleccion,
                      "estabilidad_ari": round(_estabilidad_kmeans(zz, lab, k), 3),
                      "perfiles_mixtos": int(personas["mixto"].sum()), "patrones": fichas}


# ------------------------------------------------------------------ ámbito
def construir_ambito(ids_ambito: np.ndarray, vigente: np.ndarray, comp_crudo: pd.DataFrame, n_ev: pd.DataFrame,
                     ev_dim: pd.DataFrame, pos_tema: dict, vec_tema: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """(temas por persona, patrón por persona, mapas t-SNE, resumen por dimensión) de un ámbito.
    Mapas: `patrones` sobre las variables de los patrones; `temas` sobre el promedio de los
    embeddings de tema de las evidencias de la persona. Solo para visualizar."""
    vig = dict(zip(ids_ambito, vigente))
    vigentes = {p for p, v in vig.items() if v}
    en_ambito = ev_dim[ev_dim["persona_id"].isin(vig)]
    temas, patrones, mapas, resumen = [], [], [], {}
    for d, cfg in DIMENSIONES.items():
        ids = np.array([p for p in ids_ambito if n_ev.at[p, d] > 0])
        r = {"nombre": cfg["nombre"], "n_personas": int(len(ids))}
        t = temas_dimension(en_ambito[en_ambito["dimension"] == d], pos_tema, vec_tema, vigentes) if len(ids) >= MIN_PERSONAS else None
        if t:
            temas.append(t[0].assign(dimension=d))
            mapas.append(t[2].assign(dimension=d, mapa="temas"))
        r["temas"] = t[1] if t else None
        p = patrones_dimension(d, ids, comp_crudo.loc[ids], np.array([bool(vig[x]) for x in ids])) if len(ids) else None
        if p:
            patrones.append(p[0].drop(columns=["x", "y"]).assign(dimension=d))
            mapas.append(p[0][["persona_id", "x", "y"]].assign(dimension=d, mapa="patrones"))
        r["patrones"] = p[1] if p else None
        if not t and not p:
            r["nota"] = f"menos de {MIN_PERSONAS} personas con evidencias: no se subdivide"
        resumen[d] = r
    junta = lambda xs: pd.concat(xs, ignore_index=True) if xs else pd.DataFrame()  # noqa: E731
    return junta(temas), junta(patrones), junta(mapas), resumen
