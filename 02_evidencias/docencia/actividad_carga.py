"""Subtipo ACTIVIDAD_CARGA: actividades no lectivas de la carga politecnica (decisiones del
usuario, 2026-09-30).

Fuente: `data/processed/carga_politecnica_disponible.csv` (2013-2026): una fila por persona +
funcion + anio, con la funcion de catalogo (`NOMFUNCION`), una descripcion libre (`DESCFUNCION`),
la actividad (D = docencia, A = gestion, I = investigacion, V = vinculacion) y las horas.

Reglas:
- Funcion: el nombre de catalogo sin cuotas de horas ni parentesis ("CONSEJERO ACADEMICO (10
  ESTUDIANTES...)" y "CONSEJERIA ACADEMICA" son la misma funcion); los nombres muy parecidos
  (>= 0.88) se unen al mas frecuente.
- Tema: la descripcion sin lo que no es tema: las palabras de la funcion o del rol al inicio
  ("COORDINADOR DE LA MATERIA ..."), los entregables ("INFORME ...", "LISTADO DE ESTUDIANTES",
  "1. ..."), las cuotas ("1 PAO", "2H") y todo lo que sigue a "REPORTA A" (puede traer el nombre
  de otra persona).
- Tres clases de funcion:
  - con objeto propio (coordinador de materia, jefe de laboratorio, responsable de proyecto,
    comite de posgrado...): una evidencia por persona + funcion + tema (tema casi identico y con
    los mismos numeros sustantivos);
  - de rutina (consejeria, tutorias, investigador por horas...): una evidencia por persona +
    funcion, con los temas (casi siempre la carrera) en una lista. `n_personas_misma_funcion`
    permite bajarles el peso;
  - generica ("Asistencia y participacion en reuniones..."): no es evidencia.
  Una funcion sin tema es evidencia con la funcion sola (Rector, Consejo Directivo).
- No son evidencia (quedan en `registros_no_considerados.csv`):
  - permisos personales (maternal, lactancia, recien nacido, discapacidad, paternidad,
    sabatico): datos sensibles; su descripcion NO se copia;
  - la funcion generica de reuniones y registros de sistema ("ELIMINAR TUTOR ...");
  - desde 2015, cargas no aprobadas (antes de 2015 casi todo figura sin aprobar: la aprobacion
    empezo en 2015, misma regla que las materias);
  - anio invalido;
  - funciones que la misma persona ya tiene en TRAYECTORIA_FUNCION_ADICIONAL (sin contar
    subrogaciones): autoridades, coordinaciones de carrera/posgrado/practicas/vinculacion/
    acreditacion, consejos.
- Periodos: los anios en que la tuvo (`anios`); sin fecha_inicio/fecha_fin.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from difflib import SequenceMatcher

import pandas as pd

from evidencias import esquema as es
from evidencias.trayectoria.fuentes import DATA_DIR

TIPO_ID = "ACTIVIDAD_CARGA"
PREFIJO_ID = "DOC-ACT"
ARCHIVO_CARGA_POLITECNICA = DATA_DIR / "processed" / "carga_politecnica_disponible.csv"
ANIO_INICIO_APROBACION = 2015
ACTIVIDADES = {"D": "DOCENCIA", "A": "GESTION", "I": "INVESTIGACION", "V": "VINCULACION"}
_COLUMNAS_EXCLUIDAS = ["NUMEROIDENTIFICACION", "NOMDOCENTE", "EMAIL", "EMAILALTERNO"]

MOTIVO_PERMISO = "permiso personal (dato sensible, no se copia)"
MOTIVO_GENERICA = "actividad institucional genérica sin tema (reuniones)"
MOTIVO_SISTEMA = "registro de sistema, no es una actividad"
MOTIVO_NO_APROBADA = "carga no aprobada (desde 2015)"
MOTIVO_ANIO = "año inválido"
MOTIVO_YA_FUNCION = "ya registrada como función adicional en trayectoria"

# --- Clases de funcion (sobre la funcion normalizada). Revisadas con el usuario sobre las 167.
_PERMISO = re.compile(r"^PERMISO|^PERIODO SABATICO")
_GENERICA = re.compile(r"^ASISTENCIA Y PARTICIPACION EN REUNIONES")
_SISTEMA = re.compile(r"^ELIMINAR ")
_RUTINA = re.compile(
    r"CONSEJER|^TUTOR|TUTORIA|^INVESTIGADOR|^INVESTIGACION|APOYO ACADEMICO|PERSONAL DE APOYO|"
    r"ASISTE EN LA ENSENANZA|PREPARACION Y TOMA DE EXAMEN|VISITAS TECNICAS|SALIDAS DE CAMPO|"
    r"REVISOR DE FORMATOS|CAPACITACION EN METODOLOGIA"
)

# Funcion de la carga -> funciones de TRAYECTORIA_FUNCION_ADICIONAL que la repiten (normalizadas)
_EQUIVALENTE_FUNCION_ADICIONAL = [
    (re.compile(r"^COORDINADOR DE CARRERA"), {"COORDINADOR DE CARRERA", "COORDINADOR DE AREA TRANSVERSAL INSTITUCIONAL DE DOCENCIA"}),
    (re.compile(r"^COORDINADOR DE PROGRAMA DE POSTGRADO"), {"COORDINADOR DE PROGRAMA DE POSTGRADO"}),
    (re.compile(r"^COORDINADOR GENERAL DE POSGRADO"), {"COORDINADOR GENERAL DE POSTGRADO"}),
    (re.compile(r"CONSEJO DIRECTIVO"), {"MIEMBRO DEL CONSEJO DIRECTIVO", "MIEMBRO DEL CONSEJO DIRECTIVO TRABAJADORES"}),
    (re.compile(r"CONSEJO POLITECNICO"), {"MIEMBRO DEL CONSEJO POLITECNICO"}),
    (re.compile(r"^COORDINADOR DE PRACTICAS EMPRESARIALES"), {"COORDINADOR DE PRACTICAS EMPRESARIALES"}),
    (re.compile(r"^COORDINADOR DE VINCULACION"), {"COORDINADOR DE VINCULACION CON LA SOCIEDAD"}),
    (re.compile(r"^COORDINADOR (PRINCIPAL )?DE ACREDITACION INTERNACIONAL"), {"COORDINADOR DE ACREDITACION INTERNACIONAL"}),
    (re.compile(r"^SUBDECANO"), {"SUBDECANO"}),
    (re.compile(r"^DECANO"), {"DECANO", "DECANO DE GRADO"}),
    (re.compile(r"^VICERRECTOR"), {"VICERRECTOR"}),
    (re.compile(r"^RECTOR"), {"RECTOR"}),
    (re.compile(r"^JEFE DE DEPARTAMENTO"), {"DIRECTOR DEPARTAMENTO"}),
    (re.compile(r"^DIRECTOR DE (UN CENTRO|LA EDCOM|LA ESCUELA)|^SUBDIRECTOR|^DIRECCION DE LA SECRETARIA"),
     {"DIRECTOR", "DIRECTOR ACADEMICO", "DIRECTOR ACADEMICO Y DE INVESTIGACION", "SUBDIRECTOR ACADEMICO"}),
]

# --- Funcion normalizada
_CUOTA = re.compile(r"\b(MIN|MAX)\b.*|\b\d+\s*(H|HORAS?)\b.*|\bA \d+ HORAS\b|\bPOR (PROYECTO|CARRERA)\b.*")
UMBRAL_FUNCION = 0.88


def _funcion_base(nombre) -> str:
    k = es.normalizar_para_comparar(re.sub(r"\(.*?\)", " ", str(nombre)))
    k = _CUOTA.sub("", k).strip()
    k = re.sub(r"^CONSEJERIA ACADEMICA", "CONSEJERO ACADEMICO", k)
    return re.sub(r"^INVESTIGACION$", "INVESTIGADOR", k)


def _familias(nombres: pd.Series) -> pd.Series:
    """Funcion normalizada de cada fila; las muy parecidas se unen a la mas frecuente."""
    bases = nombres.map(_funcion_base)
    canon: dict[str, str] = {}
    for b in bases.value_counts().index:
        canon[b] = next((c for c in dict.fromkeys(canon.values())
                         if SequenceMatcher(None, b, c).ratio() >= UMBRAL_FUNCION), b)
    return bases.map(canon)


def _nombre_funcion(originales: pd.Series) -> str:
    """Nombre para el texto: el original mas frecuente, sin parentesis ni cuotas, en oracion."""
    t = Counter(originales).most_common(1)[0][0]
    t = re.sub(r"\(.*?\)", " ", str(t))
    t = re.sub(r"\s*\b(MIN|MAX)\b.*$|\s*\b\d+\s*(H|HORAS?)\b.*$", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" .,-")
    return t[:1].upper() + t[1:].lower()


def clase_funcion(familia: str) -> str:
    if _PERMISO.search(familia):
        return "PERMISO"
    if _GENERICA.search(familia):
        return "GENERICA"
    if _SISTEMA.search(familia):
        return "SISTEMA"
    return "RUTINA" if _RUTINA.search(familia) else "OBJETO"


# --- Tema
# "REPORTA A VRA: EDITORA DE SECCION ..." -> el tema va despues de los dos puntos
_REPORTA_INICIO = re.compile(r"^\s*REPORTA A [^:]{1,40}:\s*", re.IGNORECASE)
# Codigo de actividad al inicio: "(GES ) DIFUSION ...", "(DOC ) TUTORIA ..."
_CODIGO_ACTIVIDAD = re.compile(r"^\s*\(\s*(GES|DOC|VIN|INV)\s*\)\s*", re.IGNORECASE)
# Situaciones personales mencionadas dentro de otras funciones (datos sensibles, 2026-09-30):
# "QUIEN ESTA CON PERMISO POR MATERNIDAD", "TRABAJA HASTA EL 5 DE JULIO POR ...". Desde ahi,
# nada se copia. "PERMISOS DE INVESTIGACION" (tramite de investigacion) no es personal.
SITUACION_PERSONAL = re.compile(
    r"\bPERMISO\s+(?:POR\s+|DE\s+)?(?:MATERN|PATERN|LACTAN|M[EÉ]DIC|ENFERM|CALAMID|RECI[EÉ]N)\w*|"
    r"\bMATERNIDAD\b|\bPATERNIDAD\b|\bLACTANCIA\b|\bLICENCIA\b|\bDISCAPACIDAD\b|\bEMBARAZ\w*|"
    r"\bQUIEN\s+EST[AÁ]\b|\bTRABAJA\s+HASTA\b|\bSU\s+INCORPORACI[OÓ]N\b",
    re.IGNORECASE,
)
_CORTE = re.compile(  # lo que sigue ya no es tema: entregables, requisitos, notas, nombres de personas
    r"\s*(?:\r|\n|\.-|\s\d+\s*[.)]\s|^\d+\s*[.)]\s|[-–(]?\s*\bREPORTA A\b|\(?\bENTREGA DE\b|\bINFORMES?\b|"
    r"\bLISTADO\b|\bREPORTES?\b|\bACTAS? DE\b|\bNOTA\b|\bESTA CARGA\b|\bA PARTIR DEL\b|"
    r"\bCANTIDAD DE ESTUDIANTES\b|\bAL MENOS\b|\bNO CONTEMPLA\b|\bLOS PROYECTOS\b[^/]*\bDEBE|"
    r"\bDEBER[AÁ]N? SER\b|\b(PRESENTAR|ENTREGAR|ELABORAR)\s*$).*$",
    re.IGNORECASE | re.DOTALL,
)
_RELLENO = re.compile(r"\b\d*\s*PAO\s*\d*\b|\b\d+\s*H\b|\b\d+\s*-\s*\d+\s*ESTUDIANTES\b|\b\d+\s*PROYE\w*\b|"
                      r"\bEN EL PAE\b|\bSEMANAL(ES)?\b", re.IGNORECASE)
_CONECTOR_FINAL = {"EN", "EL", "LA", "LAS", "LOS", "DE", "DEL", "Y", "A", "AL", "CON", "PARA", "POR"}
_PALABRAS_ROL = set((
    "COORDINADOR COORDINADORA COORDINAR COORDINACION CO TUTOR TUTORA TUTORES TUTORIA TUTORIAS JEFE JEFA "
    "MIEMBRO RESPONSABLE ACADEMICO ACADEMICA ACADEMICAS DE LA DEL EL LOS LAS EN PARA Y A AL "
    "MATERIA MATERIAS ASIGNATURA ACTIVIDADES ACTIVIDAD PROYECTO PROYECTOS INSTITUCIONAL "
    "CONSEJERO CONSEJERA CONSEJERIA CONSEJERIAS INVESTIGADOR INVESTIGADORA INVESTIGACION "
    "PRACTICAS PRACTICA EMPRESARIALES PROFESIONALES INTEGRADOR INTEGRADORA LAB LABORATORIO DOCENCIA "
    "COMITE PROGRAMA POSTGRADO UNIDAD DISENO ELABORACION MATERIAL DIDACTICO GUIAS DOCENTES "
    "ORGANIZACION COLABORACION VINCULACION SOCIEDAD HORAS HORA ESTUDIANTES CARRERA POR"
).split())
_SIN_TEMA = {"REUNIONES", "VARIOS", "APOYO", "GENERAL", "TODAS", "TODOS", "ESPOL"}


def tema(descripcion, familia: str, no_son_tema: set[str] = frozenset()) -> str | None:
    """Tema de la descripcion, conservando tildes y mayusculas del original. `no_son_tema`:
    claves normalizadas que no cuentan como tema (siglas y nombres de unidades)."""
    t = es.texto_limpio(descripcion)
    if not t:
        return None
    t = _CODIGO_ACTIVIDAD.sub("", _REPORTA_INICIO.sub("", t))
    m = SITUACION_PERSONAL.search(t)
    if m:
        t = t[:m.start()]
    t = _CORTE.sub("", t)
    t = _RELLENO.sub(" ", t)
    palabras = t.replace(":", " ").replace(" - ", " ").replace("(", " ").replace(")", " ").split() \
        if re.fullmatch(r"\s*\([^()]*\)\s*", t) else t.replace(":", " ").replace(" - ", " ").split()
    quitar = set(familia.split()) | _PALABRAS_ROL
    while palabras and (es.normalizar_para_comparar(palabras[0]) in quitar
                        or re.fullmatch(r"[\d.:\-–_/]+", palabras[0])):
        palabras.pop(0)
    while palabras and (es.normalizar_para_comparar(palabras[-1]) in _CONECTOR_FINAL
                        or re.fullmatch(r"[\d.:\-–_/]+", palabras[-1])):
        palabras.pop()
    resto = " ".join(palabras).strip(" .,;:-–_/")
    clave = es.normalizar_para_comparar(resto)
    if len(clave) < 3 or clave in _SIN_TEMA or clave in no_son_tema or set(clave.split()) <= quitar:
        return None
    return resto


_CODIGO_MATERIA = re.compile(r"\(?\s*\b([A-Z]{3,5}\d{3,5})\b\s*\)?")


def resolver_codigos(tema_: str | None, catalogo: dict[str, str]) -> tuple[str | None, list[str]]:
    """Codigos de materia en el tema (2026-09-30, usuario): si el tema es solo el codigo, se
    reemplaza por el nombre de la materia ("FISG1006" -> "FÍSICA: ELECTRICIDAD Y MAGNETISMO");
    si ya trae el nombre, el codigo se quita ("MUESTREO (ESTG1006)" -> "MUESTREO"). Un codigo
    sin nombre en la carga academica no se toca (asi "ISO9001" no se confunde con una materia).
    Devuelve (tema, codigos)."""
    if not tema_:
        return tema_, []
    codigos = es.unicos(c for c in _CODIGO_MATERIA.findall(tema_.upper()) if c in catalogo)
    if not codigos:
        return tema_, []
    sin_codigo = _CODIGO_MATERIA.sub(lambda m: " " if m.group(1).upper() in catalogo else m.group(0), tema_)
    sin_codigo = re.sub(r"\(\s*\)", " ", sin_codigo)
    sin_codigo = re.sub(r"\s+", " ", sin_codigo).strip(" .,;:-–_/")
    if es.normalizar_para_comparar(sin_codigo):
        return sin_codigo, codigos
    return "; ".join(es.unicos(catalogo[c] for c in codigos)), codigos


def _mismo_tema(a: str, b: str) -> bool:
    if es.numeros_en_nombre(a)[0] != es.numeros_en_nombre(b)[0]:
        return False
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.85


def _agrupar_temas(claves: list[str]) -> dict[str, str]:
    """clave de tema -> clave representante de su grupo."""
    reps: list[str] = []
    grupo = {}
    for k in claves:
        r = next((x for x in reps if _mismo_tema(x, k)), None)
        if r is None:
            reps.append(k)
            r = k
        grupo[k] = r
    return grupo


def _funciones_adicionales(evidencias_trayectoria: pd.DataFrame) -> dict[int, set[str]]:
    """persona -> funciones (normalizadas) que ya tiene en TRAYECTORIA_FUNCION_ADICIONAL,
    sin contar subrogaciones."""
    f = evidencias_trayectoria[evidencias_trayectoria["tipo_id"] == "TRAYECTORIA_FUNCION_ADICIONAL"]
    salida: dict[int, set[str]] = {}
    for pid, a in zip(f["persona_id"], f["atributos"].map(json.loads)):
        if not a.get("es_subrogacion"):
            salida.setdefault(int(pid), set()).add(es.normalizar_para_comparar(a["funcion"]))
    return salida


def _repetida(familia: str, funciones_persona: set[str]) -> bool:
    return any(patron.search(familia) and (equivalentes & funciones_persona)
               for patron, equivalentes in _EQUIVALENTE_FUNCION_ADICIONAL)


# Unidades antiguas -> nombre de la facultad actual (misma regla que DOCENCIA_MATERIA, usuario)
_FCNM = "Facultad de Ciencias Naturales y Matemáticas"
_UNIDAD_ACTUAL = {
    "FACULTAD DE INGENIERIA MARITIMA CIENCIAS BIOLOGICAS OCEANICAS Y RECURSOS NATURALES":
        "Facultad de Ingeniería Marítima y Ciencias del Mar",
    "INSTITUTO DE CIENCIAS MATEMATICAS": _FCNM, "INSTITUTO DE CIENCIAS FISICAS": _FCNM,
    "INSTITUTO DE CIENCIAS QUIMICAS Y AMBIENTALES": _FCNM, "DEPARTAMENTO DE CIENCIAS MATEMATICAS": _FCNM,
    "DEPARTAMENTO DE CIENCIAS FISICAS": _FCNM, "DEPARTAMENTO DE CIENCIAS QUIMICAS Y AMBIENTALES": _FCNM,
}


def cargar(poblacion: set[int]) -> pd.DataFrame:
    c = pd.read_csv(ARCHIVO_CARGA_POLITECNICA, low_memory=False)
    c = c.drop(columns=[x for x in _COLUMNAS_EXCLUIDAS if x in c.columns])
    clave = c["NOMBREUNIDADCARGA"].map(es.normalizar_para_comparar)
    c["NOMBREUNIDADCARGA"] = clave.map(_UNIDAD_ACTUAL).fillna(c["NOMBREUNIDADCARGA"])
    return c[c["IDPERSONA"].isin(poblacion)].reset_index(drop=True)


def _detalle(r) -> dict:
    return {
        "anio": int(r["ANIO"]),
        "terminos": es.texto_limpio(r["TERMINOS_ACTIVOS"]),
        "actividad": ACTIVIDADES.get(r["ACTIVIDAD"]),
        "funcion_catalogo": es.limpiar_para_mostrar(r["NOMFUNCION"]),
        "tema": r["_TEMA"],
        "horas": None if es.valor_nulo(r["NUMHORAS"]) else float(r["NUMHORAS"]),
        "periodicidad": es.texto_limpio(r["PERIODICIDAD"]),
        "nivel": es.texto_limpio(r["NIVELGRADO"]),
    }


def construir(carga: pd.DataFrame, evidencias_trayectoria: pd.DataFrame,
              mapa_siglas: dict, catalogo_materias: dict[str, str]) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve (evidencias, reporte, registros_no_considerados)."""
    from evidencias.investigacion.proyecto_investigacion import sigla_de_unidad

    siglas = {es.normalizar_para_comparar(k): v for k, v in mapa_siglas.items()}
    d = carga.copy()
    d["_FAMILIA"] = _familias(d["NOMFUNCION"])
    d["_CLASE"] = d["_FAMILIA"].map(clase_funcion)
    ya = _funciones_adicionales(evidencias_trayectoria)

    d["_MOTIVO"] = None
    d.loc[~d["ANIO"].between(1990, 2100), "_MOTIVO"] = MOTIVO_ANIO
    d.loc[(d["ANIO"] >= ANIO_INICIO_APROBACION) & (d["APROBADO"] != 1), "_MOTIVO"] = MOTIVO_NO_APROBADA
    d.loc[[_repetida(f, ya.get(int(p), set())) for f, p in zip(d["_FAMILIA"], d["IDPERSONA"])], "_MOTIVO"] = MOTIVO_YA_FUNCION
    d.loc[d["_CLASE"] == "SISTEMA", "_MOTIVO"] = MOTIVO_SISTEMA
    d.loc[d["_CLASE"] == "GENERICA", "_MOTIVO"] = MOTIVO_GENERICA
    d.loc[d["_CLASE"] == "PERMISO", "_MOTIVO"] = MOTIVO_PERMISO
    excluidos, v = d[d["_MOTIVO"].notna()], d[d["_MOTIVO"].isna()].copy()

    # Una sigla o un nombre de unidad no es tema: la unidad ya va aparte ("... (FCNM)")
    no_son_tema = ({es.normalizar_para_comparar(s) for s in mapa_siglas.values() if s}
                   | {es.normalizar_para_comparar(u) for u in d["NOMBREUNIDADCARGA"].dropna().unique()}
                   | {"FIMCP", "FIMCBOR", "FIEC", "FICT", "FCNM", "FCSH", "FCV", "FADCOM", "FIMCM", "EDCOM",
                      "ESPAE", "CIBE", "CELEX", "ICM", "ICF", "ICQ", "ESPOL"})
    resueltos = [resolver_codigos(tema(x, f, no_son_tema), catalogo_materias)
                 for x, f in zip(v["DESCFUNCION"], v["_FAMILIA"])]
    v["_TEMA"] = [t for t, _ in resueltos]
    v["_CODIGOS_MATERIA"] = [c for _, c in resueltos]
    v["_CLAVE_TEMA"] = v["_TEMA"].map(lambda t: es.normalizar_para_comparar(t) if t else "")
    personas_por_familia = v.groupby("_FAMILIA")["IDPERSONA"].nunique().to_dict()
    nombre_familia = v.groupby("_FAMILIA")["NOMFUNCION"].agg(_nombre_funcion).to_dict()

    filas = []
    for (idp, familia), g in v.groupby(["IDPERSONA", "_FAMILIA"], sort=False):
        clase = g["_CLASE"].iloc[0]
        if clase == "OBJETO":
            grupo_de = _agrupar_temas([k for k in g["_CLAVE_TEMA"].unique() if k])
            g = g.assign(_GRUPO=g["_CLAVE_TEMA"].map(lambda k: grupo_de.get(k, "")))
            subgrupos = [s for _, s in g.groupby("_GRUPO", sort=False)]
        else:
            subgrupos = [g]
        for s in subgrupos:
            s = s.sort_values(["ANIO", "IDPERIODO"])
            # Un tema por clave normalizada ("BIOLOGÍA" y "BIOLOGIA" son el mismo), el mas frecuente primero
            frecuencia = Counter(s["_TEMA"].dropna())
            por_clave: dict[str, str] = {}
            for t, _ in frecuencia.most_common():
                por_clave.setdefault(es.normalizar_para_comparar(t), t)
            temas = list(por_clave.values())
            unidades = []
            for u in es.unicos(s["NOMBREUNIDADCARGA"].map(es.limpiar_para_mostrar)):
                x = {"unidad": u, "sigla": sigla_de_unidad(u, siglas)}
                if x not in unidades:
                    unidades.append(x)
            funcion = nombre_familia[familia]
            atributos = {
                "funcion": funcion,
                "clase_funcion": "CON_OBJETO" if clase == "OBJETO" else "RUTINA",
                "tema": temas[0] if clase == "OBJETO" and temas else None,
                "temas": temas,
                "codigos_materia": es.unicos(c for cs in s["_CODIGOS_MATERIA"] for c in cs),
                "funciones_catalogo": es.unicos(s["NOMFUNCION"].map(es.limpiar_para_mostrar)),
                "actividades": es.unicos(ACTIVIDADES.get(a) for a in s["ACTIVIDAD"]),
                "unidades": unidades,
                "niveles": es.unicos(s["NIVELGRADO"].map(es.texto_limpio)),
                "anios": sorted(int(a) for a in s["ANIO"].unique()),
                "n_anios": int(s["ANIO"].nunique()),
                "horas_total": float(s["NUMHORAS"].fillna(0).sum()),
                "n_personas_misma_funcion": int(personas_por_familia[familia]),
                # el detalle guarda el tema ya limpio, nunca la descripcion original
                "detalle": [_detalle(r) for _, r in s.iterrows()],
                "_origen": {"fuente": ARCHIVO_CARGA_POLITECNICA.name, "n_filas": len(s)},
            }
            partes_tema = temas[:1] if clase == "OBJETO" else temas[:3]
            texto = funcion + (f" ({'; '.join(partes_tema)})" if partes_tema else "")
            unidades_txt = [es.quitar_espol(u["unidad"]) for u in unidades]
            unidades_txt = [f"{t} ({u['sigla']})" if u["sigla"] and u["sigla"] not in t.split() else t
                            for t, u in zip(unidades_txt, unidades) if t]
            if unidades_txt:
                texto += ", " + "; ".join(unidades_txt)
            clave_id = s["_CLAVE_TEMA"].iloc[0] if clase == "OBJETO" else ""
            filas.append(es.nueva_evidencia(
                es.generar_evidencia_id(PREFIJO_ID, idp, familia, clave_id), idp, TIPO_ID, texto, atributos,
            ))

    evidencias = es.a_dataframe(filas)
    # Ningun texto puede mencionar una situacion personal (maternidad, licencias...)
    sensibles = evidencias["texto"].str.contains(SITUACION_PERSONAL)
    if sensibles.any():
        raise ValueError(f"{int(sensibles.sum())} textos de ACTIVIDAD_CARGA mencionan situaciones personales: "
                         f"{evidencias.loc[sensibles, 'texto'].head(3).tolist()}")
    permiso = excluidos["_MOTIVO"] == MOTIVO_PERMISO
    no_considerados = pd.DataFrame({
        "persona_id": excluidos["IDPERSONA"].astype(int),
        "tipo_id": TIPO_ID,
        "motivo": excluidos["_MOTIVO"],
        # los permisos son datos sensibles: ni la funcion ni la descripcion se copian
        "descripcion": excluidos["NOMFUNCION"].map(es.limpiar_para_mostrar).where(~permiso),
        "anio": excluidos["ANIO"],
    })
    reporte = {
        "fuente": ARCHIVO_CARGA_POLITECNICA.name,
        "filas_poblacion": len(d),
        "funciones_catalogo": int(d["NOMFUNCION"].nunique()),
        "funciones_normalizadas": int(d["_FAMILIA"].nunique()),
        "filas_por_clase": d["_CLASE"].value_counts().to_dict(),
        "no_considerados_por_motivo": excluidos["_MOTIVO"].value_counts().to_dict(),
        "filas_sin_tema": int(v["_TEMA"].isna().sum()),
        "evidencias": len(filas),
        "evidencias_con_objeto": sum('"CON_OBJETO"' in f["atributos"] for f in filas),
        "evidencias_rutina": sum('"clase_funcion": "RUTINA"' in f["atributos"] for f in filas),
    }
    return evidencias, reporte, no_considerados
