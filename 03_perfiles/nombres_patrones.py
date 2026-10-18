"""Nombres cortos de los patrones de actividad por dimensión (DEC-063).

Pedido de la usuaria: un nombre corto que se cumpla para TODAS las personas del patrón. Por eso no
se nombra con el centroide (que describe el promedio), sino con condiciones sobre los valores
REALES que se cumplen para el 100 % de sus integrantes:

1. Se generan condiciones candidatas por variable de la dimensión: "sin X", "N X", "N o más X",
   "hasta N X", rangos cortos ("de 2 a 5 X"), niveles ("doctorado", "nivel avanzado o más"), sí/no
   ("con título del exterior") y proporciones ("todas nacionales", "dirige todos sus proyectos";
   solo para quienes tienen denominador).
2. Se quedan las que cumplen TODOS los integrantes del patrón.
3. Se elige la más específica (la que menos personas del resto de la dimensión cumplen; a igualdad,
   la más corta) y, si suma al menos 5 puntos de especificidad, una segunda de otra variable.
4. `distingue` = parte del resto de la dimensión que NO cumple el nombre: indica qué tan propio del
   patrón es. Si es bajo, el nombre es verdadero pero poco distintivo (los patrones se solapan).

No son categorías institucionales ni juicios: describen los registros.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CONTEO = {
    "investigacion__proyectos": ("proyecto", "proyectos"), "investigacion__proyectos_dirigidos": ("proyecto dirigido", "proyectos dirigidos"),
    "investigacion__publicaciones": ("publicación", "publicaciones"), "investigacion__publicaciones_q1q2": ("publicación Q1–Q2", "publicaciones Q1–Q2"),
    "ponencias__ponencias": ("ponencia", "ponencias"), "ponencias__ponencias_exterior": ("ponencia en el exterior", "ponencias en el exterior"),
    "vinculacion__proyectos": ("proyecto", "proyectos"), "vinculacion__proyectos_dirigidos": ("proyecto dirigido", "proyectos dirigidos"),
    "tesis_dirigidas__tesis": ("tesis", "tesis"), "tesis_dirigidas__estudiantes": ("estudiante", "estudiantes"),
    "tesis_dirigidas__tesis_investigacion_doctorado": ("tesis de investigación o doctorado", "tesis de investigación o doctorado"),
    "docencia__materias": ("materia", "materias"), "docencia__semestres": ("semestre", "semestres"),
    "docencia__estudiantes": ("estudiante", "estudiantes"), "formacion__posgrados": ("posgrado", "posgrados"),
    "capacitacion__cursos": ("capacitación", "capacitaciones"), "capacitacion__cursos_exterior": ("capacitación en el exterior", "capacitaciones en el exterior"),
    "certificaciones__certificaciones": ("certificación", "certificaciones"), "certificaciones__vigentes": ("certificación vigente", "certificaciones vigentes"),
    "reconocimientos__menciones": ("mención", "menciones"), "reconocimientos__menciones_exterior": ("mención del exterior", "menciones del exterior"),
    "trayectoria_espol__cargos": ("cargo", "cargos"), "trayectoria_espol__funciones_adicionales": ("función adicional", "funciones adicionales"),
    "experiencia_externa__experiencias": ("experiencia", "experiencias"), "experiencia_externa__exterior": ("experiencia en el exterior", "experiencias en el exterior"),
    "experiencia_externa__academica": ("experiencia académica", "experiencias académicas"), "idiomas__idiomas_extranjeros": ("idioma extranjero", "idiomas extranjeros"),
}
CANTIDAD = {"vinculacion__anios": "años en vinculación", "docencia__horas_carga_docencia": "horas de carga docente",
            "capacitacion__horas": "horas de capacitación", "certificaciones__horas": "horas certificadas",
            "trayectoria_espol__anios": "años en cargos de ESPOL", "experiencia_externa__anios": "años de experiencia externa"}
NIVEL = {"formacion__nivel_maximo": {1: "bachiller", 1.5: "técnico", 2: "tercer nivel", 2.5: "otro cuarto nivel", 3: "maestría", 4: "doctorado"},
         "idiomas__nivel_maximo": {1: "nivel básico", 2: "nivel intermedio", 3: "nivel avanzado"}}
BINARIO = {"formacion__titulo_exterior": ("con título del exterior", "sin título del exterior"),
           "formacion__posgrado_en_curso": ("con posgrado en curso", "sin posgrado en curso")}
# (numerador, denominador) -> (todas, ninguna, mayoría); solo para quienes tienen denominador
PROPORCION = {
    ("investigacion", "proyectos_dirigidos", "proyectos"): ("dirige todos sus proyectos", "no dirige sus proyectos", "dirige la mayoría de sus proyectos"),
    ("investigacion", "publicaciones_q1q2", "publicaciones"): ("todas sus publicaciones en Q1–Q2", "ninguna publicación Q1–Q2", "mayoría de publicaciones en Q1–Q2"),
    ("investigacion", "publicaciones_autor", "publicaciones"): ("autor en todas sus publicaciones", "siempre coautor", "autor en la mayoría de sus publicaciones"),
    ("ponencias", "ponencias_exterior", "ponencias"): ("todas en el exterior", "todas nacionales", "mayoría en el exterior"),
    ("vinculacion", "proyectos_dirigidos", "proyectos"): ("dirige todos sus proyectos", "no dirige sus proyectos", "dirige la mayoría de sus proyectos"),
    ("tesis_dirigidas", "tesis_investigacion_doctorado", "tesis"): ("solo tesis de investigación o doctorado", "ninguna de investigación o doctorado", "mayoría de investigación o doctorado"),
    ("capacitacion", "cursos_exterior", "cursos"): ("todas en el exterior", "todas en Ecuador", "mayoría en el exterior"),
    ("certificaciones", "vigentes", "certificaciones"): ("todas vigentes", "ninguna vigente", "mayoría vigentes"),
    ("reconocimientos", "menciones_exterior", "menciones"): ("todas del exterior", "todas nacionales", "mayoría del exterior"),
    ("experiencia_externa", "exterior", "experiencias"): ("toda en el exterior", "toda en Ecuador", "mayoría en el exterior"),
    ("experiencia_externa", "academica", "experiencias"): ("toda académica", "ninguna académica", "mayoría académica"),
}
SIN_LOG = {"formacion__nivel_maximo", "formacion__titulo_exterior", "formacion__posgrado_en_curso",
           "idiomas__idiomas_extranjeros", "idiomas__nivel_maximo"}
GANANCIA_MINIMA = 0.05


def _redondo(x: float) -> int:
    """Hacia abajo a un número "redondo" (para umbrales de cantidades continuas)."""
    for paso in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
        if x < paso * 10:
            return int(np.floor(x / paso) * paso) if x >= paso else int(np.floor(x))
    return int(x)


def _rango_corto(lo: float, hi: float) -> bool:
    return hi <= 20 or hi <= 4 * max(lo, 1)


def valores_reales(dimension: str, comp: pd.DataFrame, componentes: list[str]) -> pd.DataFrame:
    """Componentes de la dimensión en su escala real (deshace el log1p de los conteos)."""
    cols = [f"{dimension}__{c}" for c in componentes]
    real = comp[cols].copy()
    for c in cols:
        if c not in SIN_LOG:
            real[c] = np.expm1(real[c]).round(2)
    return real


def _candidatas(dimension: str, real: pd.DataFrame, comp: pd.DataFrame, m: np.ndarray) -> list[tuple[str, np.ndarray, str]]:
    out = []
    for col in real.columns:
        v = real[col].to_numpy()
        if col in CONTEO:
            s, pl = CONTEO[col]
            out.append((f"sin {pl}", v == 0, col))
            for t in np.unique(v[m]).astype(int):
                if t >= 1:
                    out.append((f"1 {s}" if t == 1 else f"{t} {pl}", v == t, col))
                    out.append((f"al menos 1 {s}" if t == 1 else f"{t} o más {pl}", v >= t, col))
                    out.append((f"como máximo 1 {s}" if t == 1 else f"hasta {t} {pl}", v <= t, col))
            lo, hi = int(v[m].min()), int(v[m].max())
            if 0 < lo < hi and _rango_corto(lo, hi):
                out.append((f"de {lo} a {hi} {pl}", (v >= lo) & (v <= hi), col))
        elif col in CANTIDAD:
            if (v > 0).any():
                for t in np.unique(np.quantile(v[v > 0], [0.1, 0.25, 0.5, 0.75, 0.9])):
                    r = _redondo(t)
                    if r > 0:
                        out.append((f"{r} o más {CANTIDAD[col]}", v >= r, col))
                        out.append((f"menos de {r} {CANTIDAD[col]}", v < r, col))
            out.append((f"sin {CANTIDAD[col]}", v == 0, col))
            lo, hi = _redondo(v[m].min()), int(np.ceil(v[m].max()))
            if 0 < lo < hi and _rango_corto(lo, hi):
                out.append((f"de {lo} a {hi} {CANTIDAD[col]}", (v >= lo) & (v <= hi), col))
        elif col in NIVEL:
            for t, nombre in NIVEL[col].items():
                out.append((nombre, v == t, col))
                out.append((f"{nombre} o más", v >= t, col))
                out.append((f"hasta {nombre}", (v <= t) & (v > 0), col))
        elif col in BINARIO:
            out.append((BINARIO[col][0], v >= 1, col))
            out.append((BINARIO[col][1], v < 1, col))
    for (d, num, den), (todas, ninguna, mayoria) in PROPORCION.items():
        if d != dimension or f"{d}__{num}" not in comp.columns:
            continue
        n_ = np.expm1(comp[f"{d}__{num}"]).round().to_numpy()
        de = np.expm1(comp[f"{d}__{den}"]).round().to_numpy()
        p = np.where(de > 0, n_ / np.maximum(de, 1), np.nan)
        clave = f"{d}__prop_{num}"
        out += [(todas, (de > 0) & (p == 1), clave), (ninguna, (de > 0) & (p == 0), clave), (mayoria, (de > 0) & (p > 0.5), clave)]
    return out


def nombrar(dimension: str, comp: pd.DataFrame, componentes: list[str], etiquetas: np.ndarray) -> list[dict]:
    """Por patrón (0..k-1): {nombre, condiciones, distingue}. `comp`: componentes crudos (log1p) de
    las personas con evidencias, en el orden de `etiquetas`."""
    real = valores_reales(dimension, comp, componentes)
    salida = []
    for c in range(int(etiquetas.max()) + 1):
        m = etiquetas == c
        fuera = ~m
        todas = [z for z in _candidatas(dimension, real, comp, m) if z[1][m].all()]
        if not todas or not fuera.any():
            salida.append({"nombre": "Sin rasgo común a todos", "condiciones": [], "distingue": 0.0})
            continue
        especificidad = lambda mk: 1 - mk[fuera].mean()  # noqa: E731
        primera = max(todas, key=lambda z: (especificidad(z[1]), -len(z[0])))
        elegidas, conj = [primera], primera[1]
        otras = [z for z in todas if z[2] != primera[2]]
        if otras:
            segunda = max(otras, key=lambda z: (especificidad(conj & z[1]), -len(z[0])))
            if especificidad(conj & segunda[1]) - especificidad(conj) >= GANANCIA_MINIMA:
                elegidas.append(segunda)
                conj = conj & segunda[1]
        salida.append({"nombre": " · ".join(z[0] for z in elegidas), "condiciones": [z[0] for z in elegidas],
                       "distingue": round(float(especificidad(conj)), 3)})
    vistos: dict[str, int] = {}
    for c, s in enumerate(salida):          # nombres repetidos dentro de la dimensión: se numeran
        if s["nombre"] in vistos:
            s["nombre"] += f" (P{c + 1})"
        vistos[s["nombre"]] = c
    return salida
