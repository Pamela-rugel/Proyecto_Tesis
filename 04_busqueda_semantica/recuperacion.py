"""Recuperación de evidencias candidatas por capacidad y por tipo (DISENO.md §4.2).

Para cada capacidad y cada tipo de evidencia pertinente:
  1. denso exacto: similitud coseno con el TEMA de la capacidad y, si existe, con la
     reformulación escrita en el formato de ESE tipo (se toma la mayor de las dos);
  2. léxico: BM25 del tema (siglas y nombres propios). Se usa el tema y no la descripción porque
     las palabras del tipo ("proyectos de investigación", "docencia") no deben puntuar: el tipo ya
     lo resuelve la búsqueda por tipo;
  3. fusión por rangos: Reciprocal Rank Fusion, Σ 1/(k + rango), k = 60;
  4. posición relativa DENTRO del tipo (percentil), para que una materia y una capacitación
     compitan cada una en su escala;
  5. se conservan los `CANDIDATOS_POR_TIPO` mejores, que pasan al reranker.
Solo se consideran textos de personas del universo (vigencia y requisitos de persona).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from busqueda.comun import CANDIDATOS_POR_TIPO, RRF_K
from busqueda.indice import Indice, embeber
from busqueda.interpretacion import Capacidad


def _rangos(puntaje: np.ndarray) -> np.ndarray:
    """Rango 1 = mejor (empates rompen por orden estable)."""
    orden = np.argsort(-puntaje, kind="stable")
    r = np.empty(len(puntaje), dtype=np.int64)
    r[orden] = np.arange(1, len(puntaje) + 1)
    return r


def candidatos(ix: Indice, cap: Capacidad, textos_universo: np.ndarray, por_tipo: bool = True,
               lexico: bool = True, k: int = CANDIDATOS_POR_TIPO) -> pd.DataFrame:
    """DataFrame: texto_idx, tipo_id, denso, bm25, rrf, percentil (dentro del tipo)."""
    reformulacion = {r.tipo: r.texto for r in cap.reformulaciones}
    tipos_ref = [t for t in cap.tipos if t in reformulacion]
    q = embeber([cap.tema] + [reformulacion[t] for t in tipos_ref])
    vector_ref = {t: q[n] for n, t in enumerate(tipos_ref, 1)}  # tipo → vector de su reformulación
    denso_desc = ix.V @ q[0]
    bm25 = ix.bm25_scores(cap.tema) if lexico else np.zeros(len(ix.V), np.float32)
    en_universo = np.zeros(len(ix.V), dtype=bool)
    en_universo[textos_universo] = True

    grupos = [(t, ix.textos_por_tipo[t]) for t in cap.tipos if t in ix.textos_por_tipo] if por_tipo \
        else [("TODOS", np.arange(len(ix.V)))]
    filas = []
    for tipo, idx in grupos:
        idx = idx[en_universo[idx]]
        if not len(idx):
            continue
        d = denso_desc[idx]
        if por_tipo and tipo in vector_ref:
            d = np.maximum(d, ix.V[idx] @ vector_ref[tipo])
        rrf = 1.0 / (RRF_K + _rangos(d))
        b = bm25[idx]
        if lexico and (b > 0).any():
            rrf = rrf + np.where(b > 0, 1.0 / (RRF_K + _rangos(b)), 0.0)
        orden = np.argsort(-rrf, kind="stable")[:k]
        n = len(idx)
        for pos, o in enumerate(orden):
            filas.append((int(idx[o]), tipo, float(d[o]), float(b[o]), float(rrf[o]), 1.0 - pos / n))
    return pd.DataFrame(filas, columns=["texto_idx", "tipo_grupo", "denso", "bm25", "rrf", "percentil"])
