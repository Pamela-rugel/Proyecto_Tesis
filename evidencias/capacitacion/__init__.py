"""Evidencias individuales de la seccion CAPACITACION Y CERTIFICACION.

- capacitacion.py  -> CAPACITACION  (cursos, talleres, seminarios, congresos como asistente...)
- certificacion.py -> CERTIFICACION (certificaciones acreditadas: SERCOP, CISCO, ISO...)

Reglas comunes en `comun.py`; todos producen el esquema de `evidencias/esquema.py` y
`construir.py` los orquesta.
"""


def construir_evidencias_capacitacion(*args, **kwargs):
    from evidencias.capacitacion.construir import construir_evidencias_capacitacion as _f
    return _f(*args, **kwargs)
