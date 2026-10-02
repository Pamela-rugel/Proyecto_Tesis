"""Búsqueda semántica de personas a partir de sus evidencias (ver DISENO.md e IMPLEMENTACION.md).

Uso:
    from busqueda import buscar
    resultado = buscar("experiencia en visión artificial", vigencia="vigentes")

    python -m busqueda.buscar "consulta"          # desde la raíz del proyecto
"""
from __future__ import annotations


def buscar(*args, **kwargs):
    from busqueda.buscar import buscar as _buscar

    return _buscar(*args, **kwargs)
