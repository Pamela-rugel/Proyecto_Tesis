"""Reglas compartidas por CAPACITACION y CERTIFICACION (decisiones del usuario, 2026-09-28).

- Una evidencia por persona + NOMBRE casi identico (similitud >= 0.95). Las repeticiones del
  mismo curso van a `participaciones` (una por fechas + tipo de evento + pais + modalidad +
  certificador + asistencia/aprobacion + codigos, con su numero de registros).
- Limpieza basica del nombre (la misma de ponencias): espacios, comillas envolventes y
  puntuacion final.
- Texto: "NOMBRE, Tipo: ..., Certificado por: ..., Pais: ..., Modalidad: ...". El tipo de
  evento solo en capacitacion (y no si es "OTROS"); el certificador sin "ESPOL" (si solo era
  ESPOL, se omite) y omitido si ya esta en el nombre; el pais solo si es del exterior. Fechas,
  horas, asistencia/aprobacion, codigos y referencias solo en atributos.
- No son evidencia (quedan en `registros_no_considerados.csv`):
  - cursos institucionales obligatorios sin contenido tematico (`_OBLIGATORIOS`): etica
    publica, valores en accion, induccion/reinduccion, Somos Roca Madre, Perfil Administrativo
    Politecnico. Las inducciones a un rol y los cursos de etica con tema SI son evidencia;
  - nombres sin tema ("CURSO", "CAPACITACION", "CERTIFICATE OF PARTICIPATION"...);
  - el registro de titulo SENESCYT (no es una certificacion);
  - lo que ya es evidencia de otro tipo (misma persona + nombre + fecha de inicio);
  - inicio en el futuro.
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from evidencias import esquema as es
from evidencias.investigacion.ponencia import limpiar_nombre
from evidencias.investigacion.publicacion import _parecidos

MOTIVO_OBLIGATORIO = "curso institucional obligatorio sin contenido temático (inducción, ética, valores, PAP)"
MOTIVO_SIN_TEMA = "nombre sin tema"
MOTIVO_REGISTRO_TITULO = "registro de título (no es una certificación)"
MOTIVO_INICIO_FUTURO = "inicio en el futuro"

# Sobre el nombre normalizado (sin tildes ni signos). Lista cerrada revisada con el usuario.
_OBLIGATORIOS = re.compile(
    r"^(?:"
    r"ETICA PUBLICA|ETICA EN LA ADMINISTRACION PUBLICA|ETICA INSTITUCIONAL|ETICA Y VALORES|CODIGO DE ETICA"
    r"|(?:PROGRAMA )?(?:EDUCATIVO )?(?:NO FORMAL )?(?:DE )?VALORES EN ACCION"
    r"|(?:PROGRAMA |CURSO )?(?:EDUCATIVO )?(?:NO FORMAL )?(?:DE )?(?:RE)?INDUCCION(?: \d{4})?"
    r"|PROGRAMA DE INDUCCION PARA PROFESORES(?: NO TITULARES)?"
    r"|(?:PROGRAMA DE |CURSO DE )?(?:INDUCCION )?SOMOS ROCA MADRE(?: ESPOL)?"
    r"|PERFIL ADMINISTRATIVO POLITECNICO(?: PAP)?"
    r")$"
)
_SIN_TEMA = {
    "CURSO", "TALLER", "SEMINARIO", "CHARLA", "CONFERENCIA", "CAPACITACION", "NONE",
    "CERTIFICADO", "CERTIFICACION", "CERTIFICADO DE ASISTENCIA", "CERTIFICADO DE PARTICIPACION",
    "CERTIFICADO DE APROBACION", "CERTIFICATE OF PARTICIPATION", "CERTIFICATE OF COMPLETION",
}
_REGISTRO_TITULO = re.compile(r"^CERTIFICADO DE REGISTRO DE TITULO")

# Tipo de evento de la fuente -> como se escribe en el texto (None = no aporta)
_TIPO_EVENTO_TEXTO = {
    "PROGRAMA EDUCATIVO NO FORMAL": "Programa educativo no formal",
    "FORMACIONES TECNICAS PROFESIONALES": "Formación técnica profesional",
    "OTROS": None,
}


def tipo_evento_texto(tipo: str | None) -> str | None:
    if not tipo:
        return None
    clave = es.normalizar_para_comparar(tipo)
    return _TIPO_EVENTO_TEXTO[clave] if clave in _TIPO_EVENTO_TEXTO else tipo.capitalize()


def motivo_exclusion(clave: str, fecha_inicio, fecha_corte: pd.Timestamp) -> str | None:
    if _OBLIGATORIOS.match(clave):
        return MOTIVO_OBLIGATORIO
    if clave == "" or clave in _SIN_TEMA:
        return MOTIVO_SIN_TEMA
    if _REGISTRO_TITULO.match(clave):
        return MOTIVO_REGISTRO_TITULO
    if pd.notna(fecha_inicio) and fecha_inicio > fecha_corte:
        return MOTIVO_INICIO_FUTURO
    return None


def preparar(df: pd.DataFrame, fecha_corte: pd.Timestamp,
             ya_registrados: dict[tuple, str] | None = None) -> pd.DataFrame:
    """Agrega `_NOMBRE`, `_CLAVE` y `_MOTIVO` (None = es evidencia). `ya_registrados` mapea
    (persona, clave, fecha_inicio) de otro tipo al motivo con que se excluye aqui."""
    d = df.copy()
    d["_NOMBRE"] = d["NOMBRE"].map(limpiar_nombre)
    d["_CLAVE"] = d["_NOMBRE"].map(es.normalizar_para_comparar)
    d["_MOTIVO"] = [motivo_exclusion(k, f, fecha_corte) for k, f in zip(d["_CLAVE"], d["FECHAINICIO"])]
    if ya_registrados:
        otro = [ya_registrados.get((int(p), k, f)) for p, k, f in zip(d["IDPERSONA"], d["_CLAVE"], d["FECHAINICIO"])]
        d["_MOTIVO"] = d["_MOTIVO"].where(d["_MOTIVO"].notna(), pd.Series(otro, index=d.index))
    return d


def claves_registradas(d: pd.DataFrame) -> set[tuple]:
    """(persona, clave, fecha_inicio) de las filas que SI son evidencia."""
    v = d[d["_MOTIVO"].isna()]
    return set(zip(v["IDPERSONA"].astype(int), v["_CLAVE"], v["FECHAINICIO"]))


def _codigo(v) -> str | None:
    if es.valor_nulo(v):
        return None
    return str(int(v)) if isinstance(v, float) and v.is_integer() else es.texto_limpio(v)


_CLAVES_PARTICIPACION = ["FECHAINICIO", "FECHAFIN", "TIPOEVENTODESCRIPCION", "NOMBREPAIS",
                         "TIPOMODALIDADDESCRIPCION", "CERTIFICADOPOR", "TIPODESCRIPCION",
                         "TIPOCAPACITACION", "IDTIPOCONOCIMIEN"]


def _agrupar(registros: list[dict]) -> list[list[dict]]:
    """Registros de UNA persona agrupados por nombre casi identico (misma regla que
    `publicacion._agrupar_titulos`, sobre registros y no sobre DataFrames: hay ~46 mil grupos)."""
    representantes: list[str] = []
    grupo_de: dict[str, int] = {}
    for r in registros:
        clave = r["_CLAVE"]
        if clave not in grupo_de:
            i = next((i for i, rep in enumerate(representantes) if _parecidos(rep, clave)), None)
            if i is None:
                representantes.append(clave)
                i = len(representantes) - 1
            grupo_de[clave] = i
    grupos: list[list[dict]] = [[] for _ in representantes]
    for r in registros:
        grupos[grupo_de[r["_CLAVE"]]].append(r)
    return grupos


def _participaciones(grupo: list[dict]) -> list[dict]:
    """Una participacion por combinacion de `_CLAVES_PARTICIPACION`, con su numero de registros."""
    grupos: dict[tuple, list] = {}
    for r in grupo:
        clave = tuple(None if es.valor_nulo(r[c]) else r[c] for c in _CLAVES_PARTICIPACION)
        grupos.setdefault(clave, []).append(r)
    salida = []
    for vals, filas in grupos.items():
        inicio, fin, tipo, pais, modalidad, certificador, certificado, area, conocimiento = vals
        horas = [f["DURACION"] for f in filas if not es.valor_nulo(f["DURACION"]) and f["DURACION"] > 0]
        p = {
            "fecha_inicio": es.fecha_iso(inicio),
            "fecha_fin": es.fecha_iso(fin),
            "tipo_evento": es.texto_limpio(tipo),
            "pais": es.texto_limpio(pais),
            "modalidad": es.texto_limpio(modalidad),
            "certificado_por": es.limpiar_para_mostrar(certificador),
            "horas": float(max(horas)) if horas else None,
            "tipo_certificado": es.texto_limpio(certificado),
            "codigo_area_capacitacion": es.texto_limpio(area),
            "codigo_tipo_conocimiento": _codigo(conocimiento),
            "n_registros": len(filas),
            "ids_capacitacion": sorted(int(f["IDCAPACITACION"]) for f in filas),
        }
        if inicio is not None and fin is not None and fin < inicio:
            p["fechas_inconsistentes"] = True
        salida.append(p)
    return sorted(salida, key=lambda p: (p["fecha_inicio"] is None, p["fecha_inicio"] or ""))


def _certificadores_texto(nombre: str, certificadores: list[str]) -> list[str]:
    n = es.normalizar_para_comparar(nombre)
    salida, vistos = [], set()
    for c in certificadores:
        t = es.quitar_espol(c)
        k = es.normalizar_para_comparar(t)
        if k and k not in vistos and k not in n:
            vistos.add(k)
            salida.append(t)
    return salida


def _texto(nombre: str, tipos: list[str], certificadores: list[str],
           paises_exterior: list[str], modalidades: list[str]) -> str:
    partes = [nombre]
    if tipos:
        partes.append(f"Tipo: {'; '.join(tipos)}")
    if certificadores:
        partes.append(f"Certificado por: {'; '.join(certificadores)}")
    if paises_exterior:
        partes.append(f"País: {'; '.join(p.title() for p in paises_exterior)}")
    if modalidades:
        partes.append(f"Modalidad: {'; '.join(m.capitalize() for m in modalidades)}")
    return ", ".join(partes)


def construir(d: pd.DataFrame, *, tipo_id: str, prefijo_id: str, fuente: str,
              con_tipo_evento: bool, con_vigencia: bool,
              fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """`d` ya pasado por `preparar`. Devuelve (evidencias, reporte, registros_no_considerados)."""
    excluidos = d[d["_MOTIVO"].notna()]
    v = d[d["_MOTIVO"].isna()]
    personas_por_curso = v.groupby("_CLAVE")["IDPERSONA"].nunique().to_dict()

    por_persona: dict[int, list[dict]] = {}
    columnas = _CLAVES_PARTICIPACION + ["DURACION", "IDCAPACITACION", "IDPERSONA", "NOMBRE", "_NOMBRE", "_CLAVE"]
    for r in v[columnas].to_dict("records"):
        por_persona.setdefault(int(r["IDPERSONA"]), []).append(r)

    filas, n_multi = [], 0
    for idp, registros in por_persona.items():
        for grupo in _agrupar(registros):
            participaciones = _participaciones(grupo)
            n_multi += len(participaciones) > 1
            # El nombre mas frecuente; en empate, el primero que aparece
            nombre = Counter(r["_NOMBRE"] for r in grupo).most_common(1)[0][0]
            claves = {r["_CLAVE"] for r in grupo}
            tipos = es.unicos(p["tipo_evento"] for p in participaciones)
            paises = es.unicos(p["pais"] for p in participaciones)
            paises_exterior = [x for x in paises if x.upper() != "ECUADOR"]
            modalidades = es.unicos(p["modalidad"] for p in participaciones)
            certificadores = es.unicos(p["certificado_por"] for p in participaciones)
            inicios = [p["fecha_inicio"] for p in participaciones if p["fecha_inicio"]]
            # Sin fecha de fin, la participacion termina el dia que empieza
            fines = [p["fecha_fin"] or p["fecha_inicio"] for p in participaciones if p["fecha_fin"] or p["fecha_inicio"]]
            horas = [p["horas"] for p in participaciones if p["horas"] is not None]
            fecha_fin = max(fines) if fines else None
            atributos = {"nombre": nombre, "nombres_originales": es.unicos(es.limpiar_para_mostrar(r["NOMBRE"]) for r in grupo)}
            if con_tipo_evento:
                atributos["tipos_evento"] = tipos
            atributos.update({
                "fecha_inicio": min(inicios) if inicios else None,
                "fecha_fin": fecha_fin,
            })
            if con_vigencia:
                atributos["vigente"] = None if fecha_fin is None else pd.Timestamp(fecha_fin) >= fecha_corte
            atributos.update({
                "n_participaciones": len(participaciones),
                "n_registros": len(grupo),
                "paises": paises,
                "es_exterior": bool(paises_exterior),
                "modalidades": modalidades,
                "certificado_por": certificadores,
                "horas_total": sum(horas) if horas else None,
                "tipos_certificado": es.unicos(p["tipo_certificado"] for p in participaciones),
                "codigos_area_capacitacion": es.unicos(p["codigo_area_capacitacion"] for p in participaciones),
                "codigos_tipo_conocimiento": es.unicos(p["codigo_tipo_conocimiento"] for p in participaciones),
                "n_personas_mismo_curso": int(max(personas_por_curso.get(k, 1) for k in claves)),
                "participaciones": participaciones,
                "_origen": {"fuente": fuente, "ids_capacitacion": sorted(int(r["IDCAPACITACION"]) for r in grupo)},
            })
            tipos_txt = es.unicos(tipo_evento_texto(t) for t in tipos) if con_tipo_evento else []
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(prefijo_id, idp, grupo[0]["_CLAVE"]),
                idp, tipo_id,
                _texto(nombre, tipos_txt, _certificadores_texto(nombre, certificadores), paises_exterior, modalidades),
                atributos,
            ))

    no_considerados = pd.DataFrame({
        "persona_id": excluidos["IDPERSONA"].astype(int),
        "tipo_id": tipo_id,
        "motivo": excluidos["_MOTIVO"],
        "id_origen": excluidos["IDCAPACITACION"].astype(int),
        "descripcion": excluidos["NOMBRE"].map(es.limpiar_para_mostrar),
        "fecha_inicio": excluidos["FECHAINICIO"].map(es.fecha_iso),
    })
    reporte = {
        "fuente": fuente,
        "filas_poblacion": len(d),
        "filas_no_consideradas_por_motivo": excluidos["_MOTIVO"].value_counts().to_dict(),
        "evidencias_con_varias_participaciones": n_multi,
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
