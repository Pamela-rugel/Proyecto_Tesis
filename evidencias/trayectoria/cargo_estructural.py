"""Subtipo CARGO ESTRUCTURAL: el rol principal continuo de la persona dentro de ESPOL.

Fuente: `tramos_rol.csv` (contratos de categorias NO puntuales, sin ruido, ya fusionados
por CATEGORIA_CARGO en 04_trayectorias), re-consolidado por cargo real + unidad con
tolerancia de receso de 90 dias mediante `ec.construir_tramos_cargo_unidad_persona` (la
misma funcion que genera `data/embeddings/tramos_cargo_unidad_persona.csv`). Cada tramo
consolidado es un PERIODO continuo.

Evidencia (2026-09-27, decision del usuario): una por persona + CARGO + UNIDAD. Si la
persona ocupo el mismo cargo en la misma unidad con saltos, los periodos se listan en
`periodos` (inicio, fin, duracion, es_paralelo, es_significativo, nivel) y arriba van una
sola vez la unidad, las categorias, los tipos de empleado, los niveles, el total de
contratos, la primera fecha de inicio y la ultima de fin (null si algun periodo sigue
abierto). El mismo cargo en otra unidad es otra evidencia.

`categoria_cargo`, `tipo_empleado`, nivel y `n_contratos` no estan en el tramo consolidado:
se recuperan de las filas de `tramos_rol` que lo componen (mismo cargo + unidad, con
inicio dentro del periodo).

Texto: "CARGO (niveles), UNIDAD (SIGLA)" - sin verbos ni "ESPOL", omitiendo lo que no se
conoce.
"""
from __future__ import annotations

import pandas as pd

from evidencias import esquema as es
from evidencias.trayectoria.fuentes import (
    FuentesTrayectoria, ec, niveles_para_texto, sigla_unidad, texto_cargo_lugar, unidad_para_texto,
)

TIPO_ID = "TRAYECTORIA_CARGO_ESTRUCTURAL"
PREFIJO_ID = "TRY-EST"

_NIVEL_DOCENCIA = {"DOCENTE PREGRADO": "GRADO", "DOCENTE POSGRADO": "POSGRADO"}


def _componentes_por_tramo(tramos: pd.DataFrame, tramos_rol: pd.DataFrame, fecha_corte) -> pd.DataFrame:
    tr = tramos_rol.copy()
    tr["CARGO"] = tr["CARGO_TRAMO"].fillna("").astype(str).str.strip()
    tr["UNIDAD"] = tr["UNIDAD_TRAMO"].fillna("").astype(str).str.strip()
    cols_extra = [c for c in ("NIVELDOCENCIA_TRAMO",) if c in tr.columns]

    base = tramos.reset_index().rename(columns={"index": "_IDX"})
    # max con INICIO: un tramo con fechas invertidas en la fuente (fin < inicio) sigue
    # encontrando su propia fila de tramos_rol (la que empieza exactamente en INICIO)
    base["_FIN_CMP"] = base["FIN"].fillna(fecha_corte).where(
        base["FIN"].isna() | (base["FIN"] >= base["INICIO"]), base["INICIO"]
    )
    m = base[["_IDX", "IDPERSONA", "CARGO", "UNIDAD", "INICIO", "_FIN_CMP"]].merge(
        tr[["IDPERSONA", "CARGO", "UNIDAD", "TRAMO_INICIO", "N_CONTRATOS",
            "CATEGORIA_CARGO", "TIPOEMPLEADO_DESC", *cols_extra]],
        on=["IDPERSONA", "CARGO", "UNIDAD"],
    )
    m = m[(m["TRAMO_INICIO"] >= m["INICIO"]) & (m["TRAMO_INICIO"] <= m["_FIN_CMP"])]
    m = m.sort_values(["_IDX", "TRAMO_INICIO"])
    agg = {
        "N_CONTRATOS": ("N_CONTRATOS", "sum"),
        "N_TRAMOS_ROL": ("TRAMO_INICIO", "size"),
        "CATEGORIA_CARGO": ("CATEGORIA_CARGO", "last"),
        "TIPOEMPLEADO_DESC": ("TIPOEMPLEADO_DESC", "last"),
    }
    if cols_extra:
        agg["NIVELDOCENCIA_TRAMO"] = ("NIVELDOCENCIA_TRAMO", "last")
    return m.groupby("_IDX").agg(**agg)


def construir(fuentes: FuentesTrayectoria, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    tramos_rol = fuentes.tramos_rol[fuentes.tramos_rol["IDPERSONA"].isin(fuentes.poblacion)]
    tramos = ec.construir_tramos_cargo_unidad_persona(tramos_rol, fuentes.poblacion)
    tramos = tramos.join(_componentes_por_tramo(tramos, tramos_rol, fecha_corte))
    n_consolidados = len(tramos)

    # Periodo de un solo dia (todos sus tramos son de un dia, marcados como ruido con
    # ES_TRAMO_UN_DIA en 04_trayectorias): no es evidencia (DEC-029).
    un_dia = tramos["FIN"].notna() & (tramos["FIN"] == tramos["INICIO"])
    futuro = tramos["INICIO"] > fecha_corte
    tramos = tramos[~un_dia & ~futuro].copy()
    tramos["_CARGO"] = tramos["CARGO"].map(es.texto_limpio).fillna("cargo sin especificar")
    tramos["_UNIDAD"] = tramos["UNIDAD"].map(es.texto_limpio)

    filas = []
    for (idp, cargo, unidad), g in tramos.groupby(["IDPERSONA", "_CARGO", "_UNIDAD"], dropna=False, sort=False):
        g = g.sort_values("INICIO")
        unidad = es.texto_limpio(unidad)
        sigla = sigla_unidad(unidad, fuentes.mapa_siglas)
        niveles_periodo = [
            _NIVEL_DOCENCIA.get(n) if not es.valor_nulo(n) else None
            for n in (g["NIVELDOCENCIA_TRAMO"] if "NIVELDOCENCIA_TRAMO" in g else [None] * len(g))
        ]
        niveles = es.unicos(niveles_periodo)
        periodos = [
            {
                "inicio": es.fecha_iso(r.INICIO),
                "fin": es.fecha_iso(r.FIN),
                "duracion_anios": es.duracion_anios(r.INICIO, r.FIN, fecha_corte),
                "es_paralelo": bool(r.ES_PARALELO),
                "es_significativo": bool(r.ES_SIGNIFICATIVO),
                "nivel_docencia": nivel,
            }
            for r, nivel in zip(g.itertuples(index=False), niveles_periodo)
        ]
        atributos = {
            "cargo": cargo,
            "unidad": unidad,
            "unidad_sigla": sigla,
            "categorias_cargo": es.unicos(reversed(g["CATEGORIA_CARGO"].tolist())),
            "tipos_empleado": es.unicos(reversed(g["TIPOEMPLEADO_DESC"].tolist())),
            "niveles_docencia": niveles,
            "n_contratos": int(g["N_CONTRATOS"].sum()),
            **es.resumen_periodos(g["INICIO"].tolist(), g["FIN"].tolist(), fecha_corte),
            "periodos": periodos,
            "_origen": {
                "fuente": "trayectorias/tramos_rol.csv (consolidado cargo+unidad, receso <=90 dias)",
                "n_tramos_rol": int(g["N_TRAMOS_ROL"].sum()),
            },
        }
        texto = texto_cargo_lugar(cargo + niveles_para_texto(niveles, cargo), unidad_para_texto(unidad, sigla))
        filas.append(es.nueva_evidencia(
            es.generar_evidencia_id(PREFIJO_ID, idp, cargo, unidad), idp, TIPO_ID, texto, atributos,
        ))

    reporte = {
        "fuente": "trayectorias/tramos_rol.csv",
        "filas_fuente_poblacion": len(tramos_rol),
        "periodos_consolidados": n_consolidados,
        "periodos_de_un_solo_dia_excluidos": int(un_dia.sum()),
        "periodos_inicio_futuro_excluidos": int((futuro & ~un_dia).sum()),
        "periodos_en_evidencias": len(tramos),
        "columna_NIVELDOCENCIA_TRAMO_disponible": "NIVELDOCENCIA_TRAMO" in fuentes.tramos_rol.columns,
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte
