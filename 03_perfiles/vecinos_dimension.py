"""Personas parecidas DENTRO de cada dimensión (DEC-060, DEC-061).

Dos listas separadas por persona y dimensión, porque responden preguntas distintas:

- **actividad** ("participa de forma parecida"): distancia euclidiana en el espacio estandarizado
  de los patrones de actividad (el mismo en que se agrupa). Muchas personas tienen exactamente los
  mismos valores (una ponencia nacional, una mención); entre ellas se ordena por el contenido de
  sus evidencias (similitud del tema) y luego por la cercanía en la fecha de su última evidencia.
  Quien tiene valores idénticos queda marcado (`identico`) y se cuenta cuántas personas comparten
  exactamente su registro (`n_identicos`).
- **tema** ("trabaja temas parecidos"): similitud coseno entre el promedio de los embeddings de
  tema de sus evidencias (el mismo vector del mapa de temas); en Idiomas, coincidencia (Jaccard) de
  los idiomas registrados. Desempate por la distancia de actividad y luego por la fecha. Se guarda
  el par de evidencias más parecido (sus títulos) para explicar la cercanía, y los temas que
  comparten.

`en_ambos` marca a quien aparece en las dos listas de la persona. No se guardan puntajes: el orden
y la explicación bastan (no se presentan cosenos ni distancias como puntuaciones). Se calcula
fuera de línea por ámbito y dimensión (`construir.py`); el dashboard solo lo lee y filtra vigentes.
No mide competencia ni idoneidad.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

N_VECINOS = 15
EPS = 1e-9
SIN_FECHA = 99.0   # diferencia de años usada cuando falta la fecha (queda al final del desempate)


def _anios(fechas: pd.Series) -> np.ndarray:
    f = pd.to_datetime(fechas, errors="coerce")
    return (f.dt.year + (f.dt.dayofyear - 1) / 365.25).to_numpy(dtype=float)


def _orden(primaria: np.ndarray, secundaria: np.ndarray, terciaria: np.ndarray, i: int, n: int) -> np.ndarray:
    """Índices de los n primeros por (primaria, secundaria, terciaria), sin `i`. Se toman TODOS los
    empatados en la primaria con el n-ésimo, para que el desempate decida entre ellos."""
    p = primaria.copy()
    p[i] = np.inf
    n = min(n, len(p) - 1)
    if n <= 0:
        return np.array([], dtype=int)
    corte = np.partition(p, n - 1)[n - 1]
    cand = np.flatnonzero(p <= corte + EPS)
    orden = np.lexsort((cand, terciaria[cand], secundaria[cand], np.round(p[cand], 9)))
    return cand[orden][:n]


def construir_dimension(dimension: str, ids: np.ndarray, z: np.ndarray | None, emb: dict, ultima: dict,
                        temas_persona: dict, textos_persona: dict, vec_texto: dict, idiomas: dict | None = None) -> pd.DataFrame:
    """Vecinos de una dimensión. `ids`: personas con evidencias (filas de `z`). `emb`: persona ->
    embedding de tema normalizado. `ultima`: persona -> fecha ISO de su última evidencia.
    `temas_persona`: persona -> {tema: proporción}. `textos_persona`: persona -> títulos (texto de
    tema) de sus evidencias; `vec_texto`: título -> embedding normalizado. `idiomas`: solo en
    Idiomas, persona -> conjunto de idiomas extranjeros."""
    n = len(ids)
    if n < 2:
        return pd.DataFrame()
    anio = _anios(pd.Series([ultima.get(p) for p in ids]))
    dif_fecha = np.abs(anio[:, None] - anio[None, :])
    dif_fecha = np.where(np.isfinite(dif_fecha), dif_fecha, SIN_FECHA).astype(np.float32)

    act = None
    if z is not None:
        cuad = (z ** 2).sum(axis=1)
        act = np.sqrt(np.maximum(cuad[:, None] + cuad[None, :] - 2 * z @ z.T, 0)).astype(np.float32)
        act[act < 1e-6] = 0.0

    sim = None
    if idiomas is not None:
        conj = [idiomas.get(p, frozenset()) for p in ids]
        sim = np.array([[len(a & b) / len(a | b) if (a | b) else 0.0 for b in conj] for a in conj], dtype=np.float32)
    elif emb:
        e = np.vstack([emb.get(p, np.zeros_like(next(iter(emb.values())))) for p in ids]).astype(np.float32)
        sim = e @ e.T
        sin = np.array([p not in emb for p in ids])
        sim[sin, :] = -1.0
        sim[:, sin] = -1.0

    cero = np.zeros(n, dtype=np.float32)
    filas = []
    for i, p in enumerate(ids):
        listas = {}
        if act is not None:
            listas["actividad"] = _orden(act[i], -sim[i] if sim is not None else cero, dif_fecha[i], i, N_VECINOS)
        if sim is not None:
            listas["tema"] = _orden(-sim[i], act[i] if act is not None else cero, dif_fecha[i], i, N_VECINOS)
        n_ident = int(((act[i] == 0).sum() - 1)) if act is not None else 0
        ambos = set(listas.get("actividad", [])) & set(listas.get("tema", []))
        propios = temas_persona.get(p, {})
        mis_textos = textos_persona.get(p, [])
        for lista, idx in listas.items():
            for r, j in enumerate(idx, start=1):
                q = ids[j]
                otros = temas_persona.get(q, {})
                comunes = sorted(set(propios) & set(otros), key=lambda t: -min(propios[t], otros[t]))[:3]
                tp = tv = None
                if lista == "tema" and idiomas is None and mis_textos and textos_persona.get(q):
                    a = np.vstack([vec_texto[t] for t in mis_textos])
                    b = np.vstack([vec_texto[t] for t in textos_persona[q]])
                    s = a @ b.T
                    x, y = np.unravel_index(int(np.argmax(s)), s.shape)
                    tp, tv = mis_textos[x], textos_persona[q][y]
                identico = bool(act is not None and act[i, j] == 0) if lista == "actividad" else bool(sim[i, j] >= 1 - 1e-4)
                filas.append((int(p), dimension, lista, r, int(q), identico, j in ambos, n_ident,
                              json.dumps([int(t) for t in comunes]), tp, tv))
    return pd.DataFrame(filas, columns=["persona_id", "dimension", "lista", "rango", "vecino_id", "identico", "en_ambos",
                                        "n_identicos", "temas_compartidos", "texto_persona", "texto_vecino"])
