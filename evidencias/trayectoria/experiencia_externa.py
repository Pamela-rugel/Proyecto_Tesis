"""Subtipo EXPERIENCIA EXTERNA: experiencia laboral declarada fuera del historial de
contratos de ESPOL.

Fuente: `processed/experiencia_externa.csv`, ya limpia por `pc.limpiar_experiencia_externa`
(notebook 08): sin cargos nulos o de relleno, institucion desconocida como "DESCONOCIDA",
sin registros sin fecha de inicio ni anteriores al nacimiento, sin duplicados exactos y
con los registros solapados del mismo cargo e institucion ya fusionados. Aqui no se repite
ninguna de esas reglas: una fila de la fuente = una evidencia, con ID natural
`IDHISTORIALABORAL` (el menor de los fusionados).

Vigencia: por decision del usuario (2026-09-27) no se etiqueta vigencia en la experiencia
externa. `fecha_fin` (atributo) nula significa solo "sin fecha de salida registrada", y
`duracion_anios` se calcula unicamente cuando hay fecha de fin.

Texto (2026-09-27): "CARGO, INSTITUCION, Pais", sin verbos; el pais solo si es del exterior
(`es_exterior`), y se omite lo que no se conoce.

Columnas no copiadas: `VIGENTE` (vigencia declarada, fuera de alcance por ahora) y los
codigos/duplicados `CATEXPERIENCIA`, `CATEGORIAEXPERIENCIADESCRIPCION`, `ROLACADEMICO`,
`ROLACADEMICOEXPERIENCIA`, `IDPAIS`. Recuperables desde la fuente con
`_origen.idhistorialaboral`.
"""
from __future__ import annotations

import re

import pandas as pd

from evidencias import esquema as es
from evidencias.trayectoria.fuentes import FuentesTrayectoria

TIPO_ID = "TRAYECTORIA_EXPERIENCIA_EXTERNA"
PREFIJO_ID = "TRY-EXT"

# Registros "externos" cuya institucion es la propia ESPOL (no ESPOLTECH/FUNDESPOL/CENAIM,
# que son entidades distintas): no se modifican, solo se marcan como atributo.
_PATRON_ESPOL = re.compile(r"POLIT[EÉ]CNICA DEL LITORAL", re.IGNORECASE)


def _texto(cargo: str, institucion: str | None, pais: str | None, es_exterior: bool) -> str:
    """"CARGO, INSTITUCION, Pais" sin verbos: el pais solo si es del exterior, y se omite lo
    que no se conoce (institucion DESCONOCIDA en la fuente no se inventa)."""
    partes = [cargo, institucion, pais.title() if es_exterior and pais else None]
    return ", ".join(p for p in partes if p)


def construir(fuentes: FuentesTrayectoria, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    fuente = fuentes.experiencia_externa
    x = fuente[fuente["IDPERSONA"].isin(fuentes.poblacion)]
    fusionados = x["IDS_HISTORIALABORAL_FUSIONADOS"].astype(str).str.contains(",") \
        if "IDS_HISTORIALABORAL_FUSIONADOS" in x.columns else pd.Series(False, index=x.index)

    filas = []
    for r in x.itertuples(index=False):
        cargo = es.texto_limpio(r.CARGO)
        institucion = es.texto_limpio(r.INSTITUCION)
        pais = es.texto_limpio(r.PAIS)
        es_exterior = None if pais is None else pais.upper() != "ECUADOR"
        ids_fusionados = str(getattr(r, "IDS_HISTORIALABORAL_FUSIONADOS", r.IDHISTORIALABORAL))
        atributos = {
            "fecha_inicio": es.fecha_iso(r.FECHADESDE),
            "fecha_fin": es.fecha_iso(r.FECHAHASTA),  # null = sin fecha de salida registrada
            "cargo": cargo,
            "institucion": institucion,
            "pais": pais,
            "es_exterior": es_exterior,
            "tipo_institucion": es.texto_limpio(r.TIPOINSTITUCION),
            "relacion_laboral": es.texto_limpio(r.RELACIONLABORAL),
            "tiempo_dedicacion": es.texto_limpio(r.TIEMPODEDICACION),
            "categoria_experiencia": es.texto_limpio(r.CATEXPERIENCIA_DESC),
            "rol_academico": es.texto_limpio(r.ROLACADEMICO_DESC),
            "duracion_anios": None if es.valor_nulo(r.FECHAHASTA)
            else es.duracion_anios(r.FECHADESDE, r.FECHAHASTA, fecha_corte),
            "institucion_es_espol": bool(institucion and _PATRON_ESPOL.search(institucion)),
            "_origen": {
                "fuente": "processed/experiencia_externa.csv",
                "idhistorialaboral": r.IDHISTORIALABORAL,
                "ids_historialaboral_fusionados": [int(i) for i in ids_fusionados.split(",")],
                "ref_evidencia": es.texto_limpio(r.REFEVIDENCIA),
                "ref_evaluaciones": es.texto_limpio(r.REFEVALUACIONES),
            },
        }
        filas.append(es.nueva_evidencia(
            f"{PREFIJO_ID}-{int(r.IDHISTORIALABORAL)}",
            r.IDPERSONA, TIPO_ID,
            _texto(cargo or "cargo sin especificar", institucion, pais, bool(es_exterior)),
            atributos,
        ))

    reporte = {
        "fuente": "processed/experiencia_externa.csv (limpieza en notebook 08)",
        "filas_fuente_poblacion": len(x),
        "registros_resultado_de_fusion": int(fusionados.sum()),
        "institucion_desconocida": int(x["INSTITUCION"].map(es.texto_limpio).isna().sum()),
        "sin_fecha_fin": int(x["FECHAHASTA"].isna().sum()),
        "institucion_es_espol": int(x["INSTITUCION"].fillna("").str.contains(_PATRON_ESPOL).sum()),
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte
