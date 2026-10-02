"""Similarity Network Fusion (Wang et al., 2014, Nature Methods 11:333-337).

Implementacion propia (sin dependencias nuevas), con las mismas definiciones que la
implementacion de referencia `snfpy`:

1. Afinidad por vista (kernel gaussiano con escala local):
       eps_ij = (mean_d(i, K vecinos) + mean_d(j, K vecinos) + d_ij) / 3
       W_ij   = N(d_ij; 0, mu * eps_ij)        (densidad normal)
2. Matriz completa normalizada P (mitad en la diagonal) y kernel local S (solo los K vecinos):
       P_ij = W_ij / (2 * sum_{k != i} W_ik),  P_ii = 1/2
       S_ij = W_ij / sum_{k in N_i} W_ik  si j en N_i, 0 si no
3. Difusion: en cada iteracion, cada vista se actualiza con el promedio de las demas,
       P_v <- S_v (promedio_{u != v} P_u) S_v^T
   y se renormaliza. Al final la red fusionada es el promedio de las P_v (simetrica).

Las vistas pueden tener dimensiones y escalas distintas (1024 vs 40): SNF solo ve distancias
dentro de cada vista y su estructura de vecindad local, no mezcla las variables.
"""
from __future__ import annotations

import numpy as np
from scipy import sparse
from scipy.spatial.distance import cdist


def distancias(x: np.ndarray, metrica: str = "euclidean") -> np.ndarray:
    return cdist(x, x, metric=metrica)


def afinidad(d: np.ndarray, k: int = 20, mu: float = 0.5) -> np.ndarray:
    """Matriz de afinidad (kernel gaussiano con escala local) desde una matriz de distancias."""
    d = (d + d.T) / 2
    np.fill_diagonal(d, 0)
    orden = np.sort(d, axis=1)
    media_vecinos = orden[:, 1:k + 1].mean(axis=1)
    eps = (media_vecinos[:, None] + media_vecinos[None, :] + d) / 3
    sigma = mu * eps
    sigma = np.maximum(sigma, np.finfo(float).eps)
    w = np.exp(-(d ** 2) / (2 * sigma ** 2)) / (sigma * np.sqrt(2 * np.pi))
    return (w + w.T) / 2


def _normalizar_completa(w: np.ndarray) -> np.ndarray:
    w = w.copy()
    np.fill_diagonal(w, 0)
    suma = w.sum(axis=1, keepdims=True)
    p = w / (2 * np.maximum(suma, np.finfo(float).eps))
    np.fill_diagonal(p, 0.5)
    return (p + p.T) / 2


def _kernel_local(w: np.ndarray, k: int) -> sparse.csr_matrix:
    n = w.shape[0]
    w = w.copy()
    np.fill_diagonal(w, 0)
    vecinos = np.argpartition(-w, kth=k, axis=1)[:, :k]
    filas = np.repeat(np.arange(n), k)
    valores = w[filas, vecinos.ravel()]
    s = sparse.csr_matrix((valores, (filas, vecinos.ravel())), shape=(n, n))
    suma = np.asarray(s.sum(axis=1)).ravel()
    return sparse.diags(1.0 / np.maximum(suma, np.finfo(float).eps)) @ s


def fusionar(afinidades: list[np.ndarray], k: int = 20, t: int = 20) -> tuple[np.ndarray, list[np.ndarray]]:
    """Red fusionada (n x n) y las P de cada vista tras la difusion (para explicar por vista)."""
    p = [_normalizar_completa(w) for w in afinidades]
    s = [_kernel_local(w, k) for w in afinidades]
    m = len(p)
    for _ in range(t):
        suma = sum(p)
        nuevas = []
        for v in range(m):
            otras = (suma - p[v]) / (m - 1)
            nueva = np.asarray(s[v] @ (s[v] @ otras).T).T  # S_v * otras * S_v^T
            nuevas.append(_normalizar_completa(nueva))
        p = nuevas
    fusionada = sum(p) / m
    fusionada = (fusionada + fusionada.T) / 2
    np.fill_diagonal(fusionada, 0)
    return fusionada, p
