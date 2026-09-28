"""Subtipo CONTRATO PUNTUAL: actividad acotada dentro de ESPOL que puede coexistir con el
cargo estructural (servicios profesionales, docencia por contrato civil - incluida toda la
docencia de posgrado -, profesor honorario, tribunales, actividad academica de un
administrativo). Son las `pc.CATEGORIAS_PUNTUALES`, excluidas de `tramos_rol` por diseno.

Fuente: `eventos_puntuales_cargo.csv` (salida de `pc.extraer_eventos_puntuales`: un
contrato por fila, ya sin filas de ruido).

Periodos: contratos solapados o separados por un receso de hasta `TOLERANCIA_RECESO_DIAS`
(vacaciones institucionales entre periodos academicos) con la misma categoria + contrato +
unidad + nivel forman un periodo continuo. La fecha fin es la efectiva
(`pc.calcular_fecha_fin_efectiva`). Contratos de un solo dia cuentan para la continuidad,
pero un periodo de un solo dia no es evidencia (DEC-029).

Evidencia (2026-09-27, decision del usuario): una por persona + CONTRATO (texto de `CARGO`)
+ UNIDAD. Los periodos van en `periodos` (inicio, fin, duracion, n_contratos, nivel,
es_paralelo, es_significativo) y arriba una sola vez la unidad, las categorias, los tipos
de empleado, los niveles, el total de contratos y la primera/ultima fecha.

Texto (sin verbos ni "ESPOL"):
- Contratos de servicios (categoria de servicios profesionales, o `CARGO` que solo nombra
  la modalidad): descripcion de la categoria + el detalle especifico que traiga el cargo
  despues del guion, p.ej. "Contrato de servicios profesionales (actividades de
  capacitacion), DIRECCION DE ADMISIONES (ADM)" o "Contrato civil de profesor (posgrado)".
- Contratos de tipo profesor u otra actividad concreta: el texto del contrato con sus
  niveles, p.ej. "PROFESOR INVITADO (grado y posgrado), FACULTAD ... (FCNM)".
"""
from __future__ import annotations

import re

import pandas as pd

from evidencias import esquema as es
from evidencias.trayectoria.fuentes import (
    FuentesTrayectoria, ec, niveles_para_texto, pc, sigla_unidad, texto_cargo_lugar,
    unidad_para_texto,
)

TIPO_ID = "TRAYECTORIA_CONTRATO_PUNTUAL"
PREFIJO_ID = "TRY-PUN"

_NIVEL_DOCENCIA = {"DOCENTE PREGRADO": "GRADO", "DOCENTE POSGRADO": "POSGRADO"}
_CLAVE_PERIODO = ["IDPERSONA", "CATEGORIA_CARGO", "CARGO", "NOMBRE_UNIDAD", "NIVELDOCENCIA"]
TOLERANCIA_RECESO_DIAS = 60
CATEGORIA_SERVICIOS = "CONTRATO_SERVICIOS_PROFESIONALES_PROYECTO"

# CARGO que solo nombra la modalidad del contrato (comparacion sin tildes, en mayusculas).
_PATRON_CARGO_GENERICO = re.compile(
    r"^(PRESTACION (DE )?SERVICIOS( PROFESIONALES| PERSONALES)?|SERVICIOS PROFESIONALES|"
    r"CONTRATAD[OA]|CONTRATISTA|CONTRATO CIVIL|HONORARIOS PROFESIONALES|SERVICIOS VARIOS.*)$"
)
# Detalle despues del guion que no agrega informacion (se omite del texto)
_DETALLES_GENERICOS = {"EJECUCION DE ACTIVIDADES", "EJECUCION DE PROYECTOS"}
# Lo que si se sabe de un contrato de servicios/generico, segun su categoria
_DESCRIPCION_POR_CATEGORIA = {
    "DOCENTE_CONTRATADO_SERVICIOS_CIVILES": "Contrato civil de profesor",
    "DOCENTE_HONORARIO_ESPECIAL": "Contrato de profesor honorario",
    CATEGORIA_SERVICIOS: "Contrato de servicios profesionales",
    "ACTIVIDAD_ACADEMICA_DESDE_ADMINISTRATIVO": "Contrato por actividad académica",
    "TRIBUNAL_COMISION_ACADEMICA": "Contrato para tribunal o comisión académica",
}


def _sin_tildes(s: str) -> str:
    s = pd.Series([s]).str.normalize("NFKD").str.encode("ascii", "ignore").str.decode("ascii").iloc[0]
    return re.sub(r"\s+", " ", s.upper().strip())


def es_contrato_generico(contrato: str | None) -> bool:
    return not contrato or bool(_PATRON_CARGO_GENERICO.match(_sin_tildes(contrato)))


def _descripcion(contrato: str | None, categoria: str, niveles: list[str]) -> str:
    """Parte del texto que describe el contrato (sin la unidad)."""
    if contrato and categoria != CATEGORIA_SERVICIOS and not es_contrato_generico(contrato):
        return contrato + niveles_para_texto(niveles, contrato)  # tipo profesor / actividad concreta
    base = _DESCRIPCION_POR_CATEGORIA.get(categoria, "Contrato")
    detalle = contrato.split(" - ", 1)[1].strip() if contrato and " - " in contrato else None
    if detalle and _sin_tildes(detalle) not in _DETALLES_GENERICOS:
        base += f" ({detalle.lower()})"
    return base + niveles_para_texto(niveles, base)


def _consolidar_periodos(contratos: pd.DataFrame) -> list[dict]:
    periodos = []
    orden = contratos.sort_values([*_CLAVE_PERIODO, "FECHAINICIOCONTRATO"], kind="stable")
    for clave, g in orden.groupby(_CLAVE_PERIODO, dropna=False, sort=False):
        actual = None
        for r in g.itertuples(index=False):
            inicio, fin = r.FECHAINICIOCONTRATO, r.FIN_EFECTIVO
            if actual is not None:
                fin_act = actual["FIN"]
                if pd.isna(fin_act) or (inicio - fin_act).days <= TOLERANCIA_RECESO_DIAS:
                    if pd.isna(fin) or (pd.notna(fin_act) and fin > fin_act):
                        actual["FIN"] = fin
                    actual["N_CONTRATOS"] += 1
                    actual["TIPOEMPLEADO_DESC"] = r.TIPOEMPLEADO_DESC
                    continue
                periodos.append(actual)
            actual = dict(zip(_CLAVE_PERIODO, clave), INICIO=inicio, FIN=fin, N_CONTRATOS=1,
                          TIPOEMPLEADO_DESC=r.TIPOEMPLEADO_DESC)
        periodos.append(actual)
    return periodos


def _marcar_paralelos(p: pd.DataFrame, tramos_rol: pd.DataFrame, fecha_corte) -> pd.Series:
    """True si el periodo se solapa con un cargo estructural o con otro periodo puntual de
    distinto contrato/unidad de la misma persona."""
    p = p.assign(_FIN=p["FIN"].fillna(fecha_corte), _K=p["CARGO"].astype(str) + "|" + p["NOMBRE_UNIDAD"].astype(str))
    est = tramos_rol.assign(_FIN=tramos_rol["TRAMO_FIN"].fillna(fecha_corte))
    est_por_persona = {k: g for k, g in est.groupby("IDPERSONA")}
    resultado = pd.Series(False, index=p.index)
    for idp, g in p.groupby("IDPERSONA"):
        e = est_por_persona.get(idp)
        for idx, r in g.iterrows():
            solapa = e is not None and bool(((e["TRAMO_INICIO"] <= r._FIN) & (e["_FIN"] >= r.INICIO)).any())
            if not solapa:
                otros = g[g["_K"] != r._K]
                solapa = bool(((otros["INICIO"] <= r._FIN) & (otros["_FIN"] >= r.INICIO)).any())
            resultado[idx] = solapa
    return resultado


def construir(fuentes: FuentesTrayectoria, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    fuente = fuentes.eventos_puntuales
    contratos = fuente[fuente["IDPERSONA"].isin(fuentes.poblacion)]
    n_poblacion = len(contratos)
    contratos = contratos.drop_duplicates()
    n_duplicados = n_poblacion - len(contratos)
    contratos = contratos.dropna(subset=["FECHAINICIOCONTRATO"]).copy()
    contratos["FIN_EFECTIVO"] = pc.calcular_fecha_fin_efectiva(contratos)

    p = pd.DataFrame(_consolidar_periodos(contratos))
    n_periodos = len(p)
    un_dia = p["FIN"].notna() & (p["FIN"] == p["INICIO"])
    futuro = p["INICIO"] > fecha_corte
    p = p[~un_dia & ~futuro].copy()
    p["ES_PARALELO"] = _marcar_paralelos(p, fuentes.tramos_rol[fuentes.tramos_rol["IDPERSONA"].isin(fuentes.poblacion)], fecha_corte)
    p["MESES"] = [
        ((fecha_corte if es.es_vigente(f, fecha_corte) else f) - i).days / 30.44 for i, f in zip(p["INICIO"], p["FIN"])
    ]
    p["CONTRATO_K"] = p["CARGO"].map(es.texto_limpio)
    p["UNIDAD_K"] = p["NOMBRE_UNIDAD"].map(es.texto_limpio)
    p["NIVEL_P"] = p["NIVELDOCENCIA"].map(lambda n: _NIVEL_DOCENCIA.get(n) if not es.valor_nulo(n) else None)

    filas = []
    for (idp, contrato, unidad), g in p.groupby(["IDPERSONA", "CONTRATO_K", "UNIDAD_K"], dropna=False, sort=False):
        g = g.sort_values("INICIO")
        contrato, unidad = es.texto_limpio(contrato), es.texto_limpio(unidad)
        sigla = sigla_unidad(unidad, fuentes.mapa_siglas)
        categorias = es.unicos(reversed(g["CATEGORIA_CARGO"].tolist()))
        niveles = es.unicos(g["NIVEL_P"])
        periodos = [
            {
                "inicio": es.fecha_iso(r.INICIO),
                "fin": es.fecha_iso(r.FIN),
                "duracion_anios": es.duracion_anios(r.INICIO, r.FIN, fecha_corte),
                "n_contratos": int(r.N_CONTRATOS),
                "nivel_docencia": r.NIVEL_P,
                "es_paralelo": bool(r.ES_PARALELO),
                "es_significativo": bool(r.MESES >= ec.MIN_MESES_CARGO_SIGNIFICATIVO),
            }
            for r in g.itertuples(index=False)
        ]
        atributos = {
            "contrato": contrato,
            "contrato_generico": es_contrato_generico(contrato),
            "unidad": unidad,
            "unidad_sigla": sigla,
            "categorias": categorias,
            "tipos_empleado": es.unicos(reversed(g["TIPOEMPLEADO_DESC"].tolist())),
            "niveles_docencia": niveles,
            "n_contratos": int(g["N_CONTRATOS"].sum()),
            **es.resumen_periodos(g["INICIO"].tolist(), g["FIN"].tolist(), fecha_corte),
            "periodos": periodos,
            "_origen": {"fuente": "trayectorias/eventos_puntuales_cargo.csv"},
        }
        texto = texto_cargo_lugar(_descripcion(contrato, categorias[0], niveles), unidad_para_texto(unidad, sigla))
        filas.append(es.nueva_evidencia(
            es.generar_evidencia_id(PREFIJO_ID, idp, contrato, unidad), idp, TIPO_ID, texto, atributos,
        ))

    reporte = {
        "fuente": "trayectorias/eventos_puntuales_cargo.csv",
        "filas_fuente_poblacion": n_poblacion,
        "duplicados_exactos_eliminados": n_duplicados,
        "contratos_validos": len(contratos),
        "tolerancia_receso_dias": TOLERANCIA_RECESO_DIAS,
        "periodos_consolidados": n_periodos,
        "periodos_de_un_solo_dia_excluidos": int(un_dia.sum()),
        "periodos_inicio_futuro_excluidos": int((futuro & ~un_dia).sum()),
        "periodos_en_evidencias": len(p),
        "evidencias_con_contrato_generico": sum('"contrato_generico": true' in f["atributos"] for f in filas),
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte
