"""Orquesta la construccion del dataset de evidencias de CAPACITACION Y CERTIFICACION.

Uso desde notebook:
    from evidencias.capacitacion import construir_evidencias_capacitacion
    evidencias, reporte, validacion = construir_evidencias_capacitacion(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.capacitacion.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.capacitacion import capacitacion, certificacion, comun
from evidencias.capacitacion.fuentes import (
    SALIDA_DIR, cargar_capacitaciones, cargar_certificados, cargar_poblacion,
)
from evidencias.investigacion import ponencia
from evidencias.investigacion.fuentes import cargar_ponencias

# Carpeta de salida y nombre de archivo por tipo: data/evidencias/<carpeta>/evidencias_<nombre>.csv
SALIDAS = {
    capacitacion.TIPO_ID: (SALIDA_DIR / "capacitaciones", "capacitaciones"),
    certificacion.TIPO_ID: (SALIDA_DIR / "certificaciones", "certificaciones"),
}
TIPOS = set(SALIDAS)


def _claves_ponencia(poblacion: set[int], fecha_corte: pd.Timestamp) -> set[tuple]:
    """(persona, nombre normalizado, fecha de inicio) de las ponencias que SI son evidencia."""
    p = cargar_ponencias(poblacion)
    p = p[p.apply(ponencia.motivo_exclusion, axis=1, fecha_corte=fecha_corte).isna()]
    claves = p["NOMBRE"].map(ponencia.limpiar_nombre).map(es.normalizar_para_comparar)
    return set(zip(p["IDPERSONA"].astype(int), claves, p["FECHAINICIO"]))


def construir_evidencias_capacitacion(
    guardar: bool = False, fecha_corte: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion)."""
    fecha_corte = fecha_corte or es.hoy()
    poblacion = cargar_poblacion()

    cer = certificacion.preparar(cargar_certificados(poblacion), fecha_corte)
    ev_cer, rep_cer, nc_cer = certificacion.construir(cer, fecha_corte)
    # Lo que ya es ponencia o certificacion no se repite como capacitacion
    ev_cap, rep_cap, nc_cap = capacitacion.construir(
        cargar_capacitaciones(poblacion), _claves_ponencia(poblacion, fecha_corte),
        comun.claves_registradas(cer), fecha_corte,
    )

    evidencias = pd.concat([ev_cap, ev_cer], ignore_index=True).sort_values(
        ["persona_id", "tipo_id", "evidencia_id"], kind="stable"
    ).reset_index(drop=True)
    no_considerados = pd.concat([nc_cap, nc_cer], ignore_index=True)
    # Sin exigir fecha de inicio: 8 capacitaciones de la fuente no la tienen y se conservan
    validacion = es.validar_evidencias(evidencias, TIPOS, poblacion, fecha_corte, exigir_fecha_inicio=False)

    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_con_trayectoria": len(poblacion),
        "personas_con_evidencias": int(evidencias["persona_id"].nunique()),
        "evidencias_total": len(evidencias),
        "registros_no_considerados": int(len(no_considerados)),
        "subtipos": {
            capacitacion.TIPO_ID: {**rep_cap, "personas": int(ev_cap["persona_id"].nunique())},
            certificacion.TIPO_ID: {**rep_cer, "personas": int(ev_cer["persona_id"].nunique())},
        },
        "validacion_ok": bool(validacion["ok"].all()),
    }

    if guardar:
        for tipo_id, (carpeta, nombre) in SALIDAS.items():
            carpeta.mkdir(parents=True, exist_ok=True)
            ev_t = evidencias[evidencias["tipo_id"] == tipo_id]
            val_t = es.validar_evidencias(ev_t, {tipo_id}, poblacion, fecha_corte, exigir_fecha_inicio=False)
            ev_t.to_csv(carpeta / f"evidencias_{nombre}.csv", index=False, encoding="utf-8-sig")
            no_considerados[no_considerados["tipo_id"] == tipo_id].to_csv(
                carpeta / "registros_no_considerados.csv", index=False, encoding="utf-8-sig"
            )
            rep_t = {
                "fecha_corte": reporte["fecha_corte"],
                "poblacion_con_trayectoria": len(poblacion),
                "tipo_id": tipo_id,
                **reporte["subtipos"][tipo_id],
                "validacion_ok": bool(val_t["ok"].all()),
                "validacion": val_t.to_dict("records"),
            }
            (carpeta / f"reporte_evidencias_{nombre}.json").write_text(
                json.dumps(rep_t, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    return evidencias, reporte, validacion


if __name__ == "__main__":
    ev, rep, val = construir_evidencias_capacitacion(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
