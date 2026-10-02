"""Evaluación automática "known-item" de la búsqueda (DISENO.md §8.4).

1. Se toman evidencias reales de tipos con información PÚBLICA (títulos de publicaciones y
   nombres de materias), de textos que tienen entre 1 y 3 personas.
2. El LLM (Groq) las parafrasea como las escribiría alguien que busca a esa persona, sin copiar
   el texto (solo se envía el título o el nombre de la materia; ningún dato de personas).
3. La "respuesta correcta" son las personas dueñas de esa evidencia. Se mide si aparecen en el
   top-k (recall@1/5/10) y en qué puesto (MRR), con vigencia = todos.
4. Se comparan variantes (ablación) y, para cada juez, una grilla de umbrales de "capacidad
   cubierta": el ranking se recalcula sin volver a buscar.

Limitaciones: mide sobre todo RECALL de una sola capacidad (las consultas son de un tema) y
favorece temas con vocabulario propio; no sustituye la evaluación con expertos (§8.1–8.3).

Uso:  python -m busqueda.evaluacion [--n 40]
"""
from __future__ import annotations

import argparse
import json
import random
import time

import numpy as np

from busqueda.buscar import buscar
from busqueda.comun import BUSQUEDA_DIR, MODELO_LLM, UMBRALES
from busqueda.indice import cargar_indice

DIR = BUSQUEDA_DIR / "evaluacion"
VARIANTES = {
    "A_base_denso_global": dict(usar_llm=False, por_tipo=False, lexico=False, juez="percentil"),
    "B_hibrido_global": dict(usar_llm=False, por_tipo=False, lexico=True, juez="percentil"),
    "C_llm_tipo_percentil": dict(usar_llm=True, por_tipo=True, lexico=True, juez="percentil"),
    "D_llm_tipo_cross_encoder": dict(usar_llm=True, por_tipo=True, lexico=True, juez="cross_encoder"),
    "E_llm_tipo_fusion": dict(usar_llm=True, por_tipo=True, lexico=True, juez="fusion"),
}
GRILLA = {
    "percentil": [0.9, 0.95, 0.98, 0.99, 0.995],
    "cross_encoder": [0.05, 0.1, 0.2, 0.3, 0.5, 0.7],
    "fusion": [0.5, 0.7, 0.8, 0.9, 0.95],
}
PROMPT_PARAFRASIS = """Te doy el {que} de un registro real. Escribe UNA consulta breve (6 a 14 palabras), en
español, como la escribiría alguien de talento humano que busca a una persona con experiencia en
ese tema. NO copies el título palabra por palabra: usa sinónimos o una descripción más general del
tema. No menciones nombres de personas. Responde solo JSON: {{"consulta": "..."}}

{que_mayus}: {texto}"""


def _muestra(n: int) -> list[dict]:
    ix = cargar_indice()
    ev = ix.ev
    random.seed(42)
    items = []
    for tipo, que in (("PUBLICACION", "título de una publicación científica"), ("DOCENCIA_MATERIA", "nombre de una materia universitaria")):
        e = ev[ev["tipo_id"] == tipo]
        dueños = e.groupby("texto_idx")["persona_id"].apply(lambda s: sorted(set(s)))
        candidatos = [t for t, ps in dueños.items() if 1 <= len(ps) <= 3]
        for t in random.sample(candidatos, n):
            texto = ix.textos.texto.iloc[t]
            corto = texto.split(", Tipo:")[0] if tipo == "PUBLICACION" else texto.split(",")[0]
            items.append({"tipo": tipo, "que": que, "texto": corto, "personas": [int(p) for p in dueños[t]]})
    return items


def _parafrasear(items: list[dict]) -> list[dict]:
    from groq import Groq

    archivo = DIR / "consultas_known_item.json"
    previos = {x["texto"]: x["consulta"] for x in json.loads(archivo.read_text(encoding="utf-8"))} if archivo.exists() else {}
    cliente = Groq(timeout=60)
    for it in items:
        if it["texto"] in previos:
            it["consulta"] = previos[it["texto"]]
            continue
        r = cliente.chat.completions.create(
            model=MODELO_LLM, temperature=0, reasoning_effort="low", response_format={"type": "json_object"},
            messages=[{"role": "user", "content": PROMPT_PARAFRASIS.format(que=it["que"], que_mayus=it["que"].split(" de ")[0].capitalize(), texto=it["texto"])}])
        it["consulta"] = json.loads(r.choices[0].message.content)["consulta"]
        time.sleep(1.5)
    DIR.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def _rango(resultados: list[dict], objetivo: set[int], umbral: float | None) -> int | None:
    """Puesto (1..n) de la primera persona objetivo; con `umbral` se recalcula la cobertura."""
    if umbral is not None:
        def clave(r):
            oblig = [c for c in r["capacidades"] if c["importancia"] == "obligatoria"]
            cub = sum(c["relevancia"] >= umbral for c in oblig)
            return (cub, r["puntaje"], r["puntaje_deseables"])
        resultados = sorted(resultados, key=clave, reverse=True)
    for k, r in enumerate(resultados, 1):
        if r["persona_id"] in objetivo:
            return k
    return None


def _metricas(rangos: list[int | None]) -> dict:
    r = [x or 10**9 for x in rangos]
    return {"recall@1": float(np.mean([x <= 1 for x in r])), "recall@5": float(np.mean([x <= 5 for x in r])),
            "recall@10": float(np.mean([x <= 10 for x in r])), "MRR": float(np.mean([1 / x for x in r]))}


def evaluar(n: int = 40) -> dict:
    items = _parafrasear(_muestra(n))
    rangos = {v: [] for v in VARIANTES}
    rangos_umbral = {(v, u): [] for v, cfg in VARIANTES.items() if cfg["usar_llm"] for u in GRILLA[cfg["juez"]]}
    tiempos = {v: [] for v in VARIANTES}
    for k, it in enumerate(items, 1):
        objetivo = set(it["personas"])
        for v, cfg in VARIANTES.items():
            t0 = time.time()
            r = buscar(it["consulta"], vigencia="todos", n=10**6, registrar=False, **cfg)
            tiempos[v].append(time.time() - t0)
            rangos[v].append(_rango(r["resultados"], objetivo, None))
            if cfg["usar_llm"]:
                for u in GRILLA[cfg["juez"]]:
                    rangos_umbral[(v, u)].append(_rango(r["resultados"], objetivo, u))
        print(f"{k}/{len(items)} " + " ".join(f"{v[:1]}={rangos[v][-1]}" for v in VARIANTES), flush=True)

    salida = {
        "n_consultas": len(items), "por_tipo": {t: sum(i["tipo"] == t for i in items) for t in ("PUBLICACION", "DOCENCIA_MATERIA")},
        "variantes": {v: {**_metricas(rangos[v]), "umbral_por_defecto": UMBRALES[VARIANTES[v]["juez"]],
                          "segundos_medio": round(float(np.mean(tiempos[v])), 2)} for v in VARIANTES},
        "grilla_umbrales": {f"{v}@{u}": _metricas(rs) for (v, u), rs in rangos_umbral.items()},
        "por_tipo_de_consulta": {
            t: {v: _metricas([rg for rg, it in zip(rangos[v], items) if it["tipo"] == t]) for v in VARIANTES}
            for t in ("PUBLICACION", "DOCENCIA_MATERIA")},
    }
    (DIR / "resultados.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1), encoding="utf-8")
    return salida


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="consultas por tipo (publicaciones y materias)")
    s = evaluar(ap.parse_args().n)
    print(json.dumps(s["variantes"], ensure_ascii=False, indent=1))
