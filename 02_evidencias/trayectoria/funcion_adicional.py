"""Subtipo FUNCION ADICIONAL / SUBROGACION: designaciones del registro de autoridades
(director, decano, miembro de consejo, coordinaciones, subrogaciones).

Fuente: `funciones_adicionales_persona.csv` (salida de `pc.procesar_registro_autoridades`),
una designacion por fila. Filtros (mismos que `pc.construir_eventos_trayectoria`, mas los
de DEC-029):

- excluidas por calidad: `ES_REPRESENTANTE_ESTUDIANTIL`, `ES_RUIDO_CALIDAD_DATOS`,
  `ES_DUPLICADO_EXACTO` y `ES_DESIGNACION_UN_DIA` (designacion de un dia que no es
  subrogacion; las subrogaciones de un dia se conservan);
- excluidas por duplicar otra evidencia: `ES_COINCIDENTE_CONTRATO=True` (la designacion
  coincide con un contrato del mismo cargo, que ya es una evidencia de cargo estructural).
  `incluir_coincidentes=True` las conserva;
- designaciones que todavia no empiezan (inicio futuro).

Evidencia (2026-09-27, decision del usuario): una por persona + tipo de funcion + unidad
(p.ej. "Decano" en la FCNM). En subrogaciones, una por persona + rol subrogado + unidad
(p.ej. subrogante de Decano en la FCNM). Cada designacion es un periodo en `periodos`.

Regla de negocio (DEC-025): una designacion con nivel conocido (coordinacion de carrera o
de programa de posgrado, etc.) es un cargo de dedicacion continua; se marca con
`tratado_como_cargo` y la carrera/programa de cada periodo va en `detalle_nivel`.

Texto (sin verbos ni "ESPOL"): "FUNCION (carreras), UNIDAD (SIGLA)"; en subrogaciones
"ROL (subrogación), UNIDAD (SIGLA)".
"""
from __future__ import annotations

import pandas as pd

from evidencias import esquema as es
from evidencias.trayectoria.fuentes import (
    FuentesTrayectoria, pc, sigla_unidad, texto_cargo_lugar, unidad_para_texto,
)

TIPO_ID = "TRAYECTORIA_FUNCION_ADICIONAL"
PREFIJO_ID = "TRY-FUN"

_CLAVE_DUPLICADO = ["IDPERSONA", "FUNCION_ADICIONAL", "ROL_SUBROGADO", "UNIDAD_FUNCION",
                    "FECHA_DESDE", "FECHA_HASTA"]
_FLAGS_RUIDO = ["ES_REPRESENTANTE_ESTUDIANTIL", "ES_RUIDO_CALIDAD_DATOS", "ES_DUPLICADO_EXACTO",
                "ES_DESIGNACION_UN_DIA"]


def _descripcion(funcion: str, es_subrogacion: bool, carreras: list[str]) -> str:
    if es_subrogacion:
        return f"{funcion} (subrogación)"
    return f"{funcion} ({'; '.join(carreras)})" if carreras else funcion


def construir(fuentes: FuentesTrayectoria, fecha_corte: pd.Timestamp,
              incluir_coincidentes: bool = False) -> tuple[pd.DataFrame, dict]:
    fuente = fuentes.funciones_adicionales
    f = fuente[fuente["IDPERSONA"].isin(fuentes.poblacion)]
    reporte = {"fuente": "trayectorias/funciones_adicionales_persona.csv",
               "filas_fuente_poblacion": len(f)}

    for flag in (fl for fl in _FLAGS_RUIDO if fl in f.columns):
        reporte[f"excluidas_{flag.lower()}"] = int(f[flag].astype(bool).sum())
        f = f[~f[flag].astype(bool)]
    coincidentes = f["ES_COINCIDENTE_CONTRATO"] == True  # noqa: E712 (nulo no cuenta)
    reporte["coincidentes_con_contrato"] = int(coincidentes.sum())
    reporte["coincidentes_incluidas"] = incluir_coincidentes
    if not incluir_coincidentes:
        f = f[~coincidentes]
    n_antes = len(f)
    f = f.drop_duplicates(subset=_CLAVE_DUPLICADO)
    reporte["duplicados_misma_designacion_y_fechas_eliminados"] = n_antes - len(f)
    f = f.dropna(subset=["FECHA_DESDE"])
    futuro = f["FECHA_DESDE"] > fecha_corte
    reporte["excluidas_inicio_futuro"] = int(futuro.sum())
    f = f[~futuro].copy()

    f["_SUB"] = f["ES_SUBROGACION"].astype(bool)
    f["_FUNCION"] = [
        es.texto_limpio(r if s else fa) or "función sin especificar"
        for r, fa, s in zip(f["ROL_SUBROGADO"], f["FUNCION_ADICIONAL"], f["_SUB"])
    ]
    f["_UNIDAD"] = f["UNIDAD_FUNCION"].map(es.texto_limpio)

    filas = []
    for (idp, es_sub, funcion, unidad), g in f.groupby(["IDPERSONA", "_SUB", "_FUNCION", "_UNIDAD"], dropna=False, sort=False):
        g = g.sort_values("FECHA_DESDE")
        unidad = es.texto_limpio(unidad)
        sigla = sigla_unidad(unidad, fuentes.mapa_siglas)
        periodos, niveles, carreras = [], [], []
        for r in g.itertuples(index=False):
            nivel_columna = es.texto_limpio(r.NIVEL_FUNCION)
            nivel = nivel_columna or pc._nivel_por_nombre_cargo(funcion)
            detalle = es.texto_limpio(r.DETALLE_NIVEL_FUNCION)
            niveles.append(nivel)
            carreras.append(detalle)
            periodos.append({
                "inicio": es.fecha_iso(r.FECHA_DESDE),
                "fin": es.fecha_iso(r.FECHA_HASTA),
                "duracion_dias": es.duracion_dias(r.FECHA_DESDE, r.FECHA_HASTA, fecha_corte),
                "nivel_funcion": nivel,
                "nivel_funcion_origen": "columna" if nivel_columna else ("nombre_cargo" if nivel else None),
                "detalle_nivel": detalle,
                "coincide_con_contrato": None if es.valor_nulo(r.ES_COINCIDENTE_CONTRATO) else bool(r.ES_COINCIDENTE_CONTRATO),
                "tipo_empleado_durante": es.texto_limpio(r.TIPOEMPLEADO_CONTRATO_DURANTE),
                "categoria_cargo_durante": es.texto_limpio(r.CATEGORIA_CARGO_CONTRATO_DURANTE),
            })
        carreras = es.unicos(carreras)
        resumen = es.resumen_periodos(g["FECHA_DESDE"].tolist(), g["FECHA_HASTA"].tolist(), fecha_corte)
        atributos = {
            "funcion": funcion,
            "es_subrogacion": bool(es_sub),
            "rol_subrogado": funcion if es_sub else None,
            "categoria": es.unicos(reversed(
                (g["CATEGORIA_ROL_SUBROGADO"] if es_sub else g["CATEGORIA_FUNCION_ADICIONAL"]).tolist()
            )),
            "unidad": unidad,
            "unidad_sigla": sigla,
            "niveles_funcion": es.unicos(niveles),
            "carreras_programas": carreras,
            "tratado_como_cargo": any(n is not None for n in niveles),
            **{k: v for k, v in resumen.items() if k != "duracion_total_anios"},
            "duracion_total_dias": sum(p["duracion_dias"] or 0 for p in periodos),
            "periodos": periodos,
            "_origen": {
                "fuente": "trayectorias/funciones_adicionales_persona.csv",
                "idestructuraorganica": es.unicos(g["IDESTRUCTURAORGANICA"]),
            },
        }
        texto = texto_cargo_lugar(_descripcion(funcion, bool(es_sub), carreras), unidad_para_texto(unidad, sigla))
        filas.append(es.nueva_evidencia(
            es.generar_evidencia_id(PREFIJO_ID, idp, "SUB" if es_sub else "FUN", funcion, unidad),
            idp, TIPO_ID, texto, atributos,
        ))

    reporte["designaciones_en_evidencias"] = len(f)
    reporte["evidencias"] = len(filas)
    return es.a_dataframe(filas), reporte
