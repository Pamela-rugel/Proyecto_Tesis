"""Subtipo IDIOMA: un idioma que la persona declara, con sus niveles (decisiones del usuario,
2026-09-29).

- Una evidencia = persona + idioma. Si la persona registro el mismo idioma varias veces, cada
  tipo de nivel es una lista con todos los niveles que declaro (de mayor a menor); no se
  guarda el detalle ni el conteo de registros.
- IDIOMA = 'OTRO': el nombre real sale de DESCRIPCION; se unifican solo las variantes de
  escritura del mismo idioma (`_NOMBRES_OTRO`). Sin DESCRIPCION no es evidencia.
- Espanol como lengua nativa: no es evidencia (no distingue a nadie). Cualquier otro idioma
  marcado como nativo si lo es, con `es_lengua_nativa = true`.
- Niveles en el texto: el mayor declarado de conversacion, lectura y escritura, y el MCER al
  final si existe. Un nivel 'Ninguna' (N) nunca se escribe. NIVELCOMPRESION no va al texto:
  desde 2021 el sistema la llena siempre con 'B', incluso con todo lo demas en avanzado
  (valor por defecto, no un nivel real); se conserva en los atributos.
- Registro con 'Ninguna' en las tres habilidades y sin MCER: la persona registro un idioma
  que no sabe; no es evidencia.
- Sin fechas: la fuente no dice desde cuando se sabe el idioma, y la fecha de modificacion
  del registro no describe a la persona.
"""
from __future__ import annotations

import json

import pandas as pd

from evidencias import esquema as es
from evidencias.idiomas.fuentes import ARCHIVO_IDIOMAS

TIPO_ID = "IDIOMA"
PREFIJO_ID = "IDI"

# catalogo_idiomas.csv, de mayor a menor
NIVELES = {"A": "AVANZADO", "I": "INTERMEDIO", "B": "BÁSICO", "N": "NINGUNA"}
ORDEN_MCER = ["C2", "C1", "B2", "B1", "A2", "A1"]
HABILIDADES_TEXTO = [("NIVELCONVERSACION", "Conversación"), ("NIVELLECTURA", "Lectura"),
                     ("NIVELESCRITURA", "Escritura")]
# columna de la fuente -> atributo con la lista de niveles declarados
ATRIBUTOS_NIVEL = {"NIVELCONVERSACION": "niveles_conversacion", "NIVELLECTURA": "niveles_lectura",
                   "NIVELESCRITURA": "niveles_escritura", "NIVELCOMPRESION": "niveles_comprension"}

# Nombres del catalogo con su ortografia correcta (la fuente omite algunas tildes)
_NOMBRES_CATALOGO = {"INGLES": "INGLÉS", "FRANCES": "FRANCÉS", "PORTUGUES": "PORTUGUÉS",
                     "MANDARIN": "MANDARÍN"}
# DESCRIPCION de 'OTRO', comparada sin tildes ni mayusculas -> nombre unificado. Holandes,
# neerlandes y 'Nederland' son el mismo idioma (el neerlandes).
_NOMBRES_OTRO = {
    "CATALAN": "CATALÁN", "HOLANDES": "NEERLANDÉS", "NEERLANDES": "NEERLANDÉS",
    "NERLANDES": "NEERLANDÉS", "NEDERLAND": "NEERLANDÉS", "KICHWA": "KICHWA", "BULGARO": "BÚLGARO",
    "HUNGARO": "HÚNGARO", "MANDARIN": "MANDARÍN", "ESPANOL": "ESPAÑOL", "SERBO CROATA": "SERBOCROATA",
    "FARSI": "FARSI",
}

MOTIVO_OTRO_SIN_NOMBRE = "idioma 'OTRO' sin nombre en DESCRIPCION"
MOTIVO_TODO_NINGUNA = "nivel 'Ninguna' en lectura, escritura y conversación, sin MCER"
MOTIVO_ESPANOL_NATIVO = "español como lengua nativa"


def _nombre_idioma(r) -> str | None:
    if r["IDIOMA"] != "OTRO":
        return _NOMBRES_CATALOGO.get(r["IDIOMA"], r["IDIOMA"])
    desc = es.limpiar_para_mostrar(r["DESCRIPCION"])
    if not desc:
        return None
    clave = es.normalizar_para_comparar(desc)
    return _NOMBRES_OTRO.get(clave, clave)


def _niveles(codigos: pd.Series) -> list[str]:
    """Niveles distintos declarados, de mayor a menor."""
    presentes = set(codigos.dropna())
    return [nombre for codigo, nombre in NIVELES.items() if codigo in presentes]


def _niveles_mcer(valores: pd.Series) -> list[str]:
    presentes = set(valores.dropna())
    return [n for n in ORDEN_MCER if n in presentes]


def _lengua_nativa(valores: pd.Series) -> bool | None:
    """True si algun registro lo marca nativo; null si ninguno trae el dato."""
    if valores.isna().all():
        return None
    return bool((valores == "S").any())


def _texto(idioma: str, atributos: dict) -> str:
    partes = [idioma]
    for col, etiqueta in HABILIDADES_TEXTO:
        niveles = atributos[ATRIBUTOS_NIVEL[col]]
        if niveles and niveles[0] != "NINGUNA":
            partes.append(f"{etiqueta}: {niveles[0].lower()}")
    if atributos["niveles_mcer"]:
        partes.append(f"MCER: {atributos['niveles_mcer'][0]}")
    return ", ".join(partes)


def construir(df: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    df = df.assign(IDIOMA_NOMBRE=df.apply(_nombre_idioma, axis=1))

    otro_sin_nombre = df["IDIOMA_NOMBRE"].isna()
    todo_ninguna = (
        df[[c for c, _ in HABILIDADES_TEXTO]].eq("N").all(axis=1) & df["NIVELMCER"].isna()
    ) & ~otro_sin_nombre
    no_considerados = [df[otro_sin_nombre].assign(motivo=MOTIVO_OTRO_SIN_NOMBRE),
                       df[todo_ninguna].assign(motivo=MOTIVO_TODO_NINGUNA)]
    df = df[~otro_sin_nombre & ~todo_ninguna]

    # El espanol se descarta como grupo: si algun registro lo marca nativo, ninguno es evidencia
    grupos = df.groupby(["IDPERSONA", "IDIOMA_NOMBRE"])
    espanol_nativo = (df["IDIOMA_NOMBRE"] == "ESPAÑOL") & grupos["LENGUANATIVA"].transform(lambda s: (s == "S").any())
    no_considerados.append(df[espanol_nativo].assign(motivo=MOTIVO_ESPANOL_NATIVO))
    df = df[~espanol_nativo]

    filas = []
    for (persona, idioma), g in df.sort_values("IDIDIOMAPERSONA").groupby(["IDPERSONA", "IDIOMA_NOMBRE"], sort=True):
        atributos = {
            "idioma": idioma,
            "nombres_originales": es.unicos(
                r["IDIOMA"] if r["IDIOMA"] != "OTRO" else f"OTRO: {es.limpiar_para_mostrar(r['DESCRIPCION'])}"
                for _, r in g.iterrows()
            ),
            **{atributo: _niveles(g[col]) for col, atributo in ATRIBUTOS_NIVEL.items()},
            "niveles_mcer": _niveles_mcer(g["NIVELMCER"]),
            "es_lengua_nativa": _lengua_nativa(g["LENGUANATIVA"]),
            "tiene_archivo_respaldo": bool(g["NAMEARCHDOC"].notna().any()),
            "_origen": {"archivo": ARCHIVO_IDIOMAS.name, "ids_idioma_persona": g["IDIDIOMAPERSONA"].tolist()},
        }
        filas.append(es.nueva_evidencia(
            es.generar_evidencia_id(PREFIJO_ID, persona, idioma), persona, TIPO_ID,
            _texto(idioma, atributos), atributos,
        ))

    evidencias = es.a_dataframe(filas)
    no_considerados = pd.concat(no_considerados, ignore_index=True)
    attrs = [json.loads(a) for a in evidencias["atributos"]]
    reporte = {
        "registros_en_poblacion": int(len(df) + len(no_considerados)),
        "no_considerados_por_motivo": no_considerados["motivo"].value_counts().to_dict(),
        "registros_agrupados_en_otra_evidencia": int(len(df) - len(evidencias)),
        "evidencias": len(evidencias),
        "evidencias_por_idioma": pd.Series([a["idioma"] for a in attrs]).value_counts().to_dict() if attrs else {},
        "con_mcer": sum(bool(a["niveles_mcer"]) for a in attrs),
        "con_varios_niveles_declarados": sum(
            any(len(a[k]) > 1 for k in [*ATRIBUTOS_NIVEL.values(), "niveles_mcer"]) for a in attrs
        ),
        "lengua_nativa_no_espanol": sum(a["es_lengua_nativa"] is True for a in attrs),
        "lengua_nativa_desconocida": sum(a["es_lengua_nativa"] is None for a in attrs),
    }
    return evidencias, reporte, no_considerados
