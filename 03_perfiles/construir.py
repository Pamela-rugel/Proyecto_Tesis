"""Orquesta el clustering multivista del personal y persiste los resultados (DEC-045).

Uso (raiz del proyecto, entorno global con GPU para los embeddings):
    python -m perfiles.embeddings      # 1) embeddings de evidencias (incremental)
    python -m perfiles.construir       # 2) vistas + SNF + clustering de los tres ambitos

Salida versionada en data/perfiles/clustering/<version>/:
    manifest.json                 que datos, modelo y parametros produjeron esta version
    personas_vistas.npz           persona_id + embeddings de persona V1 y V2 (para la busqueda)
    vista_estructurada.parquet    variables de V3 sin escalar
    <ambito>/personas.parquet     asignacion, pertenencias, representante, t-SNE, estado
    <ambito>/clusters.json        fichas de los clusters, metricas y seleccion de k
    <ambito>/centroides_v1.npy, centroides_v2.npy   centroide semantico de cada cluster
    <ambito>/vecinos.parquet      30 vecinos mas cercanos de cada persona en la red fusionada
y data/perfiles/clustering/actual.json apunta a la version vigente. Se recalcula cuando cambian
las evidencias o los embeddings (la huella del manifest deja de coincidir; /api/health lo avisa).
"""
from __future__ import annotations

import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from perfiles import clustering as cl
from perfiles import embeddings as emb
from perfiles import interpretacion, snf, vistas
from perfiles.comun import (
    AMBITOS, ARCHIVO_HISTORIAL_FEATURES, CLUSTERING_DIR, archivos_evidencias, cargar_estado_personas, cargar_evidencias, huella_archivos,
    huella_texto,
)

PARAMETROS = {"snf_k_vecinos": 20, "snf_mu": 0.5, "snf_iteraciones": 20, "k_min": cl.K_MIN, "k_max": cl.K_MAX,
              "min_subdividir": cl.MIN_SUBDIVIDIR, "k_min_sub": cl.K_MIN_SUB, "k_max_sub": cl.K_MAX_SUB,
              "umbral_mixto": cl.UMBRAL_MIXTO, "tsne_perplexity": 30, "semilla": cl.SEMILLA}
NOMBRES_VISTAS = ["v1_trayectoria", "v2_academico", "v3_estructurada"]


def huella_entradas() -> dict:
    _, _, manifest_emb = emb.cargar()
    # el estado de las personas (vigencia, tipo, cargo actual) tambien define la version
    return {"evidencias": huella_archivos(archivos_evidencias()), "estado_personas": huella_archivos([ARCHIVO_HISTORIAL_FEATURES]),
            "embeddings": manifest_emb["huella_textos"],
            "modelo_embeddings": manifest_emb["modelo"], "parametros": PARAMETROS}


def _subdividir(p: pd.DataFrame, fichas: list[dict], etiquetas: np.ndarray, v1: np.ndarray, v2: np.ndarray,
                x: pd.DataFrame, ev: pd.DataFrame) -> None:
    """Segundo nivel: dentro de cada patron con >= MIN_SUBDIVIDIR personas se recalcula SNF con las
    mismas tres vistas (escalas de afinidad y estandarizacion LOCALES al patron) y se agrupa con
    clustering espectral (k por eigengap entre 2 y 8). Los subpatrones se describen frente a su
    patron padre. Modifica `p` (columnas sub*) y agrega `subdivision` a cada ficha."""
    p["subpatron"] = -1
    p["subpatron_id"] = None
    for col in ("sub_pertenencia_1", "sub_pertenencia_2", "similitud_subrepresentante"):
        p[col] = np.nan
    p["sub_cluster_2"] = -1
    p["sub_perfil_mixto"] = False
    p["subrepresentante_id"] = -1
    p["es_subrepresentante"] = False
    for f in fichas:
        c = f["cluster"]
        pos = np.flatnonzero(etiquetas == c)
        if len(pos) < cl.MIN_SUBDIVIDIR:
            f["subdivision"] = None
            continue
        xs = x.iloc[pos]
        desv = xs.std()
        zs = ((xs - xs.mean()) / desv.where(desv > 0, 1)).loc[:, desv > 0]
        afin = [snf.afinidad(snf.distancias(v), PARAMETROS["snf_k_vecinos"], PARAMETROS["snf_mu"])
                for v in (v1[pos], v2[pos], zs.to_numpy())]
        ws, _ = snf.fusionar(afin, PARAMETROS["snf_k_vecinos"], PARAMETROS["snf_iteraciones"])
        k_s, sel_s = cl.seleccionar_k(ws, cl.K_MIN_SUB, cl.K_MAX_SUB)
        lab = cl.espectral(ws, k_s)
        estab = cl.estabilidad(ws, lab, k_s)
        memb = cl.pertenencias(ws, lab, k_s)
        med = cl.medoides(ws, lab, k_s)
        orden = np.argsort(-memb, axis=1)
        filas = np.arange(len(pos))
        rep = med[lab]
        afin_rep = ws[filas, rep]
        max_afin = pd.Series(afin_rep).groupby(lab).transform("max").to_numpy()
        idx = p.index[pos]
        p.loc[idx, "subpatron"] = lab
        p.loc[idx, "subpatron_id"] = [f"{c}.{s}" for s in lab]
        p.loc[idx, "sub_pertenencia_1"] = memb[filas, orden[:, 0]]
        p.loc[idx, "sub_cluster_2"] = orden[:, 1]
        p.loc[idx, "sub_pertenencia_2"] = memb[filas, orden[:, 1]]
        p.loc[idx, "sub_perfil_mixto"] = memb[filas, orden[:, 1]] >= cl.UMBRAL_MIXTO * memb[filas, orden[:, 0]]
        p.loc[idx, "subrepresentante_id"] = p["persona_id"].to_numpy()[pos][rep]
        p.loc[idx, "es_subrepresentante"] = filas == rep
        p.loc[idx, "similitud_subrepresentante"] = np.where(filas == rep, 1.0, afin_rep / np.maximum(max_afin, 1e-12))

        sub = p.iloc[pos]
        fichas_sub = interpretacion.describir(sub[["persona_id", "tipo_empleado"]], lab, zs, xs, ev, k_s, referencia="grupo")
        for fs in fichas_sub:
            s = fs["cluster"]
            r = sub.iloc[med[s]]
            fs["subpatron_id"] = f"{c}.{s}"
            fs["representante"] = {"persona_id": int(r["persona_id"]), "cargo_actual": r["cargo_actual"],
                                   "unidad_actual": r["unidad_actual"], "vigente": bool(r["vigente"])}
            m = sub[sub["subpatron"] == s]
            fs["tamano_vigentes"] = int(m["vigente"].sum())
            fs["perfiles_mixtos"] = int(m["sub_perfil_mixto"].sum())
            fs["cohesion"] = round(float(m["sub_pertenencia_1"].mean()), 3)
        f["subdivision"] = {"k": k_s, "seleccion_k": sel_s, "estabilidad_ari": round(estab, 3),
                            "nota": "subpatrones descritos frente a su patrón padre (no frente al ámbito)",
                            "subpatrones": fichas_sub}


def _analizar(ambito: str, personas: pd.DataFrame, sem: dict, x_crudo: pd.DataFrame, ev: pd.DataFrame,
              idx: np.ndarray) -> tuple[pd.DataFrame, dict, dict]:
    t0 = time.time()
    v1, v2 = sem["v1_trayectoria"]["matriz"][idx], sem["v2_academico"]["matriz"][idx]
    x = x_crudo.iloc[idx]
    desv = x.std()
    x_z = ((x - x.mean()) / desv.where(desv > 0, 1)).loc[:, desv > 0]

    afin = [snf.afinidad(snf.distancias(v), PARAMETROS["snf_k_vecinos"], PARAMETROS["snf_mu"]) for v in (v1, v2, x_z.to_numpy())]
    w, p_vistas = snf.fusionar(afin, PARAMETROS["snf_k_vecinos"], PARAMETROS["snf_iteraciones"])

    k, seleccion = cl.seleccionar_k(w)
    etiquetas = cl.espectral(w, k)
    estab = cl.estabilidad(w, etiquetas, k)
    memb = cl.pertenencias(w, etiquetas, k)
    por_vista = cl.cluster_por_vista(p_vistas, etiquetas, k)
    med = cl.medoides(w, etiquetas, k)
    cent_v1, cent_v2 = cl.centroides(v1, etiquetas, k), cl.centroides(v2, etiquetas, k)
    xy = cl.tsne(w)
    vec_idx, vec_af = cl.vecinos(w)

    p = personas.iloc[idx].reset_index(drop=True).copy()
    orden = np.argsort(-memb, axis=1)
    p["cluster"] = etiquetas
    p["pertenencia_1"] = memb[np.arange(len(p)), orden[:, 0]]
    p["cluster_2"] = orden[:, 1]
    p["pertenencia_2"] = memb[np.arange(len(p)), orden[:, 1]]
    p["perfil_mixto"] = p["pertenencia_2"] >= cl.UMBRAL_MIXTO * p["pertenencia_1"]
    p["pertenencias"] = [json.dumps([round(float(v), 4) for v in fila]) for fila in memb]
    for j, nombre in enumerate(NOMBRES_VISTAS):
        p[f"cluster_{nombre}"] = por_vista[:, j]
    rep = med[etiquetas]
    afin_rep = w[np.arange(len(p)), rep]
    max_afin = pd.Series(afin_rep).groupby(etiquetas).transform("max").to_numpy()
    p["representante_id"] = p["persona_id"].to_numpy()[rep]
    p["es_representante"] = np.arange(len(p)) == rep
    p["similitud_representante"] = np.where(p["es_representante"], 1.0, afin_rep / np.maximum(max_afin, 1e-12))
    p["coseno_v1_representante"] = (v1 * v1[rep]).sum(axis=1)
    p["coseno_v2_representante"] = (v2 * v2[rep]).sum(axis=1)
    p["coseno_v1_centroide"] = (v1 * cent_v1[etiquetas]).sum(axis=1)
    p["coseno_v2_centroide"] = (v2 * cent_v2[etiquetas]).sum(axis=1)
    p["tsne_x"], p["tsne_y"] = xy[:, 0], xy[:, 1]
    p["vista_v1_faltante"] = sem["v1_trayectoria"]["faltante"][idx]
    p["vista_v2_faltante"] = sem["v2_academico"]["faltante"][idx]

    fichas = interpretacion.describir(p[["persona_id", "tipo_empleado"]], etiquetas, x_z, x, ev, k)
    for f in fichas:
        c = f["cluster"]
        r = p.iloc[med[c]]
        f["representante"] = {"persona_id": int(r["persona_id"]), "cargo_actual": r["cargo_actual"],
                              "unidad_actual": r["unidad_actual"], "vigente": bool(r["vigente"])}
        miembros = p[p["cluster"] == c]
        f["tamano_vigentes"] = int(miembros["vigente"].sum())
        f["perfiles_mixtos"] = int(miembros["perfil_mixto"].sum())
        f["cohesion"] = round(float(miembros["pertenencia_1"].mean()), 3)
    _subdividir(p, fichas, etiquetas, v1, v2, x, ev)
    vecinos = pd.DataFrame({
        "persona_id": np.repeat(p["persona_id"].to_numpy(), vec_idx.shape[1]),
        "vecino_id": p["persona_id"].to_numpy()[vec_idx.ravel()],
        "afinidad": vec_af.ravel().astype(np.float32),
        "rango": np.tile(np.arange(1, vec_idx.shape[1] + 1), len(p)),
    })
    resumen = {
        "ambito": ambito, "nombre": AMBITOS[ambito], "n_personas": len(p), "n_vigentes": int(p["vigente"].sum()),
        "k": k, "seleccion_k": seleccion, "estabilidad_ari": round(estab, 3),
        "perfiles_mixtos": int(p["perfil_mixto"].sum()),
        "variables_estructuradas_usadas": list(x_z.columns),
        "vistas": NOMBRES_VISTAS, "segundos": round(time.time() - t0, 1), "clusters": fichas,
    }
    return p, resumen, {"centroides_v1": cent_v1, "centroides_v2": cent_v2, "vecinos": vecinos}


def construir() -> dict:
    ev = cargar_evidencias()
    personas_ids = sorted(ev["persona_id"].unique().tolist())
    estado = cargar_estado_personas().set_index("persona_id")
    personas = pd.DataFrame({"persona_id": personas_ids})
    personas = personas.join(estado, on="persona_id")
    personas["vigente"] = personas["vigente"].fillna(False).astype(bool)

    sem = vistas.vistas_semanticas(ev, personas_ids)
    x_crudo = vistas.vista_estructurada(ev, personas_ids)

    entradas = huella_entradas()
    huella = huella_texto(entradas)
    version = f"{datetime.now():%Y%m%d-%H%M}_{huella[:8]}"
    carpeta = CLUSTERING_DIR / version
    carpeta.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(carpeta / "personas_vistas.npz", persona_id=np.array(personas_ids),
                        v1_trayectoria=sem["v1_trayectoria"]["matriz"], v2_academico=sem["v2_academico"]["matriz"])
    x_crudo.reset_index().to_parquet(carpeta / "vista_estructurada.parquet", index=False)

    resumenes = {}
    tipo = personas["tipo_empleado"]
    seleccion = {"todos": np.arange(len(personas)),
                 "administrativos": np.flatnonzero(tipo == "ADMINISTRATIVO"),
                 "docentes": np.flatnonzero(tipo == "DOCENTE")}
    for ambito, idx in seleccion.items():
        p, resumen, extra = _analizar(ambito, personas, sem, x_crudo, ev, idx)
        d = carpeta / ambito
        d.mkdir(exist_ok=True)
        p.to_parquet(d / "personas.parquet", index=False)
        (d / "clusters.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        np.save(d / "centroides_v1.npy", extra["centroides_v1"])
        np.save(d / "centroides_v2.npy", extra["centroides_v2"])
        extra["vecinos"].to_parquet(d / "vecinos.parquet", index=False)
        resumenes[ambito] = {k: resumen[k] for k in ("n_personas", "n_vigentes", "k", "estabilidad_ari", "perfiles_mixtos", "segundos")}
        print(ambito, json.dumps(resumenes[ambito], ensure_ascii=False))

    manifest = {
        "version": version, "huella": huella, "fecha": datetime.now().isoformat(timespec="seconds"),
        "entradas": entradas, "ambitos": resumenes,
        "fuente_estado_personas": "data/processed/historial_laboral_features.csv (VIGENTE_ACTUALMENTE, TIPOEMPLEADO_ACTUAL_DESC)",
        "vistas": {
            "v1_trayectoria": "embeddings (bge-m3) de cargos, contratos, funciones, experiencia externa y actividades de carga",
            "v2_academico": "embeddings (bge-m3) de formación, investigación, publicaciones, tesis, ponencias, vinculación, materias, capacitación y menciones",
            "v3_estructurada": "variables agregadas de los atributos de las evidencias (perfiles/vistas.py)",
        },
        "metodo": "Similarity Network Fusion + clustering espectral; pertenencia derivada de la red fusionada; medoide como representante; t-SNE sobre la red fusionada solo para visualizar",
    }
    (carpeta / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (CLUSTERING_DIR / "actual.json").write_text(json.dumps({"version": version, "huella": huella}, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(construir()["ambitos"], ensure_ascii=False, indent=2))
