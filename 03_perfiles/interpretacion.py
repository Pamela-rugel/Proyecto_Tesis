"""Caracteristicas y descripcion de cada cluster (DEC-045).

Primero se MIDEN los rasgos del cluster frente a su ambito, despues se arma la etiqueta con
ellos (nunca un nombre inventado):
- tipos de evidencia: proporcion de integrantes que tiene cada tipo vs el ambito (lift);
- variables estructuradas: media estandarizada (z) del cluster; las mas alejadas de 0;
- evidencias mas compartidas: textos que tienen mas integrantes (excluye los que tiene mas del
  30 % del ambito, que no distinguen);
- terminos distintivos: c-TF-IDF sobre los textos de las evidencias de los integrantes;
- unidades y categorias de cargo predominantes (cargo estructural).
Etiqueta: rol predominante + unidad (si concentra >= 40 %) + los dos rasgos estructurales mas
distintivos (z >= 0.5).
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter

import numpy as np
import pandas as pd

from perfiles.vistas import VARIABLES_ESTRUCTURADAS

NOMBRE_TIPO = {
    "TRAYECTORIA_CARGO_ESTRUCTURAL": "cargo estructural", "TRAYECTORIA_CONTRATO_PUNTUAL": "contrato puntual",
    "TRAYECTORIA_FUNCION_ADICIONAL": "función adicional", "TRAYECTORIA_EXPERIENCIA_EXTERNA": "experiencia externa",
    "FORMACION_TITULO": "título", "FORMACION_EN_CURSO": "formación en curso",
    "PROYECTO_INVESTIGACION": "proyecto de investigación", "PROYECTO_VINCULACION": "proyecto de vinculación",
    "PUBLICACION": "publicación", "TESIS_DIRIGIDA": "tesis dirigida", "PONENCIA": "ponencia",
    "CAPACITACION": "capacitación", "CERTIFICACION": "certificación", "IDIOMA": "idioma",
    "MENCION_HONOR": "mención de honor", "DOCENCIA_MATERIA": "materia dictada", "ACTIVIDAD_CARGA": "actividad de carga",
}
# Frase corta para la etiqueta, segun la variable estructurada mas distintiva
FRASE_VARIABLE = {
    "n_publicaciones": "publicaciones", "n_publicaciones_q1q2": "publicaciones Q1–Q2",
    "n_proyectos_investigacion": "proyectos de investigación", "dirigio_proyecto": "dirección de proyectos",
    "n_tesis_dirigidas": "dirección de tesis", "n_ponencias": "ponencias", "n_proyectos_vinculacion": "vinculación",
    "n_materias": "docencia en varias materias", "n_periodos_docencia": "docencia sostenida",
    "prop_solo_practico": "docencia práctica/laboratorio", "anios_con_carga": "carga politécnica sostenida",
    "prop_horas_gestion": "carga de gestión", "prop_horas_investigacion": "carga de investigación",
    "prop_horas_vinculacion": "carga de vinculación", "prop_horas_docencia": "carga docente",
    "n_funciones_adicionales": "funciones adicionales", "fue_autoridad": "cargos de autoridad",
    "nivel_formacion": "formación de posgrado", "titulo_exterior": "títulos del exterior", "n_posgrados": "posgrados",
    "estudiando_posgrado": "posgrado en curso", "anios_espol": "trayectoria larga en ESPOL",
    "anios_experiencia_externa": "experiencia externa", "experiencia_exterior": "experiencia en el exterior",
    "n_capacitaciones": "capacitación continua", "n_certificaciones": "certificaciones",
    "nivel_ingles": "inglés avanzado", "n_idiomas_extranjeros": "idiomas extranjeros", "n_menciones": "reconocimientos",
    "n_contratos_puntuales": "contratos puntuales", "docencia_posgrado_contrato": "docencia de posgrado",
    "n_cargos_estructurales": "varios cargos", "prop_experiencia_academica": "experiencia académica externa",
}
ROL_GRUPO = {
    "docente_titular": "Docentes titulares", "docente_no_titular": "Docentes no titulares",
    "tecnico_docente": "Técnicos docentes", "autoridad": "Autoridades", "jefatura": "Jefaturas",
    "profesional": "Profesionales/analistas", "asistencia_oficina": "Asistencia y oficina",
    "operativo": "Personal operativo", "otros": "Otros cargos",
}
_STOP = set("""de la el los las y en del a al para por con sin un una o u e que su sus se lo como mas más entre sobre
the of and in for to on with an at by from is are this that de nivel tipo cine subarea subárea frascati
facultad escuela superior politecnica politécnica litoral unidad programa proyecto curso ingenieria ingeniería
modalidad virtual presencial certificado certificados organizado otorgado publicado indexacion indexación pais país
roles rol participante contrato profesor docente materia tipo seminario taller conferencia congreso mencion
""".split())


def _tokens(texto: str) -> list[str]:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode("ascii")
    return [w for w in re.findall(r"[a-z]{4,}", t) if w not in _STOP]


def terminos_distintivos(textos_por_cluster: dict[int, list[str]], n: int = 10) -> dict[int, list[str]]:
    """c-TF-IDF: frecuencia del termino en el cluster x log(1 + promedio de palabras por
    cluster / frecuencia total del termino)."""
    conteos = {c: Counter(w for t in ts for w in set(_tokens(t))) for c, ts in textos_por_cluster.items()}
    total = Counter()
    for c in conteos.values():
        total.update(c)
    media_palabras = np.mean([sum(c.values()) for c in conteos.values()]) or 1
    salida = {}
    for c, cnt in conteos.items():
        tam = sum(cnt.values()) or 1
        puntaje = {w: (f / tam) * math.log(1 + media_palabras / total[w]) for w, f in cnt.items() if f >= 3}
        salida[c] = [w for w, _ in sorted(puntaje.items(), key=lambda x: -x[1])[:n]]
    return salida


def describir(ambito_personas: pd.DataFrame, etiquetas: np.ndarray, x_z: pd.DataFrame, x_crudo: pd.DataFrame,
              ev: pd.DataFrame, k: int, referencia: str = "personal analizado") -> list[dict]:
    """Una ficha por cluster. `ambito_personas`: persona_id, tipo_empleado (orden = etiquetas).
    `referencia` nombra el conjunto contra el que se compara en el texto ("personal analizado", o "patrón"
    para los subpatrones; los campos *_ambito contienen entonces los valores del patrón padre)."""
    personas = ambito_personas["persona_id"].to_numpy()
    cluster_de = dict(zip(personas, etiquetas))
    e = ev[ev["persona_id"].isin(cluster_de)].copy()
    e["cluster"] = e["persona_id"].map(cluster_de)
    n_ambito = len(personas)

    # tipos de evidencia: proporcion de personas con el tipo
    tiene = e.groupby(["tipo_id", "persona_id"]).size().reset_index()[["tipo_id", "persona_id"]]
    tiene["cluster"] = tiene["persona_id"].map(cluster_de)
    prop_ambito = tiene.groupby("tipo_id")["persona_id"].nunique() / n_ambito
    # evidencias compartidas: textos con cobertura global baja
    personas_texto = e.groupby("texto")["persona_id"].nunique()
    comunes = set(personas_texto[personas_texto > 0.30 * n_ambito].index)
    # cargo estructural: unidad y categoria
    est = e[e["tipo_id"] == "TRAYECTORIA_CARGO_ESTRUCTURAL"].copy()
    est["_a"] = est["atributos"].map(json.loads)
    est["unidad"] = est["_a"].map(lambda a: a.get("unidad_sigla") or a.get("unidad"))
    textos_cluster = {c: e.loc[e["cluster"] == c, "texto"].tolist() for c in range(k)}
    terminos = terminos_distintivos(textos_cluster)

    fichas = []
    for c in range(k):
        miembros = personas[etiquetas == c]
        n = len(miembros)
        t_c = tiene[tiene["cluster"] == c].groupby("tipo_id")["persona_id"].nunique() / n
        tipos = [{"tipo_id": t, "tipo": NOMBRE_TIPO.get(t, t), "prop_integrantes": round(float(p), 3),
                  "prop_ambito": round(float(prop_ambito.get(t, 0)), 3),
                  "lift": round(float(p / prop_ambito[t]), 2) if prop_ambito.get(t) else None}
                 for t, p in t_c.items()]
        tipos.sort(key=lambda x: -(x["lift"] or 0) * x["prop_integrantes"])

        z = x_z.loc[miembros].mean()
        crudo_c, crudo_a = x_crudo.loc[miembros].mean(), x_crudo.mean()
        rasgos = [{"variable": v, "descripcion": VARIABLES_ESTRUCTURADAS[v], "z": round(float(z[v]), 2),
                   "media_cluster": round(float(crudo_c[v]), 3), "media_ambito": round(float(crudo_a[v]), 3)}
                  for v in z.abs().sort_values(ascending=False).index[:8]]

        e_c = e[(e["cluster"] == c) & ~e["texto"].isin(comunes)]
        compartidas = (e_c.groupby(["tipo_id", "texto"])["persona_id"].nunique().sort_values(ascending=False).head(10))
        evidencias = [{"tipo": NOMBRE_TIPO.get(t, t), "texto": txt, "integrantes": int(m), "prop": round(m / n, 3)}
                      for (t, txt), m in compartidas.items() if m >= 2]

        est_c = est[est["cluster"] == c]
        unidades = (est_c.groupby("unidad")["persona_id"].nunique() / n).sort_values(ascending=False).head(4)
        tipo_emp = ambito_personas.loc[etiquetas == c, "tipo_empleado"].value_counts(normalize=True)

        rol = max((g for g in ROL_GRUPO), key=lambda g: crudo_c.get(f"prop_cargo_{g}", 0))
        rol_prop = crudo_c.get(f"prop_cargo_{rol}", 0)
        distintivos = [r for r in rasgos if r["z"] >= 0.5 and r["variable"] in FRASE_VARIABLE][:2]
        # "Cargos diversos" (no "mixto": ese termino se reserva para la pertenencia a dos patrones)
        partes = [ROL_GRUPO[rol] if rol_prop >= 0.3 else "Cargos diversos"]
        if len(unidades) and unidades.iloc[0] >= 0.4 and unidades.index[0]:
            partes.append(str(unidades.index[0]))
        partes += [FRASE_VARIABLE[r["variable"]] for r in distintivos]
        etiqueta = " · ".join(partes)

        bajos = [r for r in rasgos if r["z"] <= -0.5 and r["variable"] in FRASE_VARIABLE][:2]
        descripcion = (
            f"{n} personas ({n / n_ambito:.0%} del {referencia}). "
            f"Cargo más común: {ROL_GRUPO[rol].lower()} (ocupa el {rol_prop:.0%} de sus años en cargos de planta). "
            + (f"Destacan en: {', '.join(FRASE_VARIABLE[r['variable']] for r in distintivos)}. " if distintivos else "")
            + (f"Tienen menos: {', '.join(FRASE_VARIABLE[r['variable']] for r in bajos)}. " if bajos else "")
            + (f"Registros más frecuentes que en el resto: {', '.join(x['tipo'] for x in tipos[:3])}. " if tipos else "")
            + (f"Unidad más frecuente: {unidades.index[0]} ({unidades.iloc[0]:.0%})." if len(unidades) else "")
        )
        fichas.append({
            "cluster": c, "etiqueta": etiqueta, "descripcion": descripcion, "tamano": int(n),
            "tipo_empleado": {k_: round(float(v), 3) for k_, v in tipo_emp.items()},
            "tipos_evidencia": tipos[:8], "rasgos_estructurados": rasgos, "evidencias_compartidas": evidencias,
            "terminos_distintivos": terminos.get(c, []),
            "unidades": [{"unidad": u, "prop": round(float(p), 3)} for u, p in unidades.items() if u],
        })
    return fichas
