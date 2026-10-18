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
   evidencias: KMeans, k entre 3 y 6 = mayor silueta entre los k estables (ARI >= 0,9, la misma
   regla que los patrones globales; DEC-061). La etiqueta sale del centroide (rasgos muy altos,
   altos y bajos frente al resto de la dimensión). Sobre estas variables (pocas, continuas o
   discretas) KMeans separa roles mejor que el clustering espectral, que dejaba un grupo "típico"
   con el 75 % de las personas.
   Proporciones (DEC-061): las de tipo "parte de" (casos / total) se estiman con contracción
   bayesiana empírica beta-binomial, (casos + a) / (total + a + b), con a y b ajustados por máxima
   verosimilitud en el ámbito: sin denominador quedan en la media del grupo (neutral, no penaliza a
   quien no tiene publicaciones) y con pocos casos se suavizan (1 de 1 no es 100 %). Las tasas
   ("por" materia, tesis, curso, cargo) sin denominador toman la media de quienes sí lo tienen.

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
ARI_MINIMO_PATRON = 0.9   # mismo umbral de estabilidad que los patrones globales (perfil_conjunto)
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


def es_tasa(texto: str) -> bool:
    """Tasas ("por" materia, tesis, curso, cargo): no son una parte de un total, van en log."""
    return texto.startswith(("Horas por", "Estudiantes por", "Funciones adicionales por"))


def ajustar_beta_binomial(casos: np.ndarray, totales: np.ndarray) -> tuple[float, float]:
    """(a, b) de una Beta(a, b) por máxima verosimilitud beta-binomial con quienes tienen total > 0.
    Con menos de 5 personas o si no converge, método de momentos; en último caso Beta(1, 1)."""
    from scipy.optimize import minimize
    from scipy.special import betaln

    m = totales > 0
    k, n = casos[m].astype(float), totales[m].astype(float)
    if len(k) >= 5:
        def nll(t):
            a, b = np.exp(t)
            return -np.sum(betaln(k + a, n - k + b) - betaln(a, b))
        r = minimize(nll, x0=np.log([1.0, 1.0]), method="Nelder-Mead")
        a, b = np.exp(r.x)
        if r.success and np.isfinite([a, b]).all() and 1e-3 < a < 1e4 and 1e-3 < b < 1e4:
            return float(a), float(b)
    if len(k) >= 2:
        p = k / n
        media, var = p.mean(), p.var()
        if 0 < media < 1 and 0 < var < media * (1 - media):
            total = media * (1 - media) / var - 1
            return float(media * total), float((1 - media) * total)
    return 1.0, 1.0


def variables_patron(dimension: str, comp: pd.DataFrame, contraccion: dict | None = None) -> tuple[pd.DataFrame, dict[str, str]]:
    """Componentes de la dimensión + sus proporciones (conteos reales, no log). Devuelve las
    variables y {variable: descripción}. Las proporciones "parte de" se contraen hacia la media del
    grupo (beta-binomial, DEC-061) y las tasas sin denominador toman la media de quienes lo tienen;
    `contraccion`, si se pasa, recibe {variable: {a, b, media_previa, sin_denominador}}."""
    cfg = DIMENSIONES[dimension]
    cols = [f"{dimension}__{c}" for c in cfg["componentes"]]
    x = comp[cols].copy()
    desc = {c: cfg["componentes"][c.split("__", 1)[1]][1] for c in cols}
    for num, den, texto in PROPORCIONES.get(dimension, []):
        n_ = np.expm1(comp[f"{dimension}__{num}"]).round().to_numpy()
        d_ = np.expm1(comp[f"{dimension}__{den}"]).round().to_numpy()
        col = f"{dimension}__prop_{num}_{den}"
        if es_tasa(texto):
            tasa = np.where(d_ > 0, n_ / np.where(d_ > 0, d_, 1), np.nan)
            media = float(np.nanmean(tasa)) if (d_ > 0).any() else 0.0
            x[col] = np.log1p(np.where(d_ > 0, tasa, media))
            texto += " (log)"
            info = {"media_sin_denominador": round(media, 4)}
        else:
            a, b = ajustar_beta_binomial(n_, d_)
            x[col] = (n_ + a) / (d_ + a + b)
            info = {"a": round(a, 4), "b": round(b, 4), "media_previa": round(a / (a + b), 4)}
        if contraccion is not None:
            contraccion[col.split("__", 1)[1]] = {**info, "sin_denominador": int((d_ == 0).sum())}
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


def temas_dimension(e: pd.DataFrame, pos_tema: dict, vec_tema: np.ndarray, vigentes: set) -> dict | None:
    """`e`: evidencias de UNA dimensión de las personas del ámbito (columna `tema`). Devuelve
    {proporciones, resumen, mapa, evidencias (tema de cada evidencia y si se asignó por cercanía),
    embedding (por persona: promedio de los de sus evidencias, normalizado)}."""
    e = e.dropna(subset=["tema"])
    textos = np.array(sorted(e["tema"].unique()))
    res = descubrir_temas(textos, vec_tema[[pos_tema[clave_texto(t)] for t in textos]])
    if res is None:
        return None
    tema_de = dict(zip(textos, res["etiquetas"]))
    cercania_de = dict(zip(textos, res["por_cercania"]))
    e = e.assign(tema_id=e["tema"].map(tema_de), por_cercania=e["tema"].map(cercania_de).astype(bool))
    prop = (e.groupby(["persona_id", "tema_id"]).size() / e.groupby("persona_id").size()).rename("proporcion").reset_index()
    prop["dominante"] = prop["proporcion"] == prop.groupby("persona_id")["proporcion"].transform("max")
    # mapa: embedding de tema de cada persona = promedio de los de sus evidencias de la dimensión
    vec_texto = vec_tema[[pos_tema[clave_texto(t)] for t in textos]]
    fila_texto = {t: i for i, t in enumerate(textos)}
    personas_mapa = np.array(sorted(e["persona_id"].unique()))
    emb_persona = np.vstack([vec_texto[[fila_texto[t] for t in g]].mean(axis=0)
                             for _, g in e.groupby("persona_id")["tema"]])
    emb_persona = emb_persona / np.linalg.norm(emb_persona, axis=1, keepdims=True)
    xy = mapa_tsne(emb_persona)
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
    evid = e[["evidencia_id", "persona_id", "tema_id", "por_cercania"]].reset_index(drop=True)
    return {"proporciones": prop, "resumen": resumen, "mapa": mapa, "evidencias": evid,
            "embedding": pd.DataFrame({"persona_id": personas_mapa, "vector": list(emb_persona.astype(np.float32))})}


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
    """k entre K_MIN_PATRON y K_MAX_PATRON sin grupos de menos del 3 % (>= 10): mayor silueta entre
    los k ESTABLES (ARI por submuestreo >= ARI_MINIMO_PATRON); si ninguno lo es, el más estable.
    Misma regla que los patrones globales (DEC-057); con solo la silueta, Reconocimientos elegía
    un k inestable (ARI 0,75 en docentes, DEC-061)."""
    from sklearn.metrics import silhouette_score
    minimo = max(10, int(0.03 * len(z)))
    tabla = []
    for k in range(K_MIN_PATRON, min(K_MAX_PATRON, len(z) // minimo) + 1):
        lab = _kmeans(z, k).labels_
        tabla.append({"k": k, "silueta": round(float(silhouette_score(z, lab)), 4), "tamano_minimo": int(np.bincount(lab).min()),
                      "estabilidad_ari": round(_estabilidad_kmeans(z, lab, k), 3)})
    validos = [t for t in tabla if t["tamano_minimo"] >= minimo] or tabla
    estables = [t for t in validos if t["estabilidad_ari"] >= ARI_MINIMO_PATRON]
    k = (max(estables, key=lambda t: t["silueta"]) if estables else max(validos, key=lambda t: t["estabilidad_ari"]))["k"]
    return k, {"k_elegido": k, "criterio": f"mayor silueta (KMeans) entre los k con estabilidad ARI >= {ARI_MINIMO_PATRON} "
                                           f"y grupos de al menos {minimo} personas", "tabla": tabla}


def _estabilidad_kmeans(z: np.ndarray, lab: np.ndarray, k: int) -> float:
    from sklearn.metrics import adjusted_rand_score
    rng = np.random.default_rng(SEMILLA)
    aris = []
    for i in range(cl.N_SUBMUESTRAS):
        idx = np.sort(rng.choice(len(z), size=int(len(z) * cl.FRACCION_SUBMUESTRA), replace=False))
        aris.append(adjusted_rand_score(lab[idx], _kmeans(z[idx], k, SEMILLA + i + 1).labels_))
    return float(np.mean(aris))


def patrones_dimension(dimension: str, ids: np.ndarray, comp_todo: pd.DataFrame, vigente: np.ndarray,
                       espacio: dict | None = None) -> tuple[pd.DataFrame, dict] | None:
    """KMeans sobre los componentes y proporciones estandarizados. Afinidad derivada con cada patrón
    = inverso del cuadrado de la distancia al centroide, normalizado (no es probabilidad).
    `espacio`, si se pasa, recibe la matriz estandarizada ("z", alineada con `ids`) para las
    personas parecidas por dimensión."""
    contraccion: dict = {}
    comp, descripciones = variables_patron(dimension, comp_todo, contraccion)
    desv = comp.std()
    z = ((comp - comp.mean()) / desv.where(desv > 0, 1)).loc[:, desv > 0]
    if len(ids) < MIN_PERSONAS or z.shape[1] == 0:
        return None
    zz = z.to_numpy()
    if espacio is not None:
        espacio["z"] = zz
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
    # nombre corto que se cumple para TODAS las personas del patrón (DEC-063)
    from perfiles.nombres_patrones import nombrar
    nombres = nombrar(dimension, comp_todo, list(DIMENSIONES[dimension]["componentes"]), lab)
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
        fichas.append({"id": c, "nombre": nombres[c]["nombre"], "nombre_distingue": nombres[c]["distingue"],
                       "etiqueta": _etiqueta_patron(componentes), "tamano": int(m.sum()),
                       "tamano_vigentes": int(vigente[m].sum()), "proporcion": round(float(m.mean()), 3),
                       "representante_id": int(ids[reps[c]]) if reps[c] >= 0 else None, "componentes": componentes})
    xy = mapa_tsne(zz)
    personas["x"], personas["y"] = xy[:, 0], xy[:, 1]
    estab = next(t["estabilidad_ari"] for t in seleccion["tabla"] if t["k"] == k)
    return personas, {"k": k, "metodo": "KMeans sobre variables estandarizadas", "seleccion_k": seleccion,
                      "estabilidad_ari": estab, "perfiles_mixtos": int(personas["mixto"].sum()),
                      "contraccion_proporciones": contraccion, "patrones": fichas}


# ------------------------------------------------------------------ ámbito
def construir_ambito(ids_ambito: np.ndarray, vigente: np.ndarray, comp_crudo: pd.DataFrame, n_ev: pd.DataFrame,
                     ev_dim: pd.DataFrame, pos_tema: dict, vec_tema: np.ndarray, ultimas: pd.DataFrame | None = None) -> dict:
    """Microarquetipos por dimensión de un ámbito. Devuelve {temas (proporción por persona),
    patrones (patrón por persona), mapas (t-SNE, solo para visualizar: `patrones` sobre las
    variables de los patrones; `temas` sobre el promedio de los embeddings de tema), resumen (por
    dimensión), temas_evidencia (tema de cada evidencia y si se asignó por cercanía), vecinos
    (personas parecidas por dimensión, ver `vecinos_dimension`)}. `ultimas`: salida de
    `dimensiones.ultima_evidencia` (desempate de los vecinos)."""
    from perfiles import vecinos_dimension as vd

    vig = dict(zip(ids_ambito, vigente))
    vigentes = {p for p, v in vig.items() if v}
    en_ambito = ev_dim[ev_dim["persona_id"].isin(vig)]
    ult = {} if ultimas is None else {d: dict(zip(g["persona_id"], g["ultima_evidencia"])) for d, g in ultimas.groupby("dimension")}
    temas, patrones, mapas, temas_ev, vecinos, resumen = [], [], [], [], [], {}
    for d, cfg in DIMENSIONES.items():
        ids = np.array([p for p in ids_ambito if n_ev.at[p, d] > 0])
        r = {"nombre": cfg["nombre"], "n_personas": int(len(ids))}
        e_d = en_ambito[en_ambito["dimension"] == d]
        t = temas_dimension(e_d, pos_tema, vec_tema, vigentes) if len(ids) >= MIN_PERSONAS else None
        if t:
            temas.append(t["proporciones"].assign(dimension=d))
            mapas.append(t["mapa"].assign(dimension=d, mapa="temas"))
            temas_ev.append(t["evidencias"].assign(dimension=d))
        r["temas"] = t["resumen"] if t else None
        espacio: dict = {}
        p = patrones_dimension(d, ids, comp_crudo.loc[ids], np.array([bool(vig[x]) for x in ids]), espacio) if len(ids) else None
        if p:
            patrones.append(p[0].drop(columns=["x", "y"]).assign(dimension=d))
            mapas.append(p[0][["persona_id", "x", "y"]].assign(dimension=d, mapa="patrones"))
        r["patrones"] = p[1] if p else None
        if not t and not p:
            r["nota"] = f"menos de {MIN_PERSONAS} personas con evidencias: no se subdivide"
        elif len(ids) >= MIN_PERSONAS:
            con_tema = e_d.dropna(subset=["tema"])
            textos = {q: list(dict.fromkeys(g)) for q, g in con_tema.groupby("persona_id")["tema"]}
            vec_texto = {x: vec_tema[pos_tema[clave_texto(x)]] for x in con_tema["tema"].unique() if clave_texto(x) in pos_tema}
            textos = {q: [x for x in xs if x in vec_texto] for q, xs in textos.items()}
            idiomas = None
            if d == "idiomas":
                idiomas = {}
                for q, a in zip(e_d["persona_id"], e_d["atributos"]):
                    nombre = json.loads(a).get("idioma")
                    if nombre and nombre != "ESPAÑOL":
                        idiomas[q] = idiomas.get(q, frozenset()) | {nombre}
            emb = dict(zip(t["embedding"]["persona_id"], t["embedding"]["vector"])) if t else {}
            prop = {}
            if t:
                for q, tema, v in zip(t["proporciones"]["persona_id"], t["proporciones"]["tema_id"], t["proporciones"]["proporcion"]):
                    prop.setdefault(q, {})[int(tema)] = float(v)
            vecinos.append(vd.construir_dimension(d, ids, espacio.get("z"), emb, ult.get(d, {}), prop, textos, vec_texto, idiomas))
        resumen[d] = r
    junta = lambda xs: pd.concat([x for x in xs if len(x)], ignore_index=True) if any(len(x) for x in xs) else pd.DataFrame()  # noqa: E731
    return {"temas": junta(temas), "patrones": junta(patrones), "mapas": junta(mapas), "resumen": resumen,
            "temas_evidencia": junta(temas_ev), "vecinos": junta(vecinos)}
