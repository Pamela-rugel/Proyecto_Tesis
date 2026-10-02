"""Carga y consolidacion de la carga academica (materias dictadas) y de la poblacion de esta
seccion (personas con al menos una evidencia de trayectoria; misma regla que Formacion).

Fuentes (decision del usuario, 2026-09-30): cuatro extractos del mismo sistema que se solapan,
en `data/raw/`. Juntos cubren 1998-2026.
  - `carga_academica_1.csv` (1998-2026; el historial completo, pero sin TERM, nombre de unidad
    ni TIPOPROFESOR: esas columnas las completan los demas extractos cuando el curso esta en ellos)
  - `cargaacademicadisponible.csv` (2020-2026, extraido el 2026-08-31)
  - `carga_academica_2.csv` (2017-2026; sin TERM ni nombre de unidad)
  - `carga_academica_3.csv` (2019-2026)
Un mismo curso aparece en varios archivos: se consolida por persona + curso + periodo
(`consolidar`). Los datos personales (identificacion, nombre, correos) y la observacion libre
se descartan al leer y nunca llegan a las evidencias.
"""
from __future__ import annotations

import pandas as pd

from evidencias import esquema as es
from evidencias.formacion.fuentes import cargar_poblacion  # noqa: F401 (misma poblacion)
from evidencias.trayectoria.fuentes import DATA_DIR

# En orden de prioridad creciente: ante valores distintos del mismo curso gana el ultimo
ARCHIVOS_CARGA = [
    DATA_DIR / "raw" / "carga_academica_1.csv",
    DATA_DIR / "raw" / "cargaacademicadisponible.csv",
    DATA_DIR / "raw" / "carga_academica_2.csv",
    DATA_DIR / "raw" / "carga_academica_3.csv",
]
SALIDA_DIR = DATA_DIR / "evidencias" / "docencia"

_COLUMNAS_EXCLUIDAS = ["NUMEROIDENTIFICACION", "TIPOIDENTIFICACION", "NOMDOCENTE", "EMAIL",
                       "EMAILALTERNO", "OBSERVACION"]
CLAVE_CURSO = ["IDPERSONA", "IDCURSO", "IDPERIODO"]
# Unidades antiguas sin nombre en ninguna fuente, identificadas por el prefijo de sus codigos y
# sus materias; nombres confirmados por el usuario (2026-09-30), con el de la facultad ACTUAL
# cuando hay sucesora (como la fuente ya hace con ICHE -> FCSH y FIMP -> FIMCP):
#   15010 ICM (Instituto de Ciencias Matematicas), 15009 ICF (Fisicas), 15011 ICQ (Quimicas) -> FCNM
#   15006 FMAR y 15293 (acuicultura, naval, oceanografia): la antigua FIMCBOR -> FIMCM
# Sin sucesora clara, conservan su nombre: CELEX y los programas de tecnologia.
# 15012 (18 cursos de varias areas) queda sin unidad.
_FCNM = ("Facultad de Ciencias Naturales y Matemáticas", "FCNM")
_FIMCM = ("Facultad de Ingeniería Marítima y Ciencias del Mar", "FIMCM")
_UNIDADES_SIN_NOMBRE = {
    15010: _FCNM, 15009: _FCNM, 15011: _FCNM,
    15006: _FIMCM, 15293: _FIMCM,
    15255: ("Centro de Lenguas Extranjeras", "CELEX"),
    15258: ("Programa de Tecnología en Computación", "PROTCOM"),
    15257: ("Programa de Tecnología en Alimentos", "PROTAL"),
    15259: ("Programa de Tecnología Eléctrica y Electrónica", "PROTEL"),
    15260: ("Programa de Tecnología Mecánica", "PROTMEC"),
    15261: ("Programa de Tecnología Pesquera", None),
}
# Sufijo administrativo que la fuente agrega a algunos nombres ("SISTEMAS DE CONTROL -PERMISO UATH")
_SUFIJO_ADMINISTRATIVO = r"\s*-\s*PERMISO UATH\s*$"


def _termino_por_fechas(inicio: pd.Timestamp, fin: pd.Timestamp) -> str | None:
    """Termino de un periodo sin TERM en la fuente (archivos 1 y 2, anteriores a 2019), deducido
    con el patron de los periodos conocidos (acierta en los 23 que tienen TERM): el 1S empieza
    entre marzo y agosto y el 2S entre septiembre y febrero. Un periodo de menos de 100 dias es
    el intensivo (0S) si empieza entre febrero y abril; si no, un modulo corto (MOD: CELEX,
    programas de tecnologia). Sin fechas (2002-2003), no hay termino: se etiqueta solo el anio."""
    if pd.isna(inicio) or pd.isna(fin):
        return None
    if (fin - inicio).days < 100:
        return "0S" if 2 <= inicio.month <= 4 else "MOD"
    return "1S" if 3 <= inicio.month <= 8 else "2S"


def cargar_catalogo_materias() -> dict[str, str]:
    """Codigo de materia -> nombre (el mas frecuente en los cuatro extractos), sin el sufijo
    administrativo ni el parentesis final de malla o carrera ("ESTADISTICA (IIT95)" ->
    "ESTADISTICA"). Sirve para traducir los codigos que aparecen en la carga politecnica."""
    partes = [pd.read_csv(a, low_memory=False, usecols=["CODIGOMATERIA", "NOMMATERIA"]) for a in ARCHIVOS_CARGA]
    c = pd.concat(partes, ignore_index=True).dropna()
    c["CODIGOMATERIA"] = c["CODIGOMATERIA"].astype("string").str.strip().str.upper()
    nombre = (c["NOMMATERIA"].astype("string").str.replace(_SUFIJO_ADMINISTRATIVO, "", regex=True)
              .str.replace(r"\s*\([^()]*\)\s*$", "", regex=True).map(es.limpiar_para_mostrar))
    c = c.assign(NOMMATERIA=nombre).dropna()
    return c.groupby("CODIGOMATERIA")["NOMMATERIA"].agg(lambda s: s.value_counts().index[0]).to_dict()


def cargar_carga_academica(poblacion: set[int]) -> pd.DataFrame:
    partes = []
    for i, archivo in enumerate(ARCHIVOS_CARGA):
        d = pd.read_csv(archivo, low_memory=False)
        d = d.drop(columns=[c for c in _COLUMNAS_EXCLUIDAS if c in d.columns])
        partes.append(d.assign(_ARCHIVO=i))
    # Los catalogos de periodos y unidades se arman con TODOS los registros, antes de filtrar la
    # poblacion: un nombre de unidad puede venir solo en filas de personas fuera de ella (EDCOM:
    # 758 cursos en el archivo 2 sin nombre, que solo aparece en 2 filas del archivo 3).
    c = pd.concat(partes, ignore_index=True)
    for col in ("FECHA_INICIO", "FECHA_FIN"):
        c[col] = pd.to_datetime(c[col].astype("string").str[:10], format="%Y-%m-%d", errors="coerce")
    c["NOMMATERIA"] = c["NOMMATERIA"].astype("string").str.replace(_SUFIJO_ADMINISTRATIVO, "", regex=True)
    for col in ("CODUNIDAD", "TERM", "TIPOCURSO", "TIPOPROFESOR", "APROBADO", "CODIGOMATERIA"):
        if col in c.columns:
            c[col] = c[col].astype("string").str.strip()

    # Periodo: ANIO + TERM de los archivos que lo traen; si no, deducido de las fechas
    conocidos = c.dropna(subset=["TERM"]).groupby("IDPERIODO")["TERM"].first()
    fechas = c.groupby("IDPERIODO").agg(inicio=("FECHA_INICIO", "min"), fin=("FECHA_FIN", "max"))
    termino = {p: conocidos.get(p) or _termino_por_fechas(r.inicio, r.fin) for p, r in fechas.iterrows()}
    anio = c.groupby("IDPERIODO")["ANIO"].first()
    c["PERIODO"] = c["IDPERIODO"].map(lambda p: f"{int(anio[p])}-{termino[p]}" if termino.get(p) else str(anio[p]))
    c["TERMINO_DEDUCIDO"] = ~c["IDPERIODO"].isin(conocidos.index)

    # Unidad: nombre y codigo de los archivos que lo traen (el archivo 2 solo trae el ID)
    unidades = c.dropna(subset=["NOMBREUNIDAD"]).groupby("IDUNIDAD")[["NOMBREUNIDAD", "CODUNIDAD"]].first()
    for idunidad, (nombre, codigo) in _UNIDADES_SIN_NOMBRE.items():
        unidades.loc[idunidad] = [nombre, codigo]
    c["NOMBREUNIDAD"] = c["IDUNIDAD"].map(unidades["NOMBREUNIDAD"])
    c["CODUNIDAD"] = c["IDUNIDAD"].map(unidades["CODUNIDAD"])
    return consolidar(c[c["IDPERSONA"].isin(poblacion)].copy())


def consolidar(c: pd.DataFrame) -> pd.DataFrame:
    """Un curso (persona + curso + periodo) aparece en varios archivos, y a veces dos veces en el
    mismo archivo (el curso partido en dos tramos de fechas). Queda una fila:
      - valores del archivo de mayor prioridad (el mas reciente);
      - NUMREGISTRADOS: el mayor (el extracto antiguo trae 0 en los cursos aun sin matricula);
      - FECHA_INICIO la menor y FECHA_FIN la mayor de sus tramos;
      - APROBADO: 'S' si algun archivo lo aprueba.
    Las horas NO se usan: el mismo curso trae horas distintas en cada extracto (2.38 / 3.94 /
    55.6), no son fiables."""
    c = c.sort_values(CLAVE_CURSO + ["_ARCHIVO"])
    g = c.groupby(CLAVE_CURSO, sort=False)
    base = g.last()
    base["NUMREGISTRADOS"] = g["NUMREGISTRADOS"].max()
    base["FECHA_INICIO"] = g["FECHA_INICIO"].min()
    base["FECHA_FIN"] = g["FECHA_FIN"].max()
    base["APROBADO"] = g["APROBADO"].agg(lambda s: "S" if (s == "S").any() else es.texto_limpio(s.dropna().iloc[0]) if s.notna().any() else None)
    base["ARCHIVOS"] = g["_ARCHIVO"].agg(lambda s: sorted(set(int(x) + 1 for x in s)))
    return base.reset_index()
