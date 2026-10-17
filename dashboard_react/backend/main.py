"""
API FastAPI del dashboard de perfiles de personal ESPOL.

Expone los perfiles por DIMENSIÓN de evidencia (DEC-053/055) calculados fuera de línea por
`python -m perfiles.construir` y persistidos en data/perfiles/clustering/<version>/:
- intensidad de cada persona en cada dimensión (percentil dentro del ámbito);
- temas y patrones de actividad descubiertos dentro de cada dimensión.
La API solo LEE (ver `repositorio.py`): no recalcula nada ni duplica datos. Los grupos del
clustering multivista (SNF) siguen en disco pero ya no se muestran (decisión de la usuaria).

Ejecutar con (desde dashboard_react/backend/):
    d:\\Proyecto_Tesis\\.venv\\Scripts\\python -m uvicorn main:app --reload --port 8001
"""

from __future__ import annotations

import copy
import json
import threading
import unicodedata
from contextlib import asynccontextmanager
from difflib import SequenceMatcher
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import repositorio as repo


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI):
    """Precarga en segundo plano los datos reales de las personas (unos segundos) y el índice y los
    modelos de la búsqueda (~30 s en GPU, más en CPU) para que la primera ficha y la primera búsqueda
    no tengan que esperarlos; la API responde mientras tanto."""
    def precargar():
        try:
            _componentes_crudos()
        except Exception as e:  # noqa: BLE001 — la ficha sigue sin los datos reales
            print(f"Precarga de los datos reales falló: {e}", flush=True)
        try:
            from busqueda.indice import cargar_indice, modelo_embedding
            from busqueda.rerank import modelo_reranker

            cargar_indice()
            modelo_embedding()
            modelo_reranker()
        except Exception as e:  # noqa: BLE001 — la API sigue funcionando sin la búsqueda precargada
            print(f"Precarga de la búsqueda falló: {e}", flush=True)

    threading.Thread(target=precargar, daemon=True).start()
    yield


app = FastAPI(title="Perfiles ESPOL API", lifespan=_ciclo_de_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ambito(ambito: str) -> str:
    if ambito not in repo.AMBITOS:
        raise HTTPException(404, f"Ámbito desconocido: {ambito}. Use uno de {repo.AMBITOS}")
    try:
        repo.version_actual()
    except repo.SinClustering as e:
        raise HTTPException(503, str(e)) from e
    return ambito


# ------------------------------------------------------------------ patrones descritos en palabras
NOMBRE_AMBITO = {"todos": "todo el personal", "administrativos": "el personal administrativo", "docentes": "el personal docente"}
# mismos cortes que la etiqueta calculada al construir (micro_dimensiones.UMBRAL_Z y "muy alto")
CORTE_MAS, CORTE_MUCHO = 0.4, 1.5
COMPARACIONES = [("mucho_mas", "Mucho más"), ("mas", "Más"), ("menos", "Menos"), ("mucho_menos", "Mucho menos")]


def _formato_componente(componente: str, descripcion: str) -> str:
    """Cómo mostrar el valor: `porcentaje` para proporciones y marcas sí/no (su promedio es la parte
    de las personas que la tiene), `nivel` para escalas ordinales y `numero` para conteos y razones."""
    if descripcion.startswith(("Proporción", "Tiene ")) or componente == "posgrado_en_curso":
        return "porcentaje"
    if descripcion.startswith("Nivel"):
        return "nivel"
    return "numero"


def _comparacion(z: float) -> str:
    """Cuánto se aleja el grupo del promedio de la dimensión, en palabras (z del centroide)."""
    if z >= CORTE_MUCHO:
        return "mucho_mas"
    if z >= CORTE_MAS:
        return "mas"
    if z <= -CORTE_MUCHO:
        return "mucho_menos"
    if z <= -CORTE_MAS:
        return "menos"
    return "similar"


def _frase_componente(descripcion: str) -> str:
    """"Tiene título del exterior" -> "título del exterior"; sin aclaraciones entre paréntesis."""
    f = descripcion.split(" (")[0].split(":")[0]
    if f.startswith("Tiene "):
        f = f[len("Tiene "):]
    return f[:1].lower() + f[1:]


def _enumerar(xs: list[str], maximo: int = 3) -> str:
    """"a, b y c"; con más de `maximo`, los primeros y "N más" (el detalle va en los componentes)."""
    if len(xs) > maximo:
        xs = xs[:maximo] + [f"{len(xs) - maximo} más"]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def _describir_patron(componentes: list[dict], nombre_dimension: str) -> str:
    """P. ej. "Más que el promedio de Formación en títulos de cuarto nivel y nivel máximo de
    formación; menos en título del exterior". Dice frente a qué se compara; los valores van aparte."""
    partes = []
    for clave, texto in COMPARACIONES:
        xs = [_frase_componente(c["descripcion"]) for c in sorted(componentes, key=lambda c: -abs(c["z"])) if c["comparacion"] == clave]
        if xs:
            inicio = f"{texto} que el promedio de {nombre_dimension} en" if not partes else f"{texto.lower()} en"
            partes.append(f"{inicio} {_enumerar(xs)}")
    return "; ".join(partes) if partes else f"Cerca del promedio de {nombre_dimension} en todo"


def _media_dimension(patrones: list[dict], componente: str, en_log: bool) -> float:
    """Promedio de la dimensión a partir de los promedios de sus patrones (ponderados por tamaño),
    en la misma escala que `media_grupo` (en las variables en log, la media se toma en log)."""
    pares = [(p["tamano"], next(c["media_grupo"] for c in p["componentes"] if c["componente"] == componente)) for p in patrones]
    n = sum(t for t, _ in pares)
    if en_log:
        return float(np.expm1(sum(t * np.log1p(m) for t, m in pares) / n))
    return float(sum(t * m for t, m in pares) / n)


@lru_cache(maxsize=3)
def _fichas(ambito: str) -> dict:
    """Fichas de temas y patrones por dimensión (DEC-055) con cada patrón descrito en palabras. A
    cada componente se le agrega el promedio de la dimensión (`media_dimension`), cómo se compara el
    grupo con él (`comparacion`) y en qué unidad mostrarlo (`formato`); la etiqueta calculada al
    construir ("Alto: …") queda en `etiqueta_tecnica`. Solo presentación: no cambia los grupos."""
    _, _, fichas = repo.micro_dimensiones(ambito)
    fichas = copy.deepcopy(fichas)
    defs = repo.definiciones_dimensiones()
    for dim, info in fichas.items():
        patrones = (info.get("patrones") or {}).get("patrones", [])
        nombre = defs.get(dim, {}).get("nombre", dim)
        for p in patrones:
            for c in p["componentes"]:
                c["formato"] = _formato_componente(c["componente"], c["descripcion"])
                c["media_dimension"] = round(_media_dimension(patrones, c["componente"], "(log" in c["descripcion"]), 2)
                c["comparacion"] = _comparacion(c["z"])
            p["etiqueta_tecnica"] = p["etiqueta"]
            p["etiqueta"] = _describir_patron(p["componentes"], nombre)
    return fichas



# ------------------------------------------------------------------ patrones globales descritos en palabras
UMBRAL_PUNTOS_GLOBAL = 15   # mismo corte que al construir (perfil_conjunto.UMBRAL_PUNTOS)


def _distintivos_globales(dims: list[dict], fichas_dim: dict) -> list[dict]:
    """Patrones por dimensión mucho más frecuentes en el grupo que en su referencia (mismo criterio
    que al construir: lift >= 1,5, >= 50 % de quienes tienen evidencias y >= 30 % del grupo), con la
    etiqueta del patrón para mostrarlo como "P2 · Investigación"."""
    salida = []
    for e in dims:
        pf = e.get("patron_frecuente")
        if not pf or (pf.get("lift") or 0) < 1.5 or pf["proporcion"] < 0.5 or e["con_evidencia"] * pf["proporcion"] < 0.3:
            continue
        lista = ((fichas_dim.get(e["dimension"]) or {}).get("patrones") or {}).get("patrones", [])
        salida.append({"dimension": e["dimension"], "nombre": e["nombre"], "patron": pf["patron"],
                       "etiqueta_patron": lista[pf["patron"]]["etiqueta"] if pf["patron"] < len(lista) else None,
                       "proporcion": pf["proporcion"], "proporcion_referencia": pf["proporcion_referencia"], "lift": pf["lift"]})
    return sorted(salida, key=lambda x: -(x["lift"] or 0))[:3]


def _de(s: str) -> str:
    """"de el personal docente" -> "del personal docente"."""
    return f"del {s[3:]}" if s.startswith("el ") else f"de {s}"


def _describir_global(dims: list[dict], referencia: str, sin_diferencias: str) -> str:
    """P. ej. "Por encima del promedio de todo el personal en Investigación y Tesis dirigidas; por
    debajo en Idiomas" (intensidad media del grupo frente a la de su referencia, >= 15 puntos)."""
    orden = sorted(dims, key=lambda e: -e["diferencia"])
    altos = [e["nombre"] for e in orden if e["diferencia"] >= UMBRAL_PUNTOS_GLOBAL]
    bajos = [e["nombre"] for e in reversed(orden) if e["diferencia"] <= -UMBRAL_PUNTOS_GLOBAL]
    partes = []
    if altos:
        partes.append(f"Por encima del promedio {_de(referencia)} en {_enumerar(altos)}")
    if bajos:
        partes.append(f"{'por' if partes else 'Por'} debajo{'' if partes else f' del promedio {_de(referencia)}'} en {_enumerar(bajos)}")
    return "; ".join(partes) if partes else sin_diferencias


@lru_cache(maxsize=3)
def _globales(ambito: str) -> tuple[pd.DataFrame, dict]:
    """Patrones globales (DEC-057) y microarquetipos (DEC-058) con la etiqueta en palabras (la
    calculada al construir queda en `etiqueta_tecnica`) y sus patrones por dimensión distintivos
    (`patrones_distintivos`), para mostrarlos con su significado. Solo presentación."""
    glob, fichas = repo.patrones_globales(ambito)
    fichas = copy.deepcopy(fichas)
    fichas_dim = _fichas(ambito)
    nombre_ambito = NOMBRE_AMBITO.get(ambito, ambito)
    for f in fichas.get("patrones", []):
        f["etiqueta_tecnica"] = f["etiqueta"]
        f["etiqueta"] = _describir_global(f.get("dimensiones", []), nombre_ambito, "Cerca del promedio en todas las dimensiones")
        f["patrones_distintivos"] = _distintivos_globales(f.get("dimensiones", []), fichas_dim)
        for m in (f.get("microarquetipos") or {}).get("lista", []):
            m["etiqueta_tecnica"] = m["etiqueta"]
            m["etiqueta"] = _describir_global(m.get("dimensiones", []), f"su Patrón global {f['id'] + 1}",
                                              "Como su patrón global, sin diferencias marcadas")
            m["patrones_distintivos"] = _distintivos_globales(m.get("dimensiones", []), fichas_dim)
    return glob, fichas


def _dimension(ambito: str, dimension: str) -> dict:
    fichas = _fichas(_ambito(ambito))
    if dimension not in fichas:
        raise HTTPException(404, f"Dimensión desconocida o sin resultados en esta versión: {dimension}")
    return fichas[dimension]


def _norm(x) -> str:
    """Texto sin tildes y en minúsculas, para comparar nombres."""
    return unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()


def _puntaje(terminos: list[str], texto: str) -> float:
    """Cada término debe aparecer en `texto` (ya normalizado); si no aparece tal cual, se acepta una
    palabra parecida (errores de tipeo como "ciclia" -> "cecilia"). 0 = no coincide; más alto, mejor."""
    palabras = texto.replace("|", " ").split()
    total = 0.0
    for x in terminos:
        if x in texto:
            total += 1.0
            continue
        mejor = max((SequenceMatcher(None, x, w).ratio() for w in palabras), default=0.0)
        if len(x) < 4 or mejor < 0.75:
            return 0.0
        total += mejor
    return total


ORDEN_LISTA = "^(grupo|inverso|azar)$"


def _pagina_personas(x: pd.DataFrame, q: str | None, pagina: int, por_pagina: int, orden: str = "grupo",
                     semilla: int = 0) -> dict:
    """Una página de una lista de personas YA ordenada. `posicion` es el lugar de cada persona en
    ese orden y se conserva al filtrar o reordenar; `orden` = `inverso` empieza por las últimas
    (p. ej. las menos parecidas a la representante) y `azar`, una muestra al azar reproducible con
    `semilla` (para revisar el grupo sin quedarse con los extremos). Con `q`, solo quienes coinciden
    por nombre (primero las coincidencias exactas). `total_filtrado` cuenta las coincidencias; si la
    página pedida ya no existe (p. ej. el grupo se achicó), se devuelve la última."""
    x = repo.con_nombres(x.assign(posicion=range(1, len(x) + 1)))
    if orden == "inverso":
        x = x.iloc[::-1]
    elif orden == "azar":
        x = x.sample(frac=1, random_state=semilla)
    if q and q.strip():
        terminos = _norm(q).split()
        p = x["nombre"].map(lambda n: _puntaje(terminos, _norm(n)))
        x = x.assign(_p=p)[p > 0].sort_values(["_p", "posicion"], ascending=[False, True]).drop(columns="_p")
    paginas = max(1, -(-len(x) // por_pagina))
    pagina = min(pagina, paginas)
    trozo = x.iloc[(pagina - 1) * por_pagina: pagina * por_pagina]
    return {"q": q or None, "orden": orden, "total_filtrado": len(x), "pagina": pagina, "por_pagina": por_pagina,
            "paginas": paginas, "personas": repo.as_records(trozo.round(4))}


@app.get("/api/health")
def health() -> dict:
    evidencias = sorted(p.parent.name for p in repo.EVIDENCIAS_DIR.glob("*/evidencias_*.csv"))
    try:
        clustering = repo.estado_version()
    except repo.SinClustering as e:
        clustering = {"version": None, "mensaje": str(e)}
    return {"estado": "ok", "carpetas_de_evidencias": evidencias, "clustering": clustering}


@app.get("/api/ambitos")
def ambitos() -> dict:
    _ambito("todos")
    m = repo.manifest()
    salida = []
    for a, nombre in repo.AMBITOS.items():
        p = repo.personas(a)
        salida.append({"ambito": a, "nombre": nombre, "n_personas": len(p), "n_vigentes": int(p["vigente"].sum())})
    return {"version": m["version"], "fecha": m["fecha"], "estado": repo.estado_version(), "ambitos": salida}


@app.get("/api/dimensiones/{ambito}")
def dimensiones(ambito: str) -> dict:
    """Resumen de cada dimensión del ámbito: cuántas personas tienen evidencias y cuántos temas y
    patrones de actividad se descubrieron."""
    fichas = _fichas(_ambito(ambito))
    p = repo.personas(ambito)
    vigentes = set(p.loc[p["vigente"], "persona_id"])
    d = repo.dimensiones(ambito)
    con_ev = d[d["n_evidencias"] > 0]
    salida = []
    for dim, cfg in repo.definiciones_dimensiones().items():
        info = fichas.get(dim, {})
        ids = con_ev.loc[con_ev["dimension"] == dim, "persona_id"]
        salida.append({"dimension": dim, "nombre": cfg["nombre"], "n_personas": int(len(ids)),
                       "n_vigentes": int(ids.isin(vigentes).sum()), "n_personas_ambito": len(p),
                       "n_vigentes_ambito": len(vigentes),
                       "k_temas": (info.get("temas") or {}).get("k", 0), "k_patrones": (info.get("patrones") or {}).get("k", 0),
                       "nota": info.get("nota")})
    return {"ambito": ambito, "dimensiones": salida}


@app.get("/api/dimensiones/{ambito}/{dimension}")
def dimension(ambito: str, dimension: str) -> dict:
    """Temas y patrones de actividad descubiertos en la dimensión (DEC-055), con el nombre del
    representante vigente de cada patrón (leído en vivo) y la definición de sus componentes."""
    info = copy.deepcopy(_dimension(ambito, dimension))
    for f in (info.get("patrones") or {}).get("patrones", []):
        f["representante_nombre"] = repo.nombre(f["representante_id"]) if f.get("representante_id") else None
    return {"ambito": ambito, "dimension": dimension, "definicion": repo.definiciones_dimensiones().get(dimension), **info}


@app.get("/api/dimensiones/{ambito}/{dimension}/personas")
def personas_dimension(ambito: str, dimension: str, patron: int | None = Query(None), tema: int | None = Query(None),
                       solo_vigentes: bool = Query(True), q: str | None = Query(None),
                       pagina: int = Query(1, ge=1), por_pagina: int = Query(25, ge=1, le=200),
                       orden: str = Query("grupo", pattern=ORDEN_LISTA), semilla: int = Query(0)) -> dict:
    """Personas con evidencias en la dimensión, opcionalmente de un patrón o con un tema, paginadas
    y opcionalmente filtradas por nombre (`q`). Orden: afinidad con el patrón, proporción de sus
    evidencias en el tema, o intensidad. `total` es el tamaño del grupo, sin el filtro por nombre."""
    _dimension(ambito, dimension)
    p = repo.personas(ambito)[["persona_id", "vigente", "cargo_actual", "unidad_actual", "tipo_empleado"]]
    d = repo.dimensiones(ambito)
    d = d[(d["dimension"] == dimension) & (d["n_evidencias"] > 0)][["persona_id", "intensidad", "n_evidencias"]]
    temas, patrones, _ = repo.micro_dimensiones(ambito)
    cols_pat = ["persona_id", "patron", "afinidad_1", "mixto"] + (["similitud_representante"] if "similitud_representante" in patrones.columns else [])
    pat = patrones[patrones["dimension"] == dimension][cols_pat] if len(patrones) else None
    x = d.merge(p, on="persona_id")
    if pat is not None:
        x = x.merge(pat, on="persona_id", how="left")
    criterio = "intensidad"
    if patron is not None:
        if pat is None:
            raise HTTPException(404, "La dimensión no tiene patrones")
        x = x[x["patron"] == patron]
        criterio = "similitud_representante" if "similitud_representante" in x.columns else "afinidad_1"
    if tema is not None:
        t = temas[(temas["dimension"] == dimension) & (temas["tema_id"] == tema)][["persona_id", "proporcion"]]
        x = x.merge(t, on="persona_id")
        criterio = "proporcion"
    if solo_vigentes:
        x = x[x["vigente"]]
    x = x.sort_values([criterio, "intensidad"], ascending=False)
    return {"ambito": ambito, "dimension": dimension, "patron": patron, "tema": tema, "solo_vigentes": solo_vigentes,
            "total": len(x), **_pagina_personas(x, q, pagina, por_pagina, orden, semilla)}


@app.get("/api/dimensiones/{ambito}/{dimension}/mapa")
def mapa_dimension(ambito: str, dimension: str, tipo: str = Query("patrones"), solo_vigentes: bool = Query(True)) -> dict:
    """Puntos t-SNE de la dimensión (solo para visualizar): `tipo=patrones` usa las variables con
    que se formaron los patrones; `tipo=temas`, el contenido de sus evidencias. Cada punto trae su
    patrón y su tema principal."""
    if tipo not in ("patrones", "temas"):
        raise HTTPException(400, "tipo debe ser patrones o temas")
    _dimension(ambito, dimension)
    m = repo.mapas_dimension(ambito)
    m = m[(m["dimension"] == dimension) & (m["mapa"] == tipo)][["persona_id", "x", "y"]]
    if m.empty:
        return {"ambito": ambito, "dimension": dimension, "tipo": tipo, "puntos": []}
    p = repo.personas(ambito)[["persona_id", "vigente", "cargo_actual", "unidad_actual"]]
    d = repo.dimensiones(ambito)
    d = d[d["dimension"] == dimension][["persona_id", "intensidad"]]
    temas, patrones, _ = repo.micro_dimensiones(ambito)
    x = m.merge(p, on="persona_id").merge(d, on="persona_id", how="left")
    if len(patrones):
        x = x.merge(patrones[patrones["dimension"] == dimension][["persona_id", "patron"]], on="persona_id", how="left")
    if len(temas):
        t = temas[temas["dimension"] == dimension].sort_values(["persona_id", "proporcion", "tema_id"], ascending=[True, False, True])
        t = t.drop_duplicates("persona_id")[["persona_id", "tema_id", "proporcion"]].rename(columns={"tema_id": "tema", "proporcion": "proporcion_tema"})
        x = x.merge(t, on="persona_id", how="left")
    if solo_vigentes:
        x = x[x["vigente"]]
    return {"ambito": ambito, "dimension": dimension, "tipo": tipo, "solo_vigentes": solo_vigentes,
            "puntos": repo.as_records(repo.con_nombres(x.round(3)))}


@app.get("/api/perfil/{ambito}/mapa")
def mapa_perfil(ambito: str, dimension: str | None = Query(None), solo_vigentes: bool = Query(True)) -> dict:
    """Mapa t-SNE del perfil completo (todas las dimensiones, DEC-056). Con `dimension`, cada punto
    trae además su intensidad y su patrón en esa dimensión (para colorear)."""
    m, _ = repo.perfil_conjunto(_ambito(ambito))
    if m.empty:
        return {"ambito": ambito, "puntos": []}
    x = m.merge(repo.personas(ambito)[["persona_id", "vigente", "cargo_actual", "unidad_actual"]], on="persona_id")
    if dimension:
        d = repo.dimensiones(ambito)
        x = x.merge(d[d["dimension"] == dimension][["persona_id", "intensidad"]], on="persona_id", how="left")
        _, patrones, _ = repo.micro_dimensiones(ambito)
        if len(patrones):
            x = x.merge(patrones[patrones["dimension"] == dimension][["persona_id", "patron"]], on="persona_id", how="left")
    glob, _ = repo.patrones_globales(ambito)
    if len(glob):
        x = x.merge(glob[["persona_id", "patron_global", "micro"]].rename(columns={"micro": "micro_global"}), on="persona_id", how="left")
    if solo_vigentes:
        x = x[x["vigente"]]
    return {"ambito": ambito, "dimension": dimension, "puntos": repo.as_records(repo.con_nombres(x.round(3)))}


@app.get("/api/perfil/{ambito}/patrones")
def patrones_globales(ambito: str) -> dict:
    """Patrones globales descubiertos sobre el perfil completo (DEC-057) y sus microarquetipos
    (DEC-058), con el nombre de su persona más representativa (vigente, leída en vivo)."""
    _, fichas = _globales(_ambito(ambito))
    salida = copy.deepcopy(fichas)
    for f in salida.get("patrones", []):
        f["representante_nombre"] = repo.nombre(f["representante_id"]) if f.get("representante_id") else None
        for m in (f.get("microarquetipos") or {}).get("lista", []):
            m["representante_nombre"] = repo.nombre(m["representante_id"]) if m.get("representante_id") else None
    return {"ambito": ambito, **salida}


@app.get("/api/perfil/{ambito}/patrones/{patron}/dimension/{dimension}")
def reparto_en_dimension(ambito: str, patron: int, dimension: str, micro: int | None = Query(None)) -> dict:
    """Cómo se reparten entre los patrones de una dimensión las personas de un patrón global (o de
    uno de sus microarquetipos) que tienen evidencias en ella, frente a su referencia: todo el ámbito
    para un patrón global; su patrón global para un microarquetipo."""
    glob, _ = repo.patrones_globales(_ambito(ambito))
    info = _dimension(ambito, dimension)
    k = len((info.get("patrones") or {}).get("patrones", []))
    grupo = glob[glob["patron_global"] == patron]
    referencia = glob
    if micro is not None:
        referencia, grupo = grupo, grupo[grupo["micro"] == micro]
    pat = _patrones_de(ambito, dimension)["patron"]

    def reparto(ids: pd.Series) -> tuple[pd.Series, int]:
        v = pat.reindex(ids.to_numpy()).dropna().astype(int)
        return v.value_counts(), len(v)

    en_grupo, n_grupo = reparto(grupo["persona_id"])
    en_ref, n_ref = reparto(referencia["persona_id"])
    return {"ambito": ambito, "patron": patron, "micro": micro, "dimension": dimension,
            "n_grupo": int(len(grupo)), "con_evidencia": n_grupo, "n_referencia_con_evidencia": n_ref,
            "patrones": [{"patron": j, "n": int(en_grupo.get(j, 0)),
                          "proporcion": round(float(en_grupo.get(j, 0)) / n_grupo, 3) if n_grupo else 0.0,
                          "proporcion_referencia": round(float(en_ref.get(j, 0)) / n_ref, 3) if n_ref else 0.0}
                         for j in range(k)]}


@app.get("/api/perfil/{ambito}/personas")
def personas_patron_global(ambito: str, patron: int = Query(...), micro: int | None = Query(None),
                           solo_vigentes: bool = Query(True), q: str | None = Query(None),
                           pagina: int = Query(1, ge=1), por_pagina: int = Query(25, ge=1, le=200),
                           orden: str = Query("grupo", pattern=ORDEN_LISTA), semilla: int = Query(0)) -> dict:
    """Personas de un patrón global (o de uno de sus microarquetipos), ordenadas por similitud con
    su persona representativa (100 % = la representante; 0 % = la más distinta del grupo), paginadas
    y opcionalmente filtradas por nombre (`q`). `total` es el tamaño del grupo, sin ese filtro."""
    glob, _ = repo.patrones_globales(_ambito(ambito))
    x = glob[glob["patron_global"] == patron]
    if micro is not None:
        x = x[x["micro"] == micro]
        x = x.assign(similitud=x["similitud_representante_micro"], es_rep=x["es_representante_micro"], afinidad=x["micro_afinidad"],
                     entre_dos=x["micro_mixto"])
    else:
        x = x.assign(similitud=x["similitud_representante"], es_rep=x["es_representante"], afinidad=x["afinidad_1"], entre_dos=x["mixto"])
    x = x[["persona_id", "similitud", "es_rep", "afinidad", "entre_dos", "micro"]]
    x = x.merge(repo.personas(ambito)[["persona_id", "vigente", "cargo_actual", "unidad_actual"]], on="persona_id")
    if solo_vigentes:
        x = x[x["vigente"]]
    x = x.sort_values(["similitud", "afinidad"], ascending=False, na_position="last")
    return {"ambito": ambito, "patron": patron, "micro": micro, "total": len(x), **_pagina_personas(x, q, pagina, por_pagina, orden, semilla)}


def _patron_global_persona(ambito: str, persona_id: int) -> dict | None:
    """Patrón global y microarquetipo de la persona, con su similitud con cada representante."""
    glob, fichas = _globales(ambito)
    f = glob[glob["persona_id"] == persona_id]
    if f.empty:
        return None
    r = f.iloc[0]
    lista = fichas.get("patrones", [])
    ficha = lista[int(r["patron_global"])]
    salida = {"patron": int(r["patron_global"]), "etiqueta": ficha["etiqueta"],
              "afinidad": float(r["afinidad_1"]), "mixto": bool(r["mixto"]), "segundo": int(r["patron_global_2"]),
              "segundo_etiqueta": lista[int(r["patron_global_2"])]["etiqueta"], "tamano": ficha["tamano"],
              "similitud_representante": None if pd.isna(r["similitud_representante"]) else float(r["similitud_representante"]),
              "es_representante": bool(r["es_representante"]),
              "representante_id": ficha.get("representante_id"),
              "representante_nombre": repo.nombre(ficha["representante_id"]) if ficha.get("representante_id") else None,
              "micro": None}
    micros = (ficha.get("microarquetipos") or {}).get("lista", [])
    if "micro" in r and r["micro"] >= 0 and micros:
        m = micros[int(r["micro"])]
        salida["micro"] = {"micro": int(r["micro"]), "codigo": m["codigo"], "etiqueta": m["etiqueta"], "tamano": m["tamano"],
                           "mixto": bool(r["micro_mixto"]),
                           "similitud_representante": None if pd.isna(r["similitud_representante_micro"]) else float(r["similitud_representante_micro"]),
                           "es_representante": bool(r["es_representante_micro"]),
                           "representante_id": m.get("representante_id"),
                           "representante_nombre": repo.nombre(m["representante_id"]) if m.get("representante_id") else None}
    return salida


def _parecidos(ambito: str, persona_id: int, n: int = 8) -> list[dict]:
    """Personas VIGENTES con el perfil completo más parecido (vecinos más cercanos, DEC-056) y qué
    comparten: dimensiones donde ambas tienen intensidad >= 50, indicando si siguen el mismo patrón.
    Sin puntajes de similitud: solo el orden y lo que comparten."""
    _, vecinos = repo.perfil_conjunto(ambito)
    v = vecinos[vecinos["persona_id"] == persona_id].sort_values("rango")
    if v.empty:
        return []
    p = repo.personas(ambito).set_index("persona_id")
    v = v[v["vecino_id"].map(lambda i: bool(p.at[i, "vigente"]) if i in p.index else False)].head(n)
    d = repo.dimensiones(ambito)
    _, patrones, _ = repo.micro_dimensiones(ambito)
    nombres = {k: c["nombre"] for k, c in repo.definiciones_dimensiones().items()}
    ids = [persona_id, *v["vecino_id"].tolist()]
    inten = d[d["persona_id"].isin(ids)].pivot(index="persona_id", columns="dimension", values="intensidad")
    pat = (patrones[patrones["persona_id"].isin(ids)].pivot(index="persona_id", columns="dimension", values="patron")
           if len(patrones) else pd.DataFrame())
    salida = []
    for r in v.itertuples():
        comparte = []
        for dim in inten.columns:
            if inten.at[persona_id, dim] >= 50 and inten.at[r.vecino_id, dim] >= 50:
                a = pat.at[persona_id, dim] if dim in pat.columns and persona_id in pat.index else None
                b = pat.at[r.vecino_id, dim] if dim in pat.columns and r.vecino_id in pat.index else None
                mismo = a is not None and b is not None and not pd.isna(a) and a == b
                comparte.append({"dimension": dim, "nombre": nombres.get(dim, dim),
                                 "mismo_patron": bool(mismo), "patron": int(a) if mismo else None})
        comparte.sort(key=lambda c: (not c["mismo_patron"], c["nombre"]))
        salida.append({"persona_id": int(r.vecino_id), "nombre": repo.nombre(r.vecino_id), "rango": int(r.rango),
                       "cargo_actual": p.at[r.vecino_id, "cargo_actual"], "comparte": comparte})
    return salida


@app.get("/api/personas/buscar")
def buscar(ambito: str = Query("todos"), q: str = Query(..., min_length=2), solo_vigentes: bool = Query(True)) -> dict:
    """Busca personas del ámbito por nombre, cargo o unidad (sin distinguir tildes ni mayúsculas).
    Primero las coincidencias exactas (ver `_puntaje`)."""
    p = repo.con_nombres(repo.personas(_ambito(ambito)))
    if solo_vigentes:
        p = p[p["vigente"]]
    texto = (p["nombre"].map(_norm) + " | " + p["cargo_actual"].map(_norm) + " | " + p["unidad_actual"].map(_norm))
    terminos = _norm(q).split()
    puntos = texto.map(lambda t: _puntaje(terminos, t))
    m = p.assign(_p=puntos)[puntos > 0].sort_values("_p", ascending=False).head(30)
    return {"resultados": [{"persona_id": int(r.persona_id), "nombre": r.nombre, "cargo_actual": r.cargo_actual,
                            "unidad_actual": r.unidad_actual} for r in m.itertuples()]}


@app.get("/api/personas/{persona_id}")
def persona(persona_id: int, ambito: str = Query("todos")) -> dict:
    """Estado de la persona, su intensidad, patrón y temas en cada dimensión, y sus evidencias."""
    p = repo.personas(_ambito(ambito))
    fila = p[p["persona_id"] == persona_id]
    if fila.empty:
        raise HTTPException(404, f"La persona {persona_id} no está en el ámbito {ambito}")
    f = repo.as_records(fila)[0]
    ev = repo.evidencias()
    ev = ev[ev["persona_id"] == persona_id]
    evidencias = [{"tipo_id": t, "n": len(g), "textos": g["texto"].tolist()[:40]} for t, g in ev.groupby("tipo_id")]
    return {
        "persona_id": persona_id, "ambito": ambito, "nombre": repo.nombre(persona_id),
        "estado": {k: f[k] for k in ("tipo_empleado", "vigente", "cargo_actual", "unidad_actual")},
        "dimensiones": _dimensiones_persona(ambito, persona_id),
        "patron_global": _patron_global_persona(ambito, persona_id),
        "parecidos": _parecidos(ambito, persona_id),
        "evidencias": sorted(evidencias, key=lambda x: -x["n"]),
    }


def _dimensiones_persona(ambito: str, persona_id: int) -> list[dict]:
    """Intensidad (percentil 0-100 dentro del ámbito) en cada dimensión con el aporte normalizado
    de cada componente (DEC-053), su patrón de actividad y sus temas principales (DEC-055).
    Ordenadas de mayor a menor intensidad."""
    d = repo.dimensiones(ambito)
    defs = repo.definiciones_dimensiones()
    temas, patrones, _ = repo.micro_dimensiones(ambito)
    fichas = _fichas(ambito)
    temas = temas[temas["persona_id"] == persona_id]
    patrones = patrones[patrones["persona_id"] == persona_id].set_index("dimension") if len(patrones) else patrones
    salida = []
    for r in repo.as_records(d[d["persona_id"] == persona_id]):
        dim = r["dimension"]
        cfg = defs.get(dim, {})
        comps = cfg.get("componentes", {})
        info = fichas.get(dim, {})
        temas_dim = (info.get("temas") or {}).get("temas", [])
        mis_temas = [{"tema": int(t["tema_id"]), "etiqueta": temas_dim[int(t["tema_id"])]["etiqueta"], "proporcion": float(t["proporcion"])}
                     for t in repo.as_records(temas[temas["dimension"] == dim].sort_values("proporcion", ascending=False).head(3))]
        patron = None
        if dim in getattr(patrones, "index", []):
            f = patrones.loc[dim]
            lista = (info.get("patrones") or {}).get("patrones", [])
            patron = {"patron": int(f["patron"]), "etiqueta": lista[int(f["patron"])]["etiqueta"], "afinidad": float(f["afinidad_1"]),
                      "mixto": bool(f["mixto"]), "segundo": lista[int(f["patron_2"])]["etiqueta"],
                      "tamano": lista[int(f["patron"])]["tamano"], "n_personas": info.get("n_personas")}
        salida.append({"dimension": dim, "nombre": cfg.get("nombre", dim),
                       "intensidad": r["intensidad"], "n_evidencias": r["n_evidencias"],
                       "componentes": [{"componente": c, "descripcion": comps.get(c, {}).get("descripcion", c), "valor": v}
                                       for c, v in json.loads(r["componentes"]).items()],
                       "temas": mis_temas, "patron": patron})
    return sorted(salida, key=lambda x: (-x["intensidad"], x["nombre"]))


# ------------------------------------------------------------------ persona en una dimensión, comparar
@lru_cache(maxsize=64)
def _matriz_dimension(ambito: str, dimension: str) -> tuple[pd.DataFrame, np.ndarray]:
    """(componentes normalizados 0–1 de quienes tienen evidencias en la dimensión, su versión
    estandarizada). Estandarizar el valor normalizado (componente / máximo del ámbito) da lo mismo
    que estandarizar el componente, como al formar los patrones (DEC-055); no incluye las
    proporciones que también usan los patrones, porque no se guardan por persona."""
    d = repo.dimensiones(ambito)
    d = d[(d["dimension"] == dimension) & (d["n_evidencias"] > 0)]
    comp = pd.DataFrame([json.loads(c) for c in d["componentes"]], index=d["persona_id"].astype(int).to_numpy()).fillna(0.0)
    desv = comp.std()
    z = ((comp - comp.mean()) / desv.where(desv > 0, 1)).loc[:, desv > 0]
    return comp, z.to_numpy()


def _patrones_de(ambito: str, dimension: str) -> pd.DataFrame:
    """Patrón de cada persona en la dimensión, indexado por persona_id (vacío si no hay patrones)."""
    _, patrones, _ = repo.micro_dimensiones(ambito)
    if not len(patrones):
        return pd.DataFrame(columns=["patron"])
    return patrones[patrones["dimension"] == dimension].set_index("persona_id")


def _temas_de(ambito: str, dimension: str) -> pd.DataFrame:
    """Proporción de las evidencias de cada persona en cada tema de la dimensión (personas x temas)."""
    temas, _, _ = repo.micro_dimensiones(ambito)
    if not len(temas):
        return pd.DataFrame()
    t = temas[temas["dimension"] == dimension]
    return t.pivot_table(index="persona_id", columns="tema_id", values="proporcion", aggfunc="sum", fill_value=0.0)


def _evidencias(persona_id: int, tipos: list[str] | None = None, maximo: int = 40) -> list[dict]:
    """Evidencias de la persona agrupadas por tipo (solo de `tipos`, si se indican)."""
    ev = repo.evidencias()
    ev = ev[ev["persona_id"] == persona_id]
    if tipos is not None:
        ev = ev[ev["tipo_id"].isin(tipos)]
    grupos = [{"tipo_id": t, "n": len(g), "textos": g["texto"].tolist()[:maximo]} for t, g in ev.groupby("tipo_id")]
    return sorted(grupos, key=lambda x: -x["n"])


def _persona_dimension(ambito: str, dimension: str, persona_id: int, maximo_textos: int = 40) -> dict:
    """La persona vista desde una dimensión: su puntaje (índice de DEC-053) y cómo se obtiene, su
    posición frente al personal del ámbito (cuántas personas tienen un puntaje menor, igual o
    mayor), cada componente frente al promedio de su patrón y de la dimensión, su patrón (con la
    similitud con la persona representativa), sus temas y solo las evidencias de esa dimensión."""
    info = _dimension(ambito, dimension)
    cfg = repo.definiciones_dimensiones().get(dimension, {})
    comps_def = cfg.get("componentes", {})
    comp, _ = _matriz_dimension(ambito, dimension)
    d = repo.dimensiones(ambito)
    fila = d[(d["persona_id"] == persona_id) & (d["dimension"] == dimension)]
    pat = _patrones_de(ambito, dimension)
    lista = (info.get("patrones") or {}).get("patrones", [])
    patron, miembros = None, []
    if persona_id in pat.index:
        r = pat.loc[persona_id]
        f = lista[int(r["patron"])]
        miembros = pat.index[pat["patron"] == r["patron"]]
        sim = r.get("similitud_representante")
        patron = {"patron": int(r["patron"]), "etiqueta": f["etiqueta"], "tamano": f["tamano"], "afinidad": float(r["afinidad_1"]),
                  "mixto": bool(r["mixto"]), "segundo": int(r["patron_2"]), "segundo_etiqueta": lista[int(r["patron_2"])]["etiqueta"],
                  "similitud_representante": None if sim is None or pd.isna(sim) else float(sim),
                  "es_representante": bool(r.get("es_representante", False)),
                  "representante_id": f.get("representante_id"),
                  "representante_nombre": repo.nombre(f["representante_id"]) if f.get("representante_id") else None}
    del_patron = comp.loc[comp.index.intersection(miembros)]
    orden_comps = [c for c in comps_def if c in comp.columns] + [c for c in comp.columns if c not in comps_def]
    suma_pesos = sum(float(comps_def.get(c, {}).get("peso", 1.0)) for c in orden_comps) or 1.0
    componentes = []
    for c in orden_comps:
        valor = float(comp.at[persona_id, c]) if persona_id in comp.index else 0.0
        peso = float(comps_def.get(c, {}).get("peso", 1.0))
        componentes.append({"componente": c, "descripcion": comps_def.get(c, {}).get("descripcion", c), "valor": valor,
                            "media_dimension": round(float(comp[c].mean()), 3),
                            "media_patron": round(float(del_patron[c].mean()), 3) if len(del_patron) else None,
                            # puntaje = suma de aportes = sum(valor x peso) / suma de pesos (DEC-053)
                            "peso": peso, "aporte": round(100 * valor * peso / suma_pesos, 1)})
    todos = d.loc[d["dimension"] == dimension, "indice"].to_numpy(dtype=float)
    indice = float(fila["indice"].iloc[0]) if len(fila) else 0.0
    igual = np.isclose(todos, indice, atol=1e-6)
    posicion = {"n": int(len(todos)), "ambito": NOMBRE_AMBITO.get(ambito, ambito),
                "menor": round(100 * float(((todos < indice) & ~igual).mean()), 1),
                "igual": round(100 * float(igual.mean()), 1),
                "mayor": round(100 * float(((todos > indice) & ~igual).mean()), 1)}
    temas_dim = (info.get("temas") or {}).get("temas", [])
    tp = _temas_de(ambito, dimension)
    temas = []
    if persona_id in tp.index:
        mios = tp.loc[persona_id]
        temas = [{"tema": int(t), "etiqueta": temas_dim[int(t)]["etiqueta"], "proporcion": round(float(v), 3)}
                 for t, v in mios[mios > 0].sort_values(ascending=False).head(5).items()]
    return {"dimension": dimension, "nombre": cfg.get("nombre", dimension),
            "intensidad": float(fila["intensidad"].iloc[0]) if len(fila) else 0.0,
            "n_evidencias": int(fila["n_evidencias"].iloc[0]) if len(fila) else 0,
            "puntaje": round(100 * indice, 1), "suma_pesos": suma_pesos, "posicion": posicion,
            "patron": patron, "componentes": componentes, "temas": temas,
            "datos": _datos_persona(dimension, persona_id, lista[patron["patron"]] if patron else None),
            "evidencias": _evidencias(persona_id, cfg.get("tipos_evidencia", []), maximo_textos)}


# ------------------------------------------------------------------ datos reales de cada persona
@lru_cache(maxsize=1)
def _componentes_crudos() -> pd.DataFrame:
    """Componentes de cada persona en sus unidades (conteos en log1p), calculados con la misma
    función que `perfiles.construir` (`dimensiones.componentes_crudos`) sobre las evidencias. Solo
    para MOSTRAR el dato real de una persona (p. ej. "1 título de cuarto nivel"); las notas,
    puntajes y patrones siguen saliendo de los resultados guardados. Tarda unos segundos la primera
    vez (lee los atributos de todas las evidencias); se precarga al arrancar."""
    from perfiles.comun import archivos_evidencias
    from perfiles.dimensiones import componentes_crudos

    ev = pd.concat([pd.read_csv(f, usecols=["persona_id", "tipo_id", "atributos"]) for f in archivos_evidencias()],
                   ignore_index=True)
    ids = [int(x) for x in repo.personas("todos")["persona_id"]]
    comp, _ = componentes_crudos(ev, ids)
    return comp


def _datos_persona(dimension: str, persona_id: int, ficha_patron: dict | None) -> list[dict]:
    """Los datos de la persona con que se forman los patrones de la dimensión (componentes y
    proporciones, DEC-055), en sus unidades, junto al valor típico de su patrón y de la dimensión.
    Responde "qué dato la hizo terminar en ese patrón". Vacío si no se pueden calcular."""
    try:
        from perfiles.micro_dimensiones import variables_patron

        comp = _componentes_crudos()
    except Exception as e:  # noqa: BLE001 — la ficha sigue sin esta sección
        print(f"No se pudieron calcular los datos reales: {e}", flush=True)
        return []
    if persona_id not in comp.index:
        return []
    x, descripciones = variables_patron(dimension, comp.loc[[persona_id]])
    del_patron = {c["componente"]: c for c in (ficha_patron or {}).get("componentes", [])}
    salida = []
    for col, desc in descripciones.items():
        nombre = col.split("__", 1)[1]
        valor = float(x.iloc[0][col])
        if "(log" in desc:
            valor = float(np.expm1(valor))
        f = del_patron.get(nombre)
        salida.append({"componente": nombre, "descripcion": desc, "valor": round(valor, 3),
                       "formato": _formato_componente(nombre, desc),
                       # marca sí/no: para una persona se muestra "Sí"/"No", no un porcentaje
                       "marca": desc.startswith("Tiene ") or nombre == "posgrado_en_curso",
                       "media_patron": f["media_grupo"] if f else None,
                       "media_dimension": f["media_dimension"] if f else None,
                       "comparacion": f["comparacion"] if f else None, "z": f["z"] if f else None})
    return salida


def _parecidos_dimension(ambito: str, dimension: str, persona_id: int, n: int = 8) -> list[dict]:
    """Personas VIGENTES más cercanas en la dimensión, en el mismo espacio estandarizado con que se
    formaron sus patrones (sin las proporciones, ver `_matriz_dimension`). A igual distancia (p. ej.
    los mismos títulos), primero quien comparte más de sus temas. Sin puntajes: orden y qué comparten."""
    comp, z = _matriz_dimension(ambito, dimension)
    if persona_id not in comp.index:
        return []
    ids = comp.index.to_numpy()
    i = comp.index.get_loc(persona_id)
    dist = np.linalg.norm(z - z[i], axis=1) if z.shape[1] else np.zeros(len(ids))
    tp = _temas_de(ambito, dimension).reindex(ids, fill_value=0.0)
    m = tp.to_numpy()
    comun = np.minimum(m, m[i]).sum(axis=1) if m.shape[1] else np.zeros(len(ids))
    p = repo.personas(ambito).set_index("persona_id")
    vigente = p["vigente"].reindex(ids, fill_value=False).to_numpy(dtype=bool)
    orden = [j for j in np.lexsort((-comun, np.round(dist, 6))) if j != i and vigente[j]][:n]
    pat = _patrones_de(ambito, dimension)
    mi_patron = int(pat.at[persona_id, "patron"]) if persona_id in pat.index else None
    temas_dim = (_dimension(ambito, dimension).get("temas") or {}).get("temas", [])
    salida = []
    for rango, j in enumerate(orden, start=1):
        otro = int(ids[j])
        su_patron = int(pat.at[otro, "patron"]) if otro in pat.index else None
        ambos = sorted((k for k in range(m.shape[1]) if m[i, k] > 0 and m[j, k] > 0), key=lambda k: -min(m[i, k], m[j, k]))
        salida.append({"persona_id": otro, "nombre": repo.nombre(otro), "rango": rango, "cargo_actual": p.at[otro, "cargo_actual"],
                       "mismo_patron": mi_patron is not None and su_patron == mi_patron, "patron": su_patron,
                       "mismos_valores": bool(dist[j] < 1e-9),
                       "temas_comunes": [temas_dim[int(tp.columns[k])]["etiqueta"] for k in ambos[:3]]})
    return salida


@app.get("/api/personas/{persona_id}/dimension/{dimension}")
def persona_en_dimension(persona_id: int, dimension: str, ambito: str = Query("todos")) -> dict:
    """La persona vista desde una dimensión (lo primero de su ficha al abrirla desde esa dimensión):
    su patrón y componentes frente al patrón, temas, evidencias de la dimensión y personas parecidas
    en la dimensión."""
    p = repo.personas(_ambito(ambito))
    if not (p["persona_id"] == persona_id).any():
        raise HTTPException(404, f"La persona {persona_id} no está en el ámbito {ambito}")
    return {"persona_id": persona_id, "ambito": ambito, **_persona_dimension(ambito, dimension, persona_id),
            "parecidos": _parecidos_dimension(ambito, dimension, persona_id)}


@app.get("/api/comparar")
def comparar(ambito: str = Query("todos"), ids: str = Query(..., description="ids separados por coma (máx. 4)"),
             dimension: str | None = Query(None)) -> dict:
    """Varias personas (máx. 4) lado a lado. Siempre: su patrón global y microarquetipo, y su
    intensidad y patrón en cada dimensión. Con `dimension`, además cada una vista desde esa dimensión
    (patrón, componentes frente a su patrón, temas, evidencias de la dimensión); sin ella, todas sus
    evidencias resumidas."""
    try:
        lista = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))[:4]
    except ValueError as e:
        raise HTTPException(400, "ids debe ser una lista de números separados por coma") from e
    p = repo.personas(_ambito(ambito)).set_index("persona_id")
    if dimension:
        _dimension(ambito, dimension)
    defs = repo.definiciones_dimensiones()
    d = repo.dimensiones(ambito)
    d = d[d["persona_id"].isin(lista)]
    _, patrones, _ = repo.micro_dimensiones(ambito)
    pat = patrones[patrones["persona_id"].isin(lista)] if len(patrones) else pd.DataFrame(columns=["persona_id", "dimension", "patron"])
    salida = []
    for pid in lista:
        if pid not in p.index:
            continue
        suyos = pat[pat["persona_id"] == pid]
        su_patron = dict(zip(suyos["dimension"], suyos["patron"]))
        intensidades = [{"dimension": r.dimension, "nombre": defs.get(r.dimension, {}).get("nombre", r.dimension),
                         "intensidad": float(r.intensidad), "n_evidencias": int(r.n_evidencias),
                         "patron": int(su_patron[r.dimension]) if r.dimension in su_patron else None}
                        for r in d[d["persona_id"] == pid].itertuples()]
        x = {"persona_id": pid, "nombre": repo.nombre(pid), "vigente": bool(p.at[pid, "vigente"]),
             **{k: (None if pd.isna(p.at[pid, k]) else p.at[pid, k]) for k in ("cargo_actual", "unidad_actual", "tipo_empleado")},
             "patron_global": _patron_global_persona(ambito, pid), "intensidades": intensidades}
        if dimension:
            x["dimension"] = _persona_dimension(ambito, dimension, pid, maximo_textos=25)
        else:
            x["evidencias"] = _evidencias(pid, None, 15)
        salida.append(x)
    return {"ambito": ambito, "dimension": dimension, "personas": salida}


CARRIL = {"TRAYECTORIA_CARGO_ESTRUCTURAL": "Cargo de planta en ESPOL", "TRAYECTORIA_CONTRATO_PUNTUAL": "Contrato ocasional en ESPOL",
          "TRAYECTORIA_FUNCION_ADICIONAL": "Función adicional", "SUBROGACION": "Subrogación",
          "EXTERNA_ECUADOR": "Experiencia externa (Ecuador)", "EXTERNA_EXTERIOR": "Experiencia externa (exterior)"}


@app.get("/api/personas/{persona_id}/trayectoria")
def trayectoria(persona_id: int) -> dict:
    """Linea de tiempo de la persona a partir de sus evidencias de trayectoria (un tramo por
    periodo). Un periodo sin fecha de fin solo se extiende hasta hoy si la persona esta vigente
    (VIGENTE_ACTUALMENTE) y es su cargo actual o el ultimo abierto de ese tipo; si no, se marca
    "sin fecha de fin registrada" (el atributo `vigente` de las evidencias esta inflado, DEC-045)."""
    p = repo.personas("todos")
    fila = p[p["persona_id"] == persona_id]
    vigente = bool(fila["vigente"].iloc[0]) if not fila.empty else False
    cargos_actuales = set(str(fila["cargo_actual"].iloc[0] or "").upper().split(" / ")) if not fila.empty else set()
    ev = repo.evidencias_trayectoria()
    ev = ev[ev["persona_id"] == persona_id]

    tramos = []
    for e in ev.itertuples():
        a = json.loads(e.atributos)
        tipo = e.tipo_id
        if tipo == "TRAYECTORIA_EXPERIENCIA_EXTERNA":
            carril = CARRIL["EXTERNA_EXTERIOR" if a.get("es_exterior") else "EXTERNA_ECUADOR"]
            titulo = a.get("cargo") or "Cargo no registrado"
            lugar = a.get("institucion") or ""
            if a.get("es_exterior") and a.get("pais"):
                lugar = f"{lugar} ({a['pais'].title()})"
            periodos = [{"inicio": a.get("fecha_inicio"), "fin": a.get("fecha_fin")}]
        else:
            carril = CARRIL["SUBROGACION"] if a.get("es_subrogacion") else CARRIL[tipo]
            titulo = a.get("cargo") or a.get("contrato") or a.get("funcion") or e.texto
            lugar = a.get("unidad_sigla") or a.get("unidad") or ""
            periodos = a.get("periodos") or [{"inicio": a.get("fecha_inicio"), "fin": a.get("fecha_fin")}]
        for per in periodos:
            if per.get("inicio"):
                tramos.append({"carril": carril, "titulo": str(titulo), "lugar": str(lugar), "inicio": per["inicio"],
                               "fin": per.get("fin"), "estado": "cerrado" if per.get("fin") else "abierto"})

    # periodos abiertos: actuales solo si la persona esta vigente (ver docstring)
    abiertos = [t for t in tramos if t["estado"] == "abierto"]
    for carril in {t["carril"] for t in abiertos}:
        del_carril = sorted((t for t in abiertos if t["carril"] == carril), key=lambda t: t["inicio"])
        for t in del_carril:
            es_actual = vigente and (t["titulo"].upper() in cargos_actuales or t is del_carril[-1])
            t["estado"] = "actual" if es_actual else "sin_fin"
    return {"vigente": vigente, "tramos": sorted(tramos, key=lambda t: t["inicio"])}


# ---------------------------------------------------------------------------------------------
# Búsqueda semántica de personas (04_busqueda_semantica, paquete `busqueda`). Independiente de
# los perfiles. Los modelos (bge-m3 y el reranker) se cargan en la primera búsqueda (~30 s); el
# LLM (Groq) solo recibe la consulta.
# ---------------------------------------------------------------------------------------------
from pydantic import BaseModel as _BaseModel  # noqa: E402


class ConsultaBusqueda(_BaseModel):
    consulta: str
    vigencia: str = "vigentes"  # vigentes | no_vigentes | todos (la consulta puede cambiarla)


@app.get("/api/busqueda/estado")
def busqueda_estado() -> dict:
    import os

    from busqueda.comun import JUEZ, MODELO_EMBEDDING, MODELO_LLM, MODELO_RERANKER, UMBRALES
    from busqueda.indice import cargar_indice, modelo_embedding

    return {"llm_configurado": bool(os.environ.get("GROQ_API_KEY")), "modelo_llm": MODELO_LLM,
            "modelo_embedding": MODELO_EMBEDDING, "modelo_reranker": MODELO_RERANKER, "juez": JUEZ,
            "umbral": UMBRALES[JUEZ],
            "modelos_cargados": cargar_indice.cache_info().currsize > 0 and modelo_embedding.cache_info().currsize > 0}


@app.post("/api/busqueda")
def busqueda_semantica(q: ConsultaBusqueda) -> dict:
    from busqueda.buscar import buscar as buscar_personas

    if len(q.consulta.strip()) < 3:
        raise HTTPException(400, "Escribe una consulta un poco más larga")
    if q.vigencia not in ("vigentes", "no_vigentes", "todos"):
        raise HTTPException(400, "vigencia debe ser vigentes, no_vigentes o todos")
    r = buscar_personas(q.consulta, vigencia=q.vigencia)
    for res in r["resultados"]:  # nombres leídos en vivo
        res["nombre"] = repo.nombre(res["persona_id"])
    return r
