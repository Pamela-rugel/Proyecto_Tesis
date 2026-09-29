"""Subtipo TESIS_DIRIGIDA: trabajos de titulacion de posgrado dirigidos por la persona.

Fuente: `proyecto_grado.csv`, UNA FILA POR ESTUDIANTE (la persona es `IDDIRECTOR`). Solo hay
posgrado (maestria profesional, de investigacion y doctorado). No hay area tematica ni
identificador de estudiante.

Reglas (decisiones del usuario, 2026-09-28):
- Limpieza del titulo (texto y atributo `titulo`): espacios y saltos de linea, comillas que
  lo envuelven, y la marca de modalidad "EXAMEN COMPLEXIVO" (al inicio o al final); la
  modalidad pasa al atributo `modalidad`. Los titulos originales distintos quedan en
  `titulos_originales`.
- Titulos GENERICOS sin tema ("EXAMEN COMPLEXIVO - FASE 2", "CURRICULUM COMPLETO - MSIG ..."):
  no son evidencia (no aportan al embedding); quedan en `registros_no_considerados.csv`.
- Agrupacion: una evidencia por director + titulo casi identico (similitud >= 0.95). Las
  filas (estudiantes) se agrupan en `sustentaciones`: una por fecha + programa + unidad +
  promocion + nivel, con su numero de estudiantes.
- Codirectores: otras personas de la poblacion que dirigieron el mismo titulo
  (`codirectores_espol`, `n_codirectores_espol`).
- Texto: "TITULO, Nivel: ..., Programa: ..., Unidad: ... (SIGLA)"; varios valores con ";".
"""
from __future__ import annotations

import re

import pandas as pd

from evidencias import esquema as es
from evidencias.investigacion.publicacion import _agrupar_titulos
from evidencias.trayectoria.fuentes import sigla_unidad

TIPO_ID = "TESIS_DIRIGIDA"
PREFIJO_ID = "INV-TES"
MOTIVO_GENERICO = "título genérico sin tema (examen complexivo o currículum completo)"

_MARCA_COMPLEXIVO_INICIO = re.compile(r"^\s*EXAMEN\s+COMPLEXIVO\s*[.:\-–—]*\s*", re.IGNORECASE)
_MARCA_COMPLEXIVO_FIN = re.compile(r"\s*[.\-–—]*\s*EXAMEN\s+COMPLEXIVO\s*[.]*\s*$", re.IGNORECASE)
# "CURRICULUM COMPLETO – MSIG - PROM. II - <tema>": se quita la marca y la promocion; si queda
# un tema, la evidencia se conserva (modalidad CURRICULUM_COMPLETO)
_MARCA_CURRICULUM = re.compile(
    r"^\s*CURRICULUM\s+COMPLETO\s*[.:\-–—]*\s*(MSIG)?\s*[.:\-–—]*\s*"
    r"(PROM\.?\s*[IVX\d]+\.?|[IVX]+)?\s*[.:\-–—]*\s*",
    re.IGNORECASE,
)
_COMILLAS = "\"'“”«»"
_NIVEL_TEXTO = {"MAESTRIA PROFESIONAL": "Maestría profesional",
                "MAESTRIA INVESTIGACION": "Maestría de investigación",
                "DOCTORADO": "Doctorado"}


def modalidad(titulo_original) -> str:
    n = es.normalizar_para_comparar(titulo_original)
    if n.startswith("CURRICULUM COMPLETO"):
        return "CURRICULUM_COMPLETO"
    return "EXAMEN_COMPLEXIVO" if "COMPLEXIVO" in n else "TRABAJO_DE_TITULACION"


def limpiar_titulo(titulo_original) -> str | None:
    """Titulo sin espacios sobrantes, sin comillas envolventes ni marcas de modalidad
    (examen complexivo, curriculum completo)."""
    t = es.limpiar_para_mostrar(titulo_original)
    if not t:
        return None
    t = _MARCA_CURRICULUM.sub("", t)
    t = _MARCA_COMPLEXIVO_FIN.sub("", _MARCA_COMPLEXIVO_INICIO.sub("", t))
    t = t.strip().strip(_COMILLAS).strip().rstrip(" .-–—").strip()
    return t or None


def es_generico(titulo_original) -> bool:
    """Sin tema: complexivo o curriculum completo que, tras quitar la marca, no dice nada o
    solo dice 'FASE n'. Si queda un tema, NO es generico y se conserva."""
    if modalidad(titulo_original) == "TRABAJO_DE_TITULACION":
        return False
    resto = es.normalizar_para_comparar(limpiar_titulo(titulo_original))
    return resto == "" or re.fullmatch(r"FASE \d+", resto) is not None


def _nivel_texto(nivel: str) -> str:
    return _NIVEL_TEXTO.get(es.normalizar_para_comparar(nivel), nivel)


def _sustentaciones(g: pd.DataFrame) -> list[dict]:
    claves = ["FECHASUSTENTACION", "NOMBREPROGRAMA", "NOMBREUNIDAD", "NUMPROMOCION", "NIVELFORMACION"]
    salida = []
    for vals, gs in g.groupby(claves, dropna=False, sort=False):
        fecha, programa, unidad, promocion, nivel = vals
        salida.append({
            "fecha": es.fecha_iso(fecha),
            "nivel_formacion": es.texto_limpio(nivel),
            "programa": es.limpiar_para_mostrar(programa),
            "unidad": es.limpiar_para_mostrar(unidad),
            "promocion": None if es.valor_nulo(promocion) else int(promocion),
            "n_estudiantes": len(gs),
        })
    return sorted(salida, key=lambda s: (s["fecha"] is None, s["fecha"] or ""))


def _texto(titulo: str, niveles: list[str], programas: list[str], unidades_txt: list[str]) -> str:
    partes = [titulo]
    if niveles:
        partes.append(f"Nivel: {'; '.join(_nivel_texto(n) for n in niveles)}")
    if programas:
        partes.append(f"Programa: {'; '.join(programas)}")
    if unidades_txt:
        partes.append(f"Unidad: {'; '.join(unidades_txt)}")
    return ", ".join(partes)


def construir(tesis: pd.DataFrame, sin_director_fuente: int,
              mapa_siglas: dict) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    t = tesis.copy()
    t["_GENERICO"] = t["NOMBRETRABAJOTITULACION"].map(es_generico)
    genericos = t[t["_GENERICO"]]
    t = t[~t["_GENERICO"]].copy()
    t["_TITULO"] = t["NOMBRETRABAJOTITULACION"].map(limpiar_titulo)
    t["_CLAVE"] = t["_TITULO"].map(es.normalizar_para_comparar)
    t = t[t["_CLAVE"] != ""]

    directores_por_titulo = t.groupby("_CLAVE")["IDPERSONA"].apply(lambda s: sorted(set(int(x) for x in s))).to_dict()

    filas, n_multi_sust, n_codir = [], 0, 0
    for idp, g in t.groupby("IDPERSONA", sort=False):
        for grupo in _agrupar_titulos(g):
            sustentaciones = _sustentaciones(grupo)
            n_multi_sust += len(sustentaciones) > 1
            titulo = grupo["_TITULO"].value_counts().index[0]
            originales = es.unicos(grupo["NOMBRETRABAJOTITULACION"].map(es.limpiar_para_mostrar))
            codirectores = sorted({o for c in set(grupo["_CLAVE"]) for o in directores_por_titulo.get(c, []) if o != int(idp)})
            n_codir += bool(codirectores)
            niveles = es.unicos(s["nivel_formacion"] for s in sustentaciones)
            programas = es.unicos(s["programa"] for s in sustentaciones)
            unidades = es.unicos(s["unidad"] for s in sustentaciones)
            siglas = [sigla_unidad(u.upper(), mapa_siglas) if u else None for u in unidades]
            unidades_txt = [f"{u} ({s})" if s else u for u, s in zip(unidades, siglas)]
            fechas = [s["fecha"] for s in sustentaciones if s["fecha"]]
            atributos = {
                "titulo": titulo,
                "titulos_originales": originales,
                "modalidad": es.unicos(grupo["NOMBRETRABAJOTITULACION"].map(modalidad))[0],
                "niveles_formacion": niveles,
                "programas": programas,
                "unidades": [{"unidad": u, "sigla": s} for u, s in zip(unidades, siglas)],
                "fecha_inicio": None,
                "fecha_fin": max(fechas) if fechas else None,
                "n_sustentaciones": len(sustentaciones),
                "n_estudiantes": sum(s["n_estudiantes"] for s in sustentaciones),
                "promociones": sorted(es.unicos(s["promocion"] for s in sustentaciones)),
                "n_codirectores_espol": len(codirectores),
                "codirectores_espol": codirectores,
                "sustentaciones": sustentaciones,
                "_origen": {"fuente": "processed/proyecto_grado.csv", "n_filas": len(grupo)},
            }
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(PREFIJO_ID, idp, grupo["_CLAVE"].iloc[0]),
                idp, TIPO_ID, _texto(titulo, niveles, programas, unidades_txt), atributos,
            ))

    no_considerados = (
        genericos.groupby(["IDPERSONA", "NOMBRETRABAJOTITULACION"], sort=False)
        .agg(fecha_inicio=("FECHASUSTENTACION", "min"), filas=("IDPERSONA", "size"))
        .reset_index()
    )
    no_considerados = pd.DataFrame({
        "persona_id": no_considerados["IDPERSONA"].astype(int),
        "tipo_id": TIPO_ID,
        "motivo": MOTIVO_GENERICO,
        "id_origen": None,
        "descripcion": no_considerados["NOMBRETRABAJOTITULACION"].map(es.limpiar_para_mostrar)
                       + " (" + no_considerados["filas"].astype(str) + " estudiantes)",
        "fecha_inicio": no_considerados["fecha_inicio"].map(es.fecha_iso),
    })
    reporte = {
        "fuente": "processed/proyecto_grado.csv",
        "filas_sin_director_en_fuente": sin_director_fuente,
        "filas_poblacion": len(tesis),
        "filas_titulo_generico_no_consideradas": int(len(genericos)),
        "filas_complexivo_con_tema_marca_limpiada": int((t["NOMBRETRABAJOTITULACION"].map(modalidad) == "EXAMEN_COMPLEXIVO").sum()),
        "evidencias_con_varias_sustentaciones": n_multi_sust,
        "evidencias_con_codirectores_espol": n_codir,
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
