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

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import repositorio as repo


@asynccontextmanager
async def _ciclo_de_vida(_app: FastAPI):
    """Precarga en segundo plano el índice y los modelos de la búsqueda (~30 s en GPU, más en CPU)
    para que la primera búsqueda no tenga que esperarlos; la API responde mientras tanto."""
    def precargar():
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


def _dimension(ambito: str, dimension: str) -> dict:
    _, _, fichas = repo.micro_dimensiones(_ambito(ambito))
    if dimension not in fichas:
        raise HTTPException(404, f"Dimensión desconocida o sin resultados en esta versión: {dimension}")
    return fichas[dimension]


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
    _, _, fichas = repo.micro_dimensiones(_ambito(ambito))
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
                       solo_vigentes: bool = Query(True), offset: int = Query(0, ge=0),
                       limite: int = Query(500, ge=1, le=500), q: str | None = Query(None)) -> dict:
    """Personas con evidencias en la dimensión, opcionalmente de un patrón o con un tema, y con `q`
    solo las que coinciden por nombre o apellidos (ver `_pagina_personas`). Orden:
    similitud con la persona representativa del patrón, proporción de sus evidencias en el tema, o
    nivel (percentil entre quienes tienen registros, DEC-060)."""
    _dimension(ambito, dimension)
    p = repo.personas(ambito)[["persona_id", "vigente", "cargo_actual", "unidad_actual", "tipo_empleado"]]
    d = repo.dimensiones(ambito)
    d = d[(d["dimension"] == dimension) & (d["n_evidencias"] > 0)][["persona_id", "intensidad", "n_evidencias"]]
    d = d.merge(_nivel_dimension(ambito, dimension), on="persona_id", how="left")
    temas, patrones, _ = repo.micro_dimensiones(ambito)
    cols_pat = ["persona_id", "patron", "afinidad_1", "mixto", "es_representante"] + (["similitud_representante"] if "similitud_representante" in patrones.columns else [])
    pat = patrones[patrones["dimension"] == dimension][cols_pat] if len(patrones) else None
    x = d.merge(p, on="persona_id")
    if pat is not None:
        x = x.merge(pat, on="persona_id", how="left")
    orden = "nivel"
    if patron is not None:
        if pat is None:
            raise HTTPException(404, "La dimensión no tiene patrones")
        x = x[x["patron"] == patron]
        orden = "similitud_representante" if "similitud_representante" in x.columns else "afinidad_1"
    if tema is not None:
        t = temas[(temas["dimension"] == dimension) & (temas["tema_id"] == tema)][["persona_id", "proporcion"]]
        x = x.merge(t, on="persona_id")
        orden = "proporcion"
    if solo_vigentes:
        x = x[x["vigente"]]
    x = x.sort_values([orden, "nivel", "intensidad"], ascending=False, na_position="last")
    return {"ambito": ambito, "dimension": dimension, "patron": patron, "tema": tema, "solo_vigentes": solo_vigentes,
            **_pagina_personas(x, q, offset, limite)}


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
    d = d[d["dimension"] == dimension][["persona_id", "intensidad"]].merge(_nivel_dimension(ambito, dimension), on="persona_id", how="left")
    temas, patrones, _ = repo.micro_dimensiones(ambito)
    x = m.merge(p, on="persona_id").merge(d, on="persona_id", how="left")
    if len(patrones):
        x = x.merge(patrones[patrones["dimension"] == dimension][["persona_id", "patron"]], on="persona_id", how="left")
    if len(temas):
        t = temas[temas["dimension"] == dimension].sort_values(["persona_id", "proporcion", "tema_id"], ascending=[True, False, True])
        # todos sus temas [[tema, proporción], ...] para resaltar a todas las personas con evidencias en un tema
        lista: dict[int, list] = {}
        for pid, tema, prop in zip(t["persona_id"], t["tema_id"], t["proporcion"]):
            lista.setdefault(int(pid), []).append([int(tema), round(float(prop), 3)])
        todos = pd.DataFrame({"persona_id": list(lista), "temas": list(lista.values())}, columns=["persona_id", "temas"])
        todos["persona_id"] = todos["persona_id"].astype("int64")
        t = t.drop_duplicates("persona_id")[["persona_id", "tema_id", "proporcion"]].rename(columns={"tema_id": "tema", "proporcion": "proporcion_tema"})
        x = x.merge(t, on="persona_id", how="left").merge(todos, on="persona_id", how="left")
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
        x = x.merge(_nivel_dimension(ambito, dimension), on="persona_id", how="left")
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
    glob, fichas = repo.patrones_globales(_ambito(ambito))
    salida = copy.deepcopy(fichas)
    todos = set(glob["persona_id"].astype(int))
    for f in salida.get("patrones", []):
        f["representante_nombre"] = repo.nombre(f["representante_id"]) if f.get("representante_id") else None
        for t in f.get("temas", []):
            t["nombre_dimension"] = _nombre_dimension(t["dimension"])
        del_patron = set(glob.loc[glob["patron_global"] == f["id"], "persona_id"].astype(int))
        _con_registros_y_nivel(ambito, f.get("dimensiones", []), del_patron, todos)
        for m in (f.get("microarquetipos") or {}).get("lista", []):
            m["representante_nombre"] = repo.nombre(m["representante_id"]) if m.get("representante_id") else None
            for t in m.get("temas", []):
                t["nombre_dimension"] = _nombre_dimension(t["dimension"])
            del_micro = set(glob.loc[(glob["patron_global"] == f["id"]) & (glob["micro"] == m["id"]), "persona_id"].astype(int))
            _con_registros_y_nivel(ambito, m.get("dimensiones", []), del_micro, del_patron)
    return {"ambito": ambito, **salida}


def _con_registros_y_nivel(ambito: str, dims: list[dict], grupo: set[int], referencia: set[int]) -> None:
    """Añade a cada dimensión de la ficha de un grupo (patrón global o microarquetipo), para el
    grupo y su referencia: % con registros y nivel mediano de quienes tienen registros (DEC-060)."""
    d = repo.dimensiones(ambito)
    niveles = _niveles(ambito)
    for e in dims:
        g = d[d["dimension"] == e["dimension"]].set_index("persona_id")["indice"]
        for clave, ids in (("", grupo), ("_referencia", referencia)):
            indices = g.reindex(list(ids)).dropna()
            con = [p for p, v in indices.items() if v > 0]
            nv = [niveles[(int(p), e["dimension"])] for p in con if (int(p), e["dimension"]) in niveles]
            e["pct_con_registros" + clave] = round(100 * len(con) / max(len(indices), 1), 1)
            e["nivel_mediano" + clave] = round(float(pd.Series(nv).median()), 1) if nv else None


@app.get("/api/perfil/{ambito}/personas")
def personas_patron_global(ambito: str, patron: int = Query(...), micro: int | None = Query(None),
                           solo_vigentes: bool = Query(True), offset: int = Query(0, ge=0),
                       limite: int = Query(500, ge=1, le=500), q: str | None = Query(None)) -> dict:
    """Personas de un patrón global (o de uno de sus microarquetipos), ordenadas por similitud con
    su persona representativa (100 % = la representante; 0 % = la más distinta del grupo). Con `q`,
    solo las que coinciden por nombre o apellidos (ver `_pagina_personas`)."""
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
    return {"ambito": ambito, "patron": patron, "micro": micro, **_pagina_personas(x, q, offset, limite)}


def _patron_global_persona(ambito: str, persona_id: int) -> dict | None:
    """Patrón global y microarquetipo de la persona, con su similitud con cada representante."""
    glob, fichas = repo.patrones_globales(ambito)
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
              "temas": [{**t, "nombre_dimension": _nombre_dimension(t["dimension"])} for t in ficha.get("temas", [])],
              "k": fichas.get("k"), "estabilidad": fichas.get("estabilidad_ari"),
              "micro": None}
    info_micro = ficha.get("microarquetipos") or {}
    micros = info_micro.get("lista", [])
    if "micro" in r and r["micro"] >= 0 and micros:
        m = micros[int(r["micro"])]
        salida["micro"] = {"micro": int(r["micro"]), "codigo": m["codigo"], "etiqueta": m["etiqueta"], "tamano": m["tamano"],
                           "mixto": bool(r["micro_mixto"]),
                           "similitud_representante": None if pd.isna(r["similitud_representante_micro"]) else float(r["similitud_representante_micro"]),
                           "es_representante": bool(r["es_representante_micro"]),
                           "representante_id": m.get("representante_id"),
                           "representante_nombre": repo.nombre(m["representante_id"]) if m.get("representante_id") else None,
                           "temas": [{**t, "nombre_dimension": _nombre_dimension(t["dimension"])} for t in m.get("temas", [])],
                           "k": info_micro.get("k"), "estabilidad": info_micro.get("estabilidad_ari"),
                           "estable": info_micro.get("estable")}
    return salida


def _parecidos(ambito: str, persona_id: int, n: int = 8) -> list[dict]:
    """Personas VIGENTES con el perfil completo más parecido (vecinos más cercanos, DEC-056) y qué
    comparten: dimensiones donde ambas tienen nivel >= 50 (entre quienes tienen registros, DEC-060),
    indicando si siguen el mismo patrón.
    Sin puntajes de similitud: solo el orden y lo que comparten."""
    _, vecinos = repo.perfil_conjunto(ambito)
    v = vecinos[vecinos["persona_id"] == persona_id].sort_values("rango")
    if v.empty:
        return []
    p = repo.personas(ambito).set_index("persona_id")
    v = v[v["vecino_id"].map(lambda i: bool(p.at[i, "vigente"]) if i in p.index else False)].head(n)
    d = repo.dimensiones(ambito)
    _, patrones, fichas_dim = repo.micro_dimensiones(ambito)
    nombres = {k: c["nombre"] for k, c in repo.definiciones_dimensiones().items()}
    # nombre de cada patrón por dimensión (DEC-063): "Docencia: sin materias" en vez de "(P3)"
    nombre_patron = {(d, f["id"]): f.get("nombre") for d, x in fichas_dim.items() if x.get("patrones")
                     for f in x["patrones"]["patrones"]}
    ids = [persona_id, *v["vecino_id"].tolist()]
    niveles = _niveles(ambito)
    inten = d[d["persona_id"].isin(ids)].pivot(index="persona_id", columns="dimension", values="intensidad")
    nivel = lambda p, dim: niveles.get((int(p), dim), -1.0)  # noqa: E731
    pat = (patrones[patrones["persona_id"].isin(ids)].pivot(index="persona_id", columns="dimension", values="patron")
           if len(patrones) else pd.DataFrame())
    salida = []
    for r in v.itertuples():
        comparte = []
        for dim in inten.columns:
            if nivel(persona_id, dim) >= 50 and nivel(r.vecino_id, dim) >= 50:
                a = pat.at[persona_id, dim] if dim in pat.columns and persona_id in pat.index else None
                b = pat.at[r.vecino_id, dim] if dim in pat.columns and r.vecino_id in pat.index else None
                mismo = a is not None and b is not None and not pd.isna(a) and a == b
                comparte.append({"dimension": dim, "nombre": nombres.get(dim, dim),
                                 "mismo_patron": bool(mismo), "patron": int(a) if mismo else None,
                                 "patron_nombre": nombre_patron.get((dim, int(a))) if mismo else None})
        comparte.sort(key=lambda c: (not c["mismo_patron"], c["nombre"]))
        vistas = json.loads(r.vistas) if isinstance(getattr(r, "vistas", None), str) else []
        # versiones anteriores guardan solo el nombre de la vista; las nuevas, {vista, rango} (puesto en esa vista)
        vistas = [x if isinstance(x, dict) else {"vista": x, "rango": None} for x in vistas]
        salida.append({"persona_id": int(r.vecino_id), "nombre": repo.nombre(r.vecino_id), "rango": int(r.rango),
                       "cargo_actual": p.at[r.vecino_id, "cargo_actual"], "comparte": comparte,
                       "vistas": [{"vista": x["vista"], "nombre": NOMBRES_VISTAS.get(x["vista"], x["vista"]),
                                   "rango": x.get("rango")} for x in vistas]})
    return salida


# Vistas del perfil completo multivista (DEC-062, `perfiles.perfil_multivista.NOMBRES_VISTAS`)
NOMBRES_VISTAS = {"actividad": "Cómo participa", "academico": "Contenido académico", "docencia": "Materias que dicta",
                  "formacion": "Formación y desarrollo", "trayectoria": "Trayectoria laboral"}


def _nombre_dimension(dim: str) -> str:
    return repo.definiciones_dimensiones().get(dim, {}).get("nombre", dim)


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


def _pagina_personas(x: pd.DataFrame, q: str | None, offset: int, limite: int) -> dict:
    """Una página de una lista de personas YA ordenada. Con `q`, solo quienes coinciden por nombre o
    apellidos (sin tildes ni mayúsculas, tolerando errores de tipeo), sin cambiar el orden del grupo.
    `posicion` es el lugar de cada persona en ese orden (se conserva al filtrar); `total` cuenta las
    que quedan tras el filtro (lo que se pagina) y `total_grupo`, todas las del grupo."""
    x = repo.con_nombres(x.assign(posicion=range(1, len(x) + 1)))
    total_grupo = len(x)
    if q and q.strip():
        terminos = _norm(q).split()
        x = x[x["nombre"].map(lambda n: _puntaje(terminos, _norm(n)) > 0)]
    return {"q": q.strip() if q and q.strip() else None, "total": len(x), "total_grupo": total_grupo,
            "personas": repo.as_records(x.iloc[offset:offset + limite].round(4))}


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
    """Estado de la persona, su intensidad, patrón y temas en cada dimensión y sus personas
    parecidas por perfil completo. Las evidencias se piden aparte (`/evidencias`)."""
    p = repo.personas(_ambito(ambito))
    fila = p[p["persona_id"] == persona_id]
    if fila.empty:
        raise HTTPException(404, f"La persona {persona_id} no está en el ámbito {ambito}")
    f = repo.as_records(fila)[0]
    return {
        "persona_id": persona_id, "ambito": ambito, "nombre": repo.nombre(persona_id),
        "estado": {k: f[k] for k in ("tipo_empleado", "vigente", "cargo_actual", "unidad_actual")},
        "dimensiones": _dimensiones_persona(ambito, persona_id),
        "patron_global": _patron_global_persona(ambito, persona_id),
        "parecidos": _parecidos(ambito, persona_id),
    }


MIN_REFERENCIA_NIVEL = 40  # mismo mínimo que usa perfiles.micro_dimensiones para subdividir una dimensión


@lru_cache(maxsize=3)
def _referencia_dimensiones(ambito: str) -> dict[str, dict]:
    """Por dimensión: personas del ámbito, cuántas tienen un valor medible (índice > 0) y qué %
    no lo tiene. Ese % es el suelo del percentil: quien tiene registros nunca baja de él."""
    d = repo.dimensiones(ambito)
    salida = {}
    for dim, g in d.groupby("dimension"):
        con = int((g["indice"] > 0).sum())
        salida[dim] = {"n_ambito": len(g), "n_con_registros": con, "pct_sin_registros": round(100 * (len(g) - con) / max(len(g), 1), 1)}
    return salida


@lru_cache(maxsize=3)
def _niveles(ambito: str) -> dict[tuple[int, str], float]:
    """Nivel (DEC-060, opción C) = percentil del índice SOLO entre quienes tienen registros en la
    dimensión (índice > 0), con rango medio en los empates: 100 x (rango medio − 0,5) / n. Se
    calcula al leer, sobre el `indice` ya guardado en dimensiones.parquet (decisión de la usuaria,
    2026-10-18); no reemplaza a `intensidad`, que sigue usando el perfil conjunto. Sin nivel con
    menos de MIN_REFERENCIA_NIVEL personas con registros."""
    d = repo.dimensiones(ambito)
    con = d[d["indice"] > 0]
    n = con.groupby("dimension")["indice"].transform("size")
    nivel = 100 * (con.groupby("dimension")["indice"].rank(method="average") - 0.5) / n
    nivel = nivel[n >= MIN_REFERENCIA_NIVEL]
    return {(int(p), dim): round(float(v), 1) for p, dim, v in zip(con.loc[nivel.index, "persona_id"], con.loc[nivel.index, "dimension"], nivel)}


def _nivel_dimension(ambito: str, dimension: str) -> pd.DataFrame:
    """persona_id, nivel de la dimensión (solo quienes tienen nivel)."""
    filas = [(p, v) for (p, d), v in _niveles(ambito).items() if d == dimension]
    return pd.DataFrame(filas, columns=["persona_id", "nivel"]).astype({"persona_id": "int64"})


def _estado_registros(dim: str, persona_id: int, n_evidencias: int) -> str:
    """con_registros · sin_registros (no hay evidencias en las fuentes). En Idiomas se distingue
    además (decisión de la usuaria): solo_espanol, sin_validos y sin_informacion (no aparece en la
    fuente de idiomas), ver `repositorio.registro_idiomas`."""
    if dim != "idiomas":
        return "con_registros" if n_evidencias > 0 else "sin_registros"
    registro = repo.registro_idiomas().get(int(persona_id))
    if registro == "extranjero":
        return "con_registros"
    return registro or "sin_informacion"


@lru_cache(maxsize=3)
def _personas_por_idioma(ambito: str) -> dict[str, int]:
    """Cuántas personas del ámbito registran cada idioma."""
    ids = set(repo.personas(ambito)["persona_id"].astype(int))
    conteo: dict[str, int] = {}
    for p, lista in repo.idiomas_por_persona().items():
        if p in ids:
            for i in {x["idioma"] for x in lista}:
                conteo[i] = conteo.get(i, 0) + 1
    return conteo


def _idiomas(ambito: str, persona_id: int) -> list[dict]:
    """En Idiomas, los "temas" son los idiomas registrados (categorías exactas), con sus niveles."""
    conteo = _personas_por_idioma(ambito)
    return [{**x, "n_personas": conteo.get(x["idioma"], 0)} for x in repo.idiomas_por_persona().get(int(persona_id), [])]


def _sin_temas(dim: str, info: dict) -> str | None:
    """Por qué la dimensión no tiene temas (None si los tiene). Idiomas usa los idiomas como temas."""
    if info.get("temas") or dim == "idiomas":
        return None
    if info.get("nota"):
        return f"No se analizó: {info['nota']}."
    if dim == "idiomas":
        return ("Idiomas no tiene temas: cada evidencia es solo el nombre de un idioma y hay muy pocos textos distintos "
                "para agruparlos.")
    return "No se encontraron temas en esta dimensión: hay muy pocos textos distintos para agruparlos."


def _dimensiones_persona(ambito: str, persona_id: int) -> list[dict]:
    """Por dimensión: estado de los registros, intensidad (percentil 0-100 dentro del ámbito, DEC-053)
    con su población de referencia y el aporte normalizado de cada componente, su patrón de
    actividad y todos sus temas (DEC-055). Ordenadas de mayor a menor intensidad."""
    d = repo.dimensiones(ambito)
    defs = repo.definiciones_dimensiones()
    referencia = _referencia_dimensiones(ambito)
    niveles = _niveles(ambito)
    temas, patrones, fichas = repo.micro_dimensiones(ambito)
    temas = temas[temas["persona_id"] == persona_id]
    te = repo.temas_evidencia(ambito)
    te_persona = te.loc[[persona_id]] if persona_id in te.index else te.iloc[0:0]
    patrones = patrones[patrones["persona_id"] == persona_id].set_index("dimension") if len(patrones) else patrones
    salida = []
    for r in repo.as_records(d[d["persona_id"] == persona_id]):
        dim = r["dimension"]
        cfg = defs.get(dim, {})
        comps = cfg.get("componentes", {})
        info = fichas.get(dim, {})
        info_temas = info.get("temas") or {}
        temas_dim = info_temas.get("temas", [])
        propios = temas[temas["dimension"] == dim].sort_values(["proporcion", "tema_id"], ascending=[False, True])
        empate = int(propios["dominante"].sum()) > 1
        cercania = te_persona[te_persona["dimension"] == dim].groupby("tema_id")["por_cercania"].mean() if len(te_persona) else pd.Series(dtype=float)
        mis_temas = [{"tema": int(t["tema_id"]), "etiqueta": temas_dim[int(t["tema_id"])]["etiqueta"],
                      "terminos": temas_dim[int(t["tema_id"])]["terminos_distintivos"][:6],
                      "n_personas_tema": temas_dim[int(t["tema_id"])]["n_personas"],
                      "proporcion": float(t["proporcion"]), "dominante": bool(t["dominante"]),
                      "parte_por_cercania": round(float(cercania.get(int(t["tema_id"]), 0.0)), 3) if len(cercania) else None}
                     for t in repo.as_records(propios)]
        patron = None
        if dim in getattr(patrones, "index", []):
            f = patrones.loc[dim]
            lista = (info.get("patrones") or {}).get("patrones", [])
            rep = lista[int(f["patron"])].get("representante_id")
            patron = {"patron": int(f["patron"]), "etiqueta": lista[int(f["patron"])]["etiqueta"], "afinidad": float(f["afinidad_1"]),
                      "nombre": lista[int(f["patron"])].get("nombre"), "segundo_nombre": lista[int(f["patron_2"])].get("nombre"),
                      "mixto": bool(f["mixto"]), "segundo": lista[int(f["patron_2"])]["etiqueta"], "segundo_id": int(f["patron_2"]),
                      "tamano": lista[int(f["patron"])]["tamano"], "n_personas": info.get("n_personas"),
                      "representante_id": rep, "representante_nombre": repo.nombre(rep) if rep else None}
        salida.append({"dimension": dim, "nombre": cfg.get("nombre", dim),
                       "estado": _estado_registros(dim, persona_id, r["n_evidencias"]),
                       "intensidad": r["intensidad"], "nivel": niveles.get((int(persona_id), dim)),
                       "n_evidencias": r["n_evidencias"], **referencia.get(dim, {}),
                       "componentes": [{"componente": c, "descripcion": comps.get(c, {}).get("descripcion", c), "valor": v}
                                       for c, v in json.loads(r["componentes"]).items()],
                       "temas": mis_temas, "dominante_empatado": empate,
                       "temas_dimension": ({"k": info_temas["k"], "proporcion_por_cercania": info_temas.get("proporcion_asignada_por_cercania")}
                                           if info_temas else None),
                       "sin_temas": _sin_temas(dim, info), "patron": patron,
                       "idiomas": _idiomas(ambito, persona_id) if dim == "idiomas" else None,
                       "ultima_evidencia": r.get("ultima_evidencia"),
                       "parecidos": _parecidos_dimension(ambito, persona_id, dim, temas_dim)})
    # primero las dimensiones con registros (por nivel), luego las que no tienen
    return sorted(salida, key=lambda x: (x["estado"] != "con_registros", -(x["nivel"] if x["nivel"] is not None else -1),
                                         -x["intensidad"], x["nombre"]))


N_PARECIDOS_DIMENSION = 5


def _parecidos_dimension(ambito: str, persona_id: int, dim: str, temas_dim: list[dict]) -> dict | None:
    """Personas VIGENTES parecidas a la persona dentro de la dimensión (DEC-061), en dos listas:
    "actividad" (participa de forma parecida) y "tema" (trabaja temas parecidos; en Idiomas, los
    mismos idiomas), con lo que comparten. None si la versión no tiene vecinos o la dimensión no
    se compara (muy pocas personas con registros). Sin puntajes: solo orden y explicación."""
    v = repo.vecinos_dimension(ambito)
    if not len(v) or persona_id not in v.index:
        return None
    v = v.loc[[persona_id]]
    v = v[v["dimension"] == dim]
    if v.empty:
        return None
    p = repo.personas(ambito).set_index("persona_id")
    idiomas = {pid: {x["idioma"] for x in l} for pid, l in repo.idiomas_por_persona().items()} if dim == "idiomas" else {}
    salida = {"n_identicos": int(v["n_identicos"].iloc[0]), "actividad": None, "tema": None}
    for lista in ("actividad", "tema"):
        g = v[v["lista"] == lista].sort_values("rango")
        if g.empty:
            continue
        g = g[g["vecino_id"].map(lambda i: bool(p.at[i, "vigente"]) if i in p.index else False)].head(N_PARECIDOS_DIMENSION)
        filas = []
        for r in g.itertuples():
            comunes = [temas_dim[t]["etiqueta"] for t in json.loads(r.temas_compartidos) if t < len(temas_dim)]
            if dim == "idiomas":
                comunes = sorted(idiomas.get(int(persona_id), set()) & idiomas.get(int(r.vecino_id), set()))
            tp = r.texto_persona if isinstance(r.texto_persona, str) else None
            tv = r.texto_vecino if isinstance(r.texto_vecino, str) else None
            filas.append({"persona_id": int(r.vecino_id), "nombre": repo.nombre(r.vecino_id), "cargo_actual": p.at[r.vecino_id, "cargo_actual"],
                          "identico": bool(r.identico), "en_ambos": bool(r.en_ambos), "comparte": comunes,
                          "texto_persona": tp, "texto_vecino": tv, "misma_evidencia": bool(tp and tv and tp == tv)})
        salida[lista] = filas
    return salida


# Campos de `atributos` que no se muestran: identificadores internos de filas y de otras personas, y
# el `vigente` de las evidencias de trayectoria (inflado, DEC-045).
CAMPOS_OCULTOS = {"_origen", "coautores_espol", "coponentes_espol", "codirectores_espol"}


def _oculto(campo: str, tipo: str) -> bool:
    return (campo in CAMPOS_OCULTOS or campo.startswith(("id_", "ids_"))
            or (campo == "vigente" and tipo.startswith("TRAYECTORIA_")))


def _valor(v):
    """Valor legible de un atributo; None = la fuente lo trae vacío."""
    if v is None or v == "" or v == [] or v == {}:
        return None
    if isinstance(v, dict):
        return {k: _valor(x) for k, x in v.items() if not k.startswith(("id_", "ids_"))}
    if isinstance(v, list):
        return [_valor(x) for x in v]
    return v


# Tipos cuya fuente no tiene fechas: no se muestra fecha (ni "sin fecha").
TIPOS_SIN_FECHA = {"DOCENCIA_MATERIA", "IDIOMA"}
# Tipos con una sola fecha, que la evidencia guarda en `fecha_fin` pero no es un fin de periodo
# (02_evidencias: tesis = fecha de sustentación más reciente; formación = FechaGraduacion).
FECHA_UNICA = {"TESIS_DIRIGIDA": "Sustentación", "FORMACION_TITULO": "Graduación", "FORMACION_EN_CURSO": "Graduación"}


def _fechas(tipo: str, a: dict) -> str | None:
    """Fechas de la evidencia tal como vienen en sus atributos (sin completar las que faltan)."""
    if tipo in FECHA_UNICA:
        if not a.get("fecha_fin"):
            return None
        varias = tipo == "TESIS_DIRIGIDA" and (a.get("n_sustentaciones") or 1) > 1
        return f"{'Última sustentación' if varias else FECHA_UNICA[tipo]}: {str(a['fecha_fin'])[:10]}"
    inicio, fin = (str(a.get(k))[:10] if a.get(k) else None for k in ("fecha_inicio", "fecha_fin"))
    if inicio and fin:
        return inicio if inicio == fin else f"{inicio} – {fin}"
    if inicio:
        return f"desde {inicio} (sin fecha de fin registrada)"
    if fin:
        return f"hasta {fin} (sin fecha de inicio registrada)"
    for k in ("anios", "fechas"):
        if a.get(k):
            return ", ".join(str(x)[:10] for x in a[k])
    return None


def _carga_con_docencia(a: dict) -> bool:
    """Una actividad de carga cuenta en Docencia solo si tiene horas de docencia (misma regla que
    `perfiles.dimensiones.componentes_crudos`)."""
    return any(d.get("actividad") == "DOCENCIA" and (d.get("horas") or 0) > 0 for d in (a.get("detalle") or []))


@app.get("/api/personas/{persona_id}/evidencias")
def evidencias_persona(persona_id: int) -> dict:
    """Evidencias de la persona agrupadas por dimensión y tipo, con sus atributos legibles (sin
    identificadores internos). Lo que no cuenta en ninguna dimensión va en "Otras evidencias"."""
    _ambito("todos")
    defs = repo.definiciones_dimensiones()
    tipo_dim = {t: d for d, cfg in defs.items() for t in cfg.get("tipos_evidencia", [])}
    grupos: dict[str, dict[str, list]] = {}
    for e in repo.evidencias_de(persona_id).itertuples():
        a = json.loads(e.atributos) if isinstance(e.atributos, str) else {}
        dim = tipo_dim.get(e.tipo_id, "otras")
        if e.tipo_id == "ACTIVIDAD_CARGA" and not _carga_con_docencia(a):
            dim = "otras"
        grupos.setdefault(dim, {}).setdefault(e.tipo_id, []).append({
            "texto": e.texto if isinstance(e.texto, str) else None, "fechas": _fechas(e.tipo_id, a),
            "con_fecha": e.tipo_id not in TIPOS_SIN_FECHA,
            "orden": str(a.get("fecha_inicio") or a.get("fecha_fin") or ""),
            "campos": [{"campo": k, "valor": _valor(v)} for k, v in a.items() if not _oculto(k, e.tipo_id)],
        })
    salida = []
    for dim in [*defs, "otras"]:
        if dim not in grupos:
            continue
        tipos = [{"tipo_id": t, "n": len(lista), "evidencias": [{k: v for k, v in x.items() if k != "orden"}
                                                                for x in sorted(lista, key=lambda x: x["orden"], reverse=True)]}
                 for t, lista in grupos[dim].items()]
        salida.append({"dimension": dim, "nombre": defs[dim]["nombre"] if dim in defs else "Otras evidencias",
                       "n": sum(t["n"] for t in tipos), "tipos": sorted(tipos, key=lambda t: -t["n"])})
    return {"grupos": salida}


CARRIL = {"TRAYECTORIA_CARGO_ESTRUCTURAL": "Cargo de planta en ESPOL", "TRAYECTORIA_CONTRATO_PUNTUAL": "Contrato ocasional en ESPOL",
          "TRAYECTORIA_FUNCION_ADICIONAL": "Función adicional", "SUBROGACION": "Subrogación",
          "EXTERNA_ECUADOR": "Experiencia externa (Ecuador)", "EXTERNA_EXTERIOR": "Experiencia externa (exterior)"}


@app.get("/api/personas/{persona_id}/trayectoria")
def trayectoria(persona_id: int) -> dict:
    """Linea de tiempo de la persona a partir de sus evidencias de trayectoria (un tramo por
    periodo). Un periodo de ESPOL sin fecha de fin solo se extiende hasta hoy si la persona esta
    vigente (VIGENTE_ACTUALMENTE) y es su cargo actual o el ultimo abierto de ese tipo; si no, se
    marca "sin fecha de fin registrada" (el atributo `vigente` de las evidencias esta inflado,
    DEC-045). La experiencia externa sin fecha de fin siempre es "sin fecha de fin registrada"
    (decision de la usuaria): no se sabe si sigue o si falta la fecha. `sin_inicio` cuenta los
    periodos que no se pueden dibujar por no tener fecha de inicio."""
    p = repo.personas("todos")
    fila = p[p["persona_id"] == persona_id]
    vigente = bool(fila["vigente"].iloc[0]) if not fila.empty else False
    cargos_actuales = set(str(fila["cargo_actual"].iloc[0] or "").upper().split(" / ")) if not fila.empty else set()
    ev = repo.evidencias_trayectoria()
    ev = ev[ev["persona_id"] == persona_id]

    tramos, sin_inicio = [], 0
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
            else:
                sin_inicio += 1

    # periodos abiertos: actuales solo si la persona esta vigente y es un periodo de ESPOL (ver docstring)
    externos = {CARRIL["EXTERNA_ECUADOR"], CARRIL["EXTERNA_EXTERIOR"]}
    abiertos = [t for t in tramos if t["estado"] == "abierto"]
    for carril in {t["carril"] for t in abiertos}:
        del_carril = sorted((t for t in abiertos if t["carril"] == carril), key=lambda t: t["inicio"])
        for t in del_carril:
            es_actual = vigente and carril not in externos and (t["titulo"].upper() in cargos_actuales or t is del_carril[-1])
            t["estado"] = "actual" if es_actual else "sin_fin"
    return {"vigente": vigente, "tramos": sorted(tramos, key=lambda t: t["inicio"]), "sin_inicio": sin_inicio}


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
