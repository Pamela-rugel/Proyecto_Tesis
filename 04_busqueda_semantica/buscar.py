"""Búsqueda de personas: orquesta todas las etapas (DISENO.md §4).

    consulta → interpretación (LLM) → universo (vigencia + requisitos de persona)
             → candidatos por capacidad × tipo (denso + BM25, RRF, percentil en el tipo)
             → relevancia por evidencia (cross-encoder)
             → por persona y capacidad: la MEJOR evidencia (no la suma: el volumen no premia)
             → requisitos de años: unión de intervalos de las evidencias relevantes
             → ranking: nº de obligatorias cubiertas → media geométrica → deseables
             → explicación con las evidencias que sustentan cada capacidad

Uso:  python -m busqueda.buscar "consulta" [--todos | --no-vigentes] [--sin-llm] [--juez fusion|cross_encoder|percentil]
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

import numpy as np
import pandas as pd

from busqueda import temporal
from busqueda.comun import (
    ARCHIVO_REGISTRO, BUSQUEDA_DIR, EVIDENCIAS_POR_CAPACIDAD, JUEZ, N_RESULTADOS, NOMBRE_TIPO, RRF_K, UMBRALES,
)
from busqueda.indice import Indice, cargar_indice
from busqueda.interpretacion import Interpretacion, interpretar
from busqueda.recuperacion import candidatos
from busqueda.rerank import probabilidades

NIVEL_MINIMO = {"tercer_nivel": 2.0, "maestria": 3.0, "doctorado": 4.0}
NIVEL_IDIOMA_MINIMO = {"basico": 1, "intermedio": 2, "avanzado": 3, None: 1}


def _universo(ix: Indice, interp: Interpretacion, vigencia: str) -> tuple[pd.DataFrame, str, list[str]]:
    """Personas candidatas. La vigencia de la CONSULTA prevalece sobre el filtro de la vista."""
    aplicada = interp.vigencia if interp.vigencia != "no_especificada" else vigencia
    p = ix.personas
    if aplicada == "vigentes":
        p = p[p["vigente"]]
    elif aplicada == "no_vigentes":
        p = p[~p["vigente"]]
    filtros = []
    rp = interp.requisitos_persona
    if rp.nivel_formacion_minimo:
        p = p[p["nivel_formacion"] >= NIVEL_MINIMO[rp.nivel_formacion_minimo]]
        filtros.append(f"formación ≥ {rp.nivel_formacion_minimo.replace('_', ' ')}")
    for req in rp.idiomas:
        idioma, minimo = req.idioma.upper().strip(), NIVEL_IDIOMA_MINIMO[req.nivel_minimo]
        p = p[p["idiomas"].map(lambda d: d.get(idioma, 0) >= minimo)]
        filtros.append(f"{idioma.capitalize()} ≥ {req.nivel_minimo or 'registrado'}")
    return p, aplicada, filtros


def _nivel(r: float, umbral: float) -> str:
    """alta: en la mitad superior por encima del umbral; media: sobre el umbral; baja: debajo."""
    return "alta" if r >= (1 + umbral) / 2 else ("media" if r >= umbral else "baja")


def _relevancia(juez: str, cap, c: pd.DataFrame, ix: Indice) -> dict[int, float]:
    """Relevancia (0–1) de cada texto candidato de una capacidad, según el juez."""
    pct = c.groupby("texto_idx")["percentil"].max()
    if juez == "percentil":
        return pct.to_dict()
    textos = pct.index.to_numpy()
    # el reranker juzga solo el TEMA (las palabras del tipo creaban falsos positivos)
    prob = probabilidades(cap.tema, ix.textos.texto.iloc[textos].tolist())
    if juez == "cross_encoder":
        return dict(zip(textos, prob))
    r1 = pd.Series(prob).rank(ascending=False, method="first").to_numpy()
    r2 = pct.rank(ascending=False, method="first").to_numpy()
    fus = 1.0 / (RRF_K + r1) + 1.0 / (RRF_K + r2)
    return dict(zip(textos, fus / fus.max()))


def buscar(consulta: str, vigencia: str = "vigentes", usar_llm: bool = True, juez: str = JUEZ,
           umbral: float | None = None, por_tipo: bool = True, lexico: bool = True, n: int = N_RESULTADOS,
           registrar: bool = True) -> dict:
    t = {"inicio": time.time()}
    ix = cargar_indice()
    interp, meta = interpretar(consulta, usar_llm=usar_llm)
    t["interpretacion"] = time.time()

    universo, vigencia_aplicada, filtros = _universo(ix, interp, vigencia)
    ev = ix.ev[ix.ev["persona_id"].isin(universo.index)]
    textos_universo = ev["texto_idx"].unique()
    umbral = UMBRALES[juez] if umbral is None else umbral

    filas = []
    for cap in interp.capacidades:
        c = candidatos(ix, cap, textos_universo, por_tipo=por_tipo, lexico=lexico)
        if c.empty:
            continue
        rel = _relevancia(juez, cap, c, ix)
        tipos_cap = set(cap.tipos) if por_tipo else None
        e = ev[ev["texto_idx"].isin(rel)]
        if tipos_cap:
            e = e[e["tipo_id"].isin(tipos_cap)]
        e = e.assign(capacidad=cap.id, relevancia=e["texto_idx"].map(rel).astype(float))
        filas.append(e)
    t["recuperacion"] = time.time()

    resultados = []
    if filas:
        rel_ev = pd.concat(filas, ignore_index=True)
        caps = {c.id: c for c in interp.capacidades}
        mixtos = {m.capacidad: m.anios_minimos for m in interp.requisitos_mixtos}
        obligatorias = [c.id for c in interp.capacidades if c.importancia == "obligatoria"]
        deseables = [c.id for c in interp.capacidades if c.importancia == "deseable"]
        for pid, g in rel_ev.groupby("persona_id"):
            persona = universo.loc[pid]
            detalle, puntaje = [], {}
            for cid, cap in caps.items():
                gc = g[g["capacidad"] == cid].sort_values("relevancia", ascending=False)
                gc = gc.drop_duplicates("texto_idx")
                mejor = float(gc["relevancia"].iloc[0]) if len(gc) else 0.0
                puntaje[cid] = mejor
                cubierta = mejor >= umbral
                req = None
                if cid in mixtos:
                    relevantes = gc[gc["relevancia"] >= umbral]
                    ivs, precisiones = [], set()
                    for tipo, s in zip(relevantes["tipo_id"], relevantes["atributos"]):
                        iv, prec, _ = temporal.intervalos(tipo, json.loads(s), bool(persona["vigente"]))
                        if prec not in ("solo_fin", "puntual"):
                            ivs += iv
                        precisiones.add(prec)
                    anios = temporal.anios_union(ivs)
                    estado = "cumple" if anios >= mixtos[cid] else ("no_verificable" if not ivs else "no_cumple")
                    req = {"anios_minimos": mixtos[cid], "anios": anios, "estado": estado,
                           "aproximado": "semestre" in precisiones or "anio" in precisiones}
                    cubierta = cubierta and estado == "cumple"
                evidencias = []
                # se muestran las evidencias que superan el umbral; si ninguna, solo la mejor
                mostrar = gc[gc["relevancia"] >= umbral]
                mostrar = (mostrar if len(mostrar) else gc).head(EVIDENCIAS_POR_CAPACIDAD if len(mostrar) else 1)
                for _, r in mostrar.iterrows():
                    iv, prec, _ = temporal.intervalos(r["tipo_id"], json.loads(r["atributos"]), bool(persona["vigente"]))
                    evidencias.append({"tipo": NOMBRE_TIPO.get(r["tipo_id"], r["tipo_id"]), "texto": r["texto"],
                                       "fechas": temporal.rango_texto(iv, prec), "relevancia": round(float(r["relevancia"]), 3),
                                       "nivel": _nivel(float(r["relevancia"]), umbral)})
                detalle.append({"id": cid, "descripcion": cap.descripcion, "importancia": cap.importancia,
                                "cubierta": bool(cubierta), "relevancia": round(mejor, 3),
                                "nivel": _nivel(mejor, umbral), "requisito_anios": req, "evidencias": evidencias})
            cubiertas = sum(d["cubierta"] for d in detalle if d["id"] in obligatorias)
            geo = float(np.exp(np.mean([np.log(max(puntaje[c], 1e-3)) for c in obligatorias]))) if obligatorias else 0.0
            des = float(np.mean([puntaje[c] for c in deseables])) if deseables else 0.0
            resultados.append({
                "persona_id": int(pid), "cargo_actual": persona.get("cargo_actual"), "unidad_actual": persona.get("unidad_actual"),
                "tipo_empleado": persona.get("tipo_empleado"), "vigente": bool(persona["vigente"]),
                "obligatorias_cubiertas": int(cubiertas), "total_obligatorias": len(obligatorias),
                "deseables_cubiertas": int(sum(d["cubierta"] for d in detalle if d["id"] in deseables)),
                "puntaje": round(geo, 4), "puntaje_deseables": round(des, 4), "capacidades": detalle,
            })
        resultados.sort(key=lambda r: (r["obligatorias_cubiertas"], r["puntaje"], r["puntaje_deseables"]), reverse=True)
    t["ranking"] = time.time()

    salida = {
        "consulta": consulta, "interpretacion": interp.model_dump(), "interpretacion_meta": meta,
        "vigencia_aplicada": vigencia_aplicada, "requisitos_aplicados": filtros, "personas_en_universo": int(len(universo)),
        "personas_con_alguna_evidencia": len(resultados),
        "configuracion": {"juez": juez, "por_tipo": por_tipo, "lexico": lexico, "llm": usar_llm,
                          "umbral": umbral},
        "tiempos_s": {"interpretacion": round(t["interpretacion"] - t["inicio"], 2),
                      "recuperacion_y_reranking": round(t["recuperacion"] - t["interpretacion"], 2),
                      "ranking": round(t["ranking"] - t["recuperacion"], 2),
                      "total": round(t["ranking"] - t["inicio"], 2)},
        "resultados": resultados[:n],
    }
    if registrar:
        BUSQUEDA_DIR.mkdir(parents=True, exist_ok=True)
        with open(ARCHIVO_REGISTRO, "a", encoding="utf-8") as f:  # sin datos de personas
            f.write(json.dumps({"fecha": datetime.now().isoformat(timespec="seconds"), "consulta": consulta,
                                "interpretacion": salida["interpretacion"], "meta": meta,
                                "vigencia": vigencia_aplicada, "configuracion": salida["configuracion"],
                                "n_resultados": len(resultados), "tiempos_s": salida["tiempos_s"]}, ensure_ascii=False) + "\n")
    return salida


def imprimir(r: dict, n: int = 8) -> None:
    """Resumen legible (sin nombres ni identificadores de personas)."""
    i = r["interpretacion"]
    print(f"\nConsulta: {r['consulta']}")
    print(f"Entendí ({r['interpretacion_meta'].get('fuente')}): ")
    for c in i["capacidades"]:
        print(f"  {c['id']} [{c['importancia']}] {c['descripcion']}  → buscado en: {', '.join(NOMBRE_TIPO[t] for t in c['tipos'])}")
    extra = r["requisitos_aplicados"] + [f"{m['capacidad']}: ≥ {m['anios_minimos']:g} años" for m in i["requisitos_mixtos"]]
    print(f"  vigencia: {r['vigencia_aplicada']}" + (f" · {' · '.join(extra)}" if extra else ""))
    print(f"Universo {r['personas_en_universo']} personas · con evidencias relevantes {r['personas_con_alguna_evidencia']} · "
          f"tiempo {r['tiempos_s']['total']} s")
    for k, p in enumerate(r["resultados"][:n], 1):
        print(f"\n{k}. {p['cargo_actual']} · {p['unidad_actual']}  — obligatorias {p['obligatorias_cubiertas']}/{p['total_obligatorias']}"
              f" · puntaje {p['puntaje']:.3f}")
        for c in p["capacidades"]:
            marca = "✓" if c["cubierta"] else "✗"
            req = c["requisito_anios"]
            extra = f" · {req['anios']:g} años ({req['estado']})" if req else ""
            print(f"   {marca} {c['id']} {c['descripcion']}: relevancia {c['nivel']}{extra}")
            for e in c["evidencias"][:2]:
                print(f"       - [{e['tipo']} · {e['fechas']}] {e['texto'][:95]}  ({e['relevancia']:.2f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("consulta")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--todos", action="store_true")
    g.add_argument("--no-vigentes", action="store_true")
    ap.add_argument("--sin-llm", action="store_true")
    ap.add_argument("--juez", choices=["percentil", "cross_encoder", "fusion"], default=JUEZ)
    a = ap.parse_args()
    vig = "todos" if a.todos else ("no_vigentes" if a.no_vigentes else "vigentes")
    imprimir(buscar(a.consulta, vigencia=vig, usar_llm=not a.sin_llm, juez=a.juez))
