"""Subtipo FORMACION_TITULO: titulos obtenidos.

Reglas (decisiones del usuario, 2026-09-28):
- Terminado = `Estado == "Graduado"`, o `Estado` vacio (54 registros, todos de
  bachillerato: se asumen terminados).
- Un titulo graduado SIN nombre de titulo no genera evidencia; queda listado en
  `registros_no_considerados.csv` para revisarlo despues.
- Duplicados: ver `comun.fusionar_duplicados` (titulo casi identico + misma institucion).
- Nivel mostrado por persona: si tiene tercer o cuarto nivel, SOLO esos; si no, sus
  bachilleratos; si tampoco, su primaria.
"""
from __future__ import annotations

import pandas as pd

from evidencias import esquema as es
from evidencias.formacion import comun

TIPO_ID = "FORMACION_TITULO"
PREFIJO_ID = "FOR-TIT"
MOTIVO_SIN_TITULO = "título graduado sin nombre del título"


def _nivel_a_mostrar(niveles: set[str]) -> set[str]:
    if niveles & {"TERCER NIVEL", "CUARTO NIVEL"}:
        return {"TERCER NIVEL", "CUARTO NIVEL"}
    if "BACHILLERATO" in niveles:
        return {"BACHILLERATO"}
    return {"PRIMARIA"}


def terminados(titulos: pd.DataFrame) -> pd.DataFrame:
    return titulos[(titulos["Estado"] == "Graduado") | titulos["Estado"].isna()]


def construir(titulos: pd.DataFrame, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    t = terminados(titulos)
    n_terminados = len(t)
    sin_nombre = t["Titulo"].map(comun.limpiar).isna()
    no_considerados = t[sin_nombre].assign(motivo=MOTIVO_SIN_TITULO)
    t = t[~sin_nombre]
    t, n_fusionados = comun.fusionar_duplicados(t)

    mostrar = t.groupby("IDPERSONA")["Nivel"].transform(lambda s: s.isin(_nivel_a_mostrar(set(s))))
    excluidos_nivel = t[~mostrar]
    t = t[mostrar]

    filas = [comun.nueva_evidencia(r, TIPO_ID, PREFIJO_ID, None, fecha_corte) for _, r in t.iterrows()]
    reporte = {
        "registros_terminados": n_terminados,
        "estado_vacio_asumido_terminado": int(titulos["Estado"].isna().sum()),
        "sin_nombre_de_titulo_no_considerados": int(sin_nombre.sum()),
        "duplicados_fusionados": n_fusionados,
        "no_mostrados_por_tener_nivel_superior": int(len(excluidos_nivel)),
        "no_mostrados_por_nivel": excluidos_nivel["Nivel"].value_counts().to_dict(),
        "evidencias_por_nivel": t["Nivel"].value_counts().to_dict(),
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
