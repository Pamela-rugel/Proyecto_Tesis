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
                       solo_vigentes: bool = Query(True)) -> dict:
    """Personas con evidencias en la dimensión, opcionalmente de un patrón o con un tema. Orden:
    afinidad con el patrón, proporción de sus evidencias en el tema, o intensidad."""
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
    orden = "intensidad"
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
    x = x.sort_values([orden, "intensidad"], ascending=False)
    return {"ambito": ambito, "dimension": dimension, "patron": patron, "tema": tema, "solo_vigentes": solo_vigentes,
            "total": len(x), "personas": repo.as_records(repo.con_nombres(x.head(500).round(4)))}


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
    _, fichas = repo.patrones_globales(_ambito(ambito))
    salida = copy.deepcopy(fichas)
    for f in salida.get("patrones", []):
        f["representante_nombre"] = repo.nombre(f["representante_id"]) if f.get("representante_id") else None
        for m in (f.get("microarquetipos") or {}).get("lista", []):
            m["representante_nombre"] = repo.nombre(m["representante_id"]) if m.get("representante_id") else None
    return {"ambito": ambito, **salida}


@app.get("/api/perfil/{ambito}/personas")
def personas_patron_global(ambito: str, patron: int = Query(...), micro: int | None = Query(None),
                           solo_vigentes: bool = Query(True)) -> dict:
    """Personas de un patrón global (o de uno de sus microarquetipos), ordenadas por similitud con
    su persona representativa (100 % = la representante; 0 % = la más distinta del grupo)."""
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
    return {"ambito": ambito, "patron": patron, "micro": micro, "total": len(x),
            "personas": repo.as_records(repo.con_nombres(x.head(500).round(4)))}


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
    """Busca personas del ámbito por nombre, cargo o unidad (sin distinguir tildes ni mayúsculas)."""
    def norm(x) -> str:
        return unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()

    p = repo.con_nombres(repo.personas(_ambito(ambito)))
    if solo_vigentes:
        p = p[p["vigente"]]
    texto = (p["nombre"].map(norm) + " | " + p["cargo_actual"].map(norm) + " | " + p["unidad_actual"].map(norm))
    terminos = norm(q).split()

    # cada término debe aparecer; si no aparece tal cual, se acepta una palabra parecida
    # (errores de tipeo como "ciclia" -> "cecilia"). Primero las coincidencias exactas.
    def puntaje(t: str) -> float:
        palabras = t.replace("|", " ").split()
        total = 0.0
        for x in terminos:
            if x in t:
                total += 1.0
                continue
            mejor = max((SequenceMatcher(None, x, w).ratio() for w in palabras), default=0.0)
            if len(x) < 4 or mejor < 0.75:
                return 0.0
            total += mejor
        return total

    puntos = texto.map(puntaje)
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
    temas, patrones, fichas = repo.micro_dimensiones(ambito)
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
    cargo_actual = str(fila["cargo_actual"].iloc[0] or "").upper() if not fila.empty else ""
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
            es_actual = vigente and (t["titulo"].upper() == cargo_actual or t is del_carril[-1])
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
