"""Orquesta la construccion del dataset de evidencias de TRAYECTORIA: ejecuta cada
subtipo, concatena en el esquema comun, valida y (opcionalmente) guarda.

Uso desde notebook:
    from evidencias.trayectoria import construir_evidencias_trayectoria
    evidencias, reporte, validacion = construir_evidencias_trayectoria(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.trayectoria.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.trayectoria import (
    cargo_estructural, contrato_puntual, experiencia_externa, funcion_adicional,
)
from evidencias.trayectoria.fuentes import SALIDA_DIR, cargar_fuentes

SUBTIPOS = {
    cargo_estructural.TIPO_ID: cargo_estructural,
    contrato_puntual.TIPO_ID: contrato_puntual,
    funcion_adicional.TIPO_ID: funcion_adicional,
    experiencia_externa.TIPO_ID: experiencia_externa,
}

ARCHIVO_EVIDENCIAS = SALIDA_DIR / "evidencias_trayectoria.csv"
ARCHIVO_REPORTE = SALIDA_DIR / "reporte_evidencias_trayectoria.json"
ARCHIVO_NO_CONSIDERADAS = SALIDA_DIR / "personas_no_consideradas.csv"


def _excluir_inicio_futuro(evidencias: pd.DataFrame, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    """Una designacion o contrato que todavia no empezo no es trayectoria (decision del
    usuario, 2026-09-27): se excluye, sin importar el subtipo. Cada subtipo ya descarta los
    periodos futuros antes de agrupar; esto es una red de seguridad a nivel de evidencia."""
    ini, _ = es.fechas_de_atributos(evidencias)
    futuras = ini > fecha_corte
    return evidencias[~futuras], int(futuras.sum())


def _excluir_identicas(evidencias: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Evidencias que solo difieren en su ID y trazabilidad (`_origen`): misma persona,
    subtipo, texto y atributos (fechas incluidas). Se conserva la primera. Si difieren en
    cualquier atributo (p.ej. tiempo de dedicacion) NO son identicas y se conservan ambas."""
    atributos_sin_origen = evidencias["atributos"].map(
        lambda s: json.dumps({k: v for k, v in json.loads(s).items() if k != "_origen"},
                             ensure_ascii=False, sort_keys=True)
    )
    identicas = evidencias.assign(_A=atributos_sin_origen).duplicated(
        ["persona_id", "tipo_id", "texto", "_A"]
    )
    return evidencias[~identicas], int(identicas.sum())


def _personas_sin_trayectoria(fuentes, evidencias: pd.DataFrame) -> pd.DataFrame:
    """Personas de la poblacion sin ninguna evidencia de trayectoria. Se excluyen de los
    analisis basados en trayectoria (ver README): no hay informacion que describa su
    experiencia laboral, y un perfil vacio no es un perfil. El motivo distingue quien no
    aparece en ninguna fuente de quien si aparece pero todos sus registros se descartaron
    por las reglas de calidad (p.ej. solo contratos puntuales de un dia)."""
    con_registros = set()
    for df, col in ((fuentes.tramos_rol, "IDPERSONA"), (fuentes.eventos_puntuales, "IDPERSONA"),
                    (fuentes.funciones_adicionales, "IDPERSONA"), (fuentes.experiencia_externa, "IDPERSONA")):
        con_registros |= set(df[col].dropna().astype(int))
    sin = sorted(fuentes.poblacion - set(evidencias["persona_id"]))
    return pd.DataFrame({
        "persona_id": sin,
        "motivo": [
            "registros descartados por reglas de calidad (p.ej. solo contratos de un dia)"
            if p in con_registros else "sin registros de trayectoria en ninguna fuente"
            for p in sin
        ],
    })


def construir_evidencias_trayectoria(
    guardar: bool = False,
    fecha_corte: pd.Timestamp | None = None,
    incluir_funciones_coincidentes: bool = False,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion).

    - `fecha_corte`: fecha de referencia para vigencia y duraciones (por defecto hoy).
      Queda registrada en el reporte porque esos atributos cambian entre corridas.
    - `incluir_funciones_coincidentes`: ver `funcion_adicional.py`.
    """
    fecha_corte = fecha_corte or es.hoy()
    fuentes = cargar_fuentes()

    partes, reporte_subtipos = [], {}
    for tipo_id, modulo in SUBTIPOS.items():
        kwargs = {"incluir_coincidentes": incluir_funciones_coincidentes} if modulo is funcion_adicional else {}
        df, rep = modulo.construir(fuentes, fecha_corte, **kwargs)
        rep["personas"] = int(df["persona_id"].nunique())
        partes.append(df)
        reporte_subtipos[tipo_id] = rep

    evidencias = pd.concat(partes, ignore_index=True)
    evidencias = (
        evidencias.assign(_INI=es.fechas_de_atributos(evidencias)[0])
        .sort_values(["persona_id", "_INI", "tipo_id", "evidencia_id"], na_position="last", kind="stable")
        .drop(columns="_INI")
    )
    evidencias, n_futuras = _excluir_inicio_futuro(evidencias, fecha_corte)
    evidencias, n_identicas = _excluir_identicas(evidencias)
    evidencias = evidencias.reset_index(drop=True)
    for tipo_id, rep in reporte_subtipos.items():
        rep["evidencias_finales"] = int((evidencias["tipo_id"] == tipo_id).sum())
    validacion = es.validar_evidencias(evidencias, set(SUBTIPOS), fuentes.poblacion, fecha_corte)
    sin_trayectoria = _personas_sin_trayectoria(fuentes, evidencias)
    # Todas las personas de la poblacion base que no entran al analisis, con su motivo:
    # excluidas de todo analisis (p.ej. identificadas en defuncion, DEC-030) y sin trayectoria.
    no_consideradas = pd.concat([
        fuentes.personas_excluidas.rename(columns={"IDPERSONA": "persona_id", "MOTIVO": "motivo"}),
        sin_trayectoria,
    ], ignore_index=True).sort_values("persona_id").reset_index(drop=True)

    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_base": len(fuentes.poblacion) + len(fuentes.personas_excluidas),
        "personas_excluidas_de_todo_analisis": int(len(fuentes.personas_excluidas)),
        "poblacion_considerada": len(fuentes.poblacion),
        "personas_sin_trayectoria": int(len(sin_trayectoria)),
        "personas_con_evidencias": int(evidencias["persona_id"].nunique()),
        "excluidas_inicio_futuro": n_futuras,
        "excluidas_identicas": n_identicas,
        "evidencias_total": len(evidencias),
        "personas_no_consideradas_por_motivo": no_consideradas["motivo"].value_counts().to_dict(),
        "subtipos": reporte_subtipos,
        "validacion_ok": bool(validacion["ok"].all()),
    }

    if guardar:
        SALIDA_DIR.mkdir(parents=True, exist_ok=True)
        evidencias.to_csv(ARCHIVO_EVIDENCIAS, index=False, encoding="utf-8-sig")
        no_consideradas.to_csv(ARCHIVO_NO_CONSIDERADAS, index=False, encoding="utf-8-sig")
        ARCHIVO_REPORTE.write_text(
            json.dumps({**reporte, "validacion": validacion.to_dict("records")}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return evidencias, reporte, validacion


if __name__ == "__main__":
    ev, rep, val = construir_evidencias_trayectoria(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
    print(f"Guardado en {ARCHIVO_EVIDENCIAS}")
