"""Orquesta la construccion del dataset de evidencias de RECONOCIMIENTOS (menciones de honor).

Uso desde notebook:
    from evidencias.reconocimientos import construir_evidencias_reconocimientos
    evidencias, reporte, validacion = construir_evidencias_reconocimientos(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.reconocimientos.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.reconocimientos import mencion_honor
from evidencias.reconocimientos.fuentes import SALIDA_DIR, cargar_menciones, cargar_poblacion

ARCHIVO_EVIDENCIAS = SALIDA_DIR / "evidencias_menciones_honor.csv"
ARCHIVO_REPORTE = SALIDA_DIR / "reporte_evidencias_menciones_honor.json"
ARCHIVO_NO_CONSIDERADOS = SALIDA_DIR / "registros_no_considerados.csv"
TIPOS = {mencion_honor.TIPO_ID}


def construir_evidencias_reconocimientos(
    guardar: bool = False, fecha_corte: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion)."""
    fecha_corte = fecha_corte or es.hoy()
    poblacion = cargar_poblacion()

    evidencias, rep, no_considerados = mencion_honor.construir(cargar_menciones(poblacion))
    evidencias = evidencias.sort_values(["persona_id", "tipo_id", "evidencia_id"], kind="stable").reset_index(drop=True)
    no_considerados = no_considerados.sort_values("persona_id")
    # Sin fecha de inicio: una mencion es un hecho puntual; sus fechas van en la lista `fechas`
    validacion = es.validar_evidencias(evidencias, TIPOS, poblacion, fecha_corte, exigir_fecha_inicio=False)

    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_con_trayectoria": len(poblacion),
        "tipo_id": mencion_honor.TIPO_ID,
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
    ev, rep, val = construir_evidencias_reconocimientos(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
