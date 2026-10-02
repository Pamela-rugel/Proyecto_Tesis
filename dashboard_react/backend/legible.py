"""Presentacion legible de los rasgos estructurados (V3) para la vista.

El modelo trabaja con variables transformadas (conteos y años en log1p, estandarizadas en σ);
eso es necesario para la fusion de vistas pero no se entiende al leerlo. Aqui se vuelve a las
unidades originales (años, cantidades, porcentajes, si/no, niveles) SOLO para mostrar: no cambia
ningun calculo ni se persiste nada.

- Conteos y años: el valor real de la persona; para un grupo, lo tipico (mediana) o, si la
  mayoria tiene cero, el porcentaje que tiene al menos uno.
- Proporciones: porcentaje (promedio del grupo).
- Si/no: si/no para la persona; porcentaje que cumple para un grupo.
- Niveles (formacion, ingles): el nombre del nivel; para un grupo, el porcentaje con maestria o
  doctorado / con ingles intermedio o avanzado.
"""
from __future__ import annotations

import math

import pandas as pd

ROL = {
    "docente_titular": "docente titular", "docente_no_titular": "docente no titular",
    "tecnico_docente": "técnico docente", "autoridad": "autoridad", "jefatura": "jefatura",
    "profesional": "profesional o analista", "asistencia_oficina": "asistencia y oficina",
    "operativo": "personal operativo", "otros": "otros cargos",
}

# variable -> (texto, tipo, unidad singular, unidad plural)
DEFINICION: dict[str, tuple[str, str, str, str]] = {
    "anios_espol": ("Años trabajando en ESPOL (cargos de planta)", "anios", "año", "años"),
    **{f"prop_cargo_{g}": (f"Parte de su carrera en ESPOL como {r}", "prop", "", "") for g, r in ROL.items()},
    "n_cargos_estructurales": ("Cargos de planta distintos que ha tenido", "conteo", "cargo", "cargos"),
    "n_contratos_puntuales": ("Contratos ocasionales distintos (servicios, cátedras)", "conteo", "contrato", "contratos"),
    "docencia_posgrado_contrato": ("Ha dado clases de posgrado por contrato", "binaria", "", ""),
    "n_funciones_adicionales": ("Funciones adicionales asignadas (coordinaciones, etc.)", "conteo", "función", "funciones"),
    "fue_autoridad": ("Ha ejercido como autoridad", "binaria", "", ""),
    "anios_experiencia_externa": ("Años de experiencia fuera de ESPOL", "anios", "año", "años"),
    "experiencia_exterior": ("Ha trabajado en el exterior", "binaria", "", ""),
    "prop_experiencia_academica": ("Parte de su experiencia externa en el ámbito académico", "prop", "", ""),
    "nivel_formacion": ("Nivel de estudios más alto", "nivel_formacion", "", ""),
    "titulo_exterior": ("Tiene un título obtenido en el exterior", "binaria", "", ""),
    "n_posgrados": ("Títulos de posgrado", "conteo", "título", "títulos"),
    "estudiando_posgrado": ("Está cursando un posgrado", "binaria", "", ""),
    "n_proyectos_investigacion": ("Proyectos de investigación", "conteo", "proyecto", "proyectos"),
    "dirigio_proyecto": ("Ha dirigido un proyecto de investigación", "binaria", "", ""),
    "n_publicaciones": ("Publicaciones", "conteo", "publicación", "publicaciones"),
    "n_publicaciones_q1q2": ("Publicaciones en revistas de alto impacto (Q1–Q2)", "conteo", "publicación", "publicaciones"),
    "n_tesis_dirigidas": ("Tesis dirigidas", "conteo", "tesis", "tesis"),
    "n_ponencias": ("Ponencias en congresos", "conteo", "ponencia", "ponencias"),
    "n_proyectos_vinculacion": ("Proyectos de vinculación con la sociedad", "conteo", "proyecto", "proyectos"),
    "n_materias": ("Materias distintas que ha dictado", "conteo", "materia", "materias"),
    "n_periodos_docencia": ("Semestres dando clases", "conteo", "semestre", "semestres"),
    "prop_solo_practico": ("Parte de sus materias dictadas solo en la parte práctica", "prop", "", ""),
    "anios_con_carga": ("Años con carga politécnica registrada", "anios", "año", "años"),
    "prop_horas_docencia": ("Parte de su carga horaria dedicada a docencia", "prop", "", ""),
    "prop_horas_gestion": ("Parte de su carga horaria dedicada a gestión", "prop", "", ""),
    "prop_horas_investigacion": ("Parte de su carga horaria dedicada a investigación", "prop", "", ""),
    "prop_horas_vinculacion": ("Parte de su carga horaria dedicada a vinculación", "prop", "", ""),
    "n_capacitaciones": ("Capacitaciones recibidas", "conteo", "capacitación", "capacitaciones"),
    "n_certificaciones": ("Certificaciones", "conteo", "certificación", "certificaciones"),
    "nivel_ingles": ("Nivel de inglés", "nivel_ingles", "", ""),
    "n_idiomas_extranjeros": ("Idiomas extranjeros", "conteo_directo", "idioma", "idiomas"),
    "n_menciones": ("Menciones de honor y premios", "conteo", "mención", "menciones"),
}

NIVEL_FORMACION = {0.0: "Sin registro", 0.5: "Sin registro", 1.0: "Bachillerato", 1.5: "Tecnología", 2.0: "Tercer nivel",
                   2.5: "Especialización", 3.0: "Maestría", 4.0: "Doctorado"}
NIVEL_INGLES = {0.0: "Sin registro", 1.0: "Básico", 2.0: "Intermedio", 3.0: "Avanzado"}


def _real(var: str, v: pd.Series | float):
    """Deshace log1p para conteos y años (las demas variables ya estan en su escala)."""
    tipo = DEFINICION[var][1]
    if tipo in ("conteo", "anios"):
        return v.map(math.expm1) if isinstance(v, pd.Series) else math.expm1(v)
    return v


def _cantidad(var: str, n: float) -> str:
    _, tipo, sing, plur = DEFINICION[var]
    if tipo == "anios":
        n = round(n, 1) if n < 10 else round(n)
        n = int(n) if float(n).is_integer() else n
        return f"{n} {sing if n == 1 else plur}".replace(".", ",")
    n = int(round(n))
    return f"{n} {sing if n == 1 else plur}"


def valor_persona(var: str, v: float) -> str:
    if pd.isna(v):
        return "—"
    tipo = DEFINICION[var][1]
    if tipo == "binaria":
        return "Sí" if v >= 0.5 else "No"
    if tipo == "prop":
        return f"{v:.0%}".replace("%", " %")
    if tipo == "nivel_formacion":
        return NIVEL_FORMACION.get(float(v), str(v))
    if tipo == "nivel_ingles":
        return NIVEL_INGLES.get(float(round(v)), str(v))
    return _cantidad(var, _real(var, v))


def valor_grupo(var: str, s: pd.Series) -> str:
    s = s.dropna()
    if s.empty:
        return "—"
    tipo = DEFINICION[var][1]
    if tipo == "binaria":
        return f"{(s >= 0.5).mean():.0%} sí".replace("%", " %")
    if tipo == "prop":
        return f"{s.mean():.0%}".replace("%", " %") + " en promedio"
    # niveles: el porcentaje que alcanza un nivel alto marca la diferencia mejor que el mas frecuente
    if tipo == "nivel_formacion":
        return f"{(s >= 3).mean():.0%} con maestría o doctorado".replace("%", " %")
    if tipo == "nivel_ingles":
        return f"{(s >= 2).mean():.0%} con nivel intermedio o avanzado".replace("%", " %")
    real = _real(var, s)
    mediana = real.median()
    if mediana >= 1:
        return f"{_cantidad(var, mediana)} (lo típico)"
    return f"{(real >= 0.5).mean():.0%} tiene alguno".replace("%", " %")


def rasgos(variables: list[dict], crudo: pd.DataFrame, miembros, referencia, persona_id: int | None = None,
           z_persona: pd.Series | None = None) -> list[dict]:
    """`variables`: rasgos de la ficha (variable, z). `crudo`: vista estructurada por persona_id.
    Devuelve textos y valores en unidades reales para el grupo, la referencia y la persona."""
    salida = []
    g, ref = crudo.loc[crudo.index.intersection(miembros)], crudo.loc[crudo.index.intersection(referencia)]
    for r in variables:
        v = r["variable"]
        if v not in DEFINICION or v not in crudo.columns:
            continue
        item = {"variable": v, "texto": DEFINICION[v][0], "direccion": "más" if r["z"] > 0 else "menos",
                "valor_grupo": valor_grupo(v, g[v]), "valor_referencia": valor_grupo(v, ref[v])}
        if persona_id is not None:
            item["valor_persona"] = valor_persona(v, crudo.at[persona_id, v])
            zp = float(z_persona[v]) if z_persona is not None and v in z_persona else 0.0
            item["comparte"] = (zp > 0) == (r["z"] > 0) and abs(zp) >= 0.25
        salida.append(item)
    return salida
