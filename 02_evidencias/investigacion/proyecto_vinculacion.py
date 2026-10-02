"""Subtipo PROYECTO_VINCULACION: participacion en proyectos de vinculacion con la sociedad.

Fuente: `proyectos_vinculacion_disponible.csv`, una fila por persona + proyecto + rol. No hay
area tematica (`IDAREACONOCIM` vacio): el tema esta solo en los nombres del proyecto y del
programa.

Reglas (decisiones del usuario, 2026-09-28):
- Una evidencia por persona + NOMBRE de proyecto. Para agrupar se quita el sufijo
  "(Gastos Generales)"; los nombres originales distintos quedan en `nombres_similares`.
  Cada ID de proyecto es un periodo, con sus roles y su programa.
- Roles: todos, sin jerarquia (texto "Roles: tutor, director de proyecto"; lista `roles`).
- Proyectos sin fechas: se conservan, con fechas y `vigente` en null.
- `vigente` solo por fechas (sin fin pero con inicio = vigente; sin ninguna fecha = null).
- Inicio futuro: no es evidencia; queda en `registros_no_considerados.csv`.
- Fin anterior al inicio: se conservan las fechas, el periodo se marca
  `fechas_inconsistentes` y su duracion queda null.

Texto: "NOMBRE, Roles: ..., Programa: ..." (o "Programas: A; B" si hay varios). Sin etiqueta
de tipo al inicio (decision del usuario, 2026-09-28): el tipo ya esta en `tipo_id`.
"""
from __future__ import annotations

import re

import pandas as pd

from evidencias import esquema as es

TIPO_ID = "PROYECTO_VINCULACION"
PREFIJO_ID = "INV-VIN"
MOTIVO_INICIO_FUTURO = "proyecto de vinculación con fecha de inicio futura"
_SUFIJO_GASTOS = re.compile(r"\s*\(\s*gastos\s+generales\s*\)\s*$", re.IGNORECASE)


def nombre_base(nombre) -> str | None:
    """Nombre sin el sufijo "(Gastos Generales)" ni puntuacion final, para agrupar."""
    n = es.limpiar_para_mostrar(nombre)
    return _SUFIJO_GASTOS.sub("", n).rstrip(" .") if n else None


def _periodo(g: pd.DataFrame, fecha_corte) -> dict:
    r = g.iloc[0]
    ini, fin = r["FECHAINICIO"], r["FECHAFIN"]
    invertidas = not es.valor_nulo(ini) and not es.valor_nulo(fin) and fin < ini
    return {
        "id_proyecto": int(r["IDPROYECTOINVESTIGACION"]),
        "nombre_original": es.limpiar_para_mostrar(r["NOMBREPROYECTO"]),
        "inicio": es.fecha_iso(ini),
        "fin": es.fecha_iso(fin),
        "duracion_anios": None if invertidas or es.valor_nulo(ini) else es.duracion_anios(ini, fin, fecha_corte),
        "vigente": None if es.valor_nulo(ini) and es.valor_nulo(fin) else es.es_vigente(fin, fecha_corte),
        "fechas_inconsistentes": invertidas,
        "roles": es.unicos(g["ROLPROYECTO"].map(es.texto_limpio)),
        "programa": es.limpiar_para_mostrar(r["NOMBREPROGRAMA"]),
        "codigo_colaboracion": None if es.valor_nulo(r["IDVSPROYECTOCOL"]) else int(r["IDVSPROYECTOCOL"]),
        "url": es.texto_limpio(r["REFARCHIVO1"]),
    }


def _resumen(periodos: list[dict]) -> dict:
    """Fechas de la evidencia a partir de los periodos que SI tienen fechas: primer inicio,
    ultimo fin (null si alguno con inicio sigue abierto) y vigencia (null si ninguno tiene
    fechas). Los periodos sin fechas cuentan en `n_periodos` pero no en las fechas."""
    con_fecha = [p for p in periodos if p["inicio"] or p["fin"]]
    inicios = [p["inicio"] for p in con_fecha if p["inicio"]]
    fines = [p["fin"] for p in con_fecha if p["fin"]]
    abierto = any(p["inicio"] and not p["fin"] for p in con_fecha)
    vigencias = [p["vigente"] for p in periodos if p["vigente"] is not None]
    duraciones = [p["duracion_anios"] for p in periodos if p["duracion_anios"] is not None]
    return {
        "fecha_inicio": min(inicios) if inicios else None,
        "fecha_fin": None if abierto or not fines else max(fines),
        "vigente": any(vigencias) if vigencias else None,
        "n_periodos": len(periodos),
        "duracion_total_anios": round(sum(duraciones), 2) if duraciones else None,
    }


def _texto(nombre: str, roles: list[str], programas: list[str]) -> str:
    partes = [nombre]
    if roles:
        partes.append(f"Roles: {', '.join(r.lower() for r in roles)}")
    if programas:
        etiqueta = "Programa" if len(programas) == 1 else "Programas"
        partes.append(f"{etiqueta}: {'; '.join(programas)}")
    return ", ".join(partes)


def construir(vinculacion: pd.DataFrame, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    v = vinculacion.drop_duplicates()
    n_duplicados_exactos = len(vinculacion) - len(v)
    futuro = v["FECHAINICIO"] > fecha_corte
    no_considerados = v[futuro].drop_duplicates(["IDPERSONA", "IDPROYECTOINVESTIGACION"]).assign(
        motivo=MOTIVO_INICIO_FUTURO
    )
    v = v[~futuro].copy()
    v["_BASE"] = v["NOMBREPROYECTO"].map(nombre_base)
    v["_CLAVE"] = v["_BASE"].map(es.normalizar_para_comparar)

    filas, n_periodos, n_sin_fechas, n_invertidas, n_similares = [], 0, 0, 0, 0
    for (idp, _), g in v.groupby(["IDPERSONA", "_CLAVE"], sort=False):
        periodos = [_periodo(gp, fecha_corte) for _, gp in g.groupby("IDPROYECTOINVESTIGACION", sort=False)]
        periodos.sort(key=lambda p: (p["inicio"] is None, p["inicio"] or ""))
        n_periodos += len(periodos)
        n_sin_fechas += sum(1 for p in periodos if not p["inicio"] and not p["fin"])
        n_invertidas += sum(p["fechas_inconsistentes"] for p in periodos)

        # Nombre a mostrar: el nombre base mas frecuente del grupo (sin sufijo)
        nombre = g["_BASE"].value_counts().index[0]
        # Solo variantes con contenido distinto (p.ej. con "(Gastos Generales)"); no las que
        # difieren unicamente en mayusculas, tildes o puntuacion.
        clave_nombre = es.normalizar_para_comparar(nombre)
        similares = [n for n in es.unicos(p["nombre_original"] for p in periodos)
                     if es.normalizar_para_comparar(n) != clave_nombre]
        n_similares += bool(similares)
        roles = es.unicos(r for p in periodos for r in p["roles"])
        programas = es.unicos(p["programa"] for p in periodos)

        atributos = {
            "nombre": nombre,
            "nombres_similares": similares,
            "roles": roles,
            "programas": programas,
            **_resumen(periodos),
            "codigos_colaboracion": es.unicos(p["codigo_colaboracion"] for p in periodos),
            "periodos": periodos,
            "_origen": {
                "fuente": "processed/proyectos_vinculacion_disponible.csv",
                "ids_proyecto": [p["id_proyecto"] for p in periodos],
            },
        }
        filas.append(es.nueva_evidencia(
            es.generar_evidencia_id(PREFIJO_ID, idp, es.normalizar_para_comparar(nombre)),
            idp, TIPO_ID, _texto(nombre, roles, programas), atributos,
        ))

    reporte = {
        "fuente": "processed/proyectos_vinculacion_disponible.csv",
        "filas_poblacion": len(vinculacion),
        "duplicados_exactos_eliminados": n_duplicados_exactos,
        "inicio_futuro_no_considerados": int(len(no_considerados)),
        "periodos_en_evidencias": n_periodos,
        "periodos_sin_fechas_conservados": n_sin_fechas,
        "periodos_con_fechas_invertidas": int(n_invertidas),
        "evidencias_con_nombres_similares": n_similares,
        "evidencias_con_varios_periodos": sum('"n_periodos": 1,' not in f["atributos"] for f in filas),
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
