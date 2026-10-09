"""Intensidad de cada persona en dimensiones FIJAS definidas por tipo de evidencia (DEC-053).

A diferencia del clustering multivista, las dimensiones no se descubren: las define el tipo de
evidencia. Para cada persona y dimensión:

1. **Componentes**: conteos u otras medidas tomadas de los `atributos` de sus evidencias de esa
   dimensión (`DIMENSIONES`). Los conteos van en log1p.
2. **Índice bruto** (0–1): promedio ponderado de los componentes normalizados por el máximo del
   ámbito. Es la parte explicable: cada componente aporta una fracción conocida.
3. **Intensidad** (0–100): percentil del índice bruto dentro del ámbito = % de personas del ámbito
   con un índice menor o igual. Quien no tiene evidencias de la dimensión tiene intensidad 0 (no
   un percentil empatado). Es intensidad de evidencia REGISTRADA, no una medida de capacidad.

Las dimensiones son independientes (no suman 100). El percentil se calcula por separado en cada
ámbito (todos, administrativos, docentes), así que no se compara entre ámbitos.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
import pandas as pd

from perfiles.vistas import NIVEL_IDIOMA, _nivel_formacion

NIVEL_MCER = {"A1": 1, "A2": 1, "B1": 2, "B2": 2, "C1": 3, "C2": 3}

# dimensión -> tipos de evidencia y componentes {nombre: (peso, descripción)}. Los pesos se
# normalizan dentro de la dimensión; por defecto son iguales.
DIMENSIONES = {
    "investigacion": {
        "nombre": "Investigación",
        "tipos": ["PROYECTO_INVESTIGACION", "PUBLICACION"],
        "componentes": {
            "proyectos": (1.0, "Proyectos de investigación (log)"),
            "proyectos_dirigidos": (1.0, "Proyectos dirigidos o codirigidos (log)"),
            "publicaciones": (1.0, "Publicaciones (log)"),
            "publicaciones_q1q2": (1.0, "Publicaciones Q1–Q2 (log)"),
        },
    },
    "ponencias": {
        "nombre": "Ponencias",
        "tipos": ["PONENCIA"],
        "componentes": {
            "ponencias": (1.0, "Ponencias (log)"),
            "ponencias_exterior": (1.0, "Ponencias en el exterior (log)"),
        },
    },
    "vinculacion": {
        "nombre": "Vinculación",
        "tipos": ["PROYECTO_VINCULACION"],
        "componentes": {
            "proyectos": (1.0, "Proyectos de vinculación (log)"),
            "proyectos_dirigidos": (1.0, "Proyectos o programas dirigidos (log)"),
            "anios": (1.0, "Años en proyectos de vinculación (log)"),
        },
    },
    "tesis_dirigidas": {
        "nombre": "Tesis dirigidas",
        "tipos": ["TESIS_DIRIGIDA"],
        "componentes": {
            "tesis": (1.0, "Tesis dirigidas (log)"),
            "estudiantes": (1.0, "Estudiantes dirigidos (log)"),
            "tesis_investigacion_doctorado": (1.0, "Tesis de maestría de investigación o doctorado (log)"),
        },
    },
    "docencia": {
        "nombre": "Docencia",
        "tipos": ["DOCENCIA_MATERIA", "ACTIVIDAD_CARGA"],
        "componentes": {
            "materias": (1.0, "Materias dictadas (log)"),
            "semestres": (1.0, "Semestres con docencia (log)"),
            "estudiantes": (1.0, "Estudiantes atendidos (log)"),
            "horas_carga_docencia": (1.0, "Horas de carga politécnica en docencia (log)"),
        },
    },
    "formacion": {
        "nombre": "Formación",
        "tipos": ["FORMACION_TITULO", "FORMACION_EN_CURSO"],
        "componentes": {
            "nivel_maximo": (2.0, "Nivel máximo de formación (1 bachiller … 4 doctorado)"),
            "posgrados": (1.0, "Títulos de cuarto nivel (log)"),
            "titulo_exterior": (1.0, "Tiene título del exterior"),
            "posgrado_en_curso": (0.5, "Posgrado en curso"),
        },
    },
    "capacitacion": {
        "nombre": "Capacitación",
        "tipos": ["CAPACITACION"],
        "componentes": {
            "cursos": (1.0, "Capacitaciones (log)"),
            "horas": (1.0, "Horas de capacitación (log)"),
            "cursos_exterior": (1.0, "Capacitaciones en el exterior (log)"),
        },
    },
    "certificaciones": {
        "nombre": "Certificaciones",
        "tipos": ["CERTIFICACION"],
        "componentes": {
            "certificaciones": (1.0, "Certificaciones (log)"),
            "vigentes": (1.0, "Certificaciones vigentes (log)"),
            "horas": (1.0, "Horas de certificación (log)"),
        },
    },
    "idiomas": {
        "nombre": "Idiomas",
        "tipos": ["IDIOMA"],
        "componentes": {
            "idiomas_extranjeros": (1.0, "Idiomas distintos del español"),
            "nivel_maximo": (1.0, "Nivel máximo en un idioma extranjero (0–3)"),
        },
    },
    "reconocimientos": {
        "nombre": "Reconocimientos",
        "tipos": ["MENCION_HONOR"],
        "componentes": {
            "menciones": (1.0, "Menciones de honor recibidas (log, cuenta repeticiones)"),
            "menciones_exterior": (1.0, "Menciones del exterior (log)"),
        },
    },
    "trayectoria_espol": {
        "nombre": "Trayectoria en ESPOL",
        "tipos": ["TRAYECTORIA_CARGO_ESTRUCTURAL", "TRAYECTORIA_CONTRATO_PUNTUAL", "TRAYECTORIA_FUNCION_ADICIONAL"],
        "componentes": {
            "anios": (1.0, "Años en cargos estructurales de ESPOL (log)"),
            "cargos": (1.0, "Cargos estructurales y contratos puntuales en ESPOL (log)"),
            "funciones_adicionales": (1.0, "Funciones adicionales: coordinaciones, autoridades (log)"),
        },
    },
    "experiencia_externa": {
        "nombre": "Experiencia externa",
        "tipos": ["TRAYECTORIA_EXPERIENCIA_EXTERNA"],
        "componentes": {
            "anios": (1.0, "Años de experiencia fuera de ESPOL (log)"),
            "experiencias": (1.0, "Experiencias laborales externas (log)"),
            "exterior": (1.0, "Experiencias en el exterior (log)"),
            "academica": (1.0, "Experiencias académicas externas (log)"),
        },
    },
}
TIPO_A_DIMENSION = {t: d for d, cfg in DIMENSIONES.items() for t in cfg["tipos"]}
# Conteos que no entran en la intensidad pero sí en los patrones de actividad (micro_dimensiones)
COLUMNAS_EXTRA = ["investigacion__publicaciones_autor"]


def _nivel_idioma(a: dict) -> float:
    niveles = [NIVEL_IDIOMA.get(n, 0) for k in ("niveles_conversacion", "niveles_lectura", "niveles_escritura")
               for n in (a.get(k) or [])]
    niveles += [NIVEL_MCER.get(n, 0) for n in (a.get("niveles_mcer") or [])]
    return float(max(niveles, default=0))


def componentes_crudos(ev: pd.DataFrame, personas: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(componentes, n_evidencias). Componentes: columnas `<dimension>__<componente>` sin
    normalizar (log1p en conteos). n_evidencias: una columna por dimensión."""
    acc = {p: defaultdict(float) for p in personas}
    n_ev = {p: defaultdict(int) for p in personas}
    idiomas = defaultdict(set)
    for p, tipo, s in zip(ev["persona_id"], ev["tipo_id"], ev["atributos"]):
        dim = TIPO_A_DIMENSION.get(tipo)
        if p not in acc or dim is None:
            continue
        a = json.loads(s)
        v = acc[p]
        if tipo != "ACTIVIDAD_CARGA":  # la carga cuenta para docencia solo si tiene horas de docencia
            n_ev[p][dim] += 1
        if tipo == "PROYECTO_INVESTIGACION":
            v["investigacion__proyectos"] += 1
            v["investigacion__proyectos_dirigidos"] += bool(set(a.get("roles") or []) & {"DIRECTOR", "CO-DIRECTOR"})
        elif tipo == "PUBLICACION":
            v["investigacion__publicaciones"] += 1
            v["investigacion__publicaciones_q1q2"] += bool(set(a.get("cuartiles_sjr") or []) & {"Q1", "Q2"})
            v["investigacion__publicaciones_autor"] += "Autor" in (a.get("participaciones") or [])
        elif tipo == "PONENCIA":
            v["ponencias__ponencias"] += 1
            v["ponencias__ponencias_exterior"] += bool(a.get("es_exterior"))
        elif tipo == "PROYECTO_VINCULACION":
            v["vinculacion__proyectos"] += 1
            v["vinculacion__proyectos_dirigidos"] += any("DIRECTOR" in r for r in (a.get("roles") or []))
            v["vinculacion__anios"] += a.get("duracion_total_anios") or 0.0
        elif tipo == "TESIS_DIRIGIDA":
            v["tesis_dirigidas__tesis"] += 1
            v["tesis_dirigidas__estudiantes"] += a.get("n_estudiantes") or 0
            niveles = " ".join(a.get("niveles_formacion") or []).upper()
            v["tesis_dirigidas__tesis_investigacion_doctorado"] += ("INVESTIGACI" in niveles or "DOCTORADO" in niveles)
        elif tipo == "DOCENCIA_MATERIA":
            v["docencia__materias"] += 1
            v["docencia__semestres"] += a.get("n_periodos") or 0
            v["docencia__estudiantes"] += a.get("n_estudiantes_total") or 0
        elif tipo == "ACTIVIDAD_CARGA":
            horas = sum(d.get("horas") or 0.0 for d in (a.get("detalle") or []) if d.get("actividad") == "DOCENCIA")
            if horas > 0:
                v["docencia__horas_carga_docencia"] += horas
                n_ev[p]["docencia"] += 1
        elif tipo == "FORMACION_TITULO":
            v["formacion__nivel_maximo"] = max(v["formacion__nivel_maximo"], _nivel_formacion(a))
            v["formacion__posgrados"] += "CUARTO" in str(a.get("nivel") or "").upper()
            v["formacion__titulo_exterior"] = max(v["formacion__titulo_exterior"], float(bool(a.get("es_exterior"))))
        elif tipo == "FORMACION_EN_CURSO":
            if "CUARTO" in str(a.get("nivel") or "").upper():
                v["formacion__posgrado_en_curso"] = 1.0
        elif tipo == "CAPACITACION":
            v["capacitacion__cursos"] += 1
            v["capacitacion__horas"] += a.get("horas_total") or 0.0
            v["capacitacion__cursos_exterior"] += bool(a.get("es_exterior"))
        elif tipo == "CERTIFICACION":
            v["certificaciones__certificaciones"] += 1
            v["certificaciones__vigentes"] += bool(a.get("vigente"))
            v["certificaciones__horas"] += a.get("horas_total") or 0.0
        elif tipo == "IDIOMA":
            if a.get("idioma") != "ESPAÑOL":
                idiomas[p].add(a.get("idioma"))
                v["idiomas__nivel_maximo"] = max(v["idiomas__nivel_maximo"], _nivel_idioma(a))
        elif tipo == "MENCION_HONOR":
            veces = a.get("n_veces") or 1
            v["reconocimientos__menciones"] += veces
            v["reconocimientos__menciones_exterior"] += veces if a.get("es_exterior") else 0
        elif tipo == "TRAYECTORIA_CARGO_ESTRUCTURAL":
            v["trayectoria_espol__anios"] += a.get("duracion_total_anios") or 0.0
            v["trayectoria_espol__cargos"] += 1
        elif tipo == "TRAYECTORIA_CONTRATO_PUNTUAL":
            v["trayectoria_espol__cargos"] += 1
        elif tipo == "TRAYECTORIA_FUNCION_ADICIONAL":
            v["trayectoria_espol__funciones_adicionales"] += 1
        elif tipo == "TRAYECTORIA_EXPERIENCIA_EXTERNA":
            v["experiencia_externa__anios"] += a.get("duracion_anios") or 0.0
            v["experiencia_externa__experiencias"] += 1
            v["experiencia_externa__exterior"] += bool(a.get("es_exterior"))
            v["experiencia_externa__academica"] += a.get("categoria_experiencia") == "ACADEMICA"
    for p, s in idiomas.items():
        acc[p]["idiomas__idiomas_extranjeros"] = len(s)

    sin_log = {"formacion__nivel_maximo", "formacion__titulo_exterior", "formacion__posgrado_en_curso",
               "idiomas__idiomas_extranjeros", "idiomas__nivel_maximo"}
    columnas = [f"{d}__{c}" for d, cfg in DIMENSIONES.items() for c in cfg["componentes"]] + COLUMNAS_EXTRA
    filas = []
    for p in personas:
        filas.append({c: (acc[p][c] if c in sin_log else math.log1p(acc[p][c])) for c in columnas})
    comp = pd.DataFrame(filas, index=pd.Index(personas, name="persona_id"))[columnas]
    n = pd.DataFrame([{d: n_ev[p][d] for d in DIMENSIONES} for p in personas], index=comp.index)
    # formación: "sin registro" (0,5) no es evidencia; sin títulos el nivel queda en 0
    comp.loc[n["formacion"] == 0, "formacion__nivel_maximo"] = 0.0
    return comp, n


# Atributo con el TEMA de cada tipo de evidencia (sin metadatos). Los tipos que no están usan el texto.
CAMPO_TEMA = {
    "PUBLICACION": "titulo", "PROYECTO_INVESTIGACION": "nombre", "PONENCIA": "nombre", "PROYECTO_VINCULACION": "nombre",
    "TESIS_DIRIGIDA": "titulo", "DOCENCIA_MATERIA": "materia", "ACTIVIDAD_CARGA": "tema", "FORMACION_TITULO": "titulo",
    "FORMACION_EN_CURSO": "titulo", "CAPACITACION": "nombre", "CERTIFICACION": "nombre", "MENCION_HONOR": "nombre",
    "IDIOMA": "idioma", "TRAYECTORIA_CARGO_ESTRUCTURAL": "cargo", "TRAYECTORIA_FUNCION_ADICIONAL": "funcion", "TRAYECTORIA_EXPERIENCIA_EXTERNA": "cargo",
}


def texto_tema(tipo: str, atributos: str, texto: str) -> str:
    campo = CAMPO_TEMA.get(tipo)
    valor = json.loads(atributos).get(campo) if campo else None
    return valor.strip() if isinstance(valor, str) and valor.strip() else texto


def evidencias_de_dimension(ev: pd.DataFrame) -> pd.DataFrame:
    """Evidencias que cuentan en alguna dimensión, con la columna `dimension`. Una actividad de
    carga solo cuenta (para docencia) si tiene horas de docencia, igual que en `componentes_crudos`."""
    e = ev[ev["tipo_id"].isin(TIPO_A_DIMENSION)].copy()
    carga = e["tipo_id"] == "ACTIVIDAD_CARGA"
    con_docencia = e.loc[carga, "atributos"].map(lambda s: any(
        d.get("actividad") == "DOCENCIA" and (d.get("horas") or 0) > 0 for d in (json.loads(s).get("detalle") or [])))
    e = e.drop(con_docencia[~con_docencia].index)
    e["dimension"] = e["tipo_id"].map(TIPO_A_DIMENSION)
    e["tema"] = [texto_tema(t, a, x) if isinstance(x, str) else None for t, a, x in zip(e["tipo_id"], e["atributos"], e["texto"])]
    return e


def percentil_positivo(x: np.ndarray) -> np.ndarray:
    """0 si x <= 0; si no, 100 x (personas con valor <= x) / total. El máximo da 100."""
    x = np.asarray(x, dtype=float)
    orden = np.sort(x)
    pct = 100.0 * np.searchsorted(orden, x, side="right") / len(x)
    return np.where(x > 0, pct, 0.0)


def intensidades(comp: pd.DataFrame, n_ev: pd.DataFrame) -> pd.DataFrame:
    """Formato largo: persona_id, dimension, intensidad (0–100), indice (0–1), n_evidencias,
    componentes (JSON {componente: aporte normalizado 0–1}). Todo relativo a las filas recibidas
    (el ámbito)."""
    maximos = comp.max().replace(0, 1.0)
    norm = comp / maximos
    salida = []
    for d, cfg in DIMENSIONES.items():
        nombres = list(cfg["componentes"])
        pesos = np.array([cfg["componentes"][c][0] for c in nombres])
        pesos = pesos / pesos.sum()
        bloque = norm[[f"{d}__{c}" for c in nombres]].to_numpy()
        indice = bloque @ pesos
        indice = np.where(n_ev[d].to_numpy() > 0, indice, 0.0)
        salida.append(pd.DataFrame({
            "persona_id": comp.index.to_numpy(), "dimension": d, "intensidad": percentil_positivo(indice).round(1),
            "indice": indice.round(4), "n_evidencias": n_ev[d].to_numpy(),
            "componentes": [json.dumps({c: round(float(v), 3) for c, v in zip(nombres, fila)}) for fila in bloque],
        }))
    return pd.concat(salida, ignore_index=True)


def definiciones() -> dict:
    return {d: {"nombre": cfg["nombre"], "tipos_evidencia": cfg["tipos"],
                "componentes": {c: {"peso": p, "descripcion": t} for c, (p, t) in cfg["componentes"].items()}}
            for d, cfg in DIMENSIONES.items()}
