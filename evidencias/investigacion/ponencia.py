"""Subtipo PONENCIA: participaciones como ponente en congresos y eventos academicos.

Fuente: `ponentes_todos.csv`, una fila por registro de la persona (`IDCAPACITACION`). Es el
subconjunto de capacitaciones con tipo de evento CONGRESO (no se repite en
`capacitaciones_todas` ni en `certificados_todos`). No hay titulo de la ponencia ni tipo de
participacion: `NOMBRE` trae casi siempre el evento y a veces el titulo de la ponencia o
una sigla.

Reglas (decisiones del usuario, 2026-09-28):
- Una evidencia por persona + NOMBRE casi identico (similitud >= 0.95). Las ediciones y
  registros repetidos del evento van a `participaciones` (una por fechas + pais + modalidad +
  organizador + certificado + codigo de area, con su numero de registros).
- Limpieza basica del nombre: espacios, comillas envolventes y puntuacion final.
- No son evidencia (quedan en `registros_no_considerados.csv`):
  - certificado de ASISTENCIA (`TIPOCERTIFICADO = AS`) o asistencia declarada en el nombre;
  - registros que no son participacion en un evento (un cargo, un programa, un sistema, un
    comite): lista explicita `_NO_ES_EVENTO`;
  - inicio en el futuro.
- Texto: "NOMBRE, Organizado por: ..., Pais: ..." (pais solo si es del exterior). El
  organizador va sin "ESPOL" (se omite si solo era ESPOL) y se omite si ya esta en el
  nombre. Modalidad y horas solo en atributos. Sin `vigente`: un congreso es un evento puntual.
- Coponentes: `coponentes_espol` = otras personas de la poblacion que registraron el mismo
  evento (nombre normalizado) con la misma fecha de inicio. No implica la misma ponencia.
"""
from __future__ import annotations

import pandas as pd

from evidencias import esquema as es
from evidencias.investigacion.publicacion import _agrupar_titulos

TIPO_ID = "PONENCIA"
PREFIJO_ID = "INV-PON"
MOTIVO_ASISTENCIA = "certificado de asistencia (no de ponencia)"
MOTIVO_NO_EVENTO = "no es participación en un evento (cargo, programa, sistema o comité)"
MOTIVO_INICIO_FUTURO = "inicio en el futuro"

# Nombres normalizados que no son participacion en un evento (revisados uno a uno)
_NO_ES_EVENTO = {
    "COORDINADORA DE LOGISTICA",                              # cargo
    "MENTORING PROGRAM",                                      # programa de mentoria
    "PORTAL WAP",                                             # sistema (2006-2016)
    "COMITE CONSULTIVO 2023 CARRERA INGENIERIA ESTADISTICA",  # comite de carrera
}
_PREFIJO_ASISTENCIA = "CERTIFICATE FOR ATTENDING"
_COMILLAS = "\"'“”«»‘’"


def limpiar_nombre(nombre) -> str | None:
    """Espacios, comillas envolventes (o una sola comilla suelta en un extremo) y
    puntuacion final."""
    t = es.limpiar_para_mostrar(nombre)
    if not t:
        return None
    if t[0] in _COMILLAS and t[-1] in _COMILLAS:
        t = t[1:-1]
    elif t[0] in _COMILLAS and not any(c in _COMILLAS for c in t[1:]):
        t = t[1:]
    elif t[-1] in _COMILLAS and not any(c in _COMILLAS for c in t[:-1]):
        t = t[:-1]
    t = t.strip().rstrip(" .;,").strip()
    return t or None


def motivo_exclusion(r, fecha_corte: pd.Timestamp) -> str | None:
    clave = es.normalizar_para_comparar(r["NOMBRE"])
    if es.texto_limpio(r["TIPOCERTIFICADO"]) == "AS" or clave.startswith(_PREFIJO_ASISTENCIA):
        return MOTIVO_ASISTENCIA
    if clave in _NO_ES_EVENTO:
        return MOTIVO_NO_EVENTO
    if pd.notna(r["FECHAINICIO"]) and r["FECHAINICIO"] > fecha_corte:
        return MOTIVO_INICIO_FUTURO
    return None


def _participaciones(g: pd.DataFrame) -> list[dict]:
    claves = ["FECHAINICIO", "FECHAFIN", "NOMBREPAIS", "TIPOMODALIDADDESCRIPCION",
              "CERTIFICADOPOR", "TIPODESCRIPCION", "TIPOCAPACITACION"]
    salida = []
    for vals, gp in g.groupby(claves, dropna=False, sort=False):
        inicio, fin, pais, modalidad, organizador, certificado, area = vals
        horas = gp["DURACION"][gp["DURACION"] > 0]  # 0 = no declarado
        salida.append({
            "fecha_inicio": es.fecha_iso(inicio),
            "fecha_fin": es.fecha_iso(fin),
            "pais": es.texto_limpio(pais),
            "modalidad": es.texto_limpio(modalidad),
            "organizador": es.limpiar_para_mostrar(organizador),
            "horas": None if horas.empty else float(horas.max()),
            "tipo_certificado": es.texto_limpio(certificado),
            "codigo_area_capacitacion": es.texto_limpio(area),
            "n_registros": len(gp),
            "ids_capacitacion": sorted(int(x) for x in gp["IDCAPACITACION"]),
        })
    return sorted(salida, key=lambda p: (p["fecha_inicio"] is None, p["fecha_inicio"] or ""))


def _organizadores_texto(nombre: str, organizadores: list[str]) -> list[str]:
    """Sin "ESPOL" (si solo era ESPOL, se omite), sin repetidos y sin los que ya estan en el
    nombre. Misma regla que el certificador de capacitaciones."""
    n = es.normalizar_para_comparar(nombre)
    salida, vistos = [], set()
    for o in organizadores:
        t = es.quitar_espol(o)
        k = es.normalizar_para_comparar(t)
        if k and k not in vistos and k not in n:
            vistos.add(k)
            salida.append(t)
    return salida


def _texto(nombre: str, organizadores: list[str], paises_exterior: list[str]) -> str:
    partes = [nombre]
    if organizadores:
        partes.append(f"Organizado por: {'; '.join(organizadores)}")
    if paises_exterior:
        partes.append(f"País: {'; '.join(p.title() for p in paises_exterior)}")
    return ", ".join(partes)


def construir(ponencias: pd.DataFrame, fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    p = ponencias.copy()
    p["_MOTIVO"] = p.apply(motivo_exclusion, axis=1, fecha_corte=fecha_corte)
    p["_NOMBRE"] = p["NOMBRE"].map(limpiar_nombre)
    p["_CLAVE"] = p["_NOMBRE"].map(es.normalizar_para_comparar)
    p.loc[p["_MOTIVO"].isna() & (p["_CLAVE"] == ""), "_MOTIVO"] = "ponencia sin nombre"
    excluidos = p[p["_MOTIVO"].notna()]
    p = p[p["_MOTIVO"].isna()]

    # Coponentes: personas de la poblacion con el mismo evento y la misma fecha de inicio
    personas_por_evento = (
        p.groupby(["_CLAVE", "FECHAINICIO"])["IDPERSONA"]
        .apply(lambda s: set(int(x) for x in s)).to_dict()
    )

    filas, n_multi, n_copon = [], 0, 0
    for idp, g in p.groupby("IDPERSONA", sort=False):
        for grupo in _agrupar_titulos(g):
            participaciones = _participaciones(grupo)
            n_multi += len(participaciones) > 1
            nombre = grupo["_NOMBRE"].value_counts().index[0]
            originales = es.unicos(grupo["NOMBRE"].map(es.limpiar_para_mostrar))
            coponentes = sorted({
                o for k in set(zip(grupo["_CLAVE"], grupo["FECHAINICIO"]))
                for o in personas_por_evento.get(k, set()) if o != int(idp)
            })
            n_copon += bool(coponentes)
            paises = es.unicos(x["pais"] for x in participaciones)
            paises_exterior = [x for x in paises if x.upper() != "ECUADOR"]
            organizadores = es.unicos(x["organizador"] for x in participaciones)
            inicios = [x["fecha_inicio"] for x in participaciones if x["fecha_inicio"]]
            # Sin fecha de fin, la participacion termina el dia que empieza
            fines = [x["fecha_fin"] or x["fecha_inicio"] for x in participaciones if x["fecha_fin"] or x["fecha_inicio"]]
            horas = [x["horas"] for x in participaciones if x["horas"] is not None]
            atributos = {
                "nombre": nombre,
                "nombres_originales": originales,
                "fecha_inicio": min(inicios) if inicios else None,
                "fecha_fin": max(fines) if fines else None,
                "n_participaciones": len(participaciones),
                "n_registros": len(grupo),
                "paises": paises,
                "es_exterior": bool(paises_exterior),
                "modalidades": es.unicos(x["modalidad"] for x in participaciones),
                "organizadores": organizadores,
                "horas_total": sum(horas) if horas else None,
                "tipos_certificado": es.unicos(x["tipo_certificado"] for x in participaciones),
                "codigos_area_capacitacion": es.unicos(x["codigo_area_capacitacion"] for x in participaciones),
                "n_coponentes_espol": len(coponentes),
                "coponentes_espol": coponentes,
                "participaciones": participaciones,
                "_origen": {
                    "fuente": "processed/ponentes_todos.csv",
                    "ids_capacitacion": sorted(int(x) for x in grupo["IDCAPACITACION"]),
                },
            }
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(PREFIJO_ID, idp, grupo["_CLAVE"].iloc[0]),
                idp, TIPO_ID,
                _texto(nombre, _organizadores_texto(nombre, organizadores), paises_exterior),
                atributos,
            ))

    no_considerados = pd.DataFrame({
        "persona_id": excluidos["IDPERSONA"].astype(int),
        "tipo_id": TIPO_ID,
        "motivo": excluidos["_MOTIVO"],
        "id_origen": excluidos["IDCAPACITACION"].astype(int),
        "descripcion": excluidos["NOMBRE"].map(es.limpiar_para_mostrar),
        "fecha_inicio": excluidos["FECHAINICIO"].map(es.fecha_iso),
    })
    reporte = {
        "fuente": "processed/ponentes_todos.csv",
        "filas_poblacion": len(ponencias),
        "filas_no_consideradas_por_motivo": excluidos["_MOTIVO"].value_counts().to_dict(),
        "evidencias_con_varias_participaciones": n_multi,
        "evidencias_con_coponentes_espol": n_copon,
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
