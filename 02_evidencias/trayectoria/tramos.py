"""Consolidacion de tramos de cargo + unidad por persona.

Movido desde `notebooks/07_embeddings/_embeddings_comun.py` (2026-09-30, limpieza del proyecto:
el clustering y la busqueda semantica ahora se hacen sobre evidencias y esa carpeta se
elimino). Es la misma logica, sin cambios, que ya usaban las evidencias de trayectoria.
"""
from __future__ import annotations

import pandas as pd

# Duracion minima, en meses, para que un cargo cuente como "significativo". Un cargo por
# debajo del umbral sigue siendo evidencia; el umbral solo marca `es_significativo`.
MIN_MESES_CARGO_SIGNIFICATIVO = 3

# Tolerancia de receso (dias) para consolidar dos tramos consecutivos del MISMO cargo + unidad
# separados por una brecha corta (contratacion docente por periodo academico: `tramos_rol.csv`
# solo fusiona por CATEGORIA_CARGO, asi que un "Profesor Pregrado" con 22 tramos semestrales
# del mismo cargo y unidad apareceria como 22 cargos distintos si no se consolida aqui).
TOLERANCIA_RECESO_DIAS_CARGO = 90


def _meses_entre(inicio, fin) -> float:
    """Duracion en meses (30.44 dias/mes). `fin` NaT (tramo vigente) = hoy."""
    fin_efectivo = pd.Timestamp.today().normalize() if pd.isna(fin) else fin
    return (fin_efectivo - inicio).days / 30.44


def _consolidar_tramos_cargo_unidad(tramos_persona: pd.DataFrame) -> pd.DataFrame:
    """Consolida, dentro de los tramos de UNA persona, los que representan el MISMO cargo real:
    mismo `CARGO_TRAMO` + mismo `UNIDAD_TRAMO` + continuos o separados solo por un receso corto
    (`TOLERANCIA_RECESO_DIAS_CARGO`).
    - mismo cargo + misma unidad + consecutivos/solapados/receso corto -> un solo tramo;
    - mismo cargo + distinta unidad -> no se consolidan (cambio de unidad);
    - distinto cargo -> no se consolidan (cambio de cargo).

    Rastreo en paralelo por clave (cargo, unidad): un cargo largo interrumpido en la linea de
    tiempo por otro cargo intercalado (p.ej. una coordinacion breve en medio de 10 anios de
    "Profesor Pregrado") se retoma cuando vuelve a aparecer, en vez de cortarse para siempre.

    Devuelve una fila por tramo consolidado: CARGO, UNIDAD, INICIO, FIN (NaT si vigente),
    CATEGORIA_CARGO (del tramo mas reciente del grupo) y N_TRAMOS_ORIGEN."""
    columnas = ["CARGO", "UNIDAD", "INICIO", "FIN", "CATEGORIA_CARGO", "N_TRAMOS_ORIGEN"]
    if tramos_persona.empty:
        return pd.DataFrame(columns=columnas)

    filas = tramos_persona.sort_values("TRAMO_INICIO").to_dict("records")
    abiertos_por_clave: dict[tuple, dict] = {}
    cerrados: list[dict] = []
    for r in filas:
        cargo = str(r["CARGO_TRAMO"]).strip() if pd.notna(r["CARGO_TRAMO"]) else ""
        unidad = str(r["UNIDAD_TRAMO"]).strip() if pd.notna(r["UNIDAD_TRAMO"]) else ""
        inicio, fin = r["TRAMO_INICIO"], r["TRAMO_FIN"]
        clave = (cargo, unidad)
        actual = abiertos_por_clave.get(clave)

        continua = False
        if actual is not None:
            if pd.isna(actual["FIN"]):
                # grupo abierto de esta clave ya vigente: cualquier tramo posterior de la
                # misma clave es una continuacion
                continua = True
            else:
                gap_dias = (inicio - actual["FIN"]).days
                continua = gap_dias <= 0 or gap_dias <= TOLERANCIA_RECESO_DIAS_CARGO

        if continua:
            if pd.isna(fin) or (pd.notna(actual["FIN"]) and fin > actual["FIN"]):
                actual["FIN"] = fin
            actual["CATEGORIA_CARGO"] = r["CATEGORIA_CARGO"]  # el mas reciente del grupo
            actual["N_TRAMOS_ORIGEN"] += 1
            continue

        # No continua: el grupo abierto de esta clave se cierra y se abre uno nuevo
        if actual is not None:
            cerrados.append(actual)
        abiertos_por_clave[clave] = {
            "CARGO": cargo, "UNIDAD": unidad, "INICIO": inicio, "FIN": fin,
            "CATEGORIA_CARGO": r["CATEGORIA_CARGO"], "N_TRAMOS_ORIGEN": 1,
        }

    cerrados.extend(abiertos_por_clave.values())
    if not cerrados:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(cerrados)[columnas].sort_values("INICIO").reset_index(drop=True)


def construir_tramos_cargo_unidad_persona(
    tramos_rol: pd.DataFrame,
    poblacion: set[int] | None = None,
) -> pd.DataFrame:
    """Una fila por tramo consolidado (cargo + unidad) por persona.

    Devuelve: IDPERSONA, CARGO, UNIDAD, INICIO, FIN (NaT si vigente), DURACION_ANIOS,
    ES_SIGNIFICATIVO (segun MIN_MESES_CARGO_SIGNIFICATIVO) y ES_PARALELO (el tramo se solapa en
    fecha con otro tramo consolidado distinto de la misma persona)."""
    ids = poblacion if poblacion is not None else set(tramos_rol["IDPERSONA"].unique())
    columnas = ["IDPERSONA", "CARGO", "UNIDAD", "INICIO", "FIN", "DURACION_ANIOS", "ES_SIGNIFICATIVO", "ES_PARALELO"]

    filas = []
    for idp, grupo in tramos_rol[tramos_rol["IDPERSONA"].isin(ids)].groupby("IDPERSONA", sort=False):
        consolidados = _consolidar_tramos_cargo_unidad(grupo)
        if consolidados.empty:
            continue
        t = consolidados.copy()
        t["DURACION_MESES"] = t.apply(lambda r: _meses_entre(r["INICIO"], r["FIN"]), axis=1)
        t["DURACION_ANIOS"] = round(t["DURACION_MESES"] / 12, 2)
        t["ES_SIGNIFICATIVO"] = t["DURACION_MESES"] >= MIN_MESES_CARGO_SIGNIFICATIVO

        fin_cmp = t["FIN"].fillna(pd.Timestamp.today().normalize())
        es_paralelo = []
        for i in range(len(t)):
            solapa_con_otro = False
            for j in range(len(t)):
                if i == j:
                    continue
                if t["INICIO"].iloc[i] <= fin_cmp.iloc[j] and t["INICIO"].iloc[j] <= fin_cmp.iloc[i]:
                    solapa_con_otro = True
                    break
            es_paralelo.append(solapa_con_otro)
        t["ES_PARALELO"] = es_paralelo
        t["IDPERSONA"] = idp
        filas.append(t[columnas])

    if not filas:
        return pd.DataFrame(columns=columnas)
    return pd.concat(filas, ignore_index=True).sort_values(["IDPERSONA", "INICIO"]).reset_index(drop=True)
