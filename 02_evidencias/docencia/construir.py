"""Orquesta la construccion del dataset de evidencias de DOCENCIA.

Uso desde notebook:
    from evidencias.docencia import construir_evidencias_docencia
    evidencias, reporte, validacion = construir_evidencias_docencia(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.docencia.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.docencia import actividad_carga, materia
from evidencias.docencia.fuentes import (
    SALIDA_DIR, cargar_carga_academica, cargar_catalogo_materias, cargar_poblacion,
)
from evidencias.formacion.fuentes import ARCHIVO_EVIDENCIAS_TRAYECTORIA
from evidencias.investigacion.fuentes import cargar_mapa_siglas

ARCHIVO_EVIDENCIAS = SALIDA_DIR / "evidencias_docencia.csv"
ARCHIVO_REPORTE = SALIDA_DIR / "reporte_evidencias_docencia.json"
ARCHIVO_NO_CONSIDERADOS = SALIDA_DIR / "registros_no_considerados.csv"
TIPOS = {materia.TIPO_ID, actividad_carga.TIPO_ID}


def construir_evidencias_docencia(
    guardar: bool = False, fecha_corte: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion)."""
    fecha_corte = fecha_corte or es.hoy()
    poblacion = cargar_poblacion()

    mapa_siglas = cargar_mapa_siglas()
    ev_mat, rep_mat, nc_mat = materia.construir(cargar_carga_academica(poblacion), mapa_siglas, fecha_corte)
    ev_act, rep_act, nc_act = actividad_carga.construir(
        actividad_carga.cargar(poblacion), pd.read_csv(ARCHIVO_EVIDENCIAS_TRAYECTORIA), mapa_siglas,
        cargar_catalogo_materias(),
    )
    evidencias = pd.concat([ev_mat, ev_act], ignore_index=True).sort_values(
        ["persona_id", "tipo_id", "evidencia_id"], kind="stable").reset_index(drop=True)
    no_considerados = pd.concat([nc_mat, nc_act], ignore_index=True).sort_values("persona_id")
    # Sin fecha de inicio: los semestres y anios van en listas (`periodos`, `anios`)
    validacion = es.validar_evidencias(evidencias, TIPOS, poblacion, fecha_corte, exigir_fecha_inicio=False)

    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_con_trayectoria": len(poblacion),
        "personas_con_evidencias": int(evidencias["persona_id"].nunique()),
        "evidencias_total": len(evidencias),
        "subtipos": {
            materia.TIPO_ID: {**rep_mat, "personas": int(ev_mat["persona_id"].nunique())},
            actividad_carga.TIPO_ID: {**rep_act, "personas": int(ev_act["persona_id"].nunique())},
        },
        "registros_no_considerados": int(len(no_considerados)),
        "validacion_ok": bool(validacion["ok"].all()),
    }

    if guardar:
        SALIDA_DIR.mkdir(parents=True, exist_ok=True)
        evidencias.to_csv(ARCHIVO_EVIDENCIAS, index=False, encoding="utf-8-sig")
        no_considerados.to_csv(ARCHIVO_NO_CONSIDERADOS, index=False, encoding="utf-8-sig")
        ARCHIVO_REPORTE.write_text(
            json.dumps({**reporte, "validacion": validacion.to_dict("records")}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return evidencias, reporte, validacion


if __name__ == "__main__":
    ev, rep, val = construir_evidencias_docencia(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
