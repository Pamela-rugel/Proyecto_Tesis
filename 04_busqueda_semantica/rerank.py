"""Reranking con cross-encoder (DISENO.md §4.6).

`BAAI/bge-reranker-v2-m3` (multilingüe, misma familia que el embedding, sin entrenamiento) lee
juntos la capacidad y el texto de la evidencia y devuelve una probabilidad de relevancia
(sigmoide de su puntaje). A diferencia del coseno, es comparable entre consultas y entre tipos de
evidencia, por eso se usa para decidir si una evidencia ACREDITA la capacidad (umbral
`UMBRAL_RELEVANCIA`, [Validar]) y no solo para reordenar.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=1)
def modelo_reranker():
    import torch
    from sentence_transformers import CrossEncoder

    from busqueda.comun import MODELO_RERANKER

    disp = "cuda" if torch.cuda.is_available() else "cpu"
    return CrossEncoder(MODELO_RERANKER, device=disp, max_length=512,
                        model_kwargs={"torch_dtype": torch.float16} if disp == "cuda" else {})


def probabilidades(consulta: str, textos: list[str], lote: int = 64) -> np.ndarray:
    if not textos:
        return np.zeros(0, dtype=np.float32)
    s = np.asarray(modelo_reranker().predict([(consulta, t) for t in textos], batch_size=lote,
                                             show_progress_bar=False), dtype=np.float32)
    if s.min() < 0 or s.max() > 1:  # puntaje crudo (logit) → probabilidad
        s = 1.0 / (1.0 + np.exp(-s))
    return s
