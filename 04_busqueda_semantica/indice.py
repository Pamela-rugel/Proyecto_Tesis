"""Índice de búsqueda: embeddings existentes + BM25 + tablas de evidencias y personas.

- Denso: reutiliza los vectores bge-m3 de `data/perfiles/embeddings` (un vector por texto único).
  Búsqueda EXACTA (producto matriz-vector): con 87 166 × 1 024 tarda milisegundos y es
  reproducible; no hace falta un índice aproximado.
- Léxico: BM25 implementado con matrices dispersas (scipy) sobre los mismos textos únicos, para
  siglas y nombres propios (diagnóstico: búsqueda densa sola recupera 42 % de "CIBE").
  Se guarda en `data/busqueda/` y se reconstruye si cambian los textos (huella).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
from scipy import sparse

from busqueda.comun import BM25_B, BM25_K1, BUSQUEDA_DIR
from perfiles import embeddings as emb
from perfiles.comun import cargar_estado_personas, cargar_evidencias
from perfiles.vistas import NIVEL_IDIOMA, _nivel_formacion

_STOP = set("""de la el los las y en del a al para por con sin un una o u e que su sus se lo como mas
entre sobre the of and in for to on with an at by from is are tipo modalidad virtual presencial
certificado por publicado en roles programa nivel unidad cine subarea frascati otorgado""".split())


def tokens(texto: str) -> list[str]:
    t = unicodedata.normalize("NFKD", str(texto).lower()).encode("ascii", "ignore").decode("ascii")
    return [w for w in re.findall(r"[a-z0-9]+", t) if len(w) >= 2 and w not in _STOP]


@dataclass
class Indice:
    textos: pd.DataFrame          # clave, texto (orden = filas de V)
    V: np.ndarray                 # (n_textos x 1024) float32, norma 1
    bm25: sparse.csc_matrix       # (n_textos x vocab) pesos BM25
    vocab: dict[str, int]
    ev: pd.DataFrame              # evidencia_id, persona_id, tipo_id, texto_idx, atributos
    textos_por_tipo: dict[str, np.ndarray]
    personas: pd.DataFrame        # persona_id (índice): vigente, tipo_empleado, cargo, unidad, nivel_formacion, idiomas
    huella: str

    def bm25_scores(self, consulta: str) -> np.ndarray:
        cols = [self.vocab[w] for w in set(tokens(consulta)) if w in self.vocab]
        if not cols:
            return np.zeros(self.bm25.shape[0], dtype=np.float32)
        return np.asarray(self.bm25[:, cols].sum(axis=1)).ravel().astype(np.float32)


def _construir_bm25(textos: list[str]) -> tuple[sparse.csc_matrix, dict[str, int]]:
    vocab: dict[str, int] = {}
    filas, cols, vals = [], [], []
    largos = np.zeros(len(textos), dtype=np.float32)
    for i, t in enumerate(textos):
        tk = tokens(t)
        largos[i] = len(tk)
        cuenta: dict[int, int] = {}
        for w in tk:
            j = vocab.setdefault(w, len(vocab))
            cuenta[j] = cuenta.get(j, 0) + 1
        for j, c in cuenta.items():
            filas.append(i)
            cols.append(j)
            vals.append(c)
    tf = sparse.csr_matrix((np.array(vals, np.float32), (filas, cols)), shape=(len(textos), len(vocab)))
    n = len(textos)
    df = np.bincount(tf.indices, minlength=len(vocab))
    idf = np.log(1 + (n - df + 0.5) / (df + 0.5)).astype(np.float32)
    media = largos.mean() or 1.0
    tf = tf.tocoo()
    norma = BM25_K1 * (1 - BM25_B + BM25_B * largos[tf.row] / media)
    peso = idf[tf.col] * tf.data * (BM25_K1 + 1) / (tf.data + norma)
    return sparse.csc_matrix((peso, (tf.row, tf.col)), shape=tf.shape), vocab


def _personas(ev: pd.DataFrame) -> pd.DataFrame:
    estado = cargar_estado_personas().set_index("persona_id")
    ids = sorted(ev["persona_id"].unique())
    p = pd.DataFrame(index=pd.Index(ids, name="persona_id")).join(estado)
    p["vigente"] = p["vigente"].fillna(False).astype(bool)
    nivel, idiomas = {}, {}
    for pid, tipo, s in zip(ev["persona_id"], ev["tipo_id"], ev["atributos"]):
        if tipo == "FORMACION_TITULO":
            nivel[pid] = max(nivel.get(pid, 0.0), _nivel_formacion(json.loads(s)))
        elif tipo == "IDIOMA":
            a = json.loads(s)
            niv = (a.get("niveles_conversacion") or []) + (a.get("niveles_lectura") or []) + (a.get("niveles_escritura") or [])
            maximo = max([NIVEL_IDIOMA.get(x, 0) for x in niv] + [0])
            idiomas.setdefault(pid, {})[str(a.get("idioma") or "").upper()] = maximo
    p["nivel_formacion"] = p.index.map(lambda i: nivel.get(i, 0.0))
    p["idiomas"] = p.index.map(lambda i: idiomas.get(i, {}))
    return p


@lru_cache(maxsize=1)
def cargar_indice() -> Indice:
    textos, V, manifest = emb.cargar()
    huella = manifest["huella_textos"]
    ev = cargar_evidencias()
    pos = dict(zip(textos["clave"], range(len(textos))))
    ev["texto_idx"] = ev["texto"].map(emb.clave_texto).map(pos)
    if ev["texto_idx"].isna().any():
        raise ValueError("Hay evidencias sin embedding: correr `python -m perfiles.embeddings`")
    ev["texto_idx"] = ev["texto_idx"].astype(int)
    ev = ev[["evidencia_id", "persona_id", "tipo_id", "texto_idx", "texto", "atributos"]]

    BUSQUEDA_DIR.mkdir(parents=True, exist_ok=True)
    archivo_bm25, archivo_vocab = BUSQUEDA_DIR / "bm25.npz", BUSQUEDA_DIR / "bm25_vocab.json"
    if archivo_vocab.exists() and json.loads(archivo_vocab.read_text(encoding="utf-8")).get("huella") == huella:
        bm25 = sparse.load_npz(archivo_bm25).tocsc()
        vocab = json.loads(archivo_vocab.read_text(encoding="utf-8"))["vocab"]
    else:
        bm25, vocab = _construir_bm25(textos["texto"].tolist())
        sparse.save_npz(archivo_bm25, bm25)
        archivo_vocab.write_text(json.dumps({"huella": huella, "vocab": vocab}, ensure_ascii=False), encoding="utf-8")

    por_tipo = {t: np.array(sorted(g["texto_idx"].unique())) for t, g in ev.groupby("tipo_id")}
    return Indice(textos=textos, V=V, bm25=bm25, vocab=vocab, ev=ev, textos_por_tipo=por_tipo,
                  personas=_personas(ev), huella=huella)


@lru_cache(maxsize=1)
def modelo_embedding():
    import torch
    from sentence_transformers import SentenceTransformer

    from busqueda.comun import MODELO_EMBEDDING

    return SentenceTransformer(MODELO_EMBEDDING, device="cuda" if torch.cuda.is_available() else "cpu")


def embeber(textos: list[str]) -> np.ndarray:
    return modelo_embedding().encode(textos, normalize_embeddings=True, convert_to_numpy=True).astype(np.float32)

