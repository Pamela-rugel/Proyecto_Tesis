"""Evidencias individuales de la seccion INVESTIGACION Y PRODUCCION ACADEMICA.

- proyecto_investigacion.py -> PROYECTO_INVESTIGACION
(pendientes: PROYECTO_VINCULACION, PUBLICACION, TESIS_DIRIGIDA, PONENCIA)

Todos producen el esquema comun de `evidencias/esquema.py`; `construir.py` los orquesta.
"""


def construir_evidencias_investigacion(*args, **kwargs):
    from evidencias.investigacion.construir import construir_evidencias_investigacion as _f
    return _f(*args, **kwargs)
