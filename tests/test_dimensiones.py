"""Pruebas de intensidad por dimensión de evidencia (DEC-053) y de ámbitos con doble tipo (DEC-054).

- Unitarias con datos sintéticos (no dependen de los datos del proyecto).
- De propiedades sobre la versión de clustering vigente (se omiten si no hay resultados).
Uso:  python -m pytest tests -q
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from perfiles import dimensiones as dm
from perfiles.comun import AMBITOS, CLUSTERING_DIR, en_ambito


# ---------------------------------------------------------------- unitarias (sintéticas)
def test_percentil_cero_sin_evidencia_y_maximo_100():
    pct = dm.percentil_positivo(np.array([0.0, 0.0, 0.0, 0.2, 0.5, 0.5, 0.9]))
    assert list(pct[:3]) == [0.0, 0.0, 0.0]
    assert pct[-1] == 100.0
    assert pct[4] == pct[5]  # empates con el mismo percentil
    assert np.all(np.diff(pct[3:]) >= 0)


def _evidencias(filas):
    return pd.DataFrame(filas, columns=["persona_id", "tipo_id", "atributos"]).assign(
        atributos=lambda d: d["atributos"].map(json.dumps))


def test_intensidades_por_dimension_independientes():
    ev = _evidencias([
        (1, "PUBLICACION", {"cuartiles_sjr": ["Q1"]}),
        (1, "PUBLICACION", {"cuartiles_sjr": []}),
        (1, "PROYECTO_INVESTIGACION", {"roles": ["DIRECTOR"]}),
        (2, "PUBLICACION", {"cuartiles_sjr": []}),
        (2, "CAPACITACION", {"horas_total": 40, "es_exterior": False}),
        (3, "CAPACITACION", {"horas_total": 10, "es_exterior": True}),
    ])
    comp, n = dm.componentes_crudos(ev, [1, 2, 3])
    d = dm.intensidades(comp, n).set_index(["persona_id", "dimension"])
    assert d.loc[(1, "investigacion"), "intensidad"] == 100.0
    assert 0 < d.loc[(2, "investigacion"), "intensidad"] < 100.0
    assert d.loc[(3, "investigacion"), "intensidad"] == 0.0
    assert d.loc[(3, "investigacion"), "n_evidencias"] == 0
    # no suman 100: la persona 1 es 100 en investigación y 0 en capacitación
    assert d.loc[(1, "capacitacion"), "intensidad"] == 0.0
    assert d["intensidad"].between(0, 100).all()
    assert set(d.index.get_level_values("dimension")) == set(dm.DIMENSIONES)


def test_carga_sin_horas_docencia_no_cuenta_como_docencia():
    ev = _evidencias([(1, "ACTIVIDAD_CARGA", {"detalle": [{"actividad": "GESTION", "horas": 20}]}),
                      (2, "ACTIVIDAD_CARGA", {"detalle": [{"actividad": "DOCENCIA", "horas": 20}]})])
    comp, n = dm.componentes_crudos(ev, [1, 2])
    assert n.loc[1, "docencia"] == 0 and n.loc[2, "docencia"] == 1


def test_doble_tipo_entra_en_ambos_ambitos():
    tipos = pd.Series(["ADMINISTRATIVO", "DOCENTE", "ADMINISTRATIVO / DOCENTE", None])
    assert list(en_ambito(tipos, "administrativos")) == [True, False, True, False]
    assert list(en_ambito(tipos, "docentes")) == [False, True, True, False]
    assert en_ambito(tipos, "todos").all()


# ---------------------------------------------------------------- propiedades (versión vigente)
def _version():
    actual = CLUSTERING_DIR / "actual.json"
    if not actual.exists():
        pytest.skip("sin versión de clustering")
    carpeta = CLUSTERING_DIR / json.loads(actual.read_text(encoding="utf-8"))["version"]
    if not (carpeta / "todos" / "dimensiones.parquet").exists():
        pytest.skip("la versión vigente no tiene dimensiones")
    return carpeta


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_dimensiones_version_vigente(ambito):
    carpeta = _version()
    d = pd.read_parquet(carpeta / ambito / "dimensiones.parquet")
    p = pd.read_parquet(carpeta / ambito / "personas.parquet")
    assert set(d["persona_id"]) == set(p["persona_id"])
    assert (d.groupby("persona_id").size() == len(dm.DIMENSIONES)).all()
    assert d["intensidad"].between(0, 100).all()
    assert (d.loc[d["n_evidencias"] == 0, "intensidad"] == 0).all()
    assert (d.groupby("dimension")["intensidad"].max() == 100).all()


def test_doble_tipo_en_ambos_ambitos_version_vigente():
    carpeta = _version()
    adm = pd.read_parquet(carpeta / "administrativos" / "personas.parquet")
    doc = pd.read_parquet(carpeta / "docentes" / "personas.parquet")
    dobles = set(adm.loc[adm["tipo_empleado"] == "ADMINISTRATIVO / DOCENTE", "persona_id"])
    assert dobles and dobles <= set(doc["persona_id"])


# ---------------------------------------------------------------- microarquetipos por dimensión (DEC-055)
from perfiles import micro_dimensiones as md  # noqa: E402


def test_dimensiones_separan_trayectoria_espol_y_experiencia_externa():
    ev = _evidencias([(1, "TRAYECTORIA_CARGO_ESTRUCTURAL", {"duracion_total_anios": 10}),
                      (2, "TRAYECTORIA_EXPERIENCIA_EXTERNA", {"duracion_anios": 5, "es_exterior": True})])
    comp, n = dm.componentes_crudos(ev, [1, 2])
    assert n.loc[1, "trayectoria_espol"] == 1 and n.loc[1, "experiencia_externa"] == 0
    assert n.loc[2, "trayectoria_espol"] == 0 and n.loc[2, "experiencia_externa"] == 1


def test_patrones_descubren_roles_sinteticos():
    rng = np.random.default_rng(0)
    filas = []
    for i in range(60):   # dirige casi todo lo que hace
        filas.append({"proyectos": 4, "dirigidos": 4})
    for i in range(60):   # participa mucho, no dirige
        filas.append({"proyectos": 8, "dirigidos": 0})
    for i in range(60):   # participación ocasional
        filas.append({"proyectos": 1, "dirigidos": 0})
    base = pd.DataFrame(filas) + rng.integers(0, 2, (180, 2)) * np.array([1, 0])
    comp = pd.DataFrame(0.0, index=range(180), columns=[f"vinculacion__{c}" for c in DIMENSIONES_V])
    comp["vinculacion__proyectos"] = np.log1p(base["proyectos"])
    comp["vinculacion__proyectos_dirigidos"] = np.log1p(base["dirigidos"])
    comp["vinculacion__anios"] = np.log1p(base["proyectos"] * 1.0)
    personas, r = md.patrones_dimension("vinculacion", np.arange(180), comp, np.ones(180, bool))
    assert r["k"] >= 3
    m = np.vstack(personas["afinidad_1"].to_numpy())
    assert np.isfinite(m).all() and (personas["afinidad_1"] >= personas["afinidad_2"] - 1e-9).all()
    # cada rol sintético queda mayoritariamente en un patrón propio
    dominante = [personas["patron"].iloc[i:i + 60].mode().iloc[0] for i in (0, 60, 120)]
    assert len(set(dominante)) == 3


DIMENSIONES_V = list(dm.DIMENSIONES["vinculacion"]["componentes"])


def test_temas_sinteticos_y_ruido_asignado():
    rng = np.random.default_rng(1)
    centros = rng.normal(size=(3, 32))
    x = np.vstack([c + rng.normal(0, 0.15, (60, 32)) for c in centros])
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    textos = np.array([f"{p} tema{g} palabra{g}" for g, p in zip(np.repeat(range(3), 60), range(180))])
    res = md.descubrir_temas(textos, x)
    assert res is not None and res["k"] == 3
    assert (res["etiquetas"] >= 0).all()          # el ruido se reasigna al tema más cercano
    for g in range(3):
        assert len(set(res["etiquetas"][g * 60:(g + 1) * 60])) == 1


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_micro_dimensiones_version_vigente(ambito):
    carpeta = _version()
    if not (carpeta / ambito / "patrones_dimension.parquet").exists():
        pytest.skip("la versión vigente no tiene microarquetipos por dimensión")
    t = pd.read_parquet(carpeta / ambito / "temas_dimension.parquet")
    p = pd.read_parquet(carpeta / ambito / "patrones_dimension.parquet")
    d = pd.read_parquet(carpeta / ambito / "dimensiones.parquet")
    con_ev = set(map(tuple, d.loc[d["n_evidencias"] > 0, ["persona_id", "dimension"]].to_numpy()))
    assert set(map(tuple, p[["persona_id", "dimension"]].to_numpy())) <= con_ev
    assert np.allclose(t.groupby(["persona_id", "dimension"])["proporcion"].sum(), 1.0)
    assert (p["afinidad_1"] >= p["afinidad_2"] - 1e-9).all()
    r = json.loads((carpeta / ambito / "micro_dimensiones.json").read_text(encoding="utf-8"))
    for dim, x in r.items():
        if x["patrones"]:
            assert sum(f["tamano"] for f in x["patrones"]["patrones"]) == x["n_personas"]


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_mapas_dimension_version_vigente(ambito):
    carpeta = _version()
    if not (carpeta / ambito / "mapas_dimension.parquet").exists():
        pytest.skip("la versión vigente no tiene mapas por dimensión")
    m = pd.read_parquet(carpeta / ambito / "mapas_dimension.parquet")
    p = pd.read_parquet(carpeta / ambito / "patrones_dimension.parquet")
    t = pd.read_parquet(carpeta / ambito / "temas_dimension.parquet")
    assert np.isfinite(m[["x", "y"]].to_numpy()).all()
    assert not m.duplicated(["persona_id", "dimension", "mapa"]).any()
    # cada persona con patrón tiene punto en el mapa de patrones, y cada persona con temas en el de temas
    clave = lambda df: set(map(tuple, df[["persona_id", "dimension"]].to_numpy()))  # noqa: E731
    assert clave(m[m["mapa"] == "patrones"]) == clave(p)
    assert clave(m[m["mapa"] == "temas"]) == clave(t)


# ---------------------------------------------------------------- perfil completo (DEC-056)
from perfiles import perfil_conjunto as pc  # noqa: E402


def test_perfil_conjunto_cuanto_y_como():
    ids = np.array([1, 2, 3])
    dims = list(dm.DIMENSIONES)
    filas = [{"persona_id": p, "dimension": d, "intensidad": 0.0} for p in ids for d in dims]
    dim = pd.DataFrame(filas)
    dim.loc[(dim["persona_id"] == 1) & (dim["dimension"] == "investigacion"), "intensidad"] = 100.0
    dim.loc[(dim["persona_id"] == 2) & (dim["dimension"] == "investigacion"), "intensidad"] = 100.0
    dim.loc[(dim["persona_id"] == 3) & (dim["dimension"] == "investigacion"), "intensidad"] = 100.0
    pat = pd.DataFrame({"persona_id": [1, 2, 3], "dimension": "investigacion",
                        "afinidades": [json.dumps([1.0, 0.0]), json.dumps([1.0, 0.0]), json.dumps([0.0, 1.0])]})
    x, cols = pc.vectores(ids, dim, pat, {"investigacion": 2})
    assert len(cols) == x.shape[1] == len(dims) - 1 + 2
    # misma intensidad: 1 y 2 participan igual (mismo patrón), 3 distinto -> 1 más cerca de 2 que de 3
    assert np.linalg.norm(x[0] - x[1]) < np.linalg.norm(x[0] - x[2])
    # sin evidencias el bloque es 0
    assert x[:, cols.index("reconocimientos")].sum() == 0


def test_patrones_globales_sinteticos():
    rng = np.random.default_rng(0)
    dims = list(dm.DIMENSIONES)
    ids = np.arange(1, 241)
    # 3 tipos de persona: investigadores (+ reconocimientos), docentes, capacitación
    perfiles = {0: {"investigacion": 90, "reconocimientos": 85}, 1: {"docencia": 90, "trayectoria_espol": 80},
                2: {"capacitacion": 90, "certificaciones": 80}}
    filas = []
    for i, p in enumerate(ids):
        tipo = i % 3
        for d in dims:
            base = perfiles[tipo].get(d, 5)
            filas.append({"persona_id": p, "dimension": d, "intensidad": float(np.clip(base + rng.normal(0, 5), 0, 100))})
    dim = pd.DataFrame(filas)
    g, r = pc.patrones_globales(ids, np.ones(len(ids), bool), dim, pd.DataFrame(columns=["persona_id", "dimension", "patron", "afinidades"]), {})
    assert r["k"] >= 3
    # ningún patrón global mezcla tipos de persona (con k >= 4 un tipo puede partirse en dos)
    tipos = pd.Series(np.arange(len(ids)) % 3, index=g.index)
    assert (tipos.groupby(g["patron_global"]).nunique() == 1).all()
    assert np.allclose(g["afinidades"].map(lambda s: sum(json.loads(s))), 1.0, atol=1e-3)  # redondeo a 4 decimales
    etiquetas = " | ".join(f["etiqueta"] for f in r["patrones"])
    assert "Investigación" in etiquetas and "Reconocimientos" in etiquetas
    # similitud con el representante en [0, 1]; el representante tiene 1
    s = g["similitud_representante"]
    assert s.between(0, 1).all() and np.allclose(s[g["es_representante"]], 1.0)
    # microarquetipos: solo dentro de su patrón global y con identificador "patrón.micro"
    con_micro = g[g["micro"] >= 0]
    assert (con_micro["micro_id"] == con_micro["patron_global"].astype(str) + "." + con_micro["micro"].astype(str)).all()
    for f in r["patrones"]:
        if f["microarquetipos"]:
            assert sum(m["tamano"] for m in f["microarquetipos"]["lista"]) == f["tamano"]


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_perfil_conjunto_version_vigente(ambito):
    carpeta = _version()
    if not (carpeta / ambito / "perfil_conjunto_vecinos.parquet").exists():
        pytest.skip("la versión vigente no tiene perfil completo")
    m = pd.read_parquet(carpeta / ambito / "perfil_conjunto_mapa.parquet")
    v = pd.read_parquet(carpeta / ambito / "perfil_conjunto_vecinos.parquet")
    p = pd.read_parquet(carpeta / ambito / "personas.parquet")
    assert set(m["persona_id"]) == set(p["persona_id"]) and np.isfinite(m[["x", "y"]].to_numpy()).all()
    assert (v["persona_id"] != v["vecino_id"]).all()
    assert (v.groupby("persona_id")["distancia"].apply(lambda s: s.is_monotonic_increasing)).all()


# ---------------------------------------------------------------- DEC-061: proporciones, k estable, vecinos, fechas
from perfiles import vecinos_dimension as vd  # noqa: E402


def _comp_investigacion(filas):
    cols = [f"investigacion__{c}" for c in dm.DIMENSIONES["investigacion"]["componentes"]] + ["investigacion__publicaciones_autor"]
    comp = pd.DataFrame(0.0, index=range(len(filas)), columns=cols)
    for i, f in enumerate(filas):
        for k, v in f.items():
            comp.at[i, f"investigacion__{k}"] = np.log1p(v)
    return comp


def test_proporcion_sin_denominador_queda_en_la_media_y_se_suaviza():
    rng = np.random.default_rng(3)
    filas = [{"proyectos": 1}] * 10   # sin publicaciones
    filas += [{"proyectos": 1, "publicaciones": int(n), "publicaciones_q1q2": int(rng.integers(0, n + 1))} for n in rng.integers(1, 8, 60)]
    filas += [{"proyectos": 1, "publicaciones": 1, "publicaciones_q1q2": 1}]   # 1 de 1 en Q1-Q2
    info = {}
    x, _ = md.variables_patron("investigacion", _comp_investigacion(filas), info)
    col = "investigacion__prop_publicaciones_q1q2_publicaciones"
    media = info["prop_publicaciones_q1q2_publicaciones"]["media_previa"]
    assert np.allclose(x[col].iloc[:10], media, atol=1e-4)            # sin denominador: neutral, no 0
    assert 0 < x[col].iloc[-1] < 1                                     # 1 de 1 no es 100 %
    assert info["prop_publicaciones_q1q2_publicaciones"]["sin_denominador"] == 10


def test_tasa_sin_denominador_toma_la_media():
    cols = [f"docencia__{c}" for c in dm.DIMENSIONES["docencia"]["componentes"]]
    comp = pd.DataFrame(0.0, index=range(4), columns=cols)
    comp["docencia__materias"] = np.log1p([0, 2, 4, 1])
    comp["docencia__estudiantes"] = np.log1p([0, 60, 80, 10])
    x, _ = md.variables_patron("docencia", comp)
    tasa = np.expm1(x["docencia__prop_estudiantes_materias"])
    assert np.isclose(tasa.iloc[0], np.mean([30, 20, 10]))


def test_seleccion_k_prefiere_k_estable():
    rng = np.random.default_rng(4)
    z = np.vstack([c + rng.normal(0, 0.2, (80, 3)) for c in rng.normal(0, 5, (3, 3))])
    k, sel = md._seleccionar_k_patron(z)
    fila = next(t for t in sel["tabla"] if t["k"] == k)
    assert "estabilidad_ari" in fila and fila["estabilidad_ari"] >= md.ARI_MINIMO_PATRON


def test_vecinos_desempatan_identicos_por_tema():
    ids = np.array([10, 11, 12, 13])
    z = np.zeros((4, 2))                                   # actividad idéntica para todos
    e = np.array([[1, 0], [0.99, 0.14], [0, 1], [0.7, 0.7]], dtype=float)
    emb = {p: v / np.linalg.norm(v) for p, v in zip(ids, e)}
    v = vd.construir_dimension("ponencias", ids, z, emb, {}, {}, {}, {})
    act = v[(v.persona_id == 10) & (v.lista == "actividad")].sort_values("rango")
    assert list(act.vecino_id) == [11, 13, 12]             # entre idénticos, primero el tema más parecido
    assert act.identico.all() and (act.n_identicos == 3).all()
    assert not (v.persona_id == v.vecino_id).any()


def test_ultima_evidencia_semestres_y_corte():
    ev = pd.DataFrame({"persona_id": [1, 1, 2], "dimension": ["docencia", "docencia", "ponencias"],
                       "atributos": [json.dumps({"periodos": ["2019-1S", "2021-2S"]}), json.dumps({}),
                                     json.dumps({"fecha_fin": "2099-01-01"})]})
    u = dm.ultima_evidencia(ev, corte="2026-10-01").set_index("persona_id")["ultima_evidencia"]
    assert u[1] == "2021-12-31" and u[2] == "2026-10-01"


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_vecinos_y_temas_evidencia_version_vigente(ambito):
    carpeta = _version()
    if not (carpeta / ambito / "vecinos_dimension.parquet").exists():
        pytest.skip("la versión vigente no tiene vecinos por dimensión")
    v = pd.read_parquet(carpeta / ambito / "vecinos_dimension.parquet")
    d = pd.read_parquet(carpeta / ambito / "dimensiones.parquet")
    con_ev = set(map(tuple, d.loc[d["n_evidencias"] > 0, ["persona_id", "dimension"]].to_numpy()))
    assert set(map(tuple, v[["persona_id", "dimension"]].to_numpy())) <= con_ev
    assert set(map(tuple, v[["vecino_id", "dimension"]].to_numpy())) <= con_ev
    assert not (v["persona_id"] == v["vecino_id"]).any()
    assert set(v["lista"]) <= {"actividad", "tema"}
    assert v.groupby(["persona_id", "dimension", "lista"])["rango"].max().le(vd.N_VECINOS).all()
    te = pd.read_parquet(carpeta / ambito / "temas_evidencia.parquet")
    t = pd.read_parquet(carpeta / ambito / "temas_dimension.parquet")
    prop = te.groupby(["persona_id", "dimension", "tema_id"]).size() / te.groupby(["persona_id", "dimension"]).size()
    unido = t.set_index(["persona_id", "dimension", "tema_id"])["proporcion"].align(prop, join="inner")
    assert np.allclose(*unido)



# ---------------------------------------------------------------- DEC-062: perfil completo multivista (NEMO)
from perfiles import perfil_multivista as pmv  # noqa: E402


def test_nemo_no_penaliza_la_vista_faltante():
    """Sin contenido en un bloque, esa vista no cuenta para el par: la similitud sale solo de las
    vistas que ambos tienen (no de un contenido inventado)."""
    rng = np.random.default_rng(6)
    act = rng.normal(size=(40, 3))
    cont = rng.normal(size=(40, 8)); cont /= np.linalg.norm(cont, axis=1, keepdims=True)
    presente = np.ones(40, bool); presente[:10] = False
    w, vecindad = pmv.red_nemo(act, {"academico": cont}, {"academico": presente}, k=5)
    solo_act = pmv._knn_normalizada(pmv._afinidad(act, 5), 5)
    assert np.allclose(w[:10, :10], solo_act[:10, :10])          # pares sin el bloque: solo actividad
    assert not vecindad["academico"][:10].any()                  # nadie sin bloque es vecino en esa vista
    assert np.allclose(w, w.T) and (np.diag(w) == 0).all()


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_perfil_multivista_version_vigente(ambito):
    carpeta = _version()
    r = json.loads((carpeta / ambito / "patrones_globales.json").read_text(encoding="utf-8"))
    if "vistas" not in r:
        pytest.skip("la versión vigente no tiene el perfil completo multivista")
    v = pd.read_parquet(carpeta / ambito / "perfil_conjunto_vecinos.parquet")
    assert v["vistas"].map(lambda s: isinstance(json.loads(s), list)).all()
    g = pd.read_parquet(carpeta / ambito / "patrones_globales.parquet")
    assert g["patron_global"].between(0, r["k"] - 1).all() and pmv.K_MIN <= r["k"] <= pmv.K_MAX
    for f in r["patrones"]:
        m = f["microarquetipos"]
        del_patron = g[g["patron_global"] == f["id"]]
        if f["tamano"] < pmv.MIN_SUBDIVIDIR:
            assert m is None and (del_patron["micro"] == -1).all()
        else:
            assert pmv.K_MIN_MICRO <= m["k"] <= pmv.K_MAX_MICRO
            assert del_patron["micro"].value_counts().sort_index().tolist() == [x["tamano"] for x in m["lista"]]


# ---------------------------------------------------------------- DEC-063: nombres de los patrones por dimensión
from perfiles import nombres_patrones as nmp  # noqa: E402


def test_nombre_se_cumple_para_todas_las_personas_del_patron():
    cols = [f"ponencias__{c}" for c in dm.DIMENSIONES["ponencias"]["componentes"]]
    filas = [(1, 0)] * 30 + [(2, 2)] * 10 + [(3, 2)] * 10 + [(5, 0)] * 10      # (ponencias, en el exterior)
    comp = pd.DataFrame(np.log1p(np.array(filas, float)), columns=cols)
    lab = np.array([0] * 30 + [1] * 20 + [2] * 10)
    n = nmp.nombrar("ponencias", comp, list(dm.DIMENSIONES["ponencias"]["componentes"]), lab)
    real = nmp.valores_reales("ponencias", comp, list(dm.DIMENSIONES["ponencias"]["componentes"]))
    for c, info in enumerate(n):
        m = lab == c
        cands = {t: mk for t, mk, _ in nmp._candidatas("ponencias", real, comp, m)}
        assert info["condiciones"] and all(cands[t][m].all() for t in info["condiciones"])   # 100 % del patrón
    assert "1 ponencia" in n[0]["nombre"] and n[0]["distingue"] == 1.0
    assert len({x["nombre"] for x in n}) == 3                                             # nombres distintos


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_patrones_por_dimension_tienen_nombre(ambito):
    carpeta = _version()
    r = json.loads((carpeta / ambito / "micro_dimensiones.json").read_text(encoding="utf-8"))
    fichas = [f for x in r.values() if x["patrones"] for f in x["patrones"]["patrones"]]
    if not any("nombre" in f for f in fichas):
        pytest.skip("la versión vigente no tiene nombres de patrones")
    for x in r.values():
        if x["patrones"]:
            nombres = [f["nombre"] for f in x["patrones"]["patrones"]]
            assert all(nombres) and len(set(nombres)) == len(nombres)


@pytest.mark.parametrize("ambito", list(AMBITOS))
def test_similitud_con_representante_no_colapsa_en_cero(ambito):
    """La similitud se mide en el embedding espectral: no debe quedar en 0 % para la mayoría."""
    carpeta = _version()
    g = pd.read_parquet(carpeta / ambito / "patrones_globales.parquet")
    s = g["similitud_representante"].dropna()
    if not len(s) or "nicho" in g.columns:
        pytest.skip("versión anterior")
    assert (s < 0.005).mean() < 0.2 and s.between(0, 1).all()
    assert (g.loc[g["es_representante"], "similitud_representante"] == 1).all()
