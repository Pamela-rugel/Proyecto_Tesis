"""Embedding de las evidencias (DEC-045).

Se embebe cada TEXTO UNICO una sola vez (126 070 evidencias -> ~87 000 textos distintos): el
mismo proyecto de 32 participantes o el mismo curso masivo no se recalcula. Modelo: BAAI/bge-m3
(multilingue, 1024 dimensiones, el mismo que ya usaba el proyecto), vectores normalizados (L2),
guardados en float16.

Persistencia en data/perfiles/embeddings/:
    textos.parquet   clave (sha1 del texto, 16 caracteres) + texto, en el orden de los vectores
    vectores.npy     matriz float16 (n_textos x 1024)
    manifest.json    modelo, dimension, numero de textos, huella del conjunto de textos y fecha
Es incremental: al volver a correr, solo se embeben los textos que no estaban.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

import numpy as np
import pandas as pd

from perfiles.comun import EMBEDDINGS_DIR, cargar_evidencias, huella_texto

MODELO = "BAAI/bge-m3"
MAX_TOKENS = 256  # p95 de las evidencias ~ 360 caracteres (~100 tokens); max 1400 caracteres
ARCHIVO_TEXTOS = EMBEDDINGS_DIR / "textos.parquet"
ARCHIVO_VECTORES = EMBEDDINGS_DIR / "vectores.npy"
ARCHIVO_MANIFEST = EMBEDDINGS_DIR / "manifest.json"


def clave_texto(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


def cargar() -> tuple[pd.DataFrame, np.ndarray, dict]:
    """(textos con su posicion, vectores float32, manifest)."""
    textos = pd.read_parquet(ARCHIVO_TEXTOS)
    vectores = np.load(ARCHIVO_VECTORES).astype(np.float32)
    manifest = json.loads(ARCHIVO_MANIFEST.read_text(encoding="utf-8"))
    return textos, vectores, manifest


def construir(batch_size: int = 128, dispositivo: str | None = None) -> dict:
    """Embebe los textos de evidencias que aun no tienen vector. Devuelve el manifest."""
    from sentence_transformers import SentenceTransformer

    textos = sorted(cargar_evidencias(con_atributos=False)["texto"].dropna().unique())
    claves = [clave_texto(t) for t in textos]

    previos, vectores_previos = pd.DataFrame(columns=["clave", "texto"]), np.zeros((0, 1024), np.float16)
    if ARCHIVO_TEXTOS.exists() and ARCHIVO_VECTORES.exists():
        manifest_previo = json.loads(ARCHIVO_MANIFEST.read_text(encoding="utf-8"))
        if manifest_previo.get("modelo") == MODELO:
            previos, vectores_previos = pd.read_parquet(ARCHIVO_TEXTOS), np.load(ARCHIVO_VECTORES)
    posicion_previa = dict(zip(previos["clave"], range(len(previos))))
    faltan = [(c, t) for c, t in zip(claves, textos) if c not in posicion_previa]

    nuevos = np.zeros((0, vectores_previos.shape[1]), np.float16)
    if faltan:
        modelo = SentenceTransformer(MODELO, device=dispositivo)
        modelo.max_seq_length = MAX_TOKENS
        # Orden por longitud: lotes de textos parecidos en largo = menos relleno, mas rapido
        orden = sorted(range(len(faltan)), key=lambda i: len(faltan[i][1]))
        v = modelo.encode([faltan[i][1] for i in orden], batch_size=batch_size, normalize_embeddings=True,
                          show_progress_bar=True, convert_to_numpy=True)
        nuevos = np.zeros_like(v)
        nuevos[orden] = v
        nuevos = nuevos.astype(np.float16)

    # Solo se conservan los textos vigentes (los de evidencias que ya no existen se descartan)
    todos = pd.concat([previos, pd.DataFrame(faltan, columns=["clave", "texto"])], ignore_index=True)
    matriz = np.vstack([vectores_previos, nuevos]) if len(todos) else nuevos
    vigentes = todos["clave"].isin(set(claves)).to_numpy()
    todos, matriz = todos[vigentes].reset_index(drop=True), matriz[vigentes]

    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    todos.to_parquet(ARCHIVO_TEXTOS, index=False)
    np.save(ARCHIVO_VECTORES, matriz)
    manifest = {
        "modelo": MODELO,
        "dimension": int(matriz.shape[1]),
        "normalizados": True,
        "max_tokens": MAX_TOKENS,
        "n_textos": len(todos),
        "n_nuevos_en_esta_corrida": len(faltan),
        "huella_textos": huella_texto(sorted(todos["clave"])),
        "fecha": datetime.now().isoformat(timespec="seconds"),
    }
    ARCHIVO_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(construir(), ensure_ascii=False, indent=2))
