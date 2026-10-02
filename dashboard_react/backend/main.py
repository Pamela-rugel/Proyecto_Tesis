"""
API FastAPI del dashboard de perfiles de personal ESPOL.

Expone los resultados del clustering multivista (DEC-045) calculados fuera de linea por
`python -m perfiles.construir` y persistidos en data/perfiles/clustering/<version>/. La API solo
LEE (ver `repositorio.py`): no recalcula el clustering ni duplica datos.

Preparado para la etapa siguiente (busqueda semantica): cada resultado trae el cluster, su
representante, las pertenencias a los demas clusters y, en disco, los centroides semanticos y
los vecinos de cada persona en la red fusionada.

Ejecutar con (desde dashboard_react/backend/):
    d:\\Proyecto_Tesis\\.venv\\Scripts\\python -m uvicorn main:app --reload --port 8001
"""

from __future__ import annotations

import copy
import threading
from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import legible
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

NOMBRES_VISTA = {"v1_trayectoria": "trayectoria y gestión", "v2_academico": "perfil académico-temático",
                 "v3_estructurada": "datos estructurados"}


def _enriquecer(ambito: str, ficha: dict) -> dict:
    """Copia de la ficha (no se modifica la cacheada) con, para mostrar:
    - el nombre de su representante y de los de sus subpatrones (leidos en vivo);
    - `rasgos_legibles`: los rasgos en unidades reales (años, cantidades, %, si/no) para el patron
      vs todo el ambito, y para cada subpatron vs su patron (ver legible.py)."""
    ficha = copy.deepcopy(ficha)
    p = repo.personas(ambito)
    crudo = repo.vista_estructurada()
    miembros = p.loc[p["cluster"] == ficha["cluster"], "persona_id"]
    ficha["representante"]["nombre"] = repo.nombre(ficha["representante"]["persona_id"])
    ficha["rasgos_legibles"] = legible.rasgos(ficha["rasgos_estructurados"], crudo, miembros, p["persona_id"])
    for sp in (ficha.get("subdivision") or {}).get("subpatrones", []):
        sp["representante"]["nombre"] = repo.nombre(sp["representante"]["persona_id"])
        del_sub = p.loc[(p["cluster"] == ficha["cluster"]) & (p["subpatron"] == sp["cluster"]), "persona_id"]
        sp["rasgos_legibles"] = legible.rasgos(sp["rasgos_estructurados"], crudo, del_sub, miembros)
    return ficha


def _ambito(ambito: str) -> str:
    if ambito not in repo.AMBITOS:
        raise HTTPException(404, f"Ámbito desconocido: {ambito}. Use uno de {repo.AMBITOS}")
    try:
        repo.version_actual()
    except repo.SinClustering as e:
        raise HTTPException(503, str(e)) from e
    return ambito


@app.get("/api/health")
def health() -> dict:
    evidencias = sorted(p.parent.name for p in repo.EVIDENCIAS_DIR.glob("*/evidencias_*.csv"))
    try:
        clustering = repo.estado_version()
    except repo.SinClustering as e:
        clustering = {"version": None, "mensaje": str(e)}
    return {"estado": "ok", "carpetas_de_evidencias": evidencias, "clustering": clustering}


@app.get("/api/clustering/ambitos")
def ambitos() -> dict:
    _ambito("todos")
    m = repo.manifest()
    salida = []
    for a in repo.AMBITOS:
        r = repo.resumen(a)
        salida.append({"ambito": a, "nombre": r["nombre"], "n_personas": r["n_personas"], "n_vigentes": r["n_vigentes"],
                       "k": r["k"], "perfiles_mixtos": r["perfiles_mixtos"], "estabilidad_ari": r["estabilidad_ari"]})
    return {"version": m["version"], "fecha": m["fecha"], "metodo": m["metodo"], "vistas": m["vistas"],
            "estado": repo.estado_version(), "ambitos": salida}


@app.get("/api/clustering/{ambito}")
def clustering(ambito: str) -> dict:
    """Resumen del ambito: seleccion de k, metricas y la ficha de cada cluster."""
    r = repo.resumen(_ambito(ambito))
    salida = {k: v for k, v in r.items() if k not in ("segundos", "clusters")}
    salida["clusters"] = [_enriquecer(ambito, c) for c in r["clusters"]]
    return salida


@app.get("/api/clustering/{ambito}/mapa")
def mapa(ambito: str, solo_vigentes: bool = Query(True)) -> dict:
    """Puntos t-SNE (solo visualizacion) con cluster, pertenencia y si es perfil mixto."""
    p = repo.personas(_ambito(ambito))
    if solo_vigentes:
        p = p[p["vigente"] | p["es_representante"] | p["es_subrepresentante"]]
    columnas = ["persona_id", "tsne_x", "tsne_y", "cluster", "cluster_2", "pertenencia_1", "pertenencia_2",
                "perfil_mixto", "vigente", "es_representante", "cargo_actual", "unidad_actual", "tipo_empleado",
                "subpatron", "es_subrepresentante"]
    return {"ambito": ambito, "solo_vigentes": solo_vigentes, "etiquetas": repo.etiquetas(ambito),
            "puntos": repo.as_records(repo.con_nombres(p[columnas].round(4)))}


@app.get("/api/clustering/{ambito}/buscar")
def buscar(ambito: str, q: str = Query(..., min_length=2), solo_vigentes: bool = Query(True)) -> dict:
    """Busca personas del ambito por nombre, cargo o unidad (sin distinguir tildes ni mayusculas)."""
    import unicodedata

    def norm(x) -> str:
        x = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode()
        return x.lower()

    p = repo.con_nombres(repo.personas(_ambito(ambito)))
    if solo_vigentes:
        p = p[p["vigente"]]
    texto = (p["nombre"].map(norm) + " | " + p["cargo_actual"].map(norm) + " | " + p["unidad_actual"].map(norm))
    terminos = norm(q).split()

    # cada termino debe aparecer; si no aparece tal cual, se acepta una palabra parecida
    # (errores de tipeo como "ciclia" -> "cecilia"). Primero las coincidencias exactas.
    from difflib import SequenceMatcher

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
    et = repo.etiquetas(ambito)
    return {"resultados": [{"persona_id": int(r.persona_id), "nombre": r.nombre, "cargo_actual": r.cargo_actual,
                            "unidad_actual": r.unidad_actual, "cluster": int(r.cluster), "etiqueta": et[int(r.cluster)]}
                           for r in m.itertuples()]}


@app.get("/api/clustering/{ambito}/clusters/{cluster}")
def detalle_cluster(ambito: str, cluster: int) -> dict:
    """Ficha del cluster (con sus subpatrones si se subdividio) e integrantes VIGENTES ordenados por
    similitud al representante, cada uno con su subpatron. Incluye
    tambien a las personas vigentes de otros clusters con perfil mixto hacia este."""
    r = repo.resumen(_ambito(ambito))
    ficha = next((c for c in r["clusters"] if c["cluster"] == cluster), None)
    if ficha is None:
        raise HTTPException(404, f"El ámbito {ambito} no tiene el cluster {cluster}")
    p = repo.personas(ambito)
    columnas = ["persona_id", "cargo_actual", "unidad_actual", "tipo_empleado", "similitud_representante",
                "coseno_v1_representante", "coseno_v2_representante", "pertenencia_1", "cluster_2",
                "pertenencia_2", "perfil_mixto", "es_representante", "subpatron", "sub_pertenencia_1",
                "sub_perfil_mixto", "es_subrepresentante", "similitud_subrepresentante"]
    integrantes = p[(p["cluster"] == cluster) & p["vigente"]].sort_values("similitud_representante", ascending=False)
    mixtos = p[(p["cluster"] != cluster) & (p["cluster_2"] == cluster) & p["perfil_mixto"] & p["vigente"]]
    return {"ambito": ambito, "ficha": _enriquecer(ambito, ficha),
            "integrantes": repo.as_records(repo.con_nombres(integrantes[columnas].round(4))),
            "mixtos_desde_otros_clusters": repo.as_records(repo.con_nombres(
                mixtos[["persona_id", "cargo_actual", "unidad_actual", "cluster", "pertenencia_1", "pertenencia_2"]].round(4)))}


def _subpatron(ficha: dict, f: dict) -> dict | None:
    """Subpatron de la persona dentro de su patron (None si el patron no se subdividio)."""
    sub = ficha.get("subdivision")
    if not sub or f["subpatron"] < 0:
        return None
    sp = next(s for s in sub["subpatrones"] if s["cluster"] == f["subpatron"])
    segundo = next(s for s in sub["subpatrones"] if s["cluster"] == f["sub_cluster_2"])
    return {"subpatron": f["subpatron"], "subpatron_id": f["subpatron_id"], "etiqueta": sp["etiqueta"],
            "descripcion": sp["descripcion"], "pertenencia": f["sub_pertenencia_1"],
            "perfil_mixto": f["sub_perfil_mixto"], "segundo_subpatron": segundo["etiqueta"],
            "pertenencia_2": f["sub_pertenencia_2"], "es_representante": f["es_subrepresentante"],
            "representante_id": f["subrepresentante_id"],
            "representante_nombre": repo.nombre(f["subrepresentante_id"]),
            "similitud_representante": f["similitud_subrepresentante"],
            "estabilidad_ari": sub["estabilidad_ari"]}


@app.get("/api/personas/{persona_id}")
def persona(persona_id: int, ambito: str = Query("todos")) -> dict:
    """Informacion de la persona y por que pertenece a su cluster: pertenencias, cluster segun
    cada vista, similitud al representante, rasgos compartidos y sus evidencias."""
    p = repo.personas(_ambito(ambito))
    fila = p[p["persona_id"] == persona_id]
    if fila.empty:
        raise HTTPException(404, f"La persona {persona_id} no está en el ámbito {ambito}")
    f = repo.as_records(fila)[0]
    et = repo.etiquetas(ambito)
    ficha = next(c for c in repo.resumen(ambito)["clusters"] if c["cluster"] == f["cluster"])

    pertenencias = sorted(({"cluster": c, "etiqueta": et[c], "pertenencia": v}
                           for c, v in enumerate(json.loads(f["pertenencias"]))), key=lambda x: -x["pertenencia"])
    por_vista = [{"vista": v, "nombre": NOMBRES_VISTA[v], "cluster": f[f"cluster_{v}"], "etiqueta": et[f[f"cluster_{v}"]],
                  "coincide": f[f"cluster_{v}"] == f["cluster"]} for v in NOMBRES_VISTA]

    z = repo.z_ambito(ambito)
    miembros = p.loc[p["cluster"] == f["cluster"], "persona_id"]
    rasgos_legibles = legible.rasgos(ficha["rasgos_estructurados"], repo.vista_estructurada(), miembros,
                                     p["persona_id"], persona_id=persona_id, z_persona=z.loc[persona_id])
    rasgos = []
    for r in ficha["rasgos_estructurados"]:
        if r["variable"] in z.columns:
            zp = float(z.at[persona_id, r["variable"]])
            rasgos.append({**r, "z_persona": round(zp, 2), "comparte": (zp > 0) == (r["z"] > 0) and abs(zp) >= 0.25})

    ev = repo.evidencias()
    ev = ev[ev["persona_id"] == persona_id]
    compartidas = {x["texto"] for x in ficha["evidencias_compartidas"]}
    evidencias = [{"tipo_id": t, "n": len(g), "textos": g["texto"].tolist()[:40],
                   "compartidas_con_cluster": sorted(set(g["texto"]) & compartidas)}
                  for t, g in ev.groupby("tipo_id")]

    return {
        "persona_id": persona_id, "ambito": ambito, "nombre": repo.nombre(persona_id),
        "estado": {k: f[k] for k in ("tipo_empleado", "vigente", "cargo_actual", "unidad_actual")},
        "cluster": {"cluster": f["cluster"], "etiqueta": et[f["cluster"]], "pertenencia": f["pertenencia_1"],
                    "perfil_mixto": f["perfil_mixto"], "es_representante": f["es_representante"],
                    "representante_id": f["representante_id"],
                    "representante_nombre": repo.nombre(f["representante_id"]),
                    "similitud_representante": f["similitud_representante"],
                    "coseno_v1_representante": f["coseno_v1_representante"],
                    "coseno_v2_representante": f["coseno_v2_representante"],
                    "coseno_v1_centroide": f["coseno_v1_centroide"], "coseno_v2_centroide": f["coseno_v2_centroide"]},
        "subpatron": _subpatron(ficha, f),
        "pertenencias": pertenencias, "cluster_por_vista": por_vista, "rasgos": rasgos,
        "rasgos_legibles": rasgos_legibles,
        "vistas_faltantes": [v for v, falta in (("v1_trayectoria", f["vista_v1_faltante"]),
                                                  ("v2_academico", f["vista_v2_faltante"])) if falta],
        "evidencias": sorted(evidencias, key=lambda x: -x["n"]),
    }


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
# Búsqueda semántica de personas (04_busqueda_semantica, paquete `busqueda`). Independiente del
# clustering: el grupo de cada persona se agrega solo como CONTEXTO. Los modelos (bge-m3 y el
# reranker) se cargan en la primera búsqueda (~30 s); el LLM (Groq) solo recibe la consulta.
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
    # contexto del clustering (solo informativo) y nombres leídos en vivo
    try:
        p = repo.personas("todos").set_index("persona_id")
        et = repo.etiquetas("todos")
    except repo.SinClustering:
        p, et = None, {}
    for res in r["resultados"]:
        res["nombre"] = repo.nombre(res["persona_id"])
        if p is not None and res["persona_id"] in p.index:
            c = int(p.at[res["persona_id"], "cluster"])
            res["grupo"] = {"cluster": c, "etiqueta": et.get(c, "")}
    return r
