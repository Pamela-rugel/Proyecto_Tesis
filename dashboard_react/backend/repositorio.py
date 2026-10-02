"""Acceso de solo lectura a los resultados persistidos del clustering y a las evidencias.

Una sola fuente de verdad: el backend no recalcula ni copia datos. Lee
    data/perfiles/clustering/actual.json -> <version>/  (resultado de `python -m perfiles.construir`)
    data/evidencias/*/evidencias_*.csv                   (evidencias de cada persona)
La regla "solo personas vigentes" se aplica al CONSULTAR (listas de integrantes, mapa), no se
borra nada de los datos: la vigencia viene de VIGENTE_ACTUALMENTE (DEC-023), copiada en
personas.parquet por el pipeline.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CLUSTERING_DIR = DATA_DIR / "perfiles" / "clustering"
EVIDENCIAS_DIR = DATA_DIR / "evidencias"
AMBITOS = ("todos", "administrativos", "docentes")


class SinClustering(Exception):
    pass


@lru_cache(maxsize=1)
def version_actual() -> Path:
    actual = CLUSTERING_DIR / "actual.json"
    if not actual.exists():
        raise SinClustering("No hay resultados de clustering: correr `python -m perfiles.construir`")
    return CLUSTERING_DIR / json.loads(actual.read_text(encoding="utf-8"))["version"]


@lru_cache(maxsize=1)
def manifest() -> dict:
    return json.loads((version_actual() / "manifest.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def estado_version() -> dict:
    """Compara las huellas de las evidencias actuales con las que produjeron el clustering."""
    registradas = manifest()["entradas"]["evidencias"]
    actuales = {}
    for f in sorted(EVIDENCIAS_DIR.glob("*/evidencias_*.csv")):
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for bloque in iter(lambda: fh.read(1 << 20), b""):
                h.update(bloque)
        actuales[str(f.relative_to(ROOT)).replace("\\", "/")] = h.hexdigest()[:16]
    distintos = sorted(k for k in set(registradas) | set(actuales) if registradas.get(k) != actuales.get(k))
    return {"version": manifest()["version"], "fecha": manifest()["fecha"], "actualizado": not distintos,
            "evidencias_cambiadas": distintos}


@lru_cache(maxsize=3)
def resumen(ambito: str) -> dict:
    return json.loads((version_actual() / ambito / "clusters.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=3)
def personas(ambito: str) -> pd.DataFrame:
    return pd.read_parquet(version_actual() / ambito / "personas.parquet")


@lru_cache(maxsize=1)
def evidencias_trayectoria() -> pd.DataFrame:
    """Evidencias de trayectoria con sus atributos (fechas y periodos), para la linea de tiempo."""
    return pd.concat([pd.read_csv(f, usecols=["persona_id", "tipo_id", "texto", "atributos"])
                      for f in sorted((EVIDENCIAS_DIR / "trayectoria").glob("evidencias_*.csv"))], ignore_index=True)


@lru_cache(maxsize=1)
def nombres() -> dict[int, str]:
    """Nombre completo por persona, leido EN VIVO del extracto institucional (decision de la
    usuaria, 2026-10-01). No se copia a data/perfiles ni a ninguna otra salida: solo se muestra
    en la vista. Se leen unicamente IDPERSONA, APELLIDOS y NOMBRES."""
    ruta = DATA_DIR / "raw" / "historialaboralpersonas.csv"
    if not ruta.exists():
        return {}
    d = pd.read_csv(ruta, usecols=["IDPERSONA", "APELLIDOS", "NOMBRES"], dtype=str).dropna(subset=["IDPERSONA"])
    d["nombre"] = (d["APELLIDOS"].fillna("").str.strip() + " " + d["NOMBRES"].fillna("").str.strip()).str.strip().str.title()
    d = d[d["nombre"] != ""].drop_duplicates("IDPERSONA", keep="last")
    return dict(zip(d["IDPERSONA"].astype(float).astype(int), d["nombre"]))


def nombre(persona_id: int) -> str:
    return nombres().get(int(persona_id), "Nombre no disponible")


def con_nombres(df: pd.DataFrame, columna_id: str = "persona_id") -> pd.DataFrame:
    df = df.copy()
    df.insert(1, "nombre", df[columna_id].map(lambda i: nombre(i)))
    return df


@lru_cache(maxsize=1)
def vista_estructurada() -> pd.DataFrame:
    return pd.read_parquet(version_actual() / "vista_estructurada.parquet").set_index("persona_id")


@lru_cache(maxsize=1)
def evidencias() -> pd.DataFrame:
    partes = [pd.read_csv(f, usecols=["evidencia_id", "persona_id", "tipo_id", "texto"])
              for f in sorted(EVIDENCIAS_DIR.glob("*/evidencias_*.csv"))]
    return pd.concat(partes, ignore_index=True)


def etiquetas(ambito: str) -> dict[int, str]:
    return {c["cluster"]: c["etiqueta"] for c in resumen(ambito)["clusters"]}


def z_ambito(ambito: str) -> pd.DataFrame:
    """Variables estructuradas estandarizadas dentro del ambito (igual que en el clustering)."""
    x = vista_estructurada().loc[personas(ambito)["persona_id"]]
    desv = x.std()
    return ((x - x.mean()) / desv.where(desv > 0, 1)).loc[:, desv > 0]


def as_records(df: pd.DataFrame) -> list[dict]:
    """Registros JSON-seguros (sin NaN ni tipos numpy)."""
    limpio = df.astype(object).where(pd.notna(df), None)
    salida = []
    for fila in limpio.to_dict("records"):
        salida.append({k: (v.item() if isinstance(v, np.generic) else v) for k, v in fila.items()})
    return salida
