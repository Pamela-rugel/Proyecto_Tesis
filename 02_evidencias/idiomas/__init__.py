"""Evidencias individuales de la seccion IDIOMAS (1 subtipo):

- idioma.py -> IDIOMA (un idioma que la persona declara, con sus niveles)

Produce el esquema comun de `evidencias/esquema.py`; `construir.py` lo orquesta.
"""


def construir_evidencias_idiomas(*args, **kwargs):
    from evidencias.idiomas.construir import construir_evidencias_idiomas as _f
    return _f(*args, **kwargs)
