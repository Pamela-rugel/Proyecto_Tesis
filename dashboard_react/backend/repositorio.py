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
    """Todas las evidencias con sus atributos (JSON en texto), indexadas por persona_id."""
    partes = [pd.read_csv(f, usecols=["evidencia_id", "persona_id", "tipo_id", "texto", "atributos"])
              for f in sorted(EVIDENCIAS_DIR.glob("*/evidencias_*.csv"))]
    return pd.concat(partes, ignore_index=True).set_index("persona_id", drop=False).sort_index()


def evidencias_de(persona_id: int) -> pd.DataFrame:
    ev = evidencias()
    return ev.loc[[persona_id]] if persona_id in ev.index else ev.iloc[0:0]


def _es_espanol(idioma) -> bool:
    import unicodedata
    t = unicodedata.normalize("NFKD", str(idioma or "")).encode("ascii", "ignore").decode().upper()
    return "ESPANOL" in t


@lru_cache(maxsize=1)
def idiomas_por_persona() -> dict[int, list[dict]]:
    """Idiomas de cada persona (de sus evidencias de idiomas) con los niveles tal como se
    registraron. Hacen de "temas" de la dimensión Idiomas: son categorías exactas, no agrupadas.
    Comprensión no se incluye: en la fuente solo vale "BÁSICO" o vacío (posible valor por defecto,
    sin confirmar)."""
    salida: dict[int, list[dict]] = {}
    texto = lambda v: " / ".join(str(x).capitalize() for x in v) if v else None  # noqa: E731
    for f in sorted((EVIDENCIAS_DIR / "idiomas").glob("evidencias_*.csv")):
        for p, s in pd.read_csv(f, usecols=["persona_id", "atributos"]).itertuples(index=False):
            a = json.loads(s)
            salida.setdefault(int(p), []).append({
                "idioma": str(a.get("idioma") or "Sin nombre").capitalize(),
                "conversacion": texto(a.get("niveles_conversacion")), "lectura": texto(a.get("niveles_lectura")),
                "escritura": texto(a.get("niveles_escritura")), "mcer": " / ".join(a.get("niveles_mcer") or []) or None,
            })
    for lista in salida.values():
        lista.sort(key=lambda x: x["idioma"])
    return salida


@lru_cache(maxsize=1)
def registro_idiomas() -> dict[int, str]:
    """Qué registró cada persona en la fuente de idiomas, para no confundir la falta de información
    con la falta de idiomas extranjeros. Se lee de las evidencias de idiomas y de sus
    `registros_no_considerados.csv` (02_evidencias: español nativo, nivel 'Ninguna', idioma sin
    nombre). Valores:
      "extranjero"  tiene al menos una evidencia de un idioma distinto del español;
      "solo_espanol" todo lo que registró es español;
      "sin_validos" registró idiomas, pero ninguno válido (nivel 'Ninguna' o idioma sin nombre).
    Quien no está en el diccionario no aparece en la fuente de idiomas."""
    carpeta = EVIDENCIAS_DIR / "idiomas"
    idiomas: dict[int, list[tuple[str, bool]]] = {}  # persona -> [(idioma, es evidencia)]
    for f in sorted(carpeta.glob("evidencias_*.csv")):
        for p, a in pd.read_csv(f, usecols=["persona_id", "atributos"]).itertuples(index=False):
            idiomas.setdefault(int(p), []).append((json.loads(a).get("idioma"), True))
    nc = carpeta / "registros_no_considerados.csv"
    if nc.exists():
        for p, d in pd.read_csv(nc, usecols=["persona_id", "descripcion"]).itertuples(index=False):
            idiomas.setdefault(int(p), []).append((d, False))
    salida = {}
    for p, regs in idiomas.items():
        if any(ev and not _es_espanol(i) for i, ev in regs):
            salida[p] = "extranjero"
        elif all(_es_espanol(i) for i, _ in regs):
            salida[p] = "solo_espanol"
        else:
            salida[p] = "sin_validos"
    return salida


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


@lru_cache(maxsize=3)
def vecinos_dimension(ambito: str) -> pd.DataFrame:
    """Personas parecidas dentro de cada dimensión (listas "actividad" y "tema", DEC-061), indexadas
    por persona. Vacío si la versión es anterior."""
    ruta = version_actual() / ambito / "vecinos_dimension.parquet"
    if not ruta.exists():
        return pd.DataFrame(columns=["persona_id", "dimension", "lista", "rango", "vecino_id"]).set_index("persona_id", drop=False)
    return pd.read_parquet(ruta).set_index("persona_id", drop=False).sort_index()


@lru_cache(maxsize=3)
def temas_evidencia(ambito: str) -> pd.DataFrame:
    """Tema de cada evidencia y si se asignó por cercanía (DEC-061), indexado por persona."""
    ruta = version_actual() / ambito / "temas_evidencia.parquet"
    if not ruta.exists():
        return pd.DataFrame(columns=["persona_id", "dimension", "tema_id", "por_cercania"]).set_index("persona_id", drop=False)
    return pd.read_parquet(ruta).set_index("persona_id", drop=False).sort_index()


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
