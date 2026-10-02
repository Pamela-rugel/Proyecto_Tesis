"""Subtipo FORMACION_EN_CURSO: estudios no terminados (decision del usuario, 2026-09-28).

Estados: Cursando, Egresado, En proceso de Graduacion, A Prueba. El estado va en el texto
("... (cursando)") y en `atributos.estado`; `fecha_fin` normalmente es null (sin graduacion).

- Sin nombre de titulo: no genera evidencia; queda en `registros_no_considerados.csv`.
- Duplicados: ver `comun.fusionar_duplicados`.
- Si la persona ya tiene ese mismo titulo como terminado, el registro en curso es un dato
  desactualizado del mismo estudio y no se agrega como evidencia.
"""
from __future__ import annotations

import pandas as pd

from evidencias import esquema as es
from evidencias.formacion import comun

TIPO_ID = "FORMACION_EN_CURSO"
PREFIJO_ID = "FOR-CUR"
ESTADOS_EN_CURSO = {"Cursando", "Egresado", "En proceso de Graduación", "A Prueba"}
MOTIVO_SIN_TITULO = "estudio en curso sin nombre del título"


def construir(titulos: pd.DataFrame, terminados: pd.DataFrame,
              fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    c = titulos[titulos["Estado"].isin(ESTADOS_EN_CURSO)]
    sin_nombre = c["Titulo"].map(comun.limpiar).isna()
    no_considerados = c[sin_nombre].assign(motivo=MOTIVO_SIN_TITULO)
    c = c[~sin_nombre]
    c, n_fusionados = comun.fusionar_duplicados(c)

    obtenidos = terminados.dropna(subset=["Titulo"]).groupby("IDPERSONA")["Titulo"].apply(list).to_dict()
    ya_obtenido = c.apply(
        lambda r: any(comun.mismo_titulo(r["Titulo"], t) for t in obtenidos.get(r["IDPERSONA"], [])), axis=1
    ) if len(c) else pd.Series(dtype=bool)
    c = c[~ya_obtenido] if len(c) else c

    filas = [comun.nueva_evidencia(r, TIPO_ID, PREFIJO_ID, r["Estado"], fecha_corte) for _, r in c.iterrows()]
    reporte = {
        "registros_en_curso": int(len(titulos[titulos["Estado"].isin(ESTADOS_EN_CURSO)])),
        "sin_nombre_de_titulo_no_considerados": int(sin_nombre.sum()),
        "duplicados_fusionados": n_fusionados,
        "ya_obtenido_como_titulo": int(ya_obtenido.sum()) if len(ya_obtenido) else 0,
        "evidencias_por_estado": c["Estado"].value_counts().to_dict() if len(c) else {},
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
