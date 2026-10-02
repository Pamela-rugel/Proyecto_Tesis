"""Subtipo CERTIFICACION: certificaciones acreditadas (`certificados_todos.csv`), p. ej.
operador SERCOP, CISCO, CertiProf, auditor ISO, LinkedIn Learning.

Reglas en `comun.py`. Propias de este tipo:
- Sin tipo de evento en el texto (todas son certificacion).
- `vigente` = `fecha_fin` aun no llega. En muchas certificaciones `fecha_fin` es el
  VENCIMIENTO (SERCOP: 2 anios); en otras es solo el fin del curso, asi que `vigente: false`
  significa "la fecha de fin ya paso", no necesariamente "vencida".
"""
from __future__ import annotations

import pandas as pd

from evidencias.capacitacion import comun

TIPO_ID = "CERTIFICACION"
PREFIJO_ID = "CAP-CER"
FUENTE = "processed/certificados_todos.csv"


def preparar(certificados: pd.DataFrame, fecha_corte: pd.Timestamp) -> pd.DataFrame:
    return comun.preparar(certificados, fecha_corte)


def construir(d: pd.DataFrame, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """`d` = salida de `preparar`."""
    return comun.construir(d, tipo_id=TIPO_ID, prefijo_id=PREFIJO_ID, fuente=FUENTE,
                           con_tipo_evento=False, con_vigencia=True,
                           fecha_corte=fecha_corte)
