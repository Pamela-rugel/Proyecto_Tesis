"""Subtipo PUBLICACION: articulos, capitulos, libros y ponencias publicadas.

Fuente: `publicaciones.csv`, una fila por persona + publicacion (`IDPUBLICACIONPERSONA`). No
hay columna de autores: la coautoria se deduce del titulo compartido entre personas.

Reglas (decisiones del usuario, 2026-09-28):
- Una evidencia por persona + TITULO (casi identico: similitud >= 0.95 sin tildes ni
  signos). Los registros con ese titulo son `versiones`; los que no difieren en nada salvo el
  ID se unen en una sola version (con todos sus IDs). Las versiones distintas (otro tipo,
  lugar, anio, participacion o estado; p.ej. conferencia y luego revista) se conservan.
- Texto: "TITULO, Tipo: ..., Publicado en: ..., Indexacion: ..." con TODOS los tipos y
  lugares de sus versiones. La indexacion solo si el tipo no la dice ya (p.ej. "(Scopus/WoS)").
  NO van al texto: cuartiles, factores de impacto, anios, ISSN/ISBN, participacion (ruido
  para el embedding); quedan en atributos.
- Fechas: solo el anio (`anios`); `fecha_inicio`/`fecha_fin` null. Anio invalido (< 1950) -> null.
- Factores de impacto: texto tal cual viene (formatos mezclados "1,980", "1.46", "037").
- Estado vacio: null (el codigo 0 de origen no tiene significado conocido).
- Coautores: `coautores_espol` = IDPERSONA de OTRAS personas de la poblacion que registraron
  el mismo titulo normalizado; `n_coautores_espol` = cuantas. Solo coautores de ESPOL que
  registraron la publicacion (los externos no estan en la fuente).
"""
from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from evidencias import esquema as es

TIPO_ID = "PUBLICACION"
PREFIJO_ID = "INV-PUB"
UMBRAL_TITULO = 0.95

# Tipo de origen -> como se escribe en el texto (unifica CAPITULO/CAPITULO con tilde)
_TIPO_TEXTO = {
    "ARTICULO CIENTIFICO": "Artículo científico",
    "ARTICULO CIENTIFICO SCOPUS WOS": "Artículo científico (Scopus/WoS)",
    "ARTICULO DE CONFERENCIA SCOPUS WOS": "Artículo de conferencia (Scopus/WoS)",
    "LIBRO O CAPITULO DE LIBRO": "Libro o capítulo de libro",
    "ARTICULO DE DIFUSION": "Artículo de difusión",
    "ARTICULO CIENTIFICO OTRAS INDEXACIONES": "Artículo científico (otras indexaciones)",
    "ARTICULO CIENTIFICO SIN INDEXACION": "Artículo científico (sin indexación)",
    "ARTICULO DE DIVULGACION CIENTIFICA": "Artículo de divulgación científica",
}
# Campos que distinguen una version de otra (si todos coinciden, son el mismo registro)
_CAMPOS_VERSION = ["anio", "tipo_publicacion", "participacion", "publicado_en", "estado",
                   "indexada", "base_indexacion", "cuartil_sjr", "factor_sjr_reportado",
                   "cuartil_citescore", "factor_citescore_reportado", "revision_pares",
                   "evento_institucion", "issn_isbn"]


def _tipo_texto(tipo: str | None) -> str | None:
    if not tipo:
        return None
    return _TIPO_TEXTO.get(es.normalizar_para_comparar(tipo), tipo.capitalize())


def _base_ya_en_tipo(base: str, tipos: list[str]) -> bool:
    """Scopus / WoS ya aparecen en tipos como 'ARTICULO CIENTIFICO (SCOPUS/WOS)'."""
    b = base.upper()
    menciona_scopus_wos = any("SCOPUS" in t.upper() for t in tipos)
    return menciona_scopus_wos and ("SCOPUS" in b or "ISI WEB" in b or "WOS" in b)


def _version(r) -> dict:
    anio = None if es.valor_nulo(r["ANIO"]) or int(r["ANIO"]) < 1950 else int(r["ANIO"])
    cuartil = es.texto_limpio(r["CUARTIL"])
    return {
        "anio": anio,
        "tipo_publicacion": es.limpiar_para_mostrar(r["STRTIPOPUBLICACION"]),
        "participacion": es.texto_limpio(r["STRTIPOPARTICIPACION"]),
        "publicado_en": es.limpiar_para_mostrar(r["NOMBREREVISTA"]),
        "estado": es.texto_limpio(r["STRESTADOPUBLICACION"]),
        "indexada": None if es.valor_nulo(r["REVISTAINDEXADA"]) else bool(r["REVISTAINDEXADA"]),
        "base_indexacion": es.texto_limpio(r["STRTIPOIDNEXACION"]),
        "cuartil_sjr": None if cuartil in (None, "--") else cuartil,
        "factor_sjr_reportado": es.texto_limpio(r["FACTORIMPACTOSJR"]),
        "cuartil_citescore": es.texto_limpio(r["CUARTILCITESCORE"]),
        "factor_citescore_reportado": es.texto_limpio(r["FACTORIMPACTOCITESCORE"]),
        "revision_pares": None if es.valor_nulo(r["REVISIONPARES"]) else bool(r["REVISIONPARES"]),
        "evento_institucion": es.limpiar_para_mostrar(r["INSTITUCION"]),
        "issn_isbn": es.texto_limpio(r["NROISBN"]),
        "url": es.texto_limpio(r["URLPUBLICACION"]),
        "ids_publicacion": [int(r["IDPUBLICACIONPERSONA"])],
    }


def _parecidos(a: str, b: str) -> bool:
    if a == b:
        return True
    sm = SequenceMatcher(None, a, b)
    # real_quick_ratio y quick_ratio son cotas superiores de ratio: descartan rapido
    return (sm.real_quick_ratio() >= UMBRAL_TITULO and sm.quick_ratio() >= UMBRAL_TITULO
            and sm.ratio() >= UMBRAL_TITULO)


def _agrupar_titulos(g: pd.DataFrame) -> list[pd.DataFrame]:
    """Grupos de filas de UNA persona con titulo casi identico. Cada clave se compara con la
    primera clave de cada grupo; se recorren las claves unicas en orden de aparicion."""
    grupos: list[tuple[str, set]] = []
    for clave in g["_CLAVE"].unique():
        destino = next((gr for gr in grupos if _parecidos(gr[0], clave)), None)
        if destino is None:
            grupos.append((clave, {clave}))
        else:
            destino[1].add(clave)
    return [g[g["_CLAVE"].isin(claves)] for _, claves in grupos]


def _versiones(filas: pd.DataFrame) -> list[dict]:
    """Une los registros que no difieren en nada salvo el ID/URL; conserva los distintos."""
    unidas: dict[tuple, dict] = {}
    for _, r in filas.iterrows():
        v = _version(r)
        clave = tuple(str(v[c]) for c in _CAMPOS_VERSION)
        if clave in unidas:
            unidas[clave]["ids_publicacion"] += v["ids_publicacion"]
            unidas[clave]["url"] = unidas[clave]["url"] or v["url"]
        else:
            unidas[clave] = v
    return sorted(unidas.values(), key=lambda v: (v["anio"] is None, v["anio"] or 0))


def _texto(titulo: str, tipos: list[str], lugares: list[str], bases: list[str]) -> str:
    partes = [titulo]
    tipos_txt = es.unicos(_tipo_texto(t) for t in tipos)
    if tipos_txt:
        partes.append(f"Tipo: {'; '.join(tipos_txt)}")
    if lugares:
        partes.append(f"Publicado en: {'; '.join(lugares)}")
    bases_txt = [b for b in bases if not _base_ya_en_tipo(b, tipos)]
    if bases_txt:
        partes.append(f"Indexación: {'; '.join(bases_txt)}")
    return ", ".join(partes)


def construir(publicaciones: pd.DataFrame) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    p = publicaciones.drop_duplicates().copy()
    n_duplicados_exactos = len(publicaciones) - len(p)
    p["_CLAVE"] = p["TITULO"].map(es.normalizar_para_comparar)
    sin_titulo = p["_CLAVE"] == ""
    no_considerados = p[sin_titulo]
    p = p[~sin_titulo]

    # Coautores ESPOL: personas de la poblacion que registraron el mismo titulo normalizado
    personas_por_titulo = p.groupby("_CLAVE")["IDPERSONA"].apply(lambda s: sorted(set(int(x) for x in s))).to_dict()

    filas, n_versiones_total, n_multi_version, n_anio_invalido = [], 0, 0, 0
    for idp, g in p.groupby("IDPERSONA", sort=False):
        for grupo in _agrupar_titulos(g):
            versiones = _versiones(grupo)
            n_versiones_total += len(versiones)
            n_multi_version += len(versiones) > 1
            n_anio_invalido += int((grupo["ANIO"] < 1950).sum())
            titulo = es.limpiar_para_mostrar(grupo["TITULO"].iloc[0])
            claves = set(grupo["_CLAVE"])
            coautores = sorted({o for c in claves for o in personas_por_titulo.get(c, []) if o != int(idp)})
            tipos = es.unicos(v["tipo_publicacion"] for v in versiones)
            lugares = es.unicos(v["publicado_en"] for v in versiones)
            bases = es.unicos(v["base_indexacion"] for v in versiones)
            atributos = {
                "titulo": titulo,
                "tipos_publicacion": tipos,
                "participaciones": es.unicos(v["participacion"] for v in versiones),
                "publicado_en": lugares,
                "indexada": any(v["indexada"] for v in versiones if v["indexada"] is not None) if any(v["indexada"] is not None for v in versiones) else None,
                "bases_indexacion": bases,
                "cuartiles_sjr": es.unicos(v["cuartil_sjr"] for v in versiones),
                "cuartiles_citescore": es.unicos(v["cuartil_citescore"] for v in versiones),
                "estados": es.unicos(v["estado"] for v in versiones),
                "anios": sorted(es.unicos(v["anio"] for v in versiones)),
                "fecha_inicio": None,
                "fecha_fin": None,
                "n_versiones": len(versiones),
                "n_coautores_espol": len(coautores),
                "coautores_espol": coautores,
                "versiones": versiones,
                "_origen": {
                    "fuente": "processed/publicaciones.csv",
                    "ids_publicacion": sorted(i for v in versiones for i in v["ids_publicacion"]),
                },
            }
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(PREFIJO_ID, idp, grupo["_CLAVE"].iloc[0]),
                idp, TIPO_ID, _texto(titulo, tipos, lugares, bases), atributos,
            ))

    reporte = {
        "fuente": "processed/publicaciones.csv",
        "filas_poblacion": len(publicaciones),
        "duplicados_exactos_eliminados": n_duplicados_exactos,
        "sin_titulo_no_considerados": int(sin_titulo.sum()),
        "anios_invalidos_a_null": n_anio_invalido,
        "versiones_en_evidencias": n_versiones_total,
        "evidencias_con_varias_versiones": n_multi_version,
        "evidencias_con_coautores_espol": sum('"n_coautores_espol": 0,' not in f["atributos"] for f in filas),
        "evidencias": len(filas),
    }
    no_considerados = pd.DataFrame({
        "persona_id": no_considerados["IDPERSONA"].astype(int),
        "tipo_id": TIPO_ID,
        "motivo": "publicación sin título",
        "id_origen": no_considerados["IDPUBLICACIONPERSONA"],
        "descripcion": None,
        "fecha_inicio": None,
    })
    return es.a_dataframe(filas), reporte, no_considerados
