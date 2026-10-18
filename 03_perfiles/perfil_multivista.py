"""Perfil completo multivista con NEMO (DEC-062; reemplaza el método de DEC-056/057/058).

Une en una red de similitud entre personas CÓMO participan y DE QUÉ trata su evidencia:

- **Vistas.** Actividad: el vector de las 12 dimensiones (afinidades con sus patrones x
  intensidad, `perfil_conjunto.vectores`). Contenido: el promedio de los embeddings de tema
  (bge-m3) de sus evidencias en cuatro bloques (`BLOQUES`): académico, docencia, formación y
  desarrollo, trayectoria.
- **Red NEMO** (Rappoport y Shamir, 2019). Por vista, afinidad gaussiana con escala local (la de
  SNF) restringida a los K vecinos y normalizada por fila; la similitud de un par es el promedio
  de sus afinidades en las vistas que AMBOS tienen. Quien no tiene evidencias de un bloque no
  recibe un contenido inventado: esa vista simplemente no cuenta para sus pares (no se penaliza la
  falta de información; la ausencia ya queda en la vista de actividad).
- **Personas parecidas** (lo principal): los N_VECINOS con mayor similitud en la red, con las
  vistas en que son vecinas (para explicar en qué se parecen). Sin puntajes en la interfaz.
- **Perfiles amplios**: agrupamiento espectral de la red, k por eigengap entre K_MIN y K_MAX, con
  su estabilidad (ARI por submuestreo). Son orientación: los datos son casi continuos (ver
  simulaciones de DEC-062); no se fuerzan grupos pequeños ni microarquetipos.
- **Microarquetipos** (pedido de la usuaria): cada perfil amplio con al menos MIN_SUBDIVIDIR
  personas se subdivide recalculando la red NEMO SOLO con sus integrantes (escalas locales) y
  agrupando de nuevo, k entre K_MIN_MICRO y K_MAX_MICRO: entre los k estables (ARI >= ARI_MINIMO)
  el de mayor eigengap; si ninguno es estable, el más estable (misma regla que DEC-058). Se describen
  frente a su perfil amplio y se informa su estabilidad: con ARI < ARI_MINIMO son orientativos.
- **Mapa**: t-SNE sobre la distancia de la red, solo para visualizar.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from perfiles import clustering as cl
from perfiles import perfil_conjunto as pc
from perfiles import snf
from perfiles.embeddings import clave_texto

K_VECINOS_RED = 20
N_VECINOS = 15
K_MIN, K_MAX = 4, 8
MIN_SUBDIVIDIR = 60
K_MIN_MICRO, K_MAX_MICRO = 2, 5
ARI_MINIMO = 0.9
BLOQUES = {
    "academico": ["investigacion", "ponencias", "tesis_dirigidas", "vinculacion", "reconocimientos"],
    "docencia": ["docencia"],
    "formacion": ["formacion", "capacitacion", "certificaciones"],
    "trayectoria": ["trayectoria_espol", "experiencia_externa"],
}
NOMBRES_VISTAS = {"actividad": "Cómo participa", "academico": "Contenido académico", "docencia": "Materias que dicta",
                  "formacion": "Formación y desarrollo", "trayectoria": "Trayectoria laboral"}


def _knn_normalizada(w: np.ndarray, k: int) -> np.ndarray:
    n = w.shape[0]
    k = min(k, n - 1)
    w = w.copy()
    np.fill_diagonal(w, 0)
    idx = np.argpartition(-w, kth=k - 1, axis=1)[:, :k]
    a = np.zeros_like(w)
    filas = np.repeat(np.arange(n), k)
    a[filas, idx.ravel()] = w[filas, idx.ravel()]
    a /= np.maximum(a.sum(axis=1, keepdims=True), 1e-12)
    return (a + a.T) / 2


def _afinidad(x: np.ndarray, k: int) -> np.ndarray:
    return snf.afinidad(snf.distancias(x), min(k, len(x) - 1), 0.5)


def contenido_por_bloque(ids: np.ndarray, ev_dim: pd.DataFrame, pos_tema: dict, vec_tema: np.ndarray) -> tuple[dict, dict]:
    """(vectores por bloque n x dim, normalizados; máscara de quién tiene el bloque)."""
    pos_id = {p: i for i, p in enumerate(ids)}
    e = ev_dim[ev_dim["persona_id"].isin(pos_id)].dropna(subset=["tema"])
    e = e.assign(fila=e["tema"].map(lambda t: pos_tema.get(clave_texto(t)))).dropna(subset=["fila"])
    contenido, presente = {}, {}
    for b, dims in BLOQUES.items():
        m = np.zeros((len(ids), vec_tema.shape[1]), np.float32)
        tiene = np.zeros(len(ids), bool)
        for p, filas in e[e["dimension"].isin(dims)].groupby("persona_id")["fila"]:
            v = vec_tema[filas.astype(int).to_numpy()].mean(axis=0)
            m[pos_id[p]] = v / np.linalg.norm(v)
            tiene[pos_id[p]] = True
        contenido[b], presente[b] = m, tiene
    return contenido, presente


def red_nemo(act: np.ndarray, contenido: dict, presente: dict, k: int = K_VECINOS_RED) -> tuple[np.ndarray, dict]:
    """(red fusionada n x n, {vista: matriz booleana de vecindad}) para explicar los vecinos."""
    a = _knn_normalizada(_afinidad(act, k), k)
    suma, cuenta = a.copy(), np.ones_like(a)
    vecindad = {"actividad": a > 0}
    for b in contenido:
        t = np.flatnonzero(presente[b])
        if len(t) < 5:
            continue
        wb = _knn_normalizada(_afinidad(contenido[b][t], k), k)
        suma[np.ix_(t, t)] += wb
        cuenta[np.ix_(t, t)] += 1
        v = np.zeros_like(a, dtype=bool)
        v[np.ix_(t, t)] = wb > 0
        vecindad[b] = v
    w = suma / cuenta
    np.fill_diagonal(w, 0)
    return w, vecindad


def _temas_distintivos(mascara: np.ndarray, ids: np.ndarray, temas: pd.DataFrame, etiquetas: dict, n: int = 4,
                       referencia: np.ndarray | None = None) -> list[dict]:
    """Temas mucho más frecuentes en el grupo que en la referencia (por defecto el ámbito): lift >= 1,5
    y presentes en >= 15 % del grupo."""
    ref = ids if referencia is None else ids[referencia]
    base = temas[temas["persona_id"].isin(set(ref))].groupby(["dimension", "tema_id"])["persona_id"].nunique() / len(ref)
    g = temas[temas["persona_id"].isin(set(ids[mascara]))]
    prop = g.groupby(["dimension", "tema_id"])["persona_id"].nunique() / max(int(mascara.sum()), 1)
    lift = (prop / base).dropna()
    lift = lift[(prop.reindex(lift.index) >= 0.15) & (lift >= 1.5)].sort_values(ascending=False)
    return [{"dimension": d, "tema": int(t), "etiqueta": etiquetas.get((d, int(t)), f"Tema {int(t) + 1}"),
             "proporcion": round(float(prop[(d, t)]), 3), "lift": round(float(lift[(d, t)]), 2)} for d, t in lift.index[:n]]


def _similitud_con_representante(w: np.ndarray, lab: np.ndarray, reps: np.ndarray) -> np.ndarray:
    """1 - d(persona, representante) / d máxima dentro del grupo (1 = la representante; 0 = la más
    distinta), con d medida en el EMBEDDING ESPECTRAL de la red. La afinidad directa no sirve: la red
    solo conecta a cada persona con sus K vecinos, así que casi todos los pares tienen afinidad 0 y
    quedaban en 0 % aunque estuvieran cerca a través de la red (62-80 % de las personas)."""
    from sklearn.manifold import SpectralEmbedding

    n_comp = int(min(10, len(w) - 2))
    y = SpectralEmbedding(n_components=n_comp, affinity="precomputed", random_state=cl.SEMILLA).fit_transform(w)
    similitud = np.full(len(w), np.nan)
    for c, r in enumerate(reps):
        if r < 0:
            continue
        m = np.flatnonzero(lab == c)
        dd = np.linalg.norm(y[m] - y[r], axis=1)
        similitud[m] = 1.0 - dd / dd.max() if dd.max() > 0 else 1.0
    return similitud


def construir_ambito(ids: np.ndarray, vigente: np.ndarray, dim: pd.DataFrame, patrones: pd.DataFrame, k_patrones: dict,
                     ev_dim: pd.DataFrame, pos_tema: dict, vec_tema: np.ndarray, temas: pd.DataFrame, resumen_dim: dict) -> dict:
    """{mapa, vecinos, personas (perfil amplio y microarquetipo por persona), resumen (fichas)} de un ámbito."""
    act, _ = pc.vectores(ids, dim, patrones, k_patrones)
    contenido, presente = contenido_por_bloque(ids, ev_dim, pos_tema, vec_tema)
    w, vecindad = red_nemo(act, contenido, presente)

    # ---- personas parecidas
    n = min(N_VECINOS, len(ids) - 1)
    orden = np.argsort(-w, axis=1)[:, :n + 1]
    maximo = w.max()
    filas = []
    for i in range(len(ids)):
        vec = [j for j in orden[i] if j != i][:n]
        for r, j in enumerate(vec, start=1):
            vistas = [v for v, m in vecindad.items() if m[i, j] or m[j, i]]
            filas.append((int(ids[i]), int(ids[j]), float(1 - w[i, j] / maximo), r, json.dumps(vistas)))
    vecinos = pd.DataFrame(filas, columns=["persona_id", "vecino_id", "distancia", "rango", "vistas"])

    # ---- perfiles amplios
    k, seleccion = cl.seleccionar_k(w, K_MIN, K_MAX)
    lab = cl.espectral(w, k)
    renum = np.empty(k, dtype=int)
    renum[np.argsort(-np.bincount(lab, minlength=k))] = np.arange(k)
    lab = renum[lab]
    estab = cl.estabilidad(w, lab, k)
    memb = cl.pertenencias(w, lab, k)
    reps = cl.medoides(w, lab, k, elegibles=vigente)
    similitud = _similitud_con_representante(w, lab, reps)
    fila = np.arange(len(ids))
    segundo = np.argsort(-memb, axis=1)[:, 1]

    personas = pd.DataFrame({
        "persona_id": ids, "patron_global": lab, "afinidad_1": memb[fila, lab], "patron_global_2": segundo,
        "afinidad_2": memb[fila, segundo], "mixto": memb[fila, segundo] >= cl.UMBRAL_MIXTO * memb[fila, lab],
        "es_representante": np.isin(fila, reps), "similitud_representante": similitud,
        "afinidades": [json.dumps([round(float(v), 4) for v in m]) for m in memb],
        "micro": -1, "micro_id": None, "micro_afinidad": np.nan, "micro_mixto": False, "micro_2": -1,
        "es_representante_micro": False, "similitud_representante_micro": np.nan,
    })

    # ---- descripciones
    intensidad = dim.pivot(index="persona_id", columns="dimension", values="intensidad").reindex(ids).fillna(0.0)
    pat = (patrones.pivot(index="persona_id", columns="dimension", values="patron") if len(patrones) else pd.DataFrame()).reindex(ids)
    etq = {(dd, t["id"]): t["etiqueta"] for dd, x in resumen_dim.items() if x.get("temas") for t in x["temas"]["temas"]}
    nombres = {(dd, f["id"]): f["nombre"] for dd, x in resumen_dim.items() if x.get("patrones")
               for f in x["patrones"]["patrones"] if f.get("nombre")}
    todos = np.ones(len(ids), bool)
    fichas = []
    for c in range(k):
        m = lab == c
        etiqueta, dims = pc.describir(ids, m, todos, intensidad, pat, nombres=nombres)
        ficha = {"id": c, "etiqueta": etiqueta, "tamano": int(m.sum()), "tamano_vigentes": int(vigente[m].sum()),
                 "proporcion": round(float(m.mean()), 3), "representante_id": int(ids[reps[c]]) if reps[c] >= 0 else None,
                 "dimensiones": dims, "temas": _temas_distintivos(m, ids, temas, etq), "microarquetipos": None}
        pos = np.flatnonzero(m)
        if len(pos) >= MIN_SUBDIVIDIR:
            ficha["microarquetipos"] = _microarquetipos(c, pos, act, contenido, presente, vigente, ids, personas,
                                                        intensidad, pat, temas, etq, nombres)
        fichas.append(ficha)
    resumen = {"metodo": "NEMO (actividad + contenido) + espectral; microarquetipos con NEMO dentro de cada perfil", "k": k, "seleccion_k": seleccion,
               "estabilidad_ari": round(float(estab), 3),
               "vistas": {v: {"nombre": NOMBRES_VISTAS[v], "personas": int(presente[v].sum()) if v in presente else len(ids),
                              "dimensiones": BLOQUES.get(v, "las 12 dimensiones")} for v in NOMBRES_VISTAS},
               "perfiles_mixtos": int(personas["mixto"].sum()),
               "n_microarquetipos": int(sum((f["microarquetipos"] or {}).get("k", 0) for f in fichas)), "patrones": fichas}
    xy = cl.tsne(w)
    mapa = pd.DataFrame({"persona_id": ids, "x": xy[:, 0], "y": xy[:, 1]})
    return {"mapa": mapa, "vecinos": vecinos, "personas": personas, "resumen": resumen}


def _microarquetipos(c: int, pos: np.ndarray, act: np.ndarray, contenido: dict, presente: dict, vigente: np.ndarray,
                     ids: np.ndarray, personas: pd.DataFrame, intensidad: pd.DataFrame, pat: pd.DataFrame,
                     temas: pd.DataFrame, etq: dict, nombres: dict | None = None) -> dict:
    """Subdivide el perfil amplio `c` (integrantes `pos`) con una red NEMO recalculada solo con ellos.
    Rellena las columnas micro_* de `personas` y devuelve la ficha de sus microarquetipos."""
    w = red_nemo(act[pos], {b: v[pos] for b, v in contenido.items()}, {b: v[pos] for b, v in presente.items()})[0]
    k_max = max(K_MIN_MICRO, min(K_MAX_MICRO, len(pos) // 20))
    _, gaps = cl.eigengap(w, K_MIN_MICRO, k_max)
    tabla = []
    for k in range(K_MIN_MICRO, k_max + 1):
        lab = cl.espectral(w, k)
        tabla.append({"k": k, "eigengap": round(float(gaps[k - 1]), 4), "estabilidad_ari": round(float(cl.estabilidad(w, lab, k)), 3),
                      "tamano_minimo": int(np.bincount(lab, minlength=k).min()), "_lab": lab})
    estables = [t for t in tabla if t["estabilidad_ari"] >= ARI_MINIMO]
    elegida = max(estables, key=lambda t: t["eigengap"]) if estables else max(tabla, key=lambda t: t["estabilidad_ari"])
    k, lab = elegida["k"], elegida["_lab"]
    renum = np.empty(k, dtype=int)
    renum[np.argsort(-np.bincount(lab, minlength=k))] = np.arange(k)
    lab = renum[lab]
    memb = cl.pertenencias(w, lab, k)
    reps = cl.medoides(w, lab, k, elegibles=vigente[pos])
    similitud = _similitud_con_representante(w, lab, reps)
    fila = np.arange(len(pos))
    segundo = np.argsort(-memb, axis=1)[:, 1]
    idx = personas.index[pos]
    personas.loc[idx, "micro"] = lab
    personas.loc[idx, "micro_id"] = [f"{c}.{v}" for v in lab]
    personas.loc[idx, "micro_afinidad"] = memb[fila, lab]
    personas.loc[idx, "micro_mixto"] = memb[fila, segundo] >= cl.UMBRAL_MIXTO * memb[fila, lab]
    personas.loc[idx, "micro_2"] = segundo
    personas.loc[idx, "es_representante_micro"] = np.isin(fila, reps)
    personas.loc[idx, "similitud_representante_micro"] = similitud
    padre = np.zeros(len(ids), bool)
    padre[pos] = True
    lista = []
    for j in range(k):
        m = np.zeros(len(ids), bool)
        m[pos[lab == j]] = True
        etiqueta, dims = pc.describir(ids, m, padre, intensidad, pat, "Como su perfil amplio, sin diferencias marcadas", nombres)
        lista.append({"id": j, "codigo": f"G{c + 1}.{j + 1}", "etiqueta": etiqueta, "tamano": int(m.sum()),
                      "tamano_vigentes": int(vigente[m].sum()), "proporcion": round(float(m.sum() / len(pos)), 3),
                      "representante_id": int(ids[pos[reps[j]]]) if reps[j] >= 0 else None, "dimensiones": dims,
                      "temas": _temas_distintivos(m, ids, temas, etq, referencia=padre)})
    return {"k": k, "estabilidad_ari": elegida["estabilidad_ari"], "estable": elegida["estabilidad_ari"] >= ARI_MINIMO,
            "seleccion_k": {"criterio": f"entre los k estables (ARI >= {ARI_MINIMO}) el de mayor eigengap; si ninguno, el más estable",
                            "tabla": [{x: v for x, v in t.items() if x != "_lab"} for t in tabla]},
            "nota": "descritos frente a su perfil amplio", "lista": lista}
