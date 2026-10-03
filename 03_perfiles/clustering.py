"""Clustering sobre la red fusionada por SNF, pertenencias derivadas y representantes (DEC-045).

- Asignacion: clustering espectral sobre la red fusionada (afinidad precomputada). Es EXCLUSIVO:
  cada persona queda en un cluster.
- Numero de clusters: eigengap del laplaciano normalizado de la red fusionada entre K_MIN y
  K_MAX (criterio estandar para SNF); se reportan tambien la silueta (distancia derivada de la
  red) y la estabilidad por submuestreo (ARI) de cada k.
- Pertenencia derivada (perfiles mixtos): para cada persona y cluster, afinidad fusionada media
  con los integrantes del cluster, normalizada para que sume 1. No cambia la asignacion: mide
  cuanto se conecta la persona con cada grupo en la MISMA red. Perfil mixto: el segundo cluster
  tiene al menos UMBRAL_MIXTO veces la pertenencia del primero.
- Explicacion por vista: con la red de cada vista tras la difusion de SNF, el cluster con el que
  la persona tiene mayor afinidad media en esa vista.
- Representante: medoide (integrante con mayor afinidad fusionada media al resto del cluster).
  SNF no produce centroides en un espacio de variables; ademas se guarda el centroide semantico
  (promedio normalizado del embedding de persona) de V1 y V2 para la busqueda posterior.
- t-SNE solo para VISUALIZAR, sobre la distancia derivada de la red fusionada (el mismo espacio
  del clustering), no es el espacio donde se agrupa.
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import SpectralClustering
from sklearn.manifold import TSNE
from sklearn.metrics import adjusted_rand_score, silhouette_score

K_MIN, K_MAX = 4, 12
# Segundo nivel (subpatrones): se subdivide cada patron con al menos MIN_SUBDIVIDIR personas,
# recalculando SNF dentro del patron (escalas y estandarizacion locales), k entre 2 y 8.
MIN_SUBDIVIDIR = 150
K_MIN_SUB, K_MAX_SUB = 2, 8
UMBRAL_MIXTO = 0.8
N_SUBMUESTRAS, FRACCION_SUBMUESTRA = 10, 0.9
SEMILLA = 42


def distancia_desde_afinidad(w: np.ndarray) -> np.ndarray:
    """Distancia en [0, 1] desde la red fusionada: 1 - afinidad escalada por su maximo."""
    a = w / w.max()
    d = 1.0 - a
    np.fill_diagonal(d, 0)
    return d


def eigengap(w: np.ndarray, k_min: int = K_MIN, k_max: int = K_MAX) -> tuple[int, list[float]]:
    grados = w.sum(axis=1)
    d_inv = 1.0 / np.sqrt(np.maximum(grados, np.finfo(float).eps))
    lap = np.eye(len(w)) - (d_inv[:, None] * w * d_inv[None, :])
    valores = np.sort(np.linalg.eigvalsh(lap))[:k_max + 2]
    gaps = np.diff(valores)  # gap[k-1] = lambda_k - lambda_{k-1} (k clusters)
    candidatos = {k: float(gaps[k - 1]) for k in range(k_min, k_max + 1)}
    return max(candidatos, key=candidatos.get), [round(float(g), 6) for g in gaps]


def espectral(w: np.ndarray, k: int, semilla: int = SEMILLA) -> np.ndarray:
    modelo = SpectralClustering(n_clusters=k, affinity="precomputed", assign_labels="cluster_qr",
                                random_state=semilla)
    return modelo.fit_predict(w)


def estabilidad(w: np.ndarray, etiquetas: np.ndarray, k: int) -> float:
    """ARI medio entre la asignacion completa y la de submuestras del 90 % de la red."""
    rng = np.random.default_rng(SEMILLA)
    n = len(w)
    aris = []
    for _ in range(N_SUBMUESTRAS):
        idx = np.sort(rng.choice(n, size=int(n * FRACCION_SUBMUESTRA), replace=False))
        sub = espectral(w[np.ix_(idx, idx)], k)
        aris.append(adjusted_rand_score(etiquetas[idx], sub))
    return float(np.mean(aris))


def seleccionar_k(w: np.ndarray, k_min: int = K_MIN, k_max: int = K_MAX) -> tuple[int, dict]:
    k_max = min(k_max, len(w) // 10)  # al menos ~10 personas por grupo en promedio
    k_eigengap, gaps = eigengap(w, k_min, k_max)
    d = distancia_desde_afinidad(w)
    tabla = []
    for k in range(k_min, k_max + 1):
        et = espectral(w, k)
        tabla.append({"k": k, "eigengap": gaps[k - 1], "silueta": round(float(silhouette_score(d, et, metric="precomputed")), 4),
                      "tamano_minimo": int(np.bincount(et).min())})
    return k_eigengap, {"k_elegido": k_eigengap, "criterio": "eigengap del laplaciano normalizado de la red fusionada",
                        "nota_silueta": "referencia secundaria: la distancia 1 - afinidad/max de SNF esta dominada por "
                                        "afinidades cercanas a cero, por eso la silueta es baja en todos los k",
                        "tabla": tabla}


def pertenencias(w: np.ndarray, etiquetas: np.ndarray, k: int) -> np.ndarray:
    """(n x k): afinidad media de cada persona con los integrantes de cada cluster, normalizada."""
    m = np.zeros((len(w), k))
    for c in range(k):
        miembros = etiquetas == c
        suma = w[:, miembros].sum(axis=1)
        n_miembros = miembros.sum() - miembros.astype(int)  # sin contarse a si misma
        m[:, c] = suma / np.maximum(n_miembros, 1)
    m = np.clip(m, 0.0, None)
    total = m.sum(axis=1, keepdims=True)
    # persona sin afinidad con nadie (caso límite): afinidad uniforme, nunca NaN
    return np.where(total > 0, m / np.where(total > 0, total, 1.0), 1.0 / k)


def validar_afinidades(m: np.ndarray, tol: float = 1e-6) -> None:
    """Afinidades derivadas: finitas, no negativas y que suman 1 por persona (no son probabilidades)."""
    if not np.isfinite(m).all():
        raise ValueError("afinidades no finitas")
    if (m < -tol).any():
        raise ValueError("afinidades negativas")
    if not np.allclose(m.sum(axis=1), 1.0, atol=tol):
        raise ValueError("afinidades que no suman 1")


def cluster_por_vista(p_vistas: list[np.ndarray], etiquetas: np.ndarray, k: int) -> np.ndarray:
    """(n x vistas): cluster con mayor afinidad media en cada vista (tras la difusion)."""
    salida = np.zeros((len(etiquetas), len(p_vistas)), dtype=int)
    for v, p in enumerate(p_vistas):
        p = p.copy()
        np.fill_diagonal(p, 0)
        salida[:, v] = pertenencias(p, etiquetas, k).argmax(axis=1)
    return salida


def medoides(w: np.ndarray, etiquetas: np.ndarray, k: int, elegibles: np.ndarray | None = None) -> np.ndarray:
    """Medoide de cada cluster: el integrante con mayor afinidad total con el resto del cluster.
    Con `elegibles` (máscara booleana, p. ej. vigentes) solo se elige entre ellos; si el cluster no
    tiene ningún elegible se devuelve -1 (representante vacío explícito, nunca uno no elegible)."""
    idx = np.full(k, -1, dtype=int)
    for c in range(k):
        miembros = np.flatnonzero(etiquetas == c)
        if not len(miembros):
            continue
        centralidad = w[np.ix_(miembros, miembros)].sum(axis=1)
        if elegibles is not None:
            ok = elegibles[miembros]
            if not ok.any():
                continue
            centralidad = np.where(ok, centralidad, -np.inf)
        idx[c] = miembros[int(np.argmax(centralidad))]
    return idx


def centroides(x: np.ndarray, etiquetas: np.ndarray, k: int) -> np.ndarray:
    """Centroide semántico (vector, no persona) normalizado de cada cluster; falla si queda vacío o
    no finito."""
    c = np.vstack([x[etiquetas == i].mean(axis=0) if (etiquetas == i).any() else np.full(x.shape[1], np.nan)
                   for i in range(k)])
    c = c / np.linalg.norm(c, axis=1, keepdims=True)
    if not np.isfinite(c).all():
        raise ValueError("centroide vacío o no finito")
    return c


def tsne(w: np.ndarray) -> np.ndarray:
    d = distancia_desde_afinidad(w)
    modelo = TSNE(n_components=2, metric="precomputed", init="random", perplexity=30, random_state=SEMILLA)
    return modelo.fit_transform(d)


def vecinos(w: np.ndarray, n: int = 30) -> tuple[np.ndarray, np.ndarray]:
    """Indices y afinidades de los n vecinos mas cercanos de cada persona en la red fusionada
    (para la etapa de busqueda: candidatos por vecindad)."""
    idx = np.argsort(-w, axis=1)[:, :n]
    return idx, np.take_along_axis(w, idx, axis=1)
