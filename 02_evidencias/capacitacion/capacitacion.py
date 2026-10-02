"""Subtipo CAPACITACION: cursos, talleres, seminarios, charlas, congresos como asistente,
pasantias y demas eventos de formacion continua (`capacitaciones_todas.csv`).

Reglas en `comun.py`. Propias de este tipo:
- El tipo de evento va al texto ("Tipo: Curso"); "OTROS" no se escribe.
- La asistencia SI es capacitacion: se conservan asistencias y aprobaciones
  (`tipos_certificado`).
- Lo que ya es evidencia de PONENCIA o CERTIFICACION (misma persona + nombre + fecha de
  inicio) no se repite aqui.
"""
from __future__ import annotations

import pandas as pd

from evidencias.capacitacion import comun

TIPO_ID = "CAPACITACION"
PREFIJO_ID = "CAP-CUR"
FUENTE = "processed/capacitaciones_todas.csv"
MOTIVO_YA_PONENCIA = "ya registrado como ponencia"
MOTIVO_YA_CERTIFICACION = "ya registrado como certificación"


def construir(capacitaciones: pd.DataFrame, ya_ponencia: set[tuple], ya_certificacion: set[tuple],
              fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    ya = {k: MOTIVO_YA_CERTIFICACION for k in ya_certificacion}
    ya.update({k: MOTIVO_YA_PONENCIA for k in ya_ponencia})
    d = comun.preparar(capacitaciones, fecha_corte, ya)
    return comun.construir(d, tipo_id=TIPO_ID, prefijo_id=PREFIJO_ID, fuente=FUENTE,
                           con_tipo_evento=True, con_vigencia=False,
                           fecha_corte=fecha_corte)
