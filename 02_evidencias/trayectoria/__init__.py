"""Evidencias individuales de la seccion TRAYECTORIA (4 subtipos, un modulo cada uno):

- cargo_estructural.py   -> TRAYECTORIA_CARGO_ESTRUCTURAL
- contrato_puntual.py    -> TRAYECTORIA_CONTRATO_PUNTUAL
- funcion_adicional.py   -> TRAYECTORIA_FUNCION_ADICIONAL (incluye subrogaciones)
- experiencia_externa.py -> TRAYECTORIA_EXPERIENCIA_EXTERNA

Todos producen el esquema comun de `evidencias/esquema.py`; `construir.py` los orquesta.
"""


def construir_evidencias_trayectoria(*args, **kwargs):
    from evidencias.trayectoria.construir import construir_evidencias_trayectoria as _f
    return _f(*args, **kwargs)
