"""Evidencias individuales de la seccion RECONOCIMIENTOS (1 subtipo):

- mencion_honor.py -> MENCION_HONOR (menciones, premios, distinciones, becas y demas
  reconocimientos declarados)

Produce el esquema comun de `evidencias/esquema.py`; `construir.py` lo orquesta.
"""


def construir_evidencias_reconocimientos(*args, **kwargs):
    from evidencias.reconocimientos.construir import construir_evidencias_reconocimientos as _f
    return _f(*args, **kwargs)
