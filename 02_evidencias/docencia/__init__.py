"""Evidencias individuales de la seccion DOCENCIA:

- materia.py -> DOCENCIA_MATERIA (materias dictadas, carga academica)

Produce el esquema comun de `evidencias/esquema.py`; `construir.py` lo orquesta.
"""


def construir_evidencias_docencia(*args, **kwargs):
    from evidencias.docencia.construir import construir_evidencias_docencia as _f
    return _f(*args, **kwargs)
