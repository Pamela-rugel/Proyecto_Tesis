"""Evidencias individuales de la seccion INVESTIGACION Y PRODUCCION ACADEMICA.

- proyecto_investigacion.py -> PROYECTO_INVESTIGACION
- proyecto_vinculacion.py   -> PROYECTO_VINCULACION
- publicacion.py            -> PUBLICACION
- tesis_dirigida.py         -> TESIS_DIRIGIDA
- ponencia.py               -> PONENCIA

Todos producen el esquema comun de `evidencias/esquema.py`; `construir.py` los orquesta.
"""


def construir_evidencias_investigacion(*args, **kwargs):
    from evidencias.investigacion.construir import construir_evidencias_investigacion as _f
    return _f(*args, **kwargs)
