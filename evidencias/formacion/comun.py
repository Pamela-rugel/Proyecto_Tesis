"""Reglas compartidas por los dos subtipos de formacion: normalizacion, duplicados, texto y
atributos (decisiones del usuario, 2026-09-28)."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

import pandas as pd

from evidencias import esquema as es

# Duplicado = MISMA persona, titulo casi identico en su totalidad y la misma institucion
# salvo errores de escritura ("UIVERSIDAD" vs "UNIVERSIDAD"). Instituciones distintas con
# nombres parecidos o siglas (ESPAE vs ESPOL, ESPOL vs ESPE) quedan muy por debajo del
# umbral y NO se fusionan.
UMBRAL_TITULO = 0.95
UMBRAL_INSTITUCION = 0.85

_PATRON_ESPOL = re.compile(r"POLIT[EÉ]CNICA DEL LITORAL", re.IGNORECASE)
_NIVELES_SUPERIORES = {"TERCER NIVEL", "CUARTO NIVEL"}


normalizar = es.normalizar_para_comparar
limpiar = es.limpiar_para_mostrar


def _similar(a: str, b: str) -> float:
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def _completitud(r) -> int:
    campos = ("FechaGraduacion", "Pais", "AreaCine", "SubAreaCine", "AreaFrascati", "SubAreaFrascati")
    return sum(not es.valor_nulo(r[c]) for c in campos) + int(r.get("ValidadoThTitulo") == 1)


def fusionar_duplicados(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Una fila por titulo (persona + titulo casi identico + misma institucion salvo
    errores de escritura). Se conserva el registro mas completo (fecha, pais, areas,
    validacion TH); los demas quedan listados en `_REGISTROS` para trazabilidad."""
    if df.empty:
        return df.assign(_REGISTROS=pd.Series(dtype=object)), 0
    # Desempate entre registros igual de completos: gana la escritura de institucion mas
    # frecuente en la fuente (una errata como "UIVERSIDAD" es rara; la forma correcta, comun).
    frecuencia = df["Institucion"].map(normalizar).value_counts()
    filas, n_fusionados = [], 0
    for _, g in df.groupby("IDPERSONA", sort=False):
        g = g.assign(
            _C=g.apply(_completitud, axis=1),
            _F=g["Institucion"].map(normalizar).map(frecuencia).fillna(0),
        ).sort_values(["_C", "_F", "IdTitulacion"], ascending=[False, False, True])
        grupos: list[list] = []
        for _, r in g.iterrows():
            t, i = normalizar(r["Titulo"]), normalizar(r["Institucion"])
            destino = next((gr for gr in grupos
                            if _similar(t, normalizar(gr[0]["Titulo"])) >= UMBRAL_TITULO
                            and _similar(i, normalizar(gr[0]["Institucion"])) >= UMBRAL_INSTITUCION), None)
            if destino is None:
                grupos.append([r])
            else:
                destino.append(r)
                n_fusionados += 1
        for gr in grupos:
            base = gr[0].copy()
            base["_REGISTROS"] = [
                {"id_titulacion": int(x["IdTitulacion"]), "titulo": limpiar(x["Titulo"]),
                 "institucion": limpiar(x["Institucion"]), "fecha_graduacion": es.fecha_iso(x["FechaGraduacion"])}
                for x in gr
            ]
            filas.append(base)
    return pd.DataFrame(filas).drop(columns=["_C", "_F"]), n_fusionados


def grado_academico(titulo: str | None, nivel: str | None) -> str | None:
    """Derivado del nombre del titulo (la fuente no lo trae): solo para cuarto nivel, donde
    `Nivel` no distingue doctorado de maestria o especializacion."""
    if nivel != "CUARTO NIVEL" or not titulo:
        return None
    t = normalizar(titulo)
    if re.search(r"\b(DOCTOR|DOCTORA|DOCTORADO|DRA|DR|PHD|PH D)\b", t):
        return "DOCTORADO"
    if re.search(r"\b(MAGISTER|MASTER|MAESTRIA|MAESTRO|MAESTRA|MSC|M SC|MBA)\b", t):
        return "MAESTRIA"
    if re.search(r"\b(ESPECIALISTA|ESPECIALIZACION|DIPLOMA|DIPLOMADO)\b", t):
        return "ESPECIALIZACION"
    return "OTRO"


def texto(titulo: str, estado: str | None, institucion: str | None, pais: str | None,
          es_exterior: bool, areas: dict) -> str:
    """"TITULO (estado), INSTITUCION, Pais, CINE: ..., Subarea CINE: ..., Frascati: ...,
    Subarea Frascati: ..." - el pais solo si es del exterior; se omite lo que no se conoce."""
    partes = [f"{titulo} ({estado.lower()})" if estado else titulo, institucion,
              pais.title() if es_exterior and pais else None]
    etiquetas = {"area_cine": "CINE", "subarea_cine": "Subárea CINE",
                 "area_frascati": "Frascati", "subarea_frascati": "Subárea Frascati"}
    partes += [f"{etiqueta}: {areas[k]}" for k, etiqueta in etiquetas.items() if areas.get(k)]
    return ", ".join(p for p in partes if p)


def atributos(r, fecha_corte: pd.Timestamp) -> dict:
    titulo, institucion = limpiar(r["Titulo"]), limpiar(r["Institucion"])
    pais = es.texto_limpio(r["Pais"])
    nivel = es.texto_limpio(r["Nivel"])
    return {
        "titulo": titulo,
        "nivel": nivel,
        "grado_academico": grado_academico(titulo, nivel),
        "estado": es.texto_limpio(r["Estado"]),
        "institucion": institucion,
        "es_espol": bool(institucion and _PATRON_ESPOL.search(institucion)),
        "pais": pais,
        "es_exterior": None if pais is None else pais.upper() != "ECUADOR",
        "fecha_inicio": None,  # la fuente no tiene fecha de inicio de estudios
        "fecha_fin": es.fecha_iso(r["FechaGraduacion"]),
        "area_cine": limpiar(r["AreaCine"]),
        "subarea_cine": limpiar(r["SubAreaCine"]),
        "area_frascati": limpiar(r["AreaFrascati"]),
        "subarea_frascati": limpiar(r["SubAreaFrascati"]),
        "validado_th": None if es.valor_nulo(r["ValidadoThTitulo"]) else bool(r["ValidadoThTitulo"]),
        "n_registros_fusionados": len(r["_REGISTROS"]),
        "_origen": {
            "fuente": "processed/reporte_titulaciones_educacion.csv",
            "id_programa": None if es.valor_nulo(r["IdPrograma"]) else int(r["IdPrograma"]),
            "cod_carrera": es.texto_limpio(r.get("CodCarrera")),
            "registros": r["_REGISTROS"],
        },
    }


def nueva_evidencia(r, tipo_id: str, prefijo: str, estado_en_texto: str | None, fecha_corte) -> dict:
    a = atributos(r, fecha_corte)
    areas = {k: a[k] for k in ("area_cine", "subarea_cine", "area_frascati", "subarea_frascati")}
    txt = texto(a["titulo"], estado_en_texto, a["institucion"], a["pais"], bool(a["es_exterior"]), areas)
    return es.nueva_evidencia(
        es.generar_evidencia_id(prefijo, r["IDPERSONA"], normalizar(r["Titulo"]), normalizar(r["Institucion"])),
        r["IDPERSONA"], tipo_id, txt, a,
    )


def es_nivel_superior(nivel) -> bool:
    return nivel in _NIVELES_SUPERIORES


def mismo_titulo(t1, t2) -> bool:
    return _similar(normalizar(t1), normalizar(t2)) >= UMBRAL_TITULO
