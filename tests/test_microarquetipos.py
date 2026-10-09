"""Pruebas de microarquetipos y afinidades derivadas (DEC-052).

- Unitarias con datos sintéticos (no dependen de los datos del proyecto).
- De propiedades sobre la versión de clustering vigente (se omiten si no hay resultados).
Uso:  python -m pytest tests -q
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from perfiles import clustering as cl
from perfiles import snf
from perfiles.comun import CLUSTERING_DIR


# ---------------------------------------------------------------- unitarias (sintéticas)
def _datos_sinteticos(semilla: int = 0):
    rng = np.random.default_rng(semilla)
    centros = np.array([[0, 0], [6, 0], [0, 6]], dtype=float)
    x = np.vstack([c + rng.normal(0, 0.6, (30, 2)) for c in centros] + [np.array([[3.0, 0.0]])])  # último: entre 2 grupos
    w = snf.afinidad(snf.distancias(x), k=10, mu=0.5)
    np.fill_diagonal(w, 0)
    return x, w


def test_afinidades_finitas_no_negativas_suman_1():
    _, w = _datos_sinteticos()
    et = cl.espectral(w, 3)
    m = cl.pertenencias(w, et, 3)
    cl.validar_afinidades(m)
    assert m.shape == (len(w), 3)


def test_persona_sin_afinidad_no_produce_nan():
    _, w = _datos_sinteticos()
    w = w.copy()
    w[5, :] = 0
    w[:, 5] = 0
    m = cl.pertenencias(w, cl.espectral(w, 3), 3)
    cl.validar_afinidades(m)
    assert np.allclose(m[5], 1 / 3)


def test_afinidad_relevante_con_mas_de_un_grupo():
    _, w = _datos_sinteticos()
    et = cl.espectral(w, 3)
    m = cl.pertenencias(w, et, 3)
    segundo = np.sort(m, axis=1)[:, -2]
    assert segundo.max() > 0.1  # el punto intermedio se conecta con dos grupos


def test_medoide_solo_entre_elegibles_y_vacio_si_no_hay():
    _, w = _datos_sinteticos()
    et = cl.espectral(w, 3)
    elegibles = np.zeros(len(w), dtype=bool)
    grupo0 = np.flatnonzero(et == 0)
    elegibles[grupo0[:3]] = True  # solo 3 elegibles en el grupo 0, ninguno en los demás
    med = cl.medoides(w, et, 3, elegibles=elegibles)
    assert med[0] in grupo0[:3]
    assert (med[1:] == -1).all()


def test_centroides_normalizados_y_falla_si_vacio():
    x, w = _datos_sinteticos()
    et = cl.espectral(w, 3)
    c = cl.centroides(np.c_[x, np.ones(len(x))], et, 3)
    assert np.isfinite(c).all() and np.allclose(np.linalg.norm(c, axis=1), 1)
    with pytest.raises(ValueError):
        cl.centroides(np.c_[x, np.ones(len(x))], et, 4)  # cluster 3 vacío


def test_reproducible_con_misma_semilla():
    _, w = _datos_sinteticos()
    a, b = cl.espectral(w, 3), cl.espectral(w, 3)
    assert (a == b).all()
    assert np.allclose(cl.pertenencias(w, a, 3), cl.pertenencias(w, b, 3))


# ---------------------------------------------------------------- propiedades (datos)
def _version():
    actual = CLUSTERING_DIR / "actual.json"
    if not actual.exists():
        pytest.skip("no hay resultados de clustering")
    return CLUSTERING_DIR / json.loads(actual.read_text(encoding="utf-8"))["version"]


AMBITOS = ["todos", "administrativos", "docentes"]


@pytest.mark.parametrize("ambito", AMBITOS)
def test_datos_afinidades_y_alineacion(ambito):
    d = _version() / ambito
    p = pd.read_parquet(d / "personas.parquet")
    if "microarquetipo" not in p.columns:
        pytest.skip("versión anterior a los microarquetipos")
    r = json.loads((d / "clusters.json").read_text(encoding="utf-8"))
    m = len(r["microarquetipos"])
    afin = np.array([json.loads(s) for s in p["micro_afinidades"]])
    assert afin.shape == (len(p), m)                       # personas × microarquetipos alineados
    assert p["persona_id"].is_unique
    assert set(p["microarquetipo"]) == set(range(m))       # ninguna hoja vacía
    assert np.isfinite(afin).all() and (afin >= 0).all()
    assert np.allclose(afin.sum(axis=1), 1, atol=1e-3)     # redondeo a 4 decimales
    assert [f["nombre"] for f in r["microarquetipos"]] == [f"Microarquetipo {i + 1}" for i in range(m)]


@pytest.mark.parametrize("ambito", AMBITOS)
def test_datos_representantes_vigentes_y_centroides(ambito):
    d = _version() / ambito
    p = pd.read_parquet(d / "personas.parquet")
    if "microarquetipo" not in p.columns:
        pytest.skip("versión anterior a los microarquetipos")
    r = json.loads((d / "clusters.json").read_text(encoding="utf-8"))
    vig = dict(zip(p["persona_id"], p["vigente"]))
    for f in r["microarquetipos"] + r["clusters"]:
        rep = f["representante"]
        if rep is None:
            assert f["tamano_vigentes"] == 0                  # vacío solo si no hay vigentes
        else:
            assert vig[rep["persona_id"]]                      # nunca un no vigente
    for nombre in ("centroides_micro_v1.npy", "centroides_micro_v2.npy"):
        c = np.load(d / nombre)
        assert c.shape[0] == len(r["microarquetipos"])
        assert np.isfinite(c).all() and np.allclose(np.linalg.norm(c, axis=1), 1, atol=1e-4)


def test_datos_aislamiento_entre_ambitos():
    v = _version()
    tipos = {a: pd.read_parquet(v / a / "personas.parquet")[["persona_id", "tipo_empleado"]] for a in AMBITOS}
    # DEC-054: solo quien tiene contratos activos de ambos tipos está en los dos ámbitos
    dobles = "ADMINISTRATIVO / DOCENTE"
    assert tipos["administrativos"]["tipo_empleado"].isin(["ADMINISTRATIVO", dobles]).all()
    assert tipos["docentes"]["tipo_empleado"].isin(["DOCENTE", dobles]).all()
    comunes = set(tipos["administrativos"]["persona_id"]) & set(tipos["docentes"]["persona_id"])
    assert comunes == set(tipos["todos"].loc[tipos["todos"]["tipo_empleado"] == dobles, "persona_id"])
    for a in AMBITOS:
        r = json.loads((v / a / "clusters.json").read_text(encoding="utf-8"))
        if "microarquetipos" not in r:
            pytest.skip("versión anterior a los microarquetipos")
        ids = set(tipos[a]["persona_id"])
        reps = [f["representante"]["persona_id"] for f in r["microarquetipos"] if f["representante"]]
        assert set(reps) <= ids                                # representantes del propio ámbito
