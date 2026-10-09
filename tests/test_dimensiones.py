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
