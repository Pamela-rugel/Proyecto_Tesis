"""Subtipo PROYECTO_INVESTIGACION: participacion de la persona en proyectos de investigacion.

Fuente: `proyectos_investigacion_disponible.csv`, una fila por persona + proyecto + rol.

Reglas (decisiones del usuario, 2026-09-28):
- Una evidencia por persona + NOMBRE de proyecto (normalizado). Cada ID de proyecto distinto
  con ese nombre (renovaciones o fases registradas con el mismo nombre) es un periodo en
  `periodos`, con su propio rol, estado, unidad, etc. Varias filas del mismo ID (la persona
  con varios roles en el mismo proyecto) forman un solo periodo con `roles`.
- `vigente` solo por fechas: sin fecha fin = vigente; con fecha fin, vigente si aun no
  llega. `estado` (de la fuente) se conserva como dato, sin corregirlo.
- Proyectos con fecha de inicio futura: no son evidencia; quedan en
  `registros_no_considerados.csv` con la persona y el motivo.

Unidades, instituciones externas y financiadores: la fuente los trae unidos por comas en un
solo texto; se separan en listas (`partir_unidades`, `partir_instituciones`) y cada unidad
lleva su sigla (2026-09-29).

Texto: "NOMBRE (roles), Tipo de investigacion: ..., UNIDAD (SIGLA); UNIDAD (SIGLA), Institucion externa: ...,
Pais: ... (solo exterior), CINE: ..., Subarea CINE: ..., CINE secundaria: ..., Frascati: ...".
Se omite lo que no existe.
"""
from __future__ import annotations

import re

import pandas as pd

from evidencias import esquema as es

TIPO_ID = "PROYECTO_INVESTIGACION"
PREFIJO_ID = "INV-PRY"
MOTIVO_INICIO_FUTURO = "proyecto de investigación con fecha de inicio futura"

_JERARQUIA_ROL = {"DIRECTOR": 3, "CO-DIRECTOR": 2, "PARTICIPANTE": 1}
_AREAS = {  # atributo -> (columna fuente, etiqueta en el texto)
    "area_cine": ("STRAREACAMPOAMPLIO", "CINE"),
    "subarea_cine": ("STRAREACAMPOESPECIFICO", "Subárea CINE"),
    "area_cine_secundaria": ("STRAREACAMPOAMPLIO2", "CINE secundaria"),
    "subarea_cine_secundaria": ("STRAREACAMPOESPECIFICO2", "Subárea CINE secundaria"),
    "area_frascati": ("STRAREAFRASCATI", "Frascati"),
    "subarea_frascati": ("STRSUBAREAFRASCATI", "Subárea Frascati"),
    "area_frascati_secundaria": ("STRAREAFRASCATI2", "Frascati secundaria"),
    "subarea_frascati_secundaria": ("STRSUBAREAFRASCATI2", "Subárea Frascati secundaria"),
}


# --- Unidades e instituciones: la fuente las trae unidas por comas en un solo texto
# (2026-09-29). Se separan en listas; algunos nombres llevan comas por dentro.

# Una unidad de ESPOL empieza con una de estas palabras; un fragmento que no empieza asi es
# la continuacion del anterior ("FACULTAD DE ARTE" + "DISEÑO Y COMUNICACIÓN AUDIOVISUAL").
# Revisado sobre los 42 fragmentos distintos de la fuente.
_CABEZA_UNIDAD = re.compile(r"^(?:FACULTAD|CENTRO|ESCUELA|VICERRECTORADO|DECANATO|OFICINA|CELEX|I3LAB|CIEC)\b")
_NO_ES_SIGLA = {"GENERAL"}

# Fragmentos de INSTITUCION_EXTERNA / RESPONSFINANC que no son una institucion sino el lugar
# o la forma juridica de la anterior ("UNIVERSITY OF ABERDEEN, SCOTLAND, UNITED KINGDOM").
# Lista cerrada revisada sobre los fragmentos de la fuente (comparados sin tildes ni signos).
_COMPLEMENTOS_INSTITUCION = {
    "ARGENTINA", "AVEIRO", "BARCELONA", "BELGICA", "BELGIUM", "BRASIL", "BRAZIL", "BUENOS AIRES",
    "CALI COLOMBIA", "CANADA", "CHILE", "CHINA", "COLOMBIA", "CONCEPCION", "CORONEL", "E P", "EE UU",
    "ECUADOR", "ENSENADA", "ESPANA", "ESTADOS UNIDOS", "GALWAY", "GUANAJUATO", "GUANGZHOU", "HUNGRIA",
    "INDIA", "IRLANDA", "ITALIA", "MADRID", "MALAYSIA", "MARYLAND", "MEXICO", "NEW ZEALAND", "NY",
    "ONTARIO", "PORTUGAL", "REINO UNIDO", "REPUBLICA DOMINICANA", "RIO DE JANEIRO", "SAINT ETIENNE",
    "SALAMANCA", "SAN FRANCISCO", "SANTIAGO", "SANTIAGO DE CHILE", "SCOTLAND", "SEDE MEDELLIN",
    "SPAIN", "STATE OF LOUISIANA", "TAMILNADU", "UK", "UNITED KINGDOM", "USA", "VALDIVIA",
    "VENEZUELA", "VIETNAM",
}


def _partir_por_comas(texto: str) -> list[str]:
    """Separa por comas que no esten dentro de parentesis."""
    partes, actual, nivel = [], [], 0
    for c in texto:
        nivel += (c == "(") - (c == ")")
        if c == "," and nivel <= 0:
            partes.append("".join(actual))
            actual = []
        else:
            actual.append(c)
    partes.append("".join(actual))
    return [p.strip() for p in partes if p.strip()]


def partir_unidades(texto) -> list[str]:
    t = es.limpiar_para_mostrar(texto)
    salida: list[str] = []
    for f in _partir_por_comas(t) if t else []:
        if salida and not _CABEZA_UNIDAD.match(f.upper()):
            salida[-1] = f"{salida[-1]}, {f}"
        else:
            salida.append(f)
    return salida


def partir_instituciones(texto) -> list[str]:
    t = es.limpiar_para_mostrar(texto)
    salida: list[str] = []
    for f in _partir_por_comas(t) if t else []:
        f = f.rstrip(" .")
        if salida and es.normalizar_para_comparar(f) in _COMPLEMENTOS_INSTITUCION:
            salida[-1] = f"{salida[-1]}, {f}"
        elif f:
            salida.append(f)
    return salida


def sigla_de_unidad(unidad: str, mapa_siglas: dict) -> str | None:
    """Sigla del registro de autoridades (comparando sin tildes, y sin el "EN" que a veces
    sobra: "INGENIERIA EN MECANICA"); si no esta, la que el propio nombre trae al inicio
    ("CIEC - ...") o entre parentesis / tras un guion al final ("... (CIBE)", "... -CIDIS")."""
    clave = es.normalizar_para_comparar(unidad)
    for k in (clave, re.sub(r"\bEN\b ", "", clave)):
        if k in mapa_siglas:
            return mapa_siglas[k]
    m = (re.match(r"^([A-Z0-9]{2,7}) - ", unidad)
         or next(iter(reversed(list(re.finditer(r"\(([A-Z0-9]{2,7})\)", unidad)))), None)
         or re.search(r"-\s*([A-Z]{2,7})\s*$", unidad))
    return m.group(1) if m and m.group(1) not in _NO_ES_SIGLA else None


def _unidad_texto(unidad: str, sigla: str | None) -> str:
    if not sigla or re.search(rf"\b{re.escape(sigla)}\b", unidad):
        return unidad
    return f"{unidad} ({sigla})"


def _roles_ordenados(roles) -> list[str]:
    return sorted(es.unicos(roles), key=lambda r: -_JERARQUIA_ROL.get(r, 0))


def _periodo(g: pd.DataFrame, fecha_corte) -> dict:
    """Un ID de proyecto de la persona (una o varias filas, una por rol)."""
    r = g.iloc[0]
    pais = es.texto_limpio(r["STRPAIS"])
    return {
        "id_proyecto": int(r["IDPROYECTOINVESTIGACION"]),
        "inicio": es.fecha_iso(r["FECHAINICIO"]),
        "fin": es.fecha_iso(r["FECHAFIN"]),
        "duracion_anios": es.duracion_anios(r["FECHAINICIO"], r["FECHAFIN"], fecha_corte),
        "vigente": es.es_vigente(r["FECHAFIN"], fecha_corte),
        "rol": _roles_ordenados(g["ROLPROYECTO"])[0],
        "roles": _roles_ordenados(g["ROLPROYECTO"]),
        "rol_codigos": sorted(int(x) for x in es.unicos(g["IDROLPROYECTO"])),
        "estado": es.texto_limpio(r["ESTADO_PROYECTO"]),
        "tipo_investigacion": es.texto_limpio(r["STRSUBTIPO"]),
        "tipo_proyecto": es.texto_limpio(r["STRTIPO"]),
        "unidades_espol": partir_unidades(r["INSTITUCION_ESPOL"]),
        "instituciones_externas": partir_instituciones(r["INSTITUCION_EXTERNA"]),
        "pais": pais,
        "es_exterior": None if pais is None else pais.upper() != "ECUADOR",
        "financiado_por": partir_instituciones(r["RESPONSFINANC"]),
        "financiamiento_externo": None if es.valor_nulo(r["TIPOFINANCIAMIENTOEXTERNO"]) else int(r["TIPOFINANCIAMIENTOEXTERNO"]),
        "_areas": {k: es.limpiar_para_mostrar(r[col]) for k, (col, _) in _AREAS.items()},
    }


def _texto(nombre: str, roles: list[str], tipos: list[str], unidades: list[str],
           externas: list[str], paises_exterior: list[str], areas: dict) -> str:
    partes = [f"{nombre} ({' y '.join(r.lower() for r in roles)})" if roles else nombre]
    if tipos:
        partes.append(f"Tipo de investigación: {'; '.join(tipos)}")
    if unidades:
        partes.append("; ".join(unidades))
    if externas:
        partes.append(f"Institución externa: {'; '.join(externas)}")
    if paises_exterior:
        partes.append(f"País: {'; '.join(p.title() for p in paises_exterior)}")
    partes += [f"{etiqueta}: {areas[k]}" for k, (_, etiqueta) in _AREAS.items() if areas.get(k)]
    return ", ".join(partes)


def construir(proyectos: pd.DataFrame, mapa_siglas: dict,
              fecha_corte: pd.Timestamp) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    p = proyectos.drop_duplicates()
    n_duplicados_exactos = len(proyectos) - len(p)
    futuro = p["FECHAINICIO"] > fecha_corte
    no_considerados = p[futuro].drop_duplicates(["IDPERSONA", "IDPROYECTOINVESTIGACION"]).assign(
        motivo=MOTIVO_INICIO_FUTURO
    )
    p = p[~futuro].copy()
    p["_NOMBRE"] = p["NOMBRE"].map(es.normalizar_para_comparar)
    siglas = {es.normalizar_para_comparar(k): v for k, v in mapa_siglas.items()}

    filas, n_periodos, n_multi_rol = [], 0, 0
    for (idp, _), g in p.groupby(["IDPERSONA", "_NOMBRE"], sort=False):
        periodos = []
        for _, gp in g.groupby("IDPROYECTOINVESTIGACION", sort=False):
            periodos.append(_periodo(gp, fecha_corte))
            n_multi_rol += gp["ROLPROYECTO"].nunique() > 1
        periodos.sort(key=lambda x: (x["inicio"] or ""))
        n_periodos += len(periodos)

        reciente = periodos[-1]
        # Areas: las del periodo mas reciente que las tenga (el mismo proyecto no cambia de area)
        areas = next((pr["_areas"] for pr in reversed(periodos) if any(pr["_areas"].values())), reciente["_areas"])
        unidades = es.unicos(u for pr in periodos for u in pr["unidades_espol"])
        unidades_espol = [{"unidad": u, "sigla": sigla_de_unidad(u, siglas)} for u in unidades]
        unidades_txt = [_unidad_texto(x["unidad"], x["sigla"]) for x in unidades_espol]
        paises = es.unicos(pr["pais"] for pr in periodos)
        paises_exterior = [x for x in paises if x.upper() != "ECUADOR"]
        roles = _roles_ordenados(r for pr in periodos for r in pr["roles"])
        tipos = es.unicos(pr["tipo_investigacion"] for pr in periodos)
        externas = es.unicos(i for pr in periodos for i in pr["instituciones_externas"])
        nombre = es.limpiar_para_mostrar(g["NOMBRE"].iloc[0])
        inicios = [pd.Timestamp(pr["inicio"]) if pr["inicio"] else pd.NaT for pr in periodos]
        fines = [pd.Timestamp(pr["fin"]) if pr["fin"] else pd.NaT for pr in periodos]

        atributos = {
            "nombre": nombre,
            "rol": roles[0] if roles else None,
            "roles": roles,
            "estado": reciente["estado"],
            "tipos_investigacion": tipos,
            "tipos_proyecto": es.unicos(pr["tipo_proyecto"] for pr in periodos),
            "unidades_espol": unidades_espol,
            "instituciones_externas": externas,
            "paises": paises,
            "es_exterior": bool(paises_exterior),
            "financiado_por": es.unicos(f for pr in periodos for f in pr["financiado_por"]),
            "financiamiento_externo": es.unicos(pr["financiamiento_externo"] for pr in periodos),
            **areas,
            **es.resumen_periodos(inicios, fines, fecha_corte),
            "periodos": [{k: v for k, v in pr.items() if k != "_areas"} for pr in periodos],
            "_origen": {
                "fuente": "processed/proyectos_investigacion_disponible.csv",
                "ids_proyecto": [pr["id_proyecto"] for pr in periodos],
            },
        }
        texto = _texto(nombre, roles, tipos, unidades_txt, externas, paises_exterior, areas)
        filas.append(es.nueva_evidencia(
            es.generar_evidencia_id(PREFIJO_ID, idp, es.normalizar_para_comparar(nombre)),
            idp, TIPO_ID, texto, atributos,
        ))

    reporte = {
        "fuente": "processed/proyectos_investigacion_disponible.csv",
        "filas_poblacion": len(proyectos),
        "duplicados_exactos_eliminados": n_duplicados_exactos,
        "inicio_futuro_no_considerados": int(len(no_considerados)),
        "periodos_en_evidencias": n_periodos,
        "periodos_con_varios_roles": int(n_multi_rol),
        "evidencias_con_varios_periodos": sum('"n_periodos": 1,' not in f["atributos"] for f in filas),
        "evidencias": len(filas),
    }
    return es.a_dataframe(filas), reporte, no_considerados
