"""Evidencias individuales de la seccion FORMACION ACADEMICA (2 subtipos):

- titulo.py   -> FORMACION_TITULO   (titulos obtenidos)
- en_curso.py -> FORMACION_EN_CURSO (estudios no terminados)

Todos producen el esquema comun de `evidencias/esquema.py`; `construir.py` los orquesta.
"""


def construir_evidencias_formacion(*args, **kwargs):
    from evidencias.formacion.construir import construir_evidencias_formacion as _f
    return _f(*args, **kwargs)
