"""Orquesta la construccion del dataset de evidencias de FORMACION ACADEMICA.

Uso desde notebook:
    from evidencias.formacion import construir_evidencias_formacion
    evidencias, reporte, validacion = construir_evidencias_formacion(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.formacion.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.formacion import en_curso, titulo
from evidencias.formacion.fuentes import SALIDA_DIR, cargar_poblacion, cargar_titulos

ARCHIVO_EVIDENCIAS = SALIDA_DIR / "evidencias_formacion.csv"
ARCHIVO_REPORTE = SALIDA_DIR / "reporte_evidencias_formacion.json"
ARCHIVO_NO_CONSIDERADOS = SALIDA_DIR / "registros_no_considerados.csv"
TIPOS = {titulo.TIPO_ID, en_curso.TIPO_ID}


def construir_evidencias_formacion(
    guardar: bool = False, fecha_corte: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion)."""
    fecha_corte = fecha_corte or es.hoy()
    poblacion = cargar_poblacion()
    titulos = cargar_titulos(poblacion)

    ev_tit, rep_tit, nc_tit = titulo.construir(titulos, fecha_corte)
    ev_cur, rep_cur, nc_cur = en_curso.construir(titulos, titulo.terminados(titulos), fecha_corte)

    evidencias = pd.concat([ev_tit, ev_cur], ignore_index=True).sort_values(
        ["persona_id", "tipo_id", "evidencia_id"], kind="stable"
    ).reset_index(drop=True)
    validacion = es.validar_evidencias(evidencias, TIPOS, poblacion, fecha_corte, exigir_fecha_inicio=False)

    no_considerados = pd.concat([nc_tit, nc_cur], ignore_index=True).rename(columns={
        "IDPERSONA": "persona_id", "IdTitulacion": "id_titulacion", "Estado": "estado",
        "Nivel": "nivel", "Institucion": "institucion",
    })[["persona_id", "motivo", "estado", "nivel", "institucion", "id_titulacion"]].sort_values("persona_id")

    con_formacion = set(evidencias["persona_id"])
    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_con_trayectoria": len(poblacion),
        "personas_con_formacion": len(con_formacion),
        "personas_sin_evidencia_de_formacion": len(poblacion - con_formacion),
        "evidencias_total": len(evidencias),
        "registros_no_considerados": int(len(no_considerados)),
        "subtipos": {
            titulo.TIPO_ID: {**rep_tit, "personas": int(ev_tit["persona_id"].nunique())},
            en_curso.TIPO_ID: {**rep_cur, "personas": int(ev_cur["persona_id"].nunique())},
        },
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
    ev, rep, val = construir_evidencias_formacion(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
