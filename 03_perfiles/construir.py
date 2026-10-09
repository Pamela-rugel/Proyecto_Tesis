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
    <ambito>/dimensiones.parquet  intensidad (percentil 0-100 en el ambito) por dimension de evidencia (DEC-053)
    dimensiones.json              definicion de dimensiones, componentes y pesos
    <ambito>/temas_dimension.parquet     proporcion de las evidencias de cada persona en cada tema descubierto (DEC-055)
    <ambito>/patrones_dimension.parquet  patron de actividad de cada persona en cada dimension (DEC-055)
    <ambito>/micro_dimensiones.json      fichas de temas y patrones por dimension
    <ambito>/mapas_dimension.parquet     coordenadas t-SNE (solo visualizacion) por dimension: mapa de patrones y de temas
    <ambito>/perfil_conjunto_mapa.parquet, perfil_conjunto_vecinos.parquet   perfil completo (todas las dimensiones): t-SNE y vecinos (DEC-056)
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
from perfiles import dimensiones, interpretacion, micro_dimensiones, perfil_conjunto, snf, vistas
from perfiles.comun import (
    AMBITOS, ARCHIVO_HISTORIAL_FEATURES, CLUSTERING_DIR, EMBEDDINGS_TEMA_DIR, archivos_evidencias, cargar_estado_personas, cargar_evidencias, en_ambito,
    huella_archivos,
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
            "modelo_embeddings": manifest_emb["modelo"], "parametros": PARAMETROS,
            "dimensiones": dimensiones.definiciones(),
            "embeddings_tema": emb.cargar(EMBEDDINGS_TEMA_DIR)[2]["huella_textos"],
            "micro_dimensiones": {"min_personas": micro_dimensiones.MIN_PERSONAS, "min_textos": micro_dimensiones.MIN_TEXTOS,
                                  "fraccion_tema": micro_dimensiones.FRACCION_TEMA,
                                  "k_patron": [micro_dimensiones.K_MIN_PATRON, micro_dimensiones.K_MAX_PATRON],
                                  "proporciones": micro_dimensiones.PROPORCIONES,
                                  "mapas": "t-SNE perplejidad<=30, PCA a 50 si hace falta"},
            "perfil_conjunto": {"n_vecinos": perfil_conjunto.N_VECINOS,
                                "patrones_globales": {"k": [perfil_conjunto.K_MIN_GLOBAL, perfil_conjunto.K_MAX_GLOBAL],
                                                      "k_micro": [perfil_conjunto.K_MIN_MICRO, perfil_conjunto.K_MAX_MICRO],
                                                      "min_subdividir": perfil_conjunto.MIN_SUBDIVIDIR,
                                                      "ari_minimo": perfil_conjunto.ARI_MINIMO}}}


def _ficha_persona(p: pd.DataFrame, i: int) -> dict | None:
    if i < 0:
        return None
    r = p.iloc[i]
    return {"persona_id": int(r["persona_id"]), "cargo_actual": r["cargo_actual"], "unidad_actual": r["unidad_actual"],
            "vigente": bool(r["vigente"])}


def _representantes(w: np.ndarray, etiquetas: np.ndarray, k: int, vigente: np.ndarray):
    """Representante = medoide elegido SOLO entre vigentes (-1 si el grupo no tiene vigentes) y
    medoide estructural (cualquier integrante, referencia del método). Devuelve
    (med_vigente, med_estructural, rep_por_persona, similitud_al_representante)."""
    med_vig = cl.medoides(w, etiquetas, k, elegibles=vigente)
    med_est = cl.medoides(w, etiquetas, k)
    rep = med_vig[etiquetas]
    filas = np.arange(len(w))
    tiene = rep >= 0
    afin = np.where(tiene, w[filas, np.where(tiene, rep, 0)], np.nan)
    maximo = pd.Series(afin).groupby(etiquetas).transform("max").to_numpy()
    sim = np.where(filas == rep, 1.0, afin / np.maximum(np.nan_to_num(maximo, nan=0.0), 1e-12))
    return med_vig, med_est, rep, np.where(tiene, sim, np.nan)


def _subdividir(p: pd.DataFrame, fichas: list[dict], etiquetas: np.ndarray, v1: np.ndarray, v2: np.ndarray,
                x: pd.DataFrame, ev: pd.DataFrame) -> None:
    """Segundo nivel: dentro de cada grupo con >= MIN_SUBDIVIDIR personas se recalcula SNF con las
    mismas tres vistas (escalas de afinidad y estandarizacion LOCALES al grupo) y se agrupa con
    clustering espectral (k por eigengap entre 2 y 8). Modifica `p` (columnas sub*) y agrega
    `subdivision` a cada ficha. Los nombres neutrales se asignan en `_microarquetipos`."""
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
        cl.validar_afinidades(memb)
        sub = p.iloc[pos]
        med_vig, med_est, rep, sim = _representantes(ws, lab, k_s, sub["vigente"].to_numpy())
        orden = np.argsort(-memb, axis=1)
        filas = np.arange(len(pos))
        idx = p.index[pos]
        p.loc[idx, "subpatron"] = lab
        p.loc[idx, "subpatron_id"] = [f"{c}.{s}" for s in lab]
        p.loc[idx, "sub_pertenencia_1"] = memb[filas, orden[:, 0]]
        p.loc[idx, "sub_cluster_2"] = orden[:, 1]
        p.loc[idx, "sub_pertenencia_2"] = memb[filas, orden[:, 1]]
        p.loc[idx, "sub_perfil_mixto"] = memb[filas, orden[:, 1]] >= cl.UMBRAL_MIXTO * memb[filas, orden[:, 0]]
        p.loc[idx, "subrepresentante_id"] = np.where(rep >= 0, sub["persona_id"].to_numpy()[np.maximum(rep, 0)], -1)
        p.loc[idx, "es_subrepresentante"] = filas == rep
        p.loc[idx, "similitud_subrepresentante"] = sim

        sub = p.iloc[pos]
        fichas_sub = interpretacion.describir(sub[["persona_id", "tipo_empleado"]], lab, zs, xs, ev, k_s, referencia="grupo")
        for fs in fichas_sub:
            s = fs["cluster"]
            fs["subpatron_id"] = f"{c}.{s}"
            fs["representante"] = _ficha_persona(sub, int(med_vig[s]))
            fs["medoide_estructural"] = _ficha_persona(sub, int(med_est[s]))
            m = sub[sub["subpatron"] == s]
            fs["tamano_vigentes"] = int(m["vigente"].sum())
            fs["perfiles_mixtos"] = int(m["sub_perfil_mixto"].sum())
            fs["cohesion"] = round(float(m["sub_pertenencia_1"].mean()), 3)
        f["subdivision"] = {"k": k_s, "seleccion_k": sel_s, "estabilidad_ari": round(estab, 3),
                            "nota": "subgrupos descritos frente a su grupo (no frente al ámbito)",
                            "subpatrones": fichas_sub}


def _microarquetipos(p: pd.DataFrame, fichas: list[dict], w: np.ndarray, v1: np.ndarray, v2: np.ndarray,
                     x_z: pd.DataFrame, x: pd.DataFrame, ev: pd.DataFrame) -> tuple[list[dict], dict, dict]:
    """Microarquetipos del ámbito = hojas de la jerarquía: cada subgrupo de un grupo subdividido y
    cada grupo no subdividido. Se reutiliza la subdivisión existente (no se impone un número).

    - Etiqueta exclusiva (la hoja) como referencia estructural.
    - Afinidad DERIVADA (no probabilidad) con cada microarquetipo del ámbito: afinidad media en la
      MISMA red fusionada del ámbito con sus integrantes, normalizada (finita, >= 0, suma 1).
    - Perfil mixto: la 2.ª afinidad >= UMBRAL_MIXTO x la 1.ª.
    - Representante: medoide entre VIGENTES (o vacío); centroide semántico V1/V2 aparte.
    - Nombres NEUTRALES ("Microarquetipo n", "Grupo n"); la descripción sale de estadísticas frente
      al ámbito (tipos de evidencia, rasgos, términos, unidades) y no del cargo predominante."""
    hoja = list(zip(p["cluster"].astype(int), p["subpatron"].astype(int)))
    claves = sorted(set(hoja))
    pos_clave = {kv: i for i, kv in enumerate(claves)}
    lab = np.array([pos_clave[h] for h in hoja])
    m = len(claves)
    memb = cl.pertenencias(w, lab, m)
    cl.validar_afinidades(memb)
    vig = p["vigente"].to_numpy()
    med_vig, med_est, rep, sim = _representantes(w, lab, m, vig)
    cent_v1, cent_v2 = cl.centroides(v1, lab, m), cl.centroides(v2, lab, m)

    orden = np.argsort(-memb, axis=1)
    filas = np.arange(len(p))
    p["microarquetipo"] = lab
    p["micro_afinidad_1"] = memb[filas, orden[:, 0]]
    p["micro_2"] = orden[:, 1] if m > 1 else -1
    p["micro_afinidad_2"] = memb[filas, orden[:, 1]] if m > 1 else 0.0
    p["micro_mixto"] = p["micro_afinidad_2"] >= cl.UMBRAL_MIXTO * p["micro_afinidad_1"]
    p["micro_afinidades"] = [json.dumps([round(float(v), 4) for v in fila]) for fila in memb]
    p["microrepresentante_id"] = np.where(rep >= 0, p["persona_id"].to_numpy()[np.maximum(rep, 0)], -1)
    p["similitud_microrepresentante"] = sim

    nombre = {i: f"Microarquetipo {i + 1}" for i in range(m)}
    fichas_m = interpretacion.describir(p[["persona_id", "tipo_empleado"]], lab, x_z, x, ev, m)
    for f in fichas_m:
        i = f["cluster"]
        c, s = claves[i]
        f["id"] = i
        f["nombre"] = nombre[i]
        f["etiqueta_descriptiva"] = f.pop("etiqueta")  # trazabilidad; la interfaz no la usa como nombre
        f["etiqueta"] = nombre[i]
        f["grupo"] = int(c)
        f["subgrupo"] = int(s)
        f["representante"] = _ficha_persona(p, int(med_vig[i]))
        f["medoide_estructural"] = _ficha_persona(p, int(med_est[i]))
        integrantes = p[lab == i]
        f["tamano_vigentes"] = int(integrantes["vigente"].sum())
        f["perfiles_mixtos"] = int(integrantes["micro_mixto"].sum())
        f["afinidad_media_propia"] = round(float(integrantes["micro_afinidad_1"].mean()), 3)

    # nombres neutrales también en los grupos y subgrupos (misma numeración que las hojas)
    for f in fichas:
        c = f["cluster"]
        f["etiqueta_descriptiva"] = f["etiqueta"]
        f["etiqueta"] = f"Grupo {c + 1}"
        f["microarquetipos"] = [pos_clave[kv] for kv in claves if kv[0] == c]
        for fs in (f.get("subdivision") or {}).get("subpatrones", []):
            fs["etiqueta_descriptiva"] = fs["etiqueta"]
            fs["etiqueta"] = nombre[pos_clave[(c, fs["cluster"])]]
            fs["microarquetipo"] = pos_clave[(c, fs["cluster"])]

    metricas = {
        "n_microarquetipos": m,
        "perfiles_mixtos": int(p["micro_mixto"].sum()),
        "afinidad_maxima_media": round(float(p["micro_afinidad_1"].mean()), 3),
        "proporcion_afinidad_maxima_igual_a_etiqueta": round(float((orden[:, 0] == lab).mean()), 3),
        "microarquetipos_sin_vigentes": int((med_vig < 0).sum()),
    }
    return fichas_m, {"centroides_micro_v1": cent_v1, "centroides_micro_v2": cent_v2}, metricas


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
    cl.validar_afinidades(memb)
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
    med_vig, med_est, rep, sim = _representantes(w, etiquetas, k, p["vigente"].to_numpy())
    tiene = rep >= 0
    rep0 = np.maximum(rep, 0)
    p["representante_id"] = np.where(tiene, p["persona_id"].to_numpy()[rep0], -1)
    p["es_representante"] = np.arange(len(p)) == rep
    p["similitud_representante"] = sim
    p["coseno_v1_representante"] = np.where(tiene, (v1 * v1[rep0]).sum(axis=1), np.nan)
    p["coseno_v2_representante"] = np.where(tiene, (v2 * v2[rep0]).sum(axis=1), np.nan)
    p["coseno_v1_centroide"] = (v1 * cent_v1[etiquetas]).sum(axis=1)
    p["coseno_v2_centroide"] = (v2 * cent_v2[etiquetas]).sum(axis=1)
    p["tsne_x"], p["tsne_y"] = xy[:, 0], xy[:, 1]
    p["vista_v1_faltante"] = sem["v1_trayectoria"]["faltante"][idx]
    p["vista_v2_faltante"] = sem["v2_academico"]["faltante"][idx]

    fichas = interpretacion.describir(p[["persona_id", "tipo_empleado"]], etiquetas, x_z, x, ev, k)
    for f in fichas:
        c = f["cluster"]
        f["representante"] = _ficha_persona(p, int(med_vig[c]))
        f["medoide_estructural"] = _ficha_persona(p, int(med_est[c]))
        miembros = p[p["cluster"] == c]
        f["tamano_vigentes"] = int(miembros["vigente"].sum())
        f["perfiles_mixtos"] = int(miembros["perfil_mixto"].sum())
        f["cohesion"] = round(float(miembros["pertenencia_1"].mean()), 3)
    _subdividir(p, fichas, etiquetas, v1, v2, x, ev)
    fichas_micro, cent_micro, met_micro = _microarquetipos(p, fichas, w, v1, v2, x_z, x, ev)
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
        "microarquetipos": fichas_micro, "metricas_microarquetipos": met_micro,
    }
    return p, resumen, {"centroides_v1": cent_v1, "centroides_v2": cent_v2, "vecinos": vecinos, **cent_micro}


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
    comp_dim, n_ev_dim = dimensiones.componentes_crudos(ev, personas_ids)
    ev_dim = dimensiones.evidencias_de_dimension(ev)
    textos_tema, vec_tema, _ = emb.cargar(EMBEDDINGS_TEMA_DIR)
    pos_tema = dict(zip(textos_tema["clave"], range(len(textos_tema))))
    (carpeta / "dimensiones.json").write_text(json.dumps(dimensiones.definiciones(), ensure_ascii=False, indent=2), encoding="utf-8")

    resumenes = {}
    # DEC-054: quien tiene hoy contratos activos administrativo y docente entra en ambos ámbitos
    seleccion = {a: np.flatnonzero(en_ambito(personas["tipo_empleado"], a).to_numpy()) for a in AMBITOS}
    for ambito, idx in seleccion.items():
        p, resumen, extra = _analizar(ambito, personas, sem, x_crudo, ev, idx)
        d = carpeta / ambito
        d.mkdir(exist_ok=True)
        p.to_parquet(d / "personas.parquet", index=False)
        (d / "clusters.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        np.save(d / "centroides_v1.npy", extra["centroides_v1"])
        np.save(d / "centroides_v2.npy", extra["centroides_v2"])
        np.save(d / "centroides_micro_v1.npy", extra["centroides_micro_v1"])
        np.save(d / "centroides_micro_v2.npy", extra["centroides_micro_v2"])
        extra["vecinos"].to_parquet(d / "vecinos.parquet", index=False)
        ids = personas["persona_id"].to_numpy()[idx]
        dim = dimensiones.intensidades(comp_dim.loc[ids], n_ev_dim.loc[ids])
        dim.to_parquet(d / "dimensiones.parquet", index=False)
        t0 = time.time()
        temas_p, patrones_p, mapas_p, micro_r = micro_dimensiones.construir_ambito(
            ids, personas["vigente"].to_numpy()[idx], comp_dim, n_ev_dim, ev_dim, pos_tema, vec_tema)
        temas_p.to_parquet(d / "temas_dimension.parquet", index=False)
        patrones_p.to_parquet(d / "patrones_dimension.parquet", index=False)
        mapas_p.to_parquet(d / "mapas_dimension.parquet", index=False)
        k_pat = {k: (v["patrones"] or {}).get("k", 0) for k, v in micro_r.items()}
        mapa_c, vecinos_c = perfil_conjunto.construir_ambito(ids, dim, patrones_p, k_pat)
        mapa_c.to_parquet(d / "perfil_conjunto_mapa.parquet", index=False)
        vecinos_c.to_parquet(d / "perfil_conjunto_vecinos.parquet", index=False)
        glob_p, glob_r = perfil_conjunto.patrones_globales(ids, personas["vigente"].to_numpy()[idx], dim, patrones_p, k_pat)
        glob_p.to_parquet(d / "patrones_globales.parquet", index=False)
        (d / "patrones_globales.json").write_text(json.dumps(glob_r, ensure_ascii=False, indent=2), encoding="utf-8")
        print(ambito, "patrones globales:", glob_r["k"], "ARI", glob_r["estabilidad_ari"],
              "microarquetipos:", glob_r["n_microarquetipos"])
        (d / "micro_dimensiones.json").write_text(json.dumps(micro_r, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(ambito, "temas / patrones por dimensión:",
              {k: ((v["temas"] or {}).get("k", 0), (v["patrones"] or {}).get("k", 0)) for k, v in micro_r.items()},
              f"{time.time() - t0:.0f}s")
        resumenes[ambito] = {**{k: resumen[k] for k in ("n_personas", "n_vigentes", "k", "estabilidad_ari", "perfiles_mixtos", "segundos")},
                             "microarquetipos": resumen["metricas_microarquetipos"]}
        print(ambito, json.dumps(resumenes[ambito], ensure_ascii=False))

    manifest = {
        "version": version, "huella": huella, "fecha": datetime.now().isoformat(timespec="seconds"),
        "entradas": entradas, "ambitos": resumenes,
        "fuente_estado_personas": "data/processed/historial_laboral_features.csv (VIGENTE_ACTUALMENTE, TIPOS_EMPLEADO_ACTUALES)",
        "vistas": {
            "v1_trayectoria": "embeddings (bge-m3) de cargos, contratos, funciones, experiencia externa y actividades de carga",
            "v2_academico": "embeddings (bge-m3) de formación, investigación, publicaciones, tesis, ponencias, vinculación, materias, capacitación y menciones",
            "v3_estructurada": "variables agregadas de los atributos de las evidencias (perfiles/vistas.py)",
        },
        "metodo": "Similarity Network Fusion + clustering espectral; pertenencia derivada de la red fusionada; medoide como representante; t-SNE sobre la red fusionada solo para visualizar",
        "microarquetipos": ("hojas de la jerarquía grupo/subgrupo (subdivisión existente, sin k impuesto); afinidad DERIVADA "
                            "(no probabilidad) con cada microarquetipo en la red fusionada del ámbito, normalizada a suma 1; "
                            f"perfil mixto si 2.ª >= {cl.UMBRAL_MIXTO} x 1.ª; representante = medoide entre VIGENTES (vacío si no hay); "
                            "centroide semántico V1/V2 aparte; nombres neutrales; ámbitos independientes"),
        "dimensiones": ("intensidad 0-100 = percentil, dentro del ámbito, de un índice ponderado de componentes "
                        "normalizados por el máximo del ámbito; 0 sin evidencias; dimensiones independientes (no suman 100); "
                        "ver dimensiones.json"),
        "micro_dimensiones": ("sin categorías predefinidas, por dimensión y ámbito: TEMAS = UMAP + HDBSCAN sobre los embeddings "
                              "del título/nombre de las evidencias (proporción por persona); PATRONES DE ACTIVIDAD = KMeans "
                              "(k 3-6 por silueta) sobre componentes y proporciones estandarizados; "
                              f"no se subdivide con menos de {micro_dimensiones.MIN_PERSONAS} personas"),
        "perfil_conjunto": ("por dimensión, afinidades con sus patrones x intensidad/100 (o solo la intensidad si no tiene "
                            f"patrones); t-SNE para visualizar y {perfil_conjunto.N_VECINOS} vecinos por distancia euclidiana; sin grupos"),
        "patrones_globales": ("KMeans sobre el vector de perfil completo; k entre 4 y 8 = mayor silueta entre los k con "
                              "estabilidad ARI >= 0,9; descritos por dimensiones con intensidad media alta/baja frente al ámbito"),
        "ambitos_doble_tipo": "quien tiene contratos activos administrativo y docente entra en ambos ámbitos (DEC-054)",
        "semilla": cl.SEMILLA,
    }
    (carpeta / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (CLUSTERING_DIR / "actual.json").write_text(json.dumps({"version": version, "huella": huella}, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(construir()["ambitos"], ensure_ascii=False, indent=2))
