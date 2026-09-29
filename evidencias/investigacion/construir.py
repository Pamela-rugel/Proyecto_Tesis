"""Orquesta la construccion del dataset de evidencias de INVESTIGACION Y PRODUCCION ACADEMICA.

Uso desde notebook:
    from evidencias.investigacion import construir_evidencias_investigacion
    evidencias, reporte, validacion = construir_evidencias_investigacion(guardar=True)

Uso desde consola (raiz del proyecto):
    python -m evidencias.investigacion.construir
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.investigacion import (
    ponencia, proyecto_investigacion, proyecto_vinculacion, publicacion, tesis_dirigida,
)
from evidencias.investigacion.fuentes import (
    SALIDA_DIR, cargar_mapa_siglas, cargar_poblacion, cargar_ponencias, cargar_proyectos,
    cargar_publicaciones, cargar_tesis, cargar_vinculacion,
)

# Carpeta de salida y nombre de archivo por tipo: data/evidencias/<carpeta>/evidencias_<nombre>.csv
SALIDAS = {
    proyecto_investigacion.TIPO_ID: (SALIDA_DIR.parent / "investigacion", "investigacion"),
    proyecto_vinculacion.TIPO_ID: (SALIDA_DIR.parent / "vinculacion", "vinculacion"),
    publicacion.TIPO_ID: (SALIDA_DIR.parent / "publicaciones", "publicaciones"),
    tesis_dirigida.TIPO_ID: (SALIDA_DIR.parent / "tesis_dirigidas", "tesis_dirigidas"),
    ponencia.TIPO_ID: (SALIDA_DIR.parent / "ponencias", "ponencias"),
}
TIPOS = set(SALIDAS)


def construir_evidencias_investigacion(
    guardar: bool = False, fecha_corte: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, validacion)."""
    fecha_corte = fecha_corte or es.hoy()
    poblacion = cargar_poblacion()

    ev_pry, rep_pry, nc_pry = proyecto_investigacion.construir(
        cargar_proyectos(poblacion), cargar_mapa_siglas(), fecha_corte
    )
    ev_vin, rep_vin, nc_vin = proyecto_vinculacion.construir(cargar_vinculacion(poblacion), fecha_corte)
    ev_pub, rep_pub, nc_pub = publicacion.construir(cargar_publicaciones(poblacion))
    mapa_siglas = cargar_mapa_siglas()
    ev_tes, rep_tes, nc_tes = tesis_dirigida.construir(*cargar_tesis(poblacion), mapa_siglas)
    ev_pon, rep_pon, nc_pon = ponencia.construir(cargar_ponencias(poblacion), fecha_corte)

    evidencias = pd.concat([ev_pry, ev_vin, ev_pub, ev_tes, ev_pon], ignore_index=True).sort_values(
        ["persona_id", "tipo_id", "evidencia_id"], kind="stable"
    ).reset_index(drop=True)
    # Sin exigir fecha de inicio: los proyectos de vinculacion sin fechas se conservan
    # (decision del usuario); en proyectos de investigacion todas las filas tienen fechas.
    validacion = es.validar_evidencias(evidencias, TIPOS, poblacion, fecha_corte, exigir_fecha_inicio=False)

    def _no_considerados(nc: pd.DataFrame, tipo_id: str, col_nombre: str) -> pd.DataFrame:
        out = nc.assign(tipo_id=tipo_id).rename(columns={
            "IDPERSONA": "persona_id", "IDPROYECTOINVESTIGACION": "id_origen", col_nombre: "descripcion",
        })
        out["fecha_inicio"] = out["FECHAINICIO"].map(es.fecha_iso)
        return out[["persona_id", "tipo_id", "motivo", "id_origen", "descripcion", "fecha_inicio"]]

    no_considerados = pd.concat([
        _no_considerados(nc_pry, proyecto_investigacion.TIPO_ID, "NOMBRE"),
        _no_considerados(nc_vin, proyecto_vinculacion.TIPO_ID, "NOMBREPROYECTO"),
        nc_pub, nc_tes, nc_pon,  # ya vienen en el formato final
    ], ignore_index=True)

    reporte = {
        "fecha_corte": es.fecha_iso(fecha_corte),
        "poblacion_con_trayectoria": len(poblacion),
        "personas_con_evidencias": int(evidencias["persona_id"].nunique()),
        "evidencias_total": len(evidencias),
        "registros_no_considerados": int(len(no_considerados)),
        "subtipos": {
            proyecto_investigacion.TIPO_ID: {**rep_pry, "personas": int(ev_pry["persona_id"].nunique())},
            proyecto_vinculacion.TIPO_ID: {**rep_vin, "personas": int(ev_vin["persona_id"].nunique())},
            publicacion.TIPO_ID: {**rep_pub, "personas": int(ev_pub["persona_id"].nunique())},
            tesis_dirigida.TIPO_ID: {**rep_tes, "personas": int(ev_tes["persona_id"].nunique())},
            ponencia.TIPO_ID: {**rep_pon, "personas": int(ev_pon["persona_id"].nunique())},
        },
        "validacion_ok": bool(validacion["ok"].all()),
    }

    if guardar:
        # Cada tipo en su propia carpeta (decision del usuario, 2026-09-28): evidencias,
        # reporte y registros no considerados de ese tipo solamente.
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
    ev, rep, val = construir_evidencias_investigacion(guardar=True)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    print(val.to_string(index=False))
