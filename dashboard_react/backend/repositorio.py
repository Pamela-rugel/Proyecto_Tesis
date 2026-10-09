"""Acceso de solo lectura a los resultados persistidos del clustering y a las evidencias.

Una sola fuente de verdad: el backend no recalcula ni copia datos. Lee
    data/perfiles/clustering/actual.json -> <version>/  (resultado de `python -m perfiles.construir`)
    data/evidencias/*/evidencias_*.csv                   (evidencias de cada persona)
La regla "solo personas vigentes" se aplica al CONSULTAR (listas de personas), no se borra nada
de los datos: la vigencia viene de VIGENTE_ACTUALMENTE (DEC-023), copiada en personas.parquet por
el pipeline. De personas.parquet solo se usa el estado de cada persona (vigencia, tipo, cargo y
unidad actuales), no los grupos del clustering SNF.
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
AMBITOS = {"todos": "Todo el personal", "administrativos": "Personal administrativo", "docentes": "Personal docente"}


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
def evidencias() -> pd.DataFrame:
    partes = [pd.read_csv(f, usecols=["evidencia_id", "persona_id", "tipo_id", "texto"])
              for f in sorted(EVIDENCIAS_DIR.glob("*/evidencias_*.csv"))]
    return pd.concat(partes, ignore_index=True)


@lru_cache(maxsize=3)
def dimensiones(ambito: str) -> pd.DataFrame:
    """Intensidad por dimensión de evidencia (DEC-053). Vacío si la versión es anterior."""
    ruta = version_actual() / ambito / "dimensiones.parquet"
    return pd.read_parquet(ruta) if ruta.exists() else pd.DataFrame(columns=["persona_id", "dimension"])


@lru_cache(maxsize=3)
def micro_dimensiones(ambito: str) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(temas por persona, patrón por persona, fichas) de los microarquetipos por dimensión (DEC-055)."""
    d = version_actual() / ambito
    if not (d / "micro_dimensiones.json").exists():
        return pd.DataFrame(columns=["persona_id"]), pd.DataFrame(columns=["persona_id"]), {}
    return (pd.read_parquet(d / "temas_dimension.parquet"), pd.read_parquet(d / "patrones_dimension.parquet"),
            json.loads((d / "micro_dimensiones.json").read_text(encoding="utf-8")))


@lru_cache(maxsize=3)
def mapas_dimension(ambito: str) -> pd.DataFrame:
    """Coordenadas t-SNE (solo visualización) por dimensión: mapa de patrones y de temas."""
    ruta = version_actual() / ambito / "mapas_dimension.parquet"
    return pd.read_parquet(ruta) if ruta.exists() else pd.DataFrame(columns=["persona_id", "dimension", "mapa", "x", "y"])


@lru_cache(maxsize=3)
def perfil_conjunto(ambito: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(mapa t-SNE, vecinos) del perfil completo de cada persona (DEC-056)."""
    d = version_actual() / ambito
    if not (d / "perfil_conjunto_mapa.parquet").exists():
        vacio = pd.DataFrame(columns=["persona_id"])
        return vacio, pd.DataFrame(columns=["persona_id", "vecino_id", "distancia", "rango"])
    return pd.read_parquet(d / "perfil_conjunto_mapa.parquet"), pd.read_parquet(d / "perfil_conjunto_vecinos.parquet")


@lru_cache(maxsize=3)
def patrones_globales(ambito: str) -> tuple[pd.DataFrame, dict]:
    """(patrón global por persona, fichas) descubiertos sobre el perfil completo (DEC-057)."""
    d = version_actual() / ambito
    if not (d / "patrones_globales.json").exists():
        return pd.DataFrame(columns=["persona_id", "patron_global"]), {}
    return pd.read_parquet(d / "patrones_globales.parquet"), json.loads((d / "patrones_globales.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def definiciones_dimensiones() -> dict:
    ruta = version_actual() / "dimensiones.json"
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def as_records(df: pd.DataFrame) -> list[dict]:
    """Registros JSON-seguros (sin NaN ni tipos numpy)."""
    limpio = df.astype(object).where(pd.notna(df), None)
    salida = []
    for fila in limpio.to_dict("records"):
        salida.append({k: (v.item() if isinstance(v, np.generic) else v) for k, v in fila.items()})
    return salida
