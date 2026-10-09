"""Perfil completo de cada persona: todas las dimensiones juntas (DEC-056).

Sirve para ver quién se parece a quién en el CONJUNTO (p. ej. quien lidera investigación y tiene
muchos reconocimientos queda cerca de otras personas así), sin crear grupos.

Vector de perfil, por cada dimensión d (12 bloques):
    - si la dimensión tiene patrones: afinidades con sus patrones (suman 1) x intensidad_d / 100;
    - si no: [intensidad_d / 100].
Así cada bloque dice CUÁNTO (su magnitud: la intensidad) y CÓMO (su dirección: el patrón) a la
vez; sin evidencias el bloque es 0. Todas las dimensiones pesan lo mismo (la magnitud de un bloque
va de 0 a 1). Los temas (de qué trata la evidencia) no entran: eso lo cubre la búsqueda semántica.

Salida por ámbito: coordenadas t-SNE (solo para visualizar) y los vecinos más cercanos de cada
persona por distancia euclidiana en el vector de perfil.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from perfiles.dimensiones import DIMENSIONES
from perfiles.micro_dimensiones import mapa_tsne

N_VECINOS = 15


def vectores(ids: np.ndarray, dim: pd.DataFrame, patrones: pd.DataFrame, k_patrones: dict[str, int]) -> tuple[np.ndarray, list[str]]:
    """(matriz n x columnas, nombre de cada columna). `dim`: salida de `dimensiones.intensidades`
    del ámbito; `patrones`: patrones por persona del ámbito (con `afinidades`)."""
    pos = {p: i for i, p in enumerate(ids)}
    intensidad = dim.pivot(index="persona_id", columns="dimension", values="intensidad").reindex(ids).fillna(0.0) / 100.0
    bloques, columnas = [], []
    for d in DIMENSIONES:
        k = k_patrones.get(d, 0)
        if k == 0:
            bloques.append(intensidad[[d]].to_numpy())
            columnas.append(f"{d}")
            continue
        b = np.zeros((len(ids), k))
        pd_ = patrones[patrones["dimension"] == d]
        for pid, af in zip(pd_["persona_id"], pd_["afinidades"]):
            if pid in pos:
                b[pos[pid]] = json.loads(af)
        bloques.append(b * intensidad[[d]].to_numpy())
        columnas += [f"{d}__patron_{j}" for j in range(k)]
    return np.hstack(bloques), columnas


def construir_ambito(ids: np.ndarray, dim: pd.DataFrame, patrones: pd.DataFrame, k_patrones: dict[str, int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(mapa: persona_id, x, y) y (vecinos: persona_id, vecino_id, distancia, rango)."""
    from sklearn.neighbors import NearestNeighbors

    x, _ = vectores(ids, dim, patrones, k_patrones)
    xy = mapa_tsne(x)
    n = min(N_VECINOS, len(ids) - 1)
    dist, idx = NearestNeighbors(n_neighbors=n + 1).fit(x).kneighbors(x)
    filas = []
    for i in range(len(ids)):
        vecinos = [(j, d) for j, d in zip(idx[i], dist[i]) if j != i][:n]
        for r, (j, d) in enumerate(vecinos, start=1):
            filas.append((int(ids[i]), int(ids[j]), float(d), r))
    return (pd.DataFrame({"persona_id": ids, "x": xy[:, 0], "y": xy[:, 1]}),
            pd.DataFrame(filas, columns=["persona_id", "vecino_id", "distancia", "rango"]))


# ------------------------------------------------------------------ patrones globales (DEC-057/058)
K_MIN_GLOBAL, K_MAX_GLOBAL = 4, 8
K_MIN_MICRO, K_MAX_MICRO = 2, 5
MIN_SUBDIVIDIR = 60   # un patrón global con menos personas no se divide en microarquetipos
ARI_MINIMO = 0.9
UMBRAL_PUNTOS = 15    # diferencia de intensidad media (puntos) frente a la referencia para llamarla alta/baja


def seleccionar_k(x: np.ndarray, k_min: int, k_max: int) -> tuple[int, dict]:
    """k entre k_min y k_max: mayor silueta entre los k ESTABLES (ARI por submuestreo >= ARI_MINIMO);
    si ninguno es estable, el más estable."""
    from sklearn.metrics import silhouette_score

    from perfiles.micro_dimensiones import _estabilidad_kmeans, _kmeans

    tabla = []
    for k in range(k_min, min(k_max, len(x) // 20) + 1):
        lab = _kmeans(x, k).labels_
        tabla.append({"k": k, "silueta": round(float(silhouette_score(x, lab)), 4), "tamano_minimo": int(np.bincount(lab).min()),
                      "estabilidad_ari": round(_estabilidad_kmeans(x, lab, k), 3)})
    if not tabla:
        return 0, {"k_elegido": 0, "criterio": "muy pocas personas", "tabla": []}
    estables = [t for t in tabla if t["estabilidad_ari"] >= ARI_MINIMO]
    k = (max(estables, key=lambda t: t["silueta"]) if estables else max(tabla, key=lambda t: t["estabilidad_ari"]))["k"]
    return k, {"k_elegido": k, "criterio": f"mayor silueta (KMeans) entre los k con estabilidad ARI >= {ARI_MINIMO}",
               "tabla": tabla}


def agrupar(x: np.ndarray, k: int, vigente: np.ndarray) -> dict:
    """KMeans numerado por tamaño (1 = el más grande). Afinidad derivada = inverso de la distancia²
    a cada centroide, normalizado (suma 1, no es probabilidad). Representante = el vigente más
    cercano a su centroide (-1 si el grupo no tiene vigentes). Similitud con el representante:
    1 - d(persona, representante) / d máxima dentro del grupo (1 = el representante; 0 = la persona
    del grupo más distinta a él)."""
    from perfiles import clustering as cl
    from perfiles.micro_dimensiones import _kmeans

    modelo = _kmeans(x, k)
    renum = np.empty(k, dtype=int)
    renum[np.argsort(-np.bincount(modelo.labels_, minlength=k))] = np.arange(k)
    lab = renum[modelo.labels_]
    centros = np.empty_like(modelo.cluster_centers_)
    centros[renum] = modelo.cluster_centers_
    dist2 = ((x[:, None, :] - centros[None, :, :]) ** 2).sum(axis=2)
    inv = 1.0 / np.maximum(dist2, 1e-9)
    memb = inv / inv.sum(axis=1, keepdims=True)
    cl.validar_afinidades(memb)
    reps = np.full(k, -1)
    similitud = np.full(len(x), np.nan)
    for c in range(k):
        miembros = np.flatnonzero(lab == c)
        cand = miembros[vigente[miembros]]
        if not len(cand):
            continue
        reps[c] = cand[np.argmin(dist2[cand, c])]
        d = np.linalg.norm(x[miembros] - x[reps[c]], axis=1)
        similitud[miembros] = 1.0 - d / d.max() if d.max() > 0 else 1.0
    orden = np.argsort(-memb, axis=1)
    fila = np.arange(len(x))
    segunda = memb[fila, orden[:, 1]] if k > 1 else np.zeros(len(x))
    return {"lab": lab, "memb": memb, "reps": reps, "similitud": similitud, "segunda": orden[:, 1] if k > 1 else lab,
            "afinidad_2": segunda, "mixto": segunda >= cl.UMBRAL_MIXTO * memb[fila, orden[:, 0]] if k > 1 else np.zeros(len(x), bool)}


def describir(ids: np.ndarray, mascara: np.ndarray, referencia: np.ndarray, intensidad: pd.DataFrame,
              pat: pd.DataFrame, sin_diferencias: str = "Cerca del promedio en todo") -> tuple[str, list[dict]]:
    """(etiqueta, detalle por dimensión) del grupo `mascara` frente a `referencia` (máscaras sobre
    `ids`): dimensiones con intensidad media alta o baja frente a la referencia y patrones por
    dimensión mucho más frecuentes que en la referencia (lift >= 1,5, compartidos por >= 50 % de
    quienes tienen evidencias y por >= 30 % del grupo)."""
    media, media_ref = intensidad[mascara].mean(), intensidad[referencia].mean()
    dims = []
    for d, cfg in DIMENSIONES.items():
        entrada = {"dimension": d, "nombre": cfg["nombre"], "intensidad_media": round(float(media[d]), 1),
                   "intensidad_media_referencia": round(float(media_ref[d]), 1),
                   "diferencia": round(float(media[d] - media_ref[d]), 1),
                   "con_evidencia": round(float((intensidad.loc[mascara, d] > 0).mean()), 3), "patron_frecuente": None}
        if d in pat.columns:
            v = pat[d][mascara].dropna()
            if len(v):
                moda = int(v.mode().iloc[0])
                prop = float((v == moda).mean())
                base = float(pat[d][referencia].dropna().eq(moda).mean()) if pat[d][referencia].notna().any() else 0.0
                entrada["patron_frecuente"] = {"patron": moda, "proporcion": round(prop, 3), "proporcion_referencia": round(base, 3),
                                               "lift": round(prop / base, 2) if base else None}
        dims.append(entrada)
    dims.sort(key=lambda e: -e["diferencia"])
    altos = [e["nombre"] for e in dims if e["diferencia"] >= UMBRAL_PUNTOS][:3]
    bajos = [e["nombre"] for e in reversed(dims) if e["diferencia"] <= -UMBRAL_PUNTOS][:3]
    distintivos = sorted(
        (e for e in dims if e["patron_frecuente"] and (e["patron_frecuente"]["lift"] or 0) >= 1.5
         and e["patron_frecuente"]["proporcion"] >= 0.5 and e["con_evidencia"] * e["patron_frecuente"]["proporcion"] >= 0.3),
        key=lambda e: -(e["patron_frecuente"]["lift"] or 0))[:2]
    partes = ([f"Alto: {', '.join(altos)}"] if altos else []) + ([f"Bajo: {', '.join(bajos)}"] if bajos else [])
    partes += [f"Patrón {e['patron_frecuente']['patron'] + 1} en {e['nombre']}" for e in distintivos]
    return " · ".join(partes) or sin_diferencias, dims


def patrones_globales(ids: np.ndarray, vigente: np.ndarray, dim: pd.DataFrame, patrones: pd.DataFrame,
                      k_patrones: dict[str, int]) -> tuple[pd.DataFrame, dict]:
    """Patrones globales sobre el perfil completo (DEC-057) y, dentro de cada uno con al menos
    MIN_SUBDIVIDIR personas, microarquetipos (DEC-058) con el mismo método (KMeans, k = mayor
    silueta entre los k estables), descritos frente a su patrón global."""
    x, _ = vectores(ids, dim, patrones, k_patrones)
    k, seleccion = seleccionar_k(x, K_MIN_GLOBAL, K_MAX_GLOBAL)
    g = agrupar(x, k, vigente)
    lab = g["lab"]
    personas = pd.DataFrame({
        "persona_id": ids, "patron_global": lab, "afinidad_1": g["memb"][np.arange(len(ids)), lab],
        "patron_global_2": g["segunda"], "afinidad_2": g["afinidad_2"], "mixto": g["mixto"],
        "es_representante": np.isin(np.arange(len(ids)), g["reps"]), "similitud_representante": g["similitud"],
        "afinidades": [json.dumps([round(float(v), 4) for v in m]) for m in g["memb"]],
        "micro": -1, "micro_id": None, "micro_afinidad": np.nan, "micro_mixto": False, "micro_2": -1,
        "es_representante_micro": False, "similitud_representante_micro": np.nan,
    })

    intensidad = dim.pivot(index="persona_id", columns="dimension", values="intensidad").reindex(ids).fillna(0.0)
    pat = (patrones.pivot(index="persona_id", columns="dimension", values="patron") if len(patrones) else pd.DataFrame()).reindex(ids)
    todos = np.ones(len(ids), bool)
    fichas = []
    for c in range(k):
        m = lab == c
        etiqueta, dims = describir(ids, m, todos, intensidad, pat)
        ficha = {"id": c, "etiqueta": etiqueta, "tamano": int(m.sum()), "tamano_vigentes": int(vigente[m].sum()),
                 "proporcion": round(float(m.mean()), 3),
                 "representante_id": int(ids[g["reps"][c]]) if g["reps"][c] >= 0 else None, "dimensiones": dims,
                 "microarquetipos": None}
        pos = np.flatnonzero(m)
        if len(pos) >= MIN_SUBDIVIDIR:
            ks, sel_s = seleccionar_k(x[pos], K_MIN_MICRO, K_MAX_MICRO)
            if ks >= 2:
                s = agrupar(x[pos], ks, vigente[pos])
                idx = personas.index[pos]
                personas.loc[idx, "micro"] = s["lab"]
                personas.loc[idx, "micro_id"] = [f"{c}.{v}" for v in s["lab"]]
                personas.loc[idx, "micro_afinidad"] = s["memb"][np.arange(len(pos)), s["lab"]]
                personas.loc[idx, "micro_mixto"] = s["mixto"]
                personas.loc[idx, "micro_2"] = s["segunda"]
                personas.loc[idx, "es_representante_micro"] = np.isin(np.arange(len(pos)), s["reps"])
                personas.loc[idx, "similitud_representante_micro"] = s["similitud"]
                micros = []
                for j in range(ks):
                    mm = np.zeros(len(ids), bool)
                    mm[pos[s["lab"] == j]] = True
                    et, dj = describir(ids, mm, m, intensidad, pat, "Como su patrón global, sin diferencias marcadas")
                    micros.append({"id": j, "codigo": f"G{c + 1}.{j + 1}", "etiqueta": et, "tamano": int(mm.sum()),
                                   "tamano_vigentes": int(vigente[mm].sum()), "proporcion": round(float(mm.sum() / m.sum()), 3),
                                   "representante_id": int(ids[pos[s["reps"][j]]]) if s["reps"][j] >= 0 else None,
                                   "dimensiones": dj})
                estab = next(t["estabilidad_ari"] for t in sel_s["tabla"] if t["k"] == ks)
                ficha["microarquetipos"] = {"k": ks, "seleccion_k": sel_s, "estabilidad_ari": estab,
                                            "nota": "descritos frente a su patrón global", "lista": micros}
        fichas.append(ficha)
    estab = next(t["estabilidad_ari"] for t in seleccion["tabla"] if t["k"] == k)
    resumen = {"k": k, "seleccion_k": seleccion, "estabilidad_ari": estab, "perfiles_mixtos": int(personas["mixto"].sum()),
               "n_microarquetipos": int(sum((f["microarquetipos"] or {}).get("k", 0) for f in fichas)), "patrones": fichas}
    return personas, resumen
