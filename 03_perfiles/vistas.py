"""Las tres vistas del perfil de cada persona (DEC-045).

V1 semantica de trayectoria y gestion y V2 semantica academico-tematica: embedding de persona
agregado desde los embeddings de sus evidencias, en dos niveles para que un tipo muy numeroso
(42 000 capacitaciones) no ahogue a los demas:
    1) promedio ponderado de las evidencias de cada TIPO de la persona;
    2) promedio simple entre los tipos que la persona tiene en esa vista;
    3) normalizacion L2.
Peso de cada evidencia: 1 / log2(1 + personas que comparten exactamente ese texto): un curso o
un cargo que tiene medio personal describe menos a la persona que uno propio (mismo criterio que
`n_personas_mismo_curso`). Si una persona no tiene evidencias de una vista, se marca y se le
asigna el promedio de la vista (neutral) para que SNF pueda operar con vistas completas.

V3 estructurada: variables numericas agregadas desde los `atributos` de las evidencias (ver
`VARIABLES_ESTRUCTURADAS`). No incluye identificadores, campos administrativos, sexo, edad ni el
tipo docente/administrativo (este solo define los ambitos del analisis). Los conteos van en
log1p; la estandarizacion se hace por ambito, en `clustering.py`.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import sparse

from perfiles import embeddings as emb
from perfiles.comun import TIPOS_V1_TRAYECTORIA, TIPOS_V2_ACADEMICO

# --- Grupos de categoria de cargo (taxonomia CATEGORIA_CARGO del proyecto) ---
GRUPO_CATEGORIA = {
    "DOCENTE_TITULAR_CARRERA": "docente_titular", "DOCENTE_INVESTIGADOR": "docente_titular",
    "DOCENTE_NO_TITULAR_OCASIONAL": "docente_no_titular", "DOCENTE_PREPOLITECNICO": "docente_no_titular",
    "AYUDANTE_ACADEMICO_JUNIOR": "docente_no_titular",
    "TECNICO_DOCENTE_APOYO": "tecnico_docente",
    "AUTORIDAD_ACADEMICA_SUPERIOR": "autoridad", "AUTORIDAD_ADMINISTRATIVA_SUPERIOR": "autoridad",
    "DIRECCION_ACADEMICA_INTERMEDIA": "autoridad",
    "JEFATURA_SUPERVISION_OPERATIVA": "jefatura",
    "PROFESIONAL_ANALISTA": "profesional", "PROFESIONAL_ESPECIALIZADO_TECNICO": "profesional",
    "ASISTENCIA_SECRETARIAL_OFICINA": "asistencia_oficina",
    "TECNICO_OPERATIVO_MANTENIMIENTO": "operativo", "AUXILIAR_AYUDANTE_OPERATIVO": "operativo",
    "SERVICIOS_GENERALES_OFICIOS": "operativo",
}
GRUPOS = ["docente_titular", "docente_no_titular", "tecnico_docente", "autoridad", "jefatura", "profesional",
          "asistencia_oficina", "operativo", "otros"]
NIVEL_IDIOMA = {"AVANZADO": 3, "INTERMEDIO": 2, "BÁSICO": 1, "NINGUNA": 0}

# Nombre -> descripcion legible (se usa para interpretar clusters). Orden = columnas de V3.
VARIABLES_ESTRUCTURADAS = {
    "anios_espol": "Años en cargos estructurales de ESPOL (log)",
    **{f"prop_cargo_{g}": f"Proporción de años como {g.replace('_', ' ')}" for g in GRUPOS},
    "n_cargos_estructurales": "Cargos estructurales distintos (log)",
    "n_contratos_puntuales": "Contratos puntuales distintos (log)",
    "docencia_posgrado_contrato": "Docencia de posgrado por contrato",
    "n_funciones_adicionales": "Funciones adicionales (log)",
    "fue_autoridad": "Fue autoridad (función adicional)",
    "anios_experiencia_externa": "Años de experiencia externa (log)",
    "experiencia_exterior": "Experiencia laboral en el exterior",
    "prop_experiencia_academica": "Proporción de experiencia externa académica",
    "nivel_formacion": "Nivel máximo de formación (1 bachiller … 4 doctorado)",
    "titulo_exterior": "Título obtenido en el exterior",
    "n_posgrados": "Títulos de cuarto nivel (log)",
    "estudiando_posgrado": "Posgrado en curso",
    "n_proyectos_investigacion": "Proyectos de investigación (log)",
    "dirigio_proyecto": "Dirigió o codirigió un proyecto de investigación",
    "n_publicaciones": "Publicaciones (log)",
    "n_publicaciones_q1q2": "Publicaciones Q1–Q2 (log)",
    "n_tesis_dirigidas": "Tesis dirigidas (log)",
    "n_ponencias": "Ponencias (log)",
    "n_proyectos_vinculacion": "Proyectos de vinculación (log)",
    "n_materias": "Materias dictadas (log)",
    "n_periodos_docencia": "Semestres con docencia (log)",
    "prop_solo_practico": "Proporción de materias dictadas solo como componente práctico",
    "anios_con_carga": "Años con carga politécnica (log)",
    "prop_horas_docencia": "Proporción de horas de carga en docencia",
    "prop_horas_gestion": "Proporción de horas de carga en gestión",
    "prop_horas_investigacion": "Proporción de horas de carga en investigación",
    "prop_horas_vinculacion": "Proporción de horas de carga en vinculación",
    "n_capacitaciones": "Capacitaciones (log)",
    "n_certificaciones": "Certificaciones (log)",
    "nivel_ingles": "Nivel máximo de inglés (0–3)",
    "n_idiomas_extranjeros": "Idiomas distintos del español",
    "n_menciones": "Menciones de honor (log)",
}


def _nivel_formacion(a: dict) -> float:
    nivel = str(a.get("nivel") or "").upper()
    grado = str(a.get("grado_academico") or "").upper()
    if "CUARTO" in nivel:
        return {"DOCTORADO": 4.0, "MAESTRIA": 3.0}.get(grado, 2.5)
    if "TERCER" in nivel:
        return 2.0
    if "TECN" in nivel:
        return 1.5
    if "BACHILLER" in nivel or "SECUNDARI" in nivel:
        return 1.0
    return 0.5


def vista_estructurada(ev: pd.DataFrame, personas: list[int]) -> pd.DataFrame:
    """Variables estructuradas por persona (sin escalar). `ev` con la columna `atributos`."""
    x = {p: defaultdict(float) for p in personas}
    anios_cat = {p: defaultdict(float) for p in personas}
    cuentas = defaultdict(lambda: defaultdict(int))
    exp_total, exp_acad = defaultdict(int), defaultdict(int)
    horas = {p: defaultdict(float) for p in personas}
    materias, solo_practico = defaultdict(int), defaultdict(int)

    for p, tipo, s in zip(ev["persona_id"], ev["tipo_id"], ev["atributos"]):
        if p not in x:
            continue
        a = json.loads(s)
        cuentas[p][tipo] += 1
        v = x[p]
        if tipo == "TRAYECTORIA_CARGO_ESTRUCTURAL":
            d = a.get("duracion_total_anios") or 0.0
            v["anios_espol"] += d
            cat = (a.get("categorias_cargo") or ["OTROS"])[0]
            anios_cat[p][GRUPO_CATEGORIA.get(cat, "otros")] += d
        elif tipo == "TRAYECTORIA_CONTRATO_PUNTUAL":
            if "POSGRADO" in (a.get("niveles_docencia") or []):
                v["docencia_posgrado_contrato"] = 1.0
        elif tipo == "TRAYECTORIA_FUNCION_ADICIONAL":
            if any("AUTORIDAD" in c for c in (a.get("categoria") or [])):
                v["fue_autoridad"] = 1.0
        elif tipo == "TRAYECTORIA_EXPERIENCIA_EXTERNA":
            v["anios_experiencia_externa"] += a.get("duracion_anios") or 0.0
            v["experiencia_exterior"] = max(v["experiencia_exterior"], 1.0 if a.get("es_exterior") else 0.0)
            exp_total[p] += 1
            exp_acad[p] += a.get("categoria_experiencia") == "ACADEMICA"
        elif tipo == "FORMACION_TITULO":
            v["nivel_formacion"] = max(v["nivel_formacion"], _nivel_formacion(a))
            v["titulo_exterior"] = max(v["titulo_exterior"], 1.0 if a.get("es_exterior") else 0.0)
            v["n_posgrados"] += "CUARTO" in str(a.get("nivel") or "").upper()
        elif tipo == "FORMACION_EN_CURSO":
            if "CUARTO" in str(a.get("nivel") or "").upper():
                v["estudiando_posgrado"] = 1.0
        elif tipo == "PROYECTO_INVESTIGACION":
            if set(a.get("roles") or []) & {"DIRECTOR", "CO-DIRECTOR"}:
                v["dirigio_proyecto"] = 1.0
        elif tipo == "PUBLICACION":
            if set(a.get("cuartiles_sjr") or []) & {"Q1", "Q2"}:
                v["n_publicaciones_q1q2"] += 1
        elif tipo == "DOCENCIA_MATERIA":
            materias[p] += 1
            v["n_periodos_docencia"] += a.get("n_periodos") or 0
            solo_practico[p] += a.get("componentes") == ["PRACTICO"]
        elif tipo == "ACTIVIDAD_CARGA":
            for d in a.get("detalle") or []:
                horas[p][d.get("actividad") or "OTRA"] += d.get("horas") or 0.0
        elif tipo == "IDIOMA":
            if a.get("idioma") != "ESPAÑOL":
                v["n_idiomas_extranjeros"] += 1
            if a.get("idioma") == "INGLÉS":
                niveles = (a.get("niveles_conversacion") or []) + (a.get("niveles_lectura") or [])
                v["nivel_ingles"] = max([v["nivel_ingles"]] + [NIVEL_IDIOMA.get(n, 0) for n in niveles])

    # Anios con carga politecnica: anios distintos en los detalles
    anios_carga = defaultdict(set)
    for p, s in zip(ev.loc[ev["tipo_id"] == "ACTIVIDAD_CARGA", "persona_id"], ev.loc[ev["tipo_id"] == "ACTIVIDAD_CARGA", "atributos"]):
        anios_carga[p].update(json.loads(s).get("anios") or [])

    filas = []
    for p in personas:
        v, c = x[p], cuentas[p]
        total_cat = sum(anios_cat[p].values())
        h = horas[p]
        total_h = sum(h.values())
        fila = {
            "persona_id": p,
            "anios_espol": math.log1p(v["anios_espol"]),
            **{f"prop_cargo_{g}": (anios_cat[p][g] / total_cat if total_cat else 0.0) for g in GRUPOS},
            "n_cargos_estructurales": math.log1p(c["TRAYECTORIA_CARGO_ESTRUCTURAL"]),
            "n_contratos_puntuales": math.log1p(c["TRAYECTORIA_CONTRATO_PUNTUAL"]),
            "docencia_posgrado_contrato": v["docencia_posgrado_contrato"],
            "n_funciones_adicionales": math.log1p(c["TRAYECTORIA_FUNCION_ADICIONAL"]),
            "fue_autoridad": v["fue_autoridad"],
            "anios_experiencia_externa": math.log1p(v["anios_experiencia_externa"]),
            "experiencia_exterior": v["experiencia_exterior"],
            "prop_experiencia_academica": exp_acad[p] / exp_total[p] if exp_total[p] else 0.0,
            "nivel_formacion": v["nivel_formacion"],
            "titulo_exterior": v["titulo_exterior"],
            "n_posgrados": math.log1p(v["n_posgrados"]),
            "estudiando_posgrado": v["estudiando_posgrado"],
            "n_proyectos_investigacion": math.log1p(c["PROYECTO_INVESTIGACION"]),
            "dirigio_proyecto": v["dirigio_proyecto"],
            "n_publicaciones": math.log1p(c["PUBLICACION"]),
            "n_publicaciones_q1q2": math.log1p(v["n_publicaciones_q1q2"]),
            "n_tesis_dirigidas": math.log1p(c["TESIS_DIRIGIDA"]),
            "n_ponencias": math.log1p(c["PONENCIA"]),
            "n_proyectos_vinculacion": math.log1p(c["PROYECTO_VINCULACION"]),
            "n_materias": math.log1p(materias[p]),
            "n_periodos_docencia": math.log1p(v["n_periodos_docencia"]),
            "prop_solo_practico": solo_practico[p] / materias[p] if materias[p] else 0.0,
            "anios_con_carga": math.log1p(len(anios_carga[p])),
            "prop_horas_docencia": h["DOCENCIA"] / total_h if total_h else 0.0,
            "prop_horas_gestion": h["GESTION"] / total_h if total_h else 0.0,
            "prop_horas_investigacion": h["INVESTIGACION"] / total_h if total_h else 0.0,
            "prop_horas_vinculacion": h["VINCULACION"] / total_h if total_h else 0.0,
            "n_capacitaciones": math.log1p(c["CAPACITACION"]),
            "n_certificaciones": math.log1p(c["CERTIFICACION"]),
            "nivel_ingles": v["nivel_ingles"],
            "n_idiomas_extranjeros": v["n_idiomas_extranjeros"],
            "n_menciones": math.log1p(c["MENCION_HONOR"]),
        }
        filas.append(fila)
    df = pd.DataFrame(filas).set_index("persona_id")
    return df[list(VARIABLES_ESTRUCTURADAS)]


def vistas_semanticas(ev: pd.DataFrame, personas: list[int], vistas: dict[str, list[str]] | None = None) -> dict[str, dict]:
    """{'v1_trayectoria': {'matriz': (n x d), 'faltante': bool[n]}, 'v2_academico': ...}. Con `vistas`
    ({nombre: tipos de evidencia}) se calcula cualquier otro agrupamiento de tipos con el mismo
    procedimiento (p. ej. una dimensión, DEC-053)."""
    if vistas is None:
        vistas = {"v1_trayectoria": TIPOS_V1_TRAYECTORIA, "v2_academico": TIPOS_V2_ACADEMICO}
    textos, vectores, _ = emb.cargar()
    posicion = dict(zip(textos["clave"], range(len(textos))))
    d = ev[["persona_id", "tipo_id", "texto"]].dropna().copy()
    d["_vec"] = d["texto"].map(lambda t: posicion.get(emb.clave_texto(t), -1))
    if (d["_vec"] < 0).any():
        raise ValueError(f"{int((d['_vec'] < 0).sum())} evidencias sin embedding: correr perfiles.embeddings primero")
    personas_por_texto = d.groupby("texto")["persona_id"].nunique()
    d["_peso"] = 1.0 / np.log2(1.0 + d["texto"].map(personas_por_texto).to_numpy())
    idx_persona = {p: i for i, p in enumerate(personas)}
    d = d[d["persona_id"].isin(idx_persona)]

    salida = {}
    for nombre, tipos in vistas.items():
        s = d[d["tipo_id"].isin(tipos)]
        # nivel 1: persona + tipo
        grupos = s.groupby(["persona_id", "tipo_id"], sort=False).ngroup().to_numpy()
        n_grupos = grupos.max() + 1 if len(grupos) else 0
        m = sparse.csr_matrix((s["_peso"].to_numpy(), (grupos, s["_vec"].to_numpy())), shape=(n_grupos, len(vectores)))
        suma = m @ vectores
        media_tipo = suma / np.asarray(m.sum(axis=1)).reshape(-1, 1)
        persona_de_grupo = s.groupby(["persona_id", "tipo_id"], sort=False)["persona_id"].first().to_numpy()
        # nivel 2: promedio simple entre tipos de la persona
        filas = np.array([idx_persona[p] for p in persona_de_grupo])
        agg = sparse.csr_matrix((np.ones(len(filas)), (filas, np.arange(len(filas)))), shape=(len(personas), len(filas)))
        conteo = np.asarray(agg.sum(axis=1)).ravel()
        matriz = np.asarray(agg @ media_tipo)
        faltante = conteo == 0
        matriz[~faltante] /= conteo[~faltante, None]
        normas = np.linalg.norm(matriz, axis=1, keepdims=True)
        matriz = np.divide(matriz, normas, out=np.zeros_like(matriz), where=normas > 0)
        if faltante.any() and (~faltante).any():  # sin evidencias en la vista: vector medio (neutral)
            media = matriz[~faltante].mean(axis=0)
            matriz[faltante] = media / np.linalg.norm(media)
        salida[nombre] = {"matriz": matriz.astype(np.float32), "faltante": faltante}
    return salida
