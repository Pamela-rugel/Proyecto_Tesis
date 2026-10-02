"""Orquesta la construccion del dataset de evidencias de IDIOMAS.

Uso desde notebook:
    from evidencias.idiomas import construir_evidencias_idiomas
    evidencias, reporte, validacion = construir_evidencias_idiomas(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.idiomas.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.idiomas import idioma
from evidencias.idiomas.fuentes import SALIDA_DIR, cargar_idiomas, cargar_poblacion

ARCHIVO_EVIDENCIAS = SALIDA_DIR / "evidencias_idiomas.csv"
ARCHIVO_REPORTE = SALIDA_DIR / "reporte_evidencias_idiomas.json"
ARCHIVO_NO_CONSIDERADOS = SALIDA_DIR / "registros_no_considerados.csv"
TIPOS = {idioma.TIPO_ID}


def construir_evidencias_idiomas(
    guardar: bool = False, fecha_corte: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion)."""
    fecha_corte = fecha_corte or es.hoy()
    poblacion = cargar_poblacion()

    evidencias, rep, nc = idioma.construir(cargar_idiomas(poblacion))
    evidencias = evidencias.sort_values(["persona_id", "tipo_id", "evidencia_id"], kind="stable").reset_index(drop=True)
    # Sin fechas: la fuente no dice desde cuando se sabe el idioma
    validacion = es.validar_evidencias(evidencias, TIPOS, poblacion, fecha_corte, exigir_fecha_inicio=False)

    no_considerados = nc.assign(
        tipo_id=idioma.TIPO_ID,
        descripcion=nc["IDIOMA"].where(nc["IDIOMA"] != "OTRO", "OTRO: " + nc["DESCRIPCION"].fillna("")),
    ).rename(columns={"IDPERSONA": "persona_id", "IDIDIOMAPERSONA": "id_origen"})[
        ["persona_id", "tipo_id", "motivo", "id_origen", "descripcion"]
    ].sort_values("persona_id")

    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_con_trayectoria": len(poblacion),
        "tipo_id": idioma.TIPO_ID,
        "personas": int(evidencias["persona_id"].nunique()),
        **rep,
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
    ev, rep, val = construir_evidencias_idiomas(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
