"""Utilidades comunes de preprocesamiento.

Proyecto de tesis: Sistema de Generacion de Perfiles del Personal Docente y
Administrativo en ESPOL para la asignacion inteligente de tareas.

Funciones compartidas por los notebooks de notebooks/01_preprocesamiento para
leer los CSV crudos de data/raw, limpiarlos de forma consistente y guardar
el resultado en data/processed.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

NOTEBOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = NOTEBOOK_DIR.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# La mayoria de los CSV vienen exportados como UTF-8, pero algunos (p.ej.
# cargapolitecnicadisponible.csv) llegaron con acentos mal codificados.
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")

VALORES_NULOS = ["", " ", "NA", "N/A", "NULL", "null", "None", "nan"]


def leer_csv(nombre_archivo: str, **kwargs) -> pd.DataFrame:
    """Lee un CSV de data/raw probando distintas codificaciones."""
    ruta = RAW_DIR / nombre_archivo
    ultimo_error = None
    for enc in ENCODINGS:
        try:
            df = pd.read_csv(
                ruta,
                encoding=enc,
                keep_default_na=True,
                na_values=VALORES_NULOS,
                **kwargs,
            )
            print(f"Leido {nombre_archivo} con encoding={enc} -> "
                  f"{df.shape[0]} filas, {df.shape[1]} columnas")
            return df
        except (UnicodeDecodeError, UnicodeError) as e:
            ultimo_error = e
    raise ultimo_error


def limpiar_strings(df: pd.DataFrame, columnas=None) -> pd.DataFrame:
    """Recorta espacios y convierte celdas vacias/"nan" a NA en columnas de texto."""
    df = df.copy()
    columnas = columnas if columnas is not None else df.select_dtypes(include="object").columns
    for c in columnas:
        df[c] = df[c].astype("string").str.strip()
        df[c] = df[c].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    return df


def quitar_columnas_duplicadas(df: pd.DataFrame) -> pd.DataFrame:
    """Colapsa columnas repetidas (sufijos .1, .2, ... de exportaciones con joins)
    conservando la primera aparicion de cada nombre base."""
    df = df.copy()
    columnas_base = df.columns.str.replace(r"\.\d+$", "", regex=True)
    duplicadas = columnas_base[columnas_base.duplicated()].unique().tolist()
    df.columns = columnas_base
    mask = ~df.columns.duplicated(keep="first")
    if duplicadas:
        print(f"Columnas duplicadas colapsadas (se conserva la primera aparicion): {duplicadas}")
    return df.loc[:, mask]


def quitar_columnas_vacias(df: pd.DataFrame, umbral: float = 0.99) -> pd.DataFrame:
    """Elimina columnas con proporcion de nulos >= umbral (por defecto 99%)."""
    nulos = df.isna().mean()
    a_eliminar = nulos[nulos >= umbral].index.tolist()
    if a_eliminar:
        print(f"Columnas eliminadas por tener >= {umbral * 100:.0f}% de nulos: {a_eliminar}")
    return df.drop(columns=a_eliminar)


def rellenar_categoricas_nulas(df: pd.DataFrame, columnas, valor: str = "DESCONOCIDA") -> pd.DataFrame:
    """Rellena con `valor` (por defecto DESCONOCIDA) los nulos de columnas de
    texto/categoricas de la lista que existan en el DataFrame (ej. nombres de
    unidad que llegan vacios en el CSV crudo). Util para que esas columnas no
    se eliminen luego por `quitar_columnas_vacias` cuando la mayoria de sus
    valores estan vacios."""
    df = df.copy()
    for c in columnas:
        if c in df.columns:
            df[c] = df[c].fillna(valor)
    return df


def quitar_columnas_constantes(df: pd.DataFrame, excluir=None) -> pd.DataFrame:
    """Elimina columnas con un unico valor no nulo (no aportan informacion)."""
    excluir = set(excluir or [])
    constantes = [c for c in df.columns if c not in excluir and df[c].nunique(dropna=True) <= 1]
    if constantes:
        print(f"Columnas eliminadas por ser constantes: {constantes}")
    return df.drop(columns=constantes)


_DB2_TS = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{2})\.(\d{2})\.(\d{2})\.(\d+)$")


def parsear_fecha(serie: pd.Series) -> pd.Series:
    """Convierte a datetime fechas simples (YYYY-MM-DD) o timestamps estilo
    DB2 (YYYY-MM-DD-HH.MM.SS.ffffff).

    Años fuera de [1950, año_actual+2] se tratan como NaT: son error de captura (un
    digito perdido, p.ej. "216-03-10" en vez de "2016-03-10", visto en
    FECHADESVINCULACION de historial_laboral) y no fechas reales - producen antiguedades
    absurdas (cientos de años) si se dejan pasar, en vez de fallar de forma visible."""
    s = serie.astype("string")
    normalizado = s.str.replace(_DB2_TS, r"\1 \2:\3:\4.\5", regex=True)
    fechas = pd.to_datetime(normalizado, errors="coerce")
    anio_max = pd.Timestamp.today().year + 2
    fuera_de_rango = fechas.notna() & ((fechas.dt.year < 1950) | (fechas.dt.year > anio_max))
    return fechas.mask(fuera_de_rango)


def a_entero(serie: pd.Series) -> pd.Series:
    """Castea a entero nullable (Int64), tolerante a texto no numerico."""
    return pd.to_numeric(serie, errors="coerce").astype("Int64")


def reparar_texto_latin1(serie: pd.Series) -> pd.Series:
    """Corrige el patron de corrupcion conocido en cargapolitecnicadisponible.csv,
    donde la 'i' con tilde quedo grabada como caracter de reemplazo + guion suave."""
    return serie.astype("string").str.replace("�\xad", "i", regex=False)


def castear_fechas(df: pd.DataFrame, columnas) -> pd.DataFrame:
    """Aplica parsear_fecha a cada columna de la lista que exista en el DataFrame."""
    df = df.copy()
    for c in columnas:
        if c in df.columns:
            df[c] = parsear_fecha(df[c])
    return df


def castear_enteros(df: pd.DataFrame, columnas) -> pd.DataFrame:
    """Aplica a_entero a cada columna de la lista que exista en el DataFrame."""
    df = df.copy()
    for c in columnas:
        if c in df.columns:
            df[c] = a_entero(df[c])
    return df


def decodificar_experiencia_externa(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas descriptivas para los codigos de experenciaexterna.csv
    usando data/raw/diccionarioexperienciaexterna.txt.

    Nota: ROLACADEMICO trae el codigo de 2 letras (PR/FA/PA/AY); la columna
    ROLACADEMICOEXPERIENCIA ya viene con el texto completo en el CSV de origen,
    por lo que no requiere decodificacion.
    """
    df = df.copy()
    if "CATEXPERIENCIA" in df.columns:
        df["CATEXPERIENCIA_DESC"] = df["CATEXPERIENCIA"].map(CATEGORIA_EXPERIENCIA)
    if "ROLACADEMICO" in df.columns:
        df["ROLACADEMICO_DESC"] = df["ROLACADEMICO"].map(ROL_ACADEMICO_EXPERIENCIA)
    return df


def detectar_outliers_iqr(df: pd.DataFrame, columna: str, factor: float = 1.5):
    """Detecta valores atipicos de una columna numerica con el metodo del rango
    intercuartilico (IQR): atipico si esta por debajo de Q1 - factor*IQR o por
    encima de Q3 + factor*IQR (factor=1.5 es el criterio clasico de boxplot).

    Devuelve (mask, limite_inferior, limite_superior), donde `mask` es una
    Serie booleana alineada con `df` (True = atipico). Uso tipico para EDA:
    `mask, li, ls = pc.detectar_outliers_iqr(df, 'RMU')` y luego
    `df[mask].sort_values('RMU')` para inspeccionar los casos mas raros.
    """
    serie = df[columna]
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    limite_inferior = q1 - factor * iqr
    limite_superior = q3 + factor * iqr
    mask = (serie < limite_inferior) | (serie > limite_superior)
    return mask, limite_inferior, limite_superior


def resumen(df: pd.DataFrame, nombre: str = "") -> None:
    """Imprime un resumen rapido: dimensiones, duplicados y nulos por columna."""
    print(f"--- Resumen {nombre} ---")
    print(f"Dimensiones: {df.shape[0]} filas x {df.shape[1]} columnas")
    print(f"Filas duplicadas: {df.duplicated().sum()}")
    nulos = df.isna().mean().sort_values(ascending=False)
    nulos = nulos[nulos > 0]
    if len(nulos):
        print("Columnas con nulos (%):")
        print((nulos * 100).round(1))
    else:
        print("Sin columnas con valores nulos.")


def guardar_procesado(df: pd.DataFrame, nombre_salida: str) -> Path:
    """Guarda el DataFrame procesado en data/processed como CSV UTF-8."""
    ruta = PROCESSED_DIR / nombre_salida
    df.to_csv(ruta, index=False, encoding="utf-8-sig")
    print(f"Guardado: {ruta} ({df.shape[0]} filas x {df.shape[1]} columnas)")
    return ruta

# --- Mapeo booleano para variables binarias institucionales (S/N) --------------
MAPEO_BOOLEANO = {
    "S": 1,
    "SI": 1,
    "1": 1,
    "N": 0,
    "NO": 0,
    "0": 0,
}


def convertir_sn_a_binario( df: pd.DataFrame, columnas: list[str] | None = None, rellenar_nulos_con_cero: bool = True) -> pd.DataFrame:
    """Convierte columnas binarias con valores 'S'/'N' (o 'SI'/'NO') a enteros (1/0).
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame de entrada.
    columnas : list[str] | None, optional
        Lista de nombres de columnas a transformar. Si es None, busca 
        automaticamente columnas que contengan unicamente patrones 'S', 'N' o nulos.
    rellenar_nulos_con_cero : bool, default True
        Si es True, los valores nulos o no reconocidos se imputan como 0. 
        Si es False, se conservan como NA usando el tipo Int64.
        
    Returns
    -------
    pd.DataFrame
        DataFrame con las columnas convertidas a 1 y 0.
    """
    df = df.copy()
    
    # Si no se pasan columnas explicitas, inferir columnas tipo S/N
    if columnas is None:
        columnas = []
        for c in df.columns:
            valores_unicos = set(df[c].dropna().astype(str).str.strip().str.upper().unique())
            if valores_unicos and valores_unicos.issubset({"S", "N", "SI", "NO", "1", "0"}):
                columnas.append(c)

    columnas_transformadas = []
    for c in columnas:
        if c in df.columns:
            serie_limpia = df[c].astype(str).str.strip().str.upper()
            serie_mapeada = serie_limpia.map(MAPEO_BOOLEANO)
            
            if rellenar_nulos_con_cero:
                df[c] = serie_mapeada.fillna(0).astype("int64")
            else:
                df[c] = serie_mapeada.astype("Int64")
                
            columnas_transformadas.append(c)

    if columnas_transformadas:
        print(f"Columnas S/N convertidas a binario (1/0): {columnas_transformadas}")
        
    return df

# --- Diccionario de codigos para experenciaexterna.csv -----------------------
# Fuente: data/raw/diccionarioexperienciaexterna.txt
CATEGORIA_EXPERIENCIA = {
    "PC": "POR CLASIFICAR",
    "AD": "ADMINISTRATIVA",
    "AC": "ACADEMICA",
}

ROL_ACADEMICO_EXPERIENCIA = {
    "PR": "PROFESOR",
    "FA": "FACILITADOR",
    "PA": "PERSONAL DE APOYO",
    "AY": "AYUDANTE",
}


# --- Graficos exploratorios ---------------------------------------------------
COLOR_PRINCIPAL = "#3b7dd8"


def grafico_barras(serie: pd.Series, titulo: str = "", top: int = 15,
                    horizontal: bool = True, ax=None):
    """Grafica el conteo de valores mas frecuentes de una columna categorica."""
    import matplotlib.pyplot as plt

    conteo = serie.dropna().astype(str).str.strip()
    conteo = conteo[conteo != ""].value_counts().head(top)
    if ax is None:
        _, ax = plt.subplots(figsize=(8, max(3, 0.35 * len(conteo))))
    if horizontal:
        conteo.sort_values().plot(kind="barh", ax=ax, color=COLOR_PRINCIPAL)
    else:
        conteo.plot(kind="bar", ax=ax, color=COLOR_PRINCIPAL)
    ax.set_title(titulo)
    plt.tight_layout()
    return ax


def grafico_histograma(serie: pd.Series, titulo: str = "", bins: int = 30,
                        recorte_percentil: float | None = 0.99, ax=None):
    """Grafica la distribucion de una columna numerica (recorta la cola larga
    de valores extremos solo para visualizar, sin alterar los datos)."""
    import matplotlib.pyplot as plt

    datos = pd.to_numeric(serie, errors="coerce").dropna()
    if recorte_percentil is not None and len(datos):
        limite = datos.quantile(recorte_percentil)
        datos = datos[datos <= limite]
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))
    ax.hist(datos, bins=bins, color=COLOR_PRINCIPAL, edgecolor="white")
    ax.set_title(titulo)
    plt.tight_layout()
    return ax


def grafico_por_anio(serie_fecha: pd.Series, titulo: str = "", ax=None):
    """Grafica el numero de registros por año a partir de una columna de fecha."""
    import matplotlib.pyplot as plt

    anios = pd.to_datetime(serie_fecha, errors="coerce").dt.year.dropna().astype(int)
    conteo = anios.value_counts().sort_index()
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4))
    conteo.plot(kind="bar", ax=ax, color=COLOR_PRINCIPAL)
    ax.set_title(titulo)
    ax.set_xlabel("Año")
    ax.set_ylabel("N.º de registros")
    plt.tight_layout()
    return ax


# --- Diccionario de codigos para historialaboralpersonas.csv -----------------
TIPO_EMPLEADO = {
    "AA": "ADMINISTRATIVO",
    "DD": "DOCENTE",
}

# LOES: Ley Organica de Educacion Superior. LOSEP: Ley Organica de Servicio
# Publico (Ecuador). CT: Codigo de Trabajo. 0: contrato civil (sin relacion
# de dependencia).
REGIMEN_LABORAL = {
    0: "CONTRATO CIVIL",
    7: "LOSEP - LEY ORGANICA DE SERVICIO PUBLICO",
    8: "LOES - LEY ORGANICA DE EDUCACION SUPERIOR",
    9: "CT - CODIGO DE TRABAJO",
}

# Nombres legibles de CATEGORIA_CARGO (ver clasificar_categoria_cargo/DEC-004), reutilizados
# tanto en 06_clustering.ipynb (PERFIL_NOMBRES por CLUSTER, ver notebooks/08_dashboard/lib.py)
# como en la construccion del documento semantico (07_embeddings) y la ficha de persona del
# dashboard - una sola fuente de verdad para no duplicar el diccionario en tres lugares.
NOMBRES_CATEGORIA_CARGO = {
    "AUTORIDAD_ACADEMICA_SUPERIOR": "Autoridad académica (Rector/Vicerrector/Decano/Subdecano)",
    "DOCENTE_TITULAR_CARRERA": "Docente titular de carrera",
    "DOCENTE_NO_TITULAR_OCASIONAL": "Docente no titular / ocasional",
    "DOCENTE_CONTRATADO_SERVICIOS_CIVILES": "Docente contratado (servicios civiles)",
    "DOCENTE_HONORARIO_ESPECIAL": "Docente honorario / invitado",
    "DOCENTE_PREPOLITECNICO": "Docente pre-politécnico",
    "DOCENTE_INVESTIGADOR": "Docente investigador",
    "DIRECCION_ACADEMICA_INTERMEDIA": "Dirección académica intermedia",
    "AYUDANTE_ACADEMICO_JUNIOR": "Ayudante académico junior",
    "TECNICO_DOCENTE_APOYO": "Técnico docente / de investigación",
    "AUTORIDAD_ADMINISTRATIVA_SUPERIOR": "Autoridad administrativa (Gerente/Director)",
    "JEFATURA_SUPERVISION_OPERATIVA": "Jefatura / supervisión operativa",
    "PROFESIONAL_ANALISTA": "Profesional / Analista",
    "PROFESIONAL_ESPECIALIZADO_TECNICO": "Profesional especializado (abogado, psicólogo, etc.)",
    "ASISTENCIA_SECRETARIAL_OFICINA": "Asistencia secretarial / oficina",
    "AUXILIAR_AYUDANTE_OPERATIVO": "Auxiliar / ayudante operativo",
    "TECNICO_OPERATIVO_MANTENIMIENTO": "Técnico operativo / mantenimiento",
    "SERVICIOS_GENERALES_OFICIOS": "Servicios generales / oficios",
    "CONTRATO_SERVICIOS_PROFESIONALES_PROYECTO": "Contrato de servicios profesionales (proyecto)",
    "TRIBUNAL_COMISION_ACADEMICA": "Tribunal / comisión académica",
    "ACTIVIDAD_ACADEMICA_DESDE_ADMINISTRATIVO": "Actividad académica desde cargo administrativo",
    "OTROS_AA": "Otros (administrativo)",
    "OTROS_DD": "Otros (docente)",
}


def decodificar_historial_laboral(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas descriptivas para los codigos de historialaboralpersonas.csv:
    TIPOEMPLEADO (AA/DD) e IDREGIMENLABORAL (0/7/8/9)."""
    df = df.copy()
    if "TIPOEMPLEADO" in df.columns:
        df["TIPOEMPLEADO_DESC"] = df["TIPOEMPLEADO"].map(TIPO_EMPLEADO)
    if "IDREGIMENLABORAL" in df.columns:
        df["IDREGIMENLABORAL_DESC"] = df["IDREGIMENLABORAL"].map(REGIMEN_LABORAL)
    return df


def _continuacion_por_corte_de_mes(fin_actual: pd.Timestamp, inicio_siguiente: pd.Timestamp) -> bool:
    """Tolerancia de brecha corta replicada del sistema origen (historia laboral
    continua): dos contratos se tratan como continuos si el primero termina
    exactamente un dia antes de que inicie el segundo, o si termina en los
    ultimos 3 dias de un mes y el segundo inicia el dia 1 del mes calendario
    siguiente (corte administrativo tipico de fin de mes)."""
    if fin_actual + pd.Timedelta(days=1) == inicio_siguiente:
        return True
    es_fin_de_mes = fin_actual.day >= fin_actual.days_in_month - 2
    primer_dia_mes_siguiente = fin_actual + pd.offsets.MonthBegin(1)
    es_inicio_mes_siguiente = (
        inicio_siguiente.day == 1
        and inicio_siguiente.month == primer_dia_mes_siguiente.month
        and inicio_siguiente.year == primer_dia_mes_siguiente.year
    )
    return es_fin_de_mes and es_inicio_mes_siguiente


# Codigos de ESTADOCONTRATO cuyo contrato sigue abierto en el sistema origen
# (ACTIVO, POR EJECUTARSE) independientemente de si FECHAFINCONTRATO/FECHADESVINCULACION
# ya vienen pobladas. Ver docstring de `calcular_fecha_fin_efectiva` para el bug que esto
# corrige: RRHH graba casi siempre una fecha fin planificada (fin de periodo academico o
# de año fiscal) incluso en contratos vigentes -  de 73,915 registros, FECHAFINCONTRATO
# es nula en solo el 1.9%, y el 54% de los contratos con ESTADOCONTRATO='AA' (ACTIVO)
# tienen FECHAFINCONTRATO poblada (a veces incluso en el futuro respecto a la fecha de
# analisis). Usar solo "FECHAFINCONTRATO vacia = vigente" subestima la vigencia real.
_ESTADOS_CONTRATO_ABIERTOS = {"AA", "PE"}

# Codigos de ESTADOCONTRATO cuyo contrato ya esta cerrado en el sistema origen
# (FINALIZADO) aunque FECHAFINCONTRATO/FECHADESVINCULACION vengan ambas vacias. Sin esto,
# un contrato FF sin fecha quedaba tratado igual que uno realmente vigente (caso real:
# IDCONTRATOLABORAL 3194, persona 865, ESTADOCONTRATO='FF' desde 2015-01-01 sin fecha de
# cierre - "infectaba" el tramo de CATEGORIA_CARGO hacia adelante indefinidamente pese a
# que la persona no tenia ningun contrato activo desde 2025-12-31). 58 contratos de 43
# personas en esta situacion (medido en historial_laboral_personas.csv).
_ESTADOS_CONTRATO_CERRADOS = {"FF"}


def calcular_fecha_fin_efectiva(df: pd.DataFrame) -> pd.Series:
    """Calcula la fecha fin efectiva de cada contrato: `FECHADESVINCULACION` si existe,
    si no `FECHAFINCONTRATO`, si ninguna existe el contrato esta vigente (NaT) — salvo la
    correccion por `ESTADOCONTRATO` descrita abajo.

    Si `ESTADOCONTRATO` existe en `df`, se sobreescribe a NaT (vigente) cuando el
    contrato esta en un estado abierto en el sistema origen (`_ESTADOS_CONTRATO_ABIERTOS`:
    AA=ACTIVO, PE=POR EJECUTARSE), sin importar si `FECHAFINCONTRATO`/
    `FECHADESVINCULACION` ya vienen pobladas — ese es el caso mas frecuente en los datos
    (ver comentario de `_ESTADOS_CONTRATO_ABIERTOS`) y sin esta correccion se subestima
    fuertemente quien sigue vigente (81% de las personas cuyo ultimo contrato es ACTIVO
    quedaban marcadas incorrectamente como no vigentes).

    En sentido contrario: si `ESTADOCONTRATO` esta en un estado cerrado
    (`_ESTADOS_CONTRATO_CERRADOS`: FF=FINALIZADO) pero no quedo ninguna fecha de cierre
    real, se usa como fecha de cierre la `FECHAINICIOCONTRATO` del contrato siguiente de
    esa misma persona (requiere `IDPERSONA`) — o, si no hay contrato siguiente (es el
    ultimo de la persona), su propia `FECHAINICIOCONTRATO` (duracion 0: conservador, nunca
    lo deja vigente por defecto). Sin esto, un FF sin fecha se trataba como vigente para
    siempre y arrastraba esa vigencia falsa a cualquier tramo que lo incluyera.

    Devuelve tambien (ver `calcular_fecha_fin_efectiva_con_flag`) si el registro esta en
    un estado abierto (`_ESTADOS_CONTRATO_ABIERTOS`) — lo usan `construir_tramos_rol` y
    `calcular_periodos_continuos` para que un nombramiento estructural abierto (AA/PE,
    caso real: autoridades academicas superiores, persona 1216 = rectora, IDCONTRATOLABORAL
    22351 desde 2022-11-13 sin fecha de cierre) no vuelva a cerrarse por actos puntuales FF
    posteriores del mismo cargo/categoria (encargos de despacho, delegaciones de firma:
    decenas de contratos FF de 1-20 dias que se repiten indefinidamente sobre el mismo
    nombramiento y nunca vuelven a AA). Confirmado con el usuario como interpretacion de
    negocio: un AA/PE nunca se cierra por un FF posterior de la misma categoria.
    """
    fin_efectivo = (
        df["FECHADESVINCULACION"].copy()
        if "FECHADESVINCULACION" in df.columns
        else pd.Series(pd.NaT, index=df.index)
    )
    if "FECHAFINCONTRATO" in df.columns:
        fin_efectivo = fin_efectivo.fillna(df["FECHAFINCONTRATO"])
    if "ESTADOCONTRATO" in df.columns:
        fin_efectivo = fin_efectivo.mask(df["ESTADOCONTRATO"].isin(_ESTADOS_CONTRATO_ABIERTOS))
        if "IDPERSONA" in df.columns and "FECHAINICIOCONTRATO" in df.columns:
            sin_fecha_pero_cerrado = fin_efectivo.isna() & df["ESTADOCONTRATO"].isin(_ESTADOS_CONTRATO_CERRADOS)
            if sin_fecha_pero_cerrado.any():
                orden = df["FECHAINICIOCONTRATO"].rank(method="first")
                siguiente_inicio = (
                    df.assign(_ORDEN=orden)
                    .sort_values(["IDPERSONA", "_ORDEN"])
                    .groupby("IDPERSONA")["FECHAINICIOCONTRATO"]
                    .shift(-1)
                )
                siguiente_inicio = siguiente_inicio.reindex(df.index)
                fallback = siguiente_inicio.fillna(df["FECHAINICIOCONTRATO"])
                fin_efectivo = fin_efectivo.mask(sin_fecha_pero_cerrado, fallback)
    return fin_efectivo


def _es_estado_abierto(df: pd.DataFrame) -> pd.Series:
    """Mascara booleana: True si `ESTADOCONTRATO` esta en `_ESTADOS_CONTRATO_ABIERTOS`
    (AA/PE). Si la columna no existe, devuelve todo False (no hay forma de saberlo)."""
    if "ESTADOCONTRATO" in df.columns:
        return df["ESTADOCONTRATO"].isin(_ESTADOS_CONTRATO_ABIERTOS)
    return pd.Series(False, index=df.index)


def calcular_periodos_continuos(df: pd.DataFrame) -> pd.DataFrame:
    """Fusiona los contratos de historialaboralpersonas.csv en periodos continuos
    de vinculacion por IDPERSONA (replica AuxiliarObtenerHistoriaContinua del
    sistema origen).

    Reglas:
    - La fecha fin efectiva de cada contrato se calcula con
      `calcular_fecha_fin_efectiva` (ver su docstring para la correccion de vigencia
      basada en `ESTADOCONTRATO`, no solo en fechas).
    - Los contratos de cada persona se procesan ordenados por
      FECHAINICIOCONTRATO. Dos contratos consecutivos se fusionan en el mismo
      periodo si se solapan (incluye un contrato totalmente contenido en el
      periodo actual, que simplemente se ignora sin retroceder el fin), son
      exactamente contiguos, o dejan una brecha corta tolerada por
      `_continuacion_por_corte_de_mes`.
    - Un periodo vigente (sin fecha fin) se preserva como vigente al fusionar:
      una fecha fin real nunca reemplaza una vigencia ya detectada.
    - Cualquier otra brecha cierra el periodo actual y abre uno nuevo.

    Nota: a diferencia de `construir_tramos_rol`, esta funcion fusiona TODO el historial
    de vinculacion de la persona sin importar `CATEGORIA_CARGO` — por eso NO aplica la
    proteccion "un AA/PE no se cierra por un FF posterior" (a diferencia de
    `construir_tramos_rol`): un AA/PE antiguo de un cargo puede coexistir con un FF real
    y posterior de un cargo totalmente distinto (caso real: persona 988, AA vigente como
    Profesor Titular hasta 2026-10-01 + un contrato de "Prestacion Servicios
    Profesionales" ya cerrado en 2026-01-25 — aplicar la proteccion aqui habria dejado
    vigentes a 53 personas cuyo ultimo vinculo con ESPOL, de cualquier tipo, ya cerro
    realmente). La proteccion solo es segura cuando ya se segmento por categoria de
    cargo, como hace `construir_tramos_rol`.

    Requiere que `df` ya tenga IDPERSONA, IDCONTRATOLABORAL, FECHAINICIOCONTRATO,
    FECHAFINCONTRATO y FECHADESVINCULACION casteadas a fecha/entero (ver
    `castear_fechas` / `castear_enteros`).

    Devuelve un dataframe con una fila por periodo continuo: IDPERSONA,
    PERIODO_INICIO, PERIODO_FIN (NaT si vigente), PERIODO_VIGENTE,
    PERIODO_DURACION_DIAS, N_CONTRATOS, IDCONTRATOLABORAL (contratos incluidos,
    separados por coma).
    """
    requeridas = ["IDPERSONA", "IDCONTRATOLABORAL", "FECHAINICIOCONTRATO"]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise KeyError(f"Faltan columnas requeridas: {faltantes}")

    trabajo = df.copy()
    trabajo["_FECHAFIN_EFECTIVA"] = calcular_fecha_fin_efectiva(trabajo)
    trabajo = trabajo.sort_values(["IDPERSONA", "FECHAINICIOCONTRATO"], kind="stable")

    periodos = []
    for id_persona, grupo in trabajo.groupby("IDPERSONA", sort=False):
        actual = None
        for _, fila in grupo.iterrows():
            inicio = fila["FECHAINICIOCONTRATO"]
            fin = fila["_FECHAFIN_EFECTIVA"]
            if pd.isna(inicio):
                continue

            if actual is None:
                actual = {
                    "IDPERSONA": id_persona,
                    "PERIODO_INICIO": inicio,
                    "PERIODO_FIN": fin,
                    "contratos": [fila["IDCONTRATOLABORAL"]],
                }
                continue

            fin_actual_cmp = pd.Timestamp.max if pd.isna(actual["PERIODO_FIN"]) else actual["PERIODO_FIN"]

            if fin_actual_cmp >= inicio:
                # PERIODO_FIN = NaT (vigente) solo si ESTE contrato (el mas reciente por
                # FECHAINICIOCONTRATO dentro del periodo, por el orden ascendente) sigue
                # vigente. Si ya tiene fecha de cierre real, el periodo cierra en el maximo
                # entre su fin anterior y este fin nuevo — nunca retrocede por contratos
                # "paraguas" con contratos cortos anidados, pero tampoco queda bloqueado en
                # NaT para siempre por un contrato intermedio sin fecha de cierre si el mas
                # reciente ya cerro (mismo fix que construir_tramos_rol, DEC-023).
                if pd.isna(fin):
                    actual["PERIODO_FIN"] = fin
                elif not pd.isna(actual["PERIODO_FIN"]):
                    actual["PERIODO_FIN"] = max(actual["PERIODO_FIN"], fin)
                else:
                    actual["PERIODO_FIN"] = fin
                actual["contratos"].append(fila["IDCONTRATOLABORAL"])
            elif not pd.isna(actual["PERIODO_FIN"]) and _continuacion_por_corte_de_mes(actual["PERIODO_FIN"], inicio):
                actual["PERIODO_FIN"] = fin
                actual["contratos"].append(fila["IDCONTRATOLABORAL"])
            else:
                periodos.append(actual)
                actual = {
                    "IDPERSONA": id_persona,
                    "PERIODO_INICIO": inicio,
                    "PERIODO_FIN": fin,
                    "contratos": [fila["IDCONTRATOLABORAL"]],
                }
        if actual is not None:
            periodos.append(actual)

    columnas = [
        "IDPERSONA", "PERIODO_INICIO", "PERIODO_FIN", "PERIODO_VIGENTE",
        "PERIODO_DURACION_DIAS", "N_CONTRATOS", "IDCONTRATOLABORAL",
    ]
    if not periodos:
        return pd.DataFrame(columns=columnas)

    resultado = pd.DataFrame(periodos)
    resultado["PERIODO_VIGENTE"] = resultado["PERIODO_FIN"].isna()
    fin_para_duracion = resultado["PERIODO_FIN"].fillna(pd.Timestamp.today().normalize())
    resultado["PERIODO_DURACION_DIAS"] = (fin_para_duracion - resultado["PERIODO_INICIO"]).dt.days + 1
    resultado["N_CONTRATOS"] = resultado["contratos"].apply(len)
    resultado["IDCONTRATOLABORAL"] = resultado["contratos"].apply(lambda xs: ",".join(str(x) for x in xs))
    resultado = resultado.drop(columns="contratos")
    return resultado[columnas].reset_index(drop=True)


# --- Taxonomia de rol (CATEGORIA_CARGO) para analisis longitudinal/trayectorias ---
# Ver context/DECISION_LOG.md (decision sobre taxonomia de CARGO) para el detalle de
# como se construyo y valido esta taxonomia con el usuario. Resumen:
# - Se clasifica por separado dentro de cada rama de TIPOEMPLEADO_DESC (nunca se
#   comparten reglas entre AA y DD) para evitar fugas por substring (p.ej. "DIRECTOR"
#   contiene "RECTOR").
# - Los rotulos legado pre-reforma LOES ("Profesor Agregado/Auxiliar/Principal", sin la
#   palabra "Titular") se fusionan en DOCENTE_TITULAR_CARRERA: se confirmo por
#   continuidad de persona que 95-100% de quienes tuvieron esos cargos despues
#   aparecen con el cargo "Titular" equivalente.
# - Los rotulos legado genericos y ambiguos ("Profesor Pregrado", "Profesor", "Docente",
#   "Docente(Grado)", todos anteriores a 2015) se resuelven por continuidad de persona:
#   si esa persona en algun momento tuvo un cargo que resuelve a DOCENTE_TITULAR_CARRERA,
#   sus registros ambiguos se asignan a DOCENTE_TITULAR_CARRERA; si no, a
#   DOCENTE_NO_TITULAR_OCASIONAL (decision de negocio confirmada por el usuario).
# - Los registros administrativos (TIPOEMPLEADO_DESC=ADMINISTRATIVO) cuyo CARGO suena a
#   docencia ("Profesor...", "Docente...") se marcan como ANOMALIA_CARGO_DOCENTE_EN_AA y
#   se excluyen de las reglas de deteccion de transicion (ES_RUIDO_CALIDAD_DATOS=True):
#   el usuario confirmo que es inconsistencia de captura de datos, no una figura
#   contractual real a modelar.
_LEGACY_TITULAR_EXACTO = {"PROFESOR AGREGADO", "PROFESOR AUXILIAR", "PROFESOR PRINCIPAL"}
_LEGACY_TITULAR_PREFIJO = ("PROFESOR AGREGADO ", "PROFESOR AUXILIAR ", "PROFESOR PRINCIPAL ")
_LEGACY_AMBIGUO_DD = {"PROFESOR PREGRADO", "PROFESOR", "DOCENTE", "DOCENTE(GRADO)"}

REGLAS_CATEGORIA_CARGO_DD = [
    ("AUTORIDAD_ACADEMICA_SUPERIOR", r"^RECTOR|^VICERRECTOR|^DECANO|^SUBDECANO"),
    ("DOCENTE_NO_TITULAR_OCASIONAL", r"NO TITULAR|OCASIONAL|ACCIDENTAL"),
    ("DOCENTE_TITULAR_CARRERA", r"TITULAR"),
    ("DIRECCION_ACADEMICA_INTERMEDIA", r"DIRECTOR|SUBDIRECTOR|COORDINADOR"),
    ("DOCENTE_PREPOLITECNICO", r"PRE-POLIT.CNICO|PRE POLIT.CNICO"),
    ("DOCENTE_HONORARIO_ESPECIAL", r"HONORARIO|INVITADO|EM.RITO|ARMADA|PASANTIAS|DANZA"),
    ("DOCENTE_CONTRATADO_SERVICIOS_CIVILES",
     r"PRESTACI.N|CONTRATO CIVIL|DOCENTE POSGRADO|PROFESOR POSGRADO|SERVICIOS PROFESIONALES|"
     r"NIVELACI.N|DICTADO DE MATERIA|EJECUCI.N DE"),
    ("TECNICO_DOCENTE_APOYO",
     r"^T.CNICO|ASISTENTE DE (INVESTIGACI.N|LABORATORIO)|AUXILIAR DE INVESTIGACI.N|ANALISTA PROGRAMADOR"),
    ("DOCENTE_INVESTIGADOR", r"INVESTIGADOR"),
    ("AYUDANTE_ACADEMICO_JUNIOR", r"AYUDANTE ACAD.MICO|INSTRUCTOR|AYUDANTE ADMINISTRATIVO"),
]

REGLAS_CATEGORIA_CARGO_AA = [
    # Se evalua primero: cargo suena a docencia pero el registro esta tipificado
    # como ADMINISTRATIVO. No se fuerza a una categoria docente ni administrativa
    # "normal" - el usuario confirmo tratarlo como ruido de captura de datos.
    ("ANOMALIA_CARGO_DOCENTE_EN_AA", r"^PROFESOR|^DOCENTE"),
    ("ACTIVIDAD_ACADEMICA_DESDE_ADMINISTRATIVO",
     r"DICTADO DE|DIRECCI.N DE.*TESIS|PARTICIPACI.N EN.*TESIS|VOCAL.*TESIS|VOCAL.*TRIBUNAL|"
     r"FACILITADOR.*FORMACI.N DOCENTE|CONSEJERO ACAD.MICO|^CAPACITACION$|^CAPACITADOR$|"
     r"CURSO DE METODOLOG.A|ENTRENADOR DE (DEPORTE|A.R.BICOS|ARTES MARCIALES|TENIS)|^ENTRENADOR$"),
    ("TRIBUNAL_COMISION_ACADEMICA", r"TRIBUNAL|^INSTRUCTOR$"),
    ("AUTORIDAD_ADMINISTRATIVA_SUPERIOR", r"^GERENTE|^SUBGERENTE|^VICEPRESIDENTE|^DIRECTOR|^SUBDIRECTOR"),
    ("JEFATURA_SUPERVISION_OPERATIVA", r"^JEFE|^COORDINADOR|^COORDINACI.N|^SUPERVISOR|TESORERO|GUARDALMAC.N"),
    ("PROFESIONAL_ANALISTA",
     r"^ANALISTA|^ASESOR|^AUDITOR|^PROGRAMADOR|^INVESTIGADOR|^PROFESIONAL$|^INGENIERO|"
     r"^ADMINISTRADOR|^CONSULTOR|^ESPECIALISTA|^ARQUITECT|^WEBMASTER"),
    ("PROFESIONAL_ESPECIALIZADO_TECNICO",
     r"ABOGADO|PSIC.LOGO|CONTADOR|M.DICO|ENFERMERA|TRABAJADOR SOCIAL|TUTOR PARVULARIO|DISE.ADOR"),
    ("ASISTENCIA_SECRETARIAL_OFICINA", r"^ASISTENTE|^SECRETARIA|^SECRETARIO|RECEPCIONISTA|DIGITADOR|^OFICINISTA"),
    ("AUXILIAR_AYUDANTE_OPERATIVO", r"^AUXILIAR|^AYUDANTE|MAQUINISTA|^BODEGUERO|^JORNALERO"),
    ("TECNICO_OPERATIVO_MANTENIMIENTO", r"^T.CNICO"),
    ("SERVICIOS_GENERALES_OFICIOS",
     r"CHOFER|JARDINERO|GUARDI.N|BIBLIOTECARIO|CONSERJE|MENSAJERO|PINTOR|ELECTRICISTA|OPERARI|OPERADOR|"
     r"ALBA.IL|SOLDADOR|GASFITERO|CAJERA|^INSPECTOR|DOCUMENTADORA|CLASIFICADORA|^GUARDIA"),
    ("CONTRATO_SERVICIOS_PROFESIONALES_PROYECTO",
     r"SERVICIOS PROFESIONALES|T.CNICOS ESPECIALIZADOS|^CONTRATO CIVIL$|^CONTRATADO$|^CONTRATISTA$|"
     r"HONORARIOS PROFESIONALES|SERVICIOS VARIOS|ACTIVIDADES PROFESIONALES|EJECUCI.N DE"),
]


# Categorias que representan un contrato puntual/por proyecto (una actividad acotada
# en el tiempo que puede coexistir con el cargo estructural continuo de la persona,
# p.ej. un Docente Titular que ademas factura un contrato civil por un proyecto
# especifico) en vez de un cambio real de rol estructural. Se excluyen de
# `construir_tramos_rol`/`detectar_transiciones_rol` (decision confirmada por el
# usuario tras encontrar "flapping": personas con decenas de transiciones espurias
# por contratos paralelos con gap negativo, ver context/DECISION_LOG.md) y se dejan
# disponibles como insumo de la futura capa de EVENTOS en `extraer_eventos_puntuales`.
CATEGORIAS_PUNTUALES = {
    "CONTRATO_SERVICIOS_PROFESIONALES_PROYECTO",
    "DOCENTE_CONTRATADO_SERVICIOS_CIVILES",
    "ACTIVIDAD_ACADEMICA_DESDE_ADMINISTRATIVO",
    "TRIBUNAL_COMISION_ACADEMICA",
    "DOCENTE_HONORARIO_ESPECIAL",
}


def _clasificar_cargo_individual(cargo, tipoempleado: str) -> str:
    if not isinstance(cargo, str):
        return "SIN_DATO"
    c = cargo.strip().upper()
    if tipoempleado == "DOCENTE":
        if c in _LEGACY_AMBIGUO_DD:
            return "_LEGACY_AMBIGUO_DD"  # resuelto luego por continuidad de persona
        if c in _LEGACY_TITULAR_EXACTO or c.startswith(_LEGACY_TITULAR_PREFIJO):
            return "DOCENTE_TITULAR_CARRERA"
        for categoria, patron in REGLAS_CATEGORIA_CARGO_DD:
            if re.search(patron, c, flags=re.IGNORECASE):
                return categoria
        return "OTROS_DD"
    if tipoempleado == "ADMINISTRATIVO":
        for categoria, patron in REGLAS_CATEGORIA_CARGO_AA:
            if re.search(patron, c, flags=re.IGNORECASE):
                return categoria
        return "OTROS_AA"
    return "SIN_TIPOEMPLEADO"


def clasificar_categoria_cargo(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega `CATEGORIA_CARGO` (subdivision de rol dentro de TIPOEMPLEADO_DESC) y
    `ES_RUIDO_CALIDAD_DATOS` a un dataframe de historial laboral (requiere `CARGO` y
    `TIPOEMPLEADO_DESC`, ver `decodificar_historial_laboral`).

    Produce la jerarquia TIPOEMPLEADO_DESC -> CATEGORIA_CARGO -> CARGO (original,
    sin modificar) para poder analizar transiciones a distinto nivel de detalle.
    Las reglas y las decisiones de negocio detras de cada una estan documentadas en
    `context/DECISION_LOG.md`. `ES_RUIDO_CALIDAD_DATOS=True` marca registros que no
    deben usarse como señal en la deteccion de transiciones de rol (actualmente solo
    ANOMALIA_CARGO_DOCENTE_EN_AA), pero se conservan en el dataframe para trazabilidad.
    """
    df = df.copy()
    df["CATEGORIA_CARGO"] = [
        _clasificar_cargo_individual(cargo, tipo)
        for cargo, tipo in zip(df["CARGO"], df["TIPOEMPLEADO_DESC"])
    ]

    # Resolucion de _LEGACY_AMBIGUO_DD por continuidad de persona (ver docstring).
    personas_con_titular = set(df.loc[df["CATEGORIA_CARGO"] == "DOCENTE_TITULAR_CARRERA", "IDPERSONA"])
    es_legacy = df["CATEGORIA_CARGO"] == "_LEGACY_AMBIGUO_DD"
    es_persona_titular = df["IDPERSONA"].isin(personas_con_titular)
    df.loc[es_legacy & es_persona_titular, "CATEGORIA_CARGO"] = "DOCENTE_TITULAR_CARRERA"
    df.loc[es_legacy & ~es_persona_titular, "CATEGORIA_CARGO"] = "DOCENTE_NO_TITULAR_OCASIONAL"

    df["ES_RUIDO_CALIDAD_DATOS"] = df["CATEGORIA_CARGO"] == "ANOMALIA_CARGO_DOCENTE_EN_AA"
    return df


def construir_tramos_rol(df: pd.DataFrame) -> pd.DataFrame:
    """Colapsa contratos consecutivos de `CATEGORIA_CARGO` identica (dentro de la misma
    persona) en "tramos de rol", usando la misma tolerancia de brecha administrativa que
    `calcular_periodos_continuos` (`_continuacion_por_corte_de_mes`). Requiere que `df`
    ya tenga `CATEGORIA_CARGO`/`ES_RUIDO_CALIDAD_DATOS` (ver `clasificar_categoria_cargo`)
    y las fechas casteadas (ver `castear_fechas`).

    Excluye del calculo las filas SIN_DATO (CARGO nulo), SIN_TIPOEMPLEADO (contratos con
    `TIPOEMPLEADO="NN"` sin decodificar en `TIPO_EMPLEADO` - en la practica, "CONTRATO
    CIVIL"/regimen 0, sin relacion de dependencia: no son personal AA ni DD, ver
    `REGIMEN_LABORAL`), ES_RUIDO_CALIDAD_DATOS=True (ver `clasificar_categoria_cargo`) y
    las categorias puntuales/por proyecto (`CATEGORIAS_PUNTUALES`) porque no aportan una
    categoria de rol *estructural* confiable para construir la linea de tiempo de ESTADO
    (pueden coexistir con el cargo estructural continuo de la persona; ver
    `extraer_eventos_puntuales` para tratarlas como EVENTOS en vez de cambios de ESTADO).

    Devuelve una fila por tramo: IDPERSONA, TIPOEMPLEADO_DESC, CATEGORIA_CARGO,
    TRAMO_INICIO, TRAMO_FIN (NaT si vigente), N_CONTRATOS, CARGO_TRAMO, UNIDAD_TRAMO,
    NIVELDOCENCIA_TRAMO.

    `NIVELDOCENCIA_TRAMO` (mismo criterio que `CARGO_TRAMO`/`UNIDAD_TRAMO`: valor del
    contrato mas reciente dentro del tramo): "DOCENTE PREGRADO"/"DOCENTE POSGRADO" segun
    `NIVELDOCENCIA` del contrato de origen, o NA si el contrato no lo especifica (en la
    practica, ~57% de los contratos no lo tienen — sobre todo los administrativos, donde
    el concepto no aplica). Permite distinguir grado/posgrado en la timeline de
    trayectoria del dashboard SOLO cuando el dato realmente lo dice, sin inventar una
    clasificacion para cargos administrativos (decision confirmada por el usuario,
    2026-09-10: separar cuando se conoce el nivel, dejar el resto en la categoria
    general).

    `CARGO_TRAMO`/`UNIDAD_TRAMO` (DEC-016, ver context/DECISION_LOG.md): el texto de
    `CARGO`/`NOMBRE_UNIDAD` (si existe) del contrato con FECHAINICIOCONTRATO mas reciente
    dentro del tramo - se actualiza en cada fusion, igual que TRAMO_FIN. Existe porque
    `CARGO_ACTUAL`/`UNIDAD_ACTUAL_NOMBRE` en dataset_personas_features.csv se calculan por
    separado sobre el ultimo contrato por fecha SIN excluir categorias puntuales/ruido
    (mismo problema de raiz que TIPOEMPLEADO_ACTUAL_DESC, DEC-010) - estos campos, en
    cambio, siempre corresponden al MISMO tramo estructural que CATEGORIA_CARGO_ACTUAL.

    `TRAMO_FIN` siempre refleja el contrato con FECHAINICIOCONTRATO mas reciente dentro
    del tramo (nunca el maximo historico de fechas de fin vistas): un contrato intermedio
    sin fecha de fin (NaT) no debe "infectar" el tramo como vigente para siempre si hubo
    contratos posteriores, ya cerrados, con fecha real (caso real: persona 865,
    IDCONTRATOLABORAL 3194 de 2015 sin fecha de cierre bloqueaba la vigencia real del
    tramo pese a que su ultimo contrato de cualquier tipo cerro en 2025-12-31) — EXCEPTO
    si esa vigencia viene de un contrato con `ESTADOCONTRATO` abierto (AA/PE, ver
    `_es_estado_abierto`): un nombramiento estructural asi no se cierra por un FF
    posterior de la misma categoria (caso real: persona 1216, rectora, IDCONTRATOLABORAL
    22351 AA desde 2022-11-13, tapado por >100 actos FF de 1-20 dias de encargo de
    despacho/delegacion de firma que se repiten indefinidamente sobre el mismo cargo y
    nunca vuelven a AA — confirmado con el usuario como interpretacion de negocio).
    """
    tiene_unidad = "NOMBRE_UNIDAD" in df.columns
    tiene_nivel_docencia = "NIVELDOCENCIA" in df.columns
    trabajo = df[
        (df["CATEGORIA_CARGO"] != "SIN_DATO")
        & (df["CATEGORIA_CARGO"] != "SIN_TIPOEMPLEADO")
        & (~df["ES_RUIDO_CALIDAD_DATOS"])
        & (~df["CATEGORIA_CARGO"].isin(CATEGORIAS_PUNTUALES))
    ].copy()
    trabajo["_FECHAFIN_EFECTIVA"] = calcular_fecha_fin_efectiva(trabajo)
    trabajo["_ESTADO_ABIERTO"] = _es_estado_abierto(trabajo)
    trabajo = trabajo.dropna(subset=["IDPERSONA", "FECHAINICIOCONTRATO"])
    trabajo = trabajo.sort_values(["IDPERSONA", "FECHAINICIOCONTRATO"], kind="stable")

    tramos = []
    for id_persona, grupo in trabajo.groupby("IDPERSONA", sort=False):
        actual = None
        for _, fila in grupo.iterrows():
            inicio, fin = fila["FECHAINICIOCONTRATO"], fila["_FECHAFIN_EFECTIVA"]
            categoria = fila["CATEGORIA_CARGO"]
            estado_abierto = bool(fila["_ESTADO_ABIERTO"])

            if actual is not None and actual["CATEGORIA_CARGO"] == categoria:
                fin_actual_cmp = pd.Timestamp.max if pd.isna(actual["TRAMO_FIN"]) else actual["TRAMO_FIN"]
                continua = fin_actual_cmp >= inicio or (
                    not pd.isna(actual["TRAMO_FIN"])
                    and _continuacion_por_corte_de_mes(actual["TRAMO_FIN"], inicio)
                )
                if continua:
                    # TRAMO_FIN = NaT (vigente) solo si el contrato mas reciente por
                    # FECHAINICIOCONTRATO dentro del tramo (osea `fila`, por el orden
                    # ascendente) esta el mismo vigente. Si ese ultimo contrato SI tiene
                    # fecha de cierre real, el tramo cierra en el maximo entre su fin
                    # anterior y este fin nuevo — nunca se "des-vigentiza" retrocediendo a
                    # una fecha anterior a un contrato ya cubierto (caso frecuente: contratos
                    # cortos/administrativos anidados dentro de un periodo "paraguas" ya mas
                    # largo, ~15,600 casos medidos), pero tampoco queda bloqueado en NaT para
                    # siempre por un contrato intermedio sin fecha de cierre si el mas
                    # reciente ya cerro (caso real: persona 865, ver docstring) — SALVO que
                    # la vigencia actual venga de un ESTADOCONTRATO abierto (AA/PE): esa no
                    # se cierra por un FF posterior (ver docstring).
                    if actual["_vigente_por_estado_abierto"] and pd.isna(actual["TRAMO_FIN"]):
                        pass
                    elif pd.isna(fin):
                        actual["TRAMO_FIN"] = fin
                        actual["_vigente_por_estado_abierto"] = estado_abierto
                    elif not pd.isna(actual["TRAMO_FIN"]):
                        actual["TRAMO_FIN"] = max(actual["TRAMO_FIN"], fin)
                    else:
                        actual["TRAMO_FIN"] = fin
                    actual["N_CONTRATOS"] += 1
                    # fila es siempre la mas reciente por construccion (orden ascendente
                    # por FECHAINICIOCONTRATO): el CARGO/UNIDAD "actual" del tramo es el
                    # de la ultima contratacion, no necesariamente el primero — salvo que la
                    # vigencia siga protegida por un AA/PE anterior, en cuyo caso este FF es
                    # un acto puntual y no debe reemplazar el CARGO/UNIDAD del nombramiento.
                    if not (actual["_vigente_por_estado_abierto"] and pd.isna(actual["TRAMO_FIN"]) and not estado_abierto):
                        actual["CARGO_TRAMO"] = fila["CARGO"]
                        if tiene_unidad:
                            actual["UNIDAD_TRAMO"] = fila["NOMBRE_UNIDAD"]
                        if tiene_nivel_docencia:
                            actual["NIVELDOCENCIA_TRAMO"] = fila["NIVELDOCENCIA"]
                    continue

            if actual is not None:
                tramos.append(actual)
            actual = {
                "IDPERSONA": id_persona,
                "TIPOEMPLEADO_DESC": fila["TIPOEMPLEADO_DESC"],
                "CATEGORIA_CARGO": categoria,
                "TRAMO_INICIO": inicio,
                "TRAMO_FIN": fin,
                "_vigente_por_estado_abierto": estado_abierto and pd.isna(fin),
                "N_CONTRATOS": 1,
                "CARGO_TRAMO": fila["CARGO"],
                "UNIDAD_TRAMO": fila["NOMBRE_UNIDAD"] if tiene_unidad else pd.NA,
                "NIVELDOCENCIA_TRAMO": fila["NIVELDOCENCIA"] if tiene_nivel_docencia else pd.NA,
            }
        if actual is not None:
            tramos.append(actual)

    columnas = ["IDPERSONA", "TIPOEMPLEADO_DESC", "CATEGORIA_CARGO", "TRAMO_INICIO", "TRAMO_FIN",
                "N_CONTRATOS", "CARGO_TRAMO", "UNIDAD_TRAMO", "NIVELDOCENCIA_TRAMO"]
    if not tramos:
        return pd.DataFrame(columns=columnas)
    resultado = pd.DataFrame(tramos)
    return resultado[columnas].reset_index(drop=True)


def construir_contrato_puntual_vigente(df: pd.DataFrame) -> pd.DataFrame:
    """Para personas cuyo *unico* contrato vigente hoy es de categoria puntual (ver
    `CATEGORIAS_PUNTUALES`, p.ej. `CONTRATO_SERVICIOS_PROFESIONALES_PROYECTO`) - es decir,
    no tienen ningun tramo estructural activo en este momento (`construir_tramos_rol` los
    excluye por diseno, DEC-004) mientras siguen contractualmente vigentes en ESPOL (ver
    DEC-016 en `context/DECISION_LOG.md`).

    Caso real que motivo esto: persona con un tramo estructural (`TECNICO_OPERATIVO_
    MANTENIMIENTO`) que termino en 2024-12-31, y desde entonces solo contratos de
    "Servicios Profesionales - Ejecucion de Actividades" (categoria puntual) vigentes hasta
    2026-12-31. Antes de esta funcion, `CARGO_ACTUAL_ESTRUCTURAL`/`CARGO_ACTUAL` mostraban
    el cargo tecnico ya finalizado (correcto para `CLUSTER`/`CATEGORIA_CARGO_ACTUAL`, que no
    deben cambiar), pero engañoso como "lo que la persona hace hoy" — VIGENTE_ACTUALMENTE=True
    contradecia visualmente un cargo mostrado como si hubiera terminado en 2024.

    Devuelve una fila por persona en esa situacion: IDPERSONA, CARGO_PUNTUAL_VIGENTE,
    UNIDAD_PUNTUAL_VIGENTE, CATEGORIA_PUNTUAL_VIGENTE, TIPOEMPLEADO_PUNTUAL_VIGENTE (el
    contrato puntual vigente con FECHAINICIOCONTRATO mas reciente). No cambia `CLUSTER` ni
    `CATEGORIA_CARGO_ACTUAL` — es exclusivamente para uso de presentacion en el dashboard,
    como *fallback* de `CARGO_ACTUAL`/`UNIDAD_ACTUAL_NOMBRE` cuando la persona no tiene un
    tramo estructural vigente hoy (ver `08_dashboard.ipynb`).
    """
    tiene_unidad = "NOMBRE_UNIDAD" in df.columns
    puntual = df[
        df["CATEGORIA_CARGO"].isin(CATEGORIAS_PUNTUALES)
        & (~df["ES_RUIDO_CALIDAD_DATOS"])
    ].copy()
    puntual["_FECHAFIN_EFECTIVA"] = calcular_fecha_fin_efectiva(puntual)
    puntual = puntual.dropna(subset=["IDPERSONA", "FECHAINICIOCONTRATO"])

    hoy = pd.Timestamp.today().normalize()
    vigente_hoy = puntual["FECHAINICIOCONTRATO"] <= hoy
    vigente_hoy &= puntual["_FECHAFIN_EFECTIVA"].isna() | (puntual["_FECHAFIN_EFECTIVA"] >= hoy)
    puntual = puntual[vigente_hoy]
    if puntual.empty:
        columnas = ["IDPERSONA", "CARGO_PUNTUAL_VIGENTE", "UNIDAD_PUNTUAL_VIGENTE",
                    "CATEGORIA_PUNTUAL_VIGENTE", "TIPOEMPLEADO_PUNTUAL_VIGENTE"]
        return pd.DataFrame(columns=columnas)

    puntual = puntual.sort_values(["IDPERSONA", "FECHAINICIOCONTRATO"], kind="stable")
    ultimo = puntual.groupby("IDPERSONA", sort=False).tail(1)

    resultado = pd.DataFrame({
        "IDPERSONA": ultimo["IDPERSONA"].values,
        "CARGO_PUNTUAL_VIGENTE": ultimo["CARGO"].values,
        "UNIDAD_PUNTUAL_VIGENTE": ultimo["NOMBRE_UNIDAD"].values if tiene_unidad else pd.NA,
        "CATEGORIA_PUNTUAL_VIGENTE": ultimo["CATEGORIA_CARGO"].values,
        "TIPOEMPLEADO_PUNTUAL_VIGENTE": ultimo["TIPOEMPLEADO_DESC"].values,
    })
    return resultado.reset_index(drop=True)


def _encontrar_par_solapado(activos: list[dict]):
    """Busca dos tramos activos de distinta `CATEGORIA_CARGO` cuyo rango de fechas se
    solape. Devuelve (indice_corto, indice_largo) del primer par encontrado (el "corto"
    es el de menor duracion, candidato a retirarse de la linea principal), o None si no
    hay ningun solapamiento pendiente."""
    for i in range(len(activos)):
        for j in range(len(activos)):
            if i == j:
                continue
            a, b = activos[i], activos[j]
            if a["CATEGORIA_CARGO"] == b["CATEGORIA_CARGO"]:
                continue
            if max(a["TRAMO_INICIO"], b["TRAMO_INICIO"]) <= min(a["_FIN_CMP"], b["_FIN_CMP"]):
                if a["_DUR"] <= b["_DUR"]:
                    return i, j
    return None


def resolver_roles_simultaneos(tramos_rol: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa, dentro de los tramos de una misma persona, los que se solapan en fecha con
    otro de distinta `CATEGORIA_CARGO` (ver DEC-011 en `context/DECISION_LOG.md`).

    `construir_tramos_rol` no modela concurrencia: ordena los contratos solo por fecha de
    inicio, asi que un nombramiento de autoridad (Rector/Vicerrector/Decano/Director) que
    una persona ejerce **en paralelo** a su cargo estructural continuo (p.ej. Profesor
    Titular) corta ese cargo en dos tramos separados por el nombramiento, generando dos
    "transiciones" de rol que en realidad nunca ocurrieron (la persona nunca dejo de ser
    profesor). Confirmado con el usuario (2026-09-09): cuando dos tramos se solapan, domina
    el de **mayor duracion** (el rol estructural) en la linea principal de ESTADO; el mas
    corto (tipicamente el nombramiento de autoridad) se retira y se devuelve aparte como
    "rol adicional simultaneo", sin generar transicion ni cambiar `CATEGORIA_CARGO_ACTUAL`.
    Tras retirarlo, los tramos de la misma categoria que quedaron separados por la
    interrupcion se vuelven a fusionar (misma tolerancia de `_continuacion_por_corte_de_mes`
    que usa `construir_tramos_rol`).

    Devuelve `(tramos_resueltos, roles_adicionales_simultaneos)`. El primero reemplaza a
    `tramos_rol` como insumo de `detectar_transiciones_rol`/`construir_features_trayectoria`.
    El segundo es informativo — mismas columnas de `tramos_rol` mas
    `CATEGORIA_CARGO_BASE_SIMULTANEA` (la categoria del tramo estructural con el que se
    solapaba) — pensado para exponerse como atributo/afinidad (ver DEC-009), no como una
    categoria nueva de agrupamiento.
    """
    INF = pd.Timestamp.max
    columnas = ["IDPERSONA", "TIPOEMPLEADO_DESC", "CATEGORIA_CARGO", "TRAMO_INICIO", "TRAMO_FIN",
                "N_CONTRATOS", "CARGO_TRAMO", "UNIDAD_TRAMO"]

    tramos_principales = []
    roles_adicionales = []

    for id_persona, grupo in tramos_rol.groupby("IDPERSONA", sort=False):
        activos = grupo.sort_values("TRAMO_INICIO", kind="stable").to_dict("records")
        for r in activos:
            r["_FIN_CMP"] = INF if pd.isna(r["TRAMO_FIN"]) else r["TRAMO_FIN"]
            r["_DUR"] = (r["_FIN_CMP"] - r["TRAMO_INICIO"]).days

        # 1) retirar solapamientos entre categorias distintas (el mas corto sale) hasta
        #    que no quede ninguno.
        while len(activos) > 1:
            par = _encontrar_par_solapado(activos)
            if par is None:
                break
            i_corto, i_largo = par
            corto = dict(activos[i_corto])
            corto["CATEGORIA_CARGO_BASE_SIMULTANEA"] = activos[i_largo]["CATEGORIA_CARGO"]
            roles_adicionales.append(corto)
            del activos[i_corto]

        # 2) re-fusionar tramos de la misma categoria que hayan quedado consecutivos o
        #    solapados tras el retiro anterior (misma logica que construir_tramos_rol).
        activos.sort(key=lambda r: r["TRAMO_INICIO"])
        fusionados: list[dict] = []
        for r in activos:
            if fusionados and fusionados[-1]["CATEGORIA_CARGO"] == r["CATEGORIA_CARGO"]:
                anterior = fusionados[-1]
                continua = anterior["_FIN_CMP"] >= r["TRAMO_INICIO"] or (
                    anterior["_FIN_CMP"] != INF
                    and _continuacion_por_corte_de_mes(anterior["TRAMO_FIN"], r["TRAMO_INICIO"])
                )
                if continua:
                    if r["_FIN_CMP"] > anterior["_FIN_CMP"]:
                        anterior["TRAMO_FIN"] = r["TRAMO_FIN"]
                        anterior["_FIN_CMP"] = r["_FIN_CMP"]
                    anterior["N_CONTRATOS"] += r["N_CONTRATOS"]
                    # r es siempre cronologicamente posterior (activos ordenado por
                    # TRAMO_INICIO ascendente): su CARGO/UNIDAD es el mas reciente.
                    anterior["CARGO_TRAMO"] = r["CARGO_TRAMO"]
                    anterior["UNIDAD_TRAMO"] = r["UNIDAD_TRAMO"]
                    continue
            fusionados.append(dict(r))

        tramos_principales.extend(fusionados)

    tramos_resueltos = pd.DataFrame(tramos_principales, columns=columnas + ["_FIN_CMP", "_DUR"])
    tramos_resueltos = tramos_resueltos[columnas] if len(tramos_resueltos) else pd.DataFrame(columns=columnas)

    columnas_secundarios = columnas + ["CATEGORIA_CARGO_BASE_SIMULTANEA"]
    roles_adicionales_df = pd.DataFrame(roles_adicionales, columns=columnas_secundarios + ["_FIN_CMP", "_DUR"])
    roles_adicionales_df = (
        roles_adicionales_df[columnas_secundarios] if len(roles_adicionales_df) else pd.DataFrame(columns=columnas_secundarios)
    )

    return (
        tramos_resueltos.sort_values(["IDPERSONA", "TRAMO_INICIO"], kind="stable").reset_index(drop=True),
        roles_adicionales_df.sort_values(["IDPERSONA", "TRAMO_INICIO"], kind="stable").reset_index(drop=True),
    )


def extraer_eventos_puntuales(df: pd.DataFrame) -> pd.DataFrame:
    """Extrae los contratos de categorias puntuales/por proyecto (`CATEGORIAS_PUNTUALES`,
    excluidos de `construir_tramos_rol` para no generar transiciones de ESTADO falsas)
    como una tabla de EVENTOS: una fila por contrato, con su fecha de inicio/fin,
    pensada como insumo de la futura capa de EVENTOS (persona x fecha x tipo de
    actividad), no como cambio de rol estructural.

    Devuelve: IDPERSONA, TIPOEMPLEADO_DESC, CATEGORIA_CARGO, CARGO (original),
    FECHAINICIOCONTRATO, FECHAFINCONTRATO, FECHADESVINCULACION, ESTADOCONTRATO, NOMBRE_UNIDAD
    (las que existan en `df`) - DEC-018: FECHADESVINCULACION/ESTADOCONTRATO se incluyen para
    que quien consuma esta tabla pueda calcular la fecha fin EFECTIVA con
    `calcular_fecha_fin_efectiva` (que necesita `ESTADOCONTRATO` para detectar un contrato
    vigente cuya `FECHAFINCONTRATO` ya esta poblada con el cierre de periodo futuro, p.ej.
    ESTADOCONTRATO=ACTIVO con FECHAFINCONTRATO=fin de año). Antes, al no incluir estas
    columnas, el contrato puntual vigente mas reciente de una persona se veia
    incorrectamente como ya finalizado en cualquier vista derivada de esta funcion (ver
    DEC-018). DEC-022: NOMBRE_UNIDAD se incluye por el mismo motivo de fondo - sin ella, la
    unidad/dependencia de un contrato puntual nunca llegaba al texto de trayectoria
    (`construir_eventos_trayectoria`/documento semantico), afectando cualquier busqueda
    semantica que combine "trabaja en <unidad>" con otra condicion.
    """
    columnas = ["IDPERSONA", "TIPOEMPLEADO_DESC", "CATEGORIA_CARGO", "CARGO",
                "FECHAINICIOCONTRATO", "FECHAFINCONTRATO"]
    columnas += [c for c in ("FECHADESVINCULACION", "ESTADOCONTRATO", "NOMBRE_UNIDAD", "NIVELDOCENCIA")
                 if c in df.columns]
    mask = (
        df["CATEGORIA_CARGO"].isin(CATEGORIAS_PUNTUALES)
        & ~df["ES_RUIDO_CALIDAD_DATOS"]
    )
    return df.loc[mask, columnas].sort_values(["IDPERSONA", "FECHAINICIOCONTRATO"]).reset_index(drop=True)


def procesar_registro_autoridades(
    autoridades: pd.DataFrame, historial_categoria_cargo: pd.DataFrame,
    poblacion_ids: set | None = None,
) -> pd.DataFrame:
    """Limpia `registro_autoridades.csv` (autoridades/funciones adicionales - cargos
    ejercidos en paralelo al contrato laboral: Director, Coordinador, subrogaciones,
    membresias de consejo) y lo enriquece comparandolo contra el contrato vigente en
    `historial_laboral_categoria_cargo` (ver DEC-012 en context/DECISION_LOG.md).

    NO asume que un registro representa una transicion de rol: es una dimension
    *paralela* al contrato (funcion/designacion), no un reemplazo de
    `CATEGORIA_CARGO_ACTUAL`/`TIPOEMPLEADO_CATEGORIA_ACTUAL`. Confirmado con el usuario:
    una subrogacion nunca se trata como transicion contractual, sin importar su duracion
    (0-252 dias en los datos observados), y se conservan TODAS las subrogaciones
    (ninguna se descarta por ser demasiado corta).

    Limpieza:
    - `ES_DUPLICADO_EXACTO`: fila identica a otra en
      (IDPERSONA, IDESTRUCTURAORGANICA, TIPOAUTORIDAD, FECHADESDE, FECHAHASTA) - se
      conserva (no se elimina) para trazabilidad, pero se excluye de los conteos por
      persona en `construir_features_funciones_adicionales`.
    - `ES_RUIDO_CALIDAD_DATOS`: FECHAHASTA anterior a FECHADESDE (78 filas observadas,
      rango de fechas invertido) - se conserva para trazabilidad, se excluye de los
      conteos por persona igual que arriba.
    - `ES_REPRESENTANTE_ESTUDIANTIL`: TIPOAUTORIDAD contiene "estudiantes" (representantes
      estudiantiles en consejos, no personal docente/administrativo - 98% de estas filas
      no tienen ningun contrato de personal solapado). Confirmado con el usuario: se
      conservan pero marcadas aparte, no se eliminan de la tabla.
    - `ES_RUIDO_FUERA_DE_POBLACION` (DEC-021, ver context/DECISION_LOG.md): si se pasa
      `poblacion_ids` (el conjunto de IDPERSONA de `datos_personales_ultimos_5anios.csv`,
      la fuente que define la poblacion del proyecto desde `02_integracion_datos.ipynb`),
      marca las filas cuyo IDPERSONA no pertenece a esa poblacion (109 personas
      confirmadas, tras excluir representantes estudiantiles) - designaciones de
      autoridad/funcion registradas para alguien que nunca aparece en la ventana
      poblacional de 5 anios, considerado ruido/dato fuera de alcance por decision
      explicita del usuario. Se conservan las filas (trazabilidad del IDPERSONA excluido,
      no se borra el dato), pero se excluyen de los conteos por persona igual que
      ES_DUPLICADO_EXACTO/ES_RUIDO_CALIDAD_DATOS - nunca deben generar una fila nueva en
      `features_trayectoria_persona.csv` para alguien fuera de la poblacion declarada.

    Enriquecimiento (comparacion contra el contrato vigente en esa fecha):
    - `TIPOEMPLEADO_CONTRATO_DURANTE`/`CATEGORIA_CARGO_CONTRATO_DURANTE`: el
      `TIPOEMPLEADO_DESC`/`CATEGORIA_CARGO` del contrato de `historial_laboral_categoria_cargo`
      (excluyendo ES_RUIDO_CALIDAD_DATOS) con mayor solape de fechas con la funcion;
      NaN si no hay ningun contrato solapado (12-15% de las funciones estructurales
      antiguas, mas frecuente en designaciones anteriores a la ventana de poblacion).
    - `CATEGORIA_FUNCION_ADICIONAL`/`CATEGORIA_ROL_SUBROGADO`: se clasifica el texto de
      `TIPOAUTORIDAD`/`CARGOSUBROGADO` reutilizando `_clasificar_cargo_individual` (las
      mismas reglas ya validadas de DEC-004) contra ambas ramas (DD/AA) y se toma la que
      no caiga en la categoria generica "OTROS_*" (si ambas son especificas, se prefiere
      AA; si ambas son genericas, queda OTROS_DD). Es una reutilizacion mecanica de una
      regla ya confirmada con el usuario, no una regla de negocio nueva.
    - `ES_COINCIDENTE_CONTRATO`: True si `CATEGORIA_CARGO_CONTRATO_DURANTE` coincide con
      `CATEGORIA_FUNCION_ADICIONAL` (o con `CATEGORIA_ROL_SUBROGADO` si es subrogacion) -
      es decir, el contrato actual YA es esa misma categoria (no aporta una dimension
      nueva). NaN si no hay contrato solapado.

    `historial_categoria_cargo` debe incluir `ESTADOCONTRATO` (se usa
    `calcular_fecha_fin_efectiva`, no `FECHAFINCONTRATO` cruda, para mantener la misma
    correccion de vigencia de DEC-005 al buscar el contrato solapado).

    `NIVEL_FUNCION` (2026-09-10, agregado desde `GRADO`/`POSGRADO` en el crudo, columnas
    nuevas del registro): "GRADO"/"POSGRADO" segun cual de las dos venga poblada, NA si
    ninguna. Solo aplica a un subconjunto de `FUNCION_ADICIONAL` de tipo coordinacion
    ("Coordinador de carrera", "Coordinador de programa de postgrado", "Coordinador de
    practicas empresariales", "Coordinador de vinculacion con la sociedad", "Coordinador
    de acreditacion internacional" — confirmado con el usuario que puede haber otros
    casos no listados aqui, se detecta por la columna poblada, no por el nombre del
    cargo) - el resto de funciones/subrogaciones (Director, Decano, miembro de consejo,
    etc.) no tiene este concepto y queda NA. `GRADO`/`POSGRADO` en si mismas (el nombre
    de la carrera o programa) tambien se conservan como `DETALLE_NIVEL_FUNCION` para
    texto legible (ej. "Ingenieria Industrial", "Maestria en Finanzas").
    """
    df = autoridades.copy()

    df["ES_DUPLICADO_EXACTO"] = df.duplicated(
        subset=["IDPERSONA", "IDESTRUCTURAORGANICA", "TIPOAUTORIDAD", "FECHADESDE", "FECHAHASTA"],
        keep="first",
    )
    df["ES_RUIDO_CALIDAD_DATOS"] = df["FECHAHASTA"].notna() & (df["FECHAHASTA"] < df["FECHADESDE"])
    df["ES_REPRESENTANTE_ESTUDIANTIL"] = df["TIPOAUTORIDAD"].str.contains("estudiantes", case=False, na=False)
    df["ES_SUBROGACION"] = df["TIPOSIGLAS"] == "SR"
    df["ES_RUIDO_FUERA_DE_POBLACION"] = (
        ~df["IDPERSONA"].isin(poblacion_ids) if poblacion_ids is not None else False
    )

    df = df.rename(columns={
        "NOMBRE": "UNIDAD_FUNCION", "TIPOAUTORIDAD": "FUNCION_ADICIONAL",
        "FECHADESDE": "FECHA_DESDE", "FECHAHASTA": "FECHA_HASTA", "CARGOSUBROGADO": "ROL_SUBROGADO",
    })
    hoy = pd.Timestamp.today().normalize()
    fin_cmp = df["FECHA_HASTA"].fillna(hoy)
    df["DURACION_DIAS"] = (fin_cmp - df["FECHA_DESDE"]).dt.days.clip(lower=0)

    def _categoria_no_generica(texto):
        if not isinstance(texto, str):
            return pd.NA
        aa = _clasificar_cargo_individual(texto, "ADMINISTRATIVO")
        dd = _clasificar_cargo_individual(texto, "DOCENTE")
        if not aa.startswith("OTROS_"):
            return aa
        if not dd.startswith("OTROS_"):
            return dd
        return aa

    df["CATEGORIA_FUNCION_ADICIONAL"] = df["FUNCION_ADICIONAL"].apply(_categoria_no_generica)
    df["CATEGORIA_ROL_SUBROGADO"] = df["ROL_SUBROGADO"].apply(_categoria_no_generica)

    if "GRADO" in df.columns or "POSGRADO" in df.columns:
        grado_col = df["GRADO"] if "GRADO" in df.columns else pd.Series(pd.NA, index=df.index)
        posgrado_col = df["POSGRADO"] if "POSGRADO" in df.columns else pd.Series(pd.NA, index=df.index)
        df["NIVEL_FUNCION"] = np.select(
            [grado_col.notna(), posgrado_col.notna()], ["GRADO", "POSGRADO"], default=pd.NA,
        )
        df["DETALLE_NIVEL_FUNCION"] = grado_col.fillna(posgrado_col)
    else:
        df["NIVEL_FUNCION"] = pd.NA
        df["DETALLE_NIVEL_FUNCION"] = pd.NA

    # SIN_TIPOEMPLEADO (TIPOEMPLEADO="NN", en la practica "contrato civil" sin relacion de
    # dependencia, ver construir_tramos_rol) tampoco cuenta como "el contrato vigente":
    # no es personal AA ni DD.
    hist = historial_categoria_cargo[
        ~historial_categoria_cargo["ES_RUIDO_CALIDAD_DATOS"]
        & (historial_categoria_cargo["CATEGORIA_CARGO"] != "SIN_TIPOEMPLEADO")
    ].copy()
    hist["_FIN_EFECTIVA"] = pd.to_datetime(calcular_fecha_fin_efectiva(hist), format="mixed", errors="coerce")
    hist_por_persona = {k: v for k, v in hist.groupby("IDPERSONA")}

    tipoempleado_durante, categoria_durante = [], []
    for _, fila in df.iterrows():
        g = hist_por_persona.get(fila["IDPERSONA"])
        fin_fila = hoy if pd.isna(fila["FECHA_HASTA"]) else fila["FECHA_HASTA"]
        if g is None or pd.isna(fila["FECHA_DESDE"]):
            tipoempleado_durante.append(pd.NA)
            categoria_durante.append(pd.NA)
            continue
        fin_g = g["_FIN_EFECTIVA"].fillna(hoy)
        solapa = g[(g["FECHAINICIOCONTRATO"] <= fin_fila) & (fin_g >= fila["FECHA_DESDE"])]
        if len(solapa) == 0:
            tipoempleado_durante.append(pd.NA)
            categoria_durante.append(pd.NA)
            continue
        ini_s = np.maximum(solapa["FECHAINICIOCONTRATO"], fila["FECHA_DESDE"])
        fin_s = np.minimum(fin_g.loc[solapa.index], fin_fila)
        idx = (fin_s - ini_s).idxmax()
        tipoempleado_durante.append(solapa.loc[idx, "TIPOEMPLEADO_DESC"])
        categoria_durante.append(solapa.loc[idx, "CATEGORIA_CARGO"])

    df["TIPOEMPLEADO_CONTRATO_DURANTE"] = tipoempleado_durante
    df["CATEGORIA_CARGO_CONTRATO_DURANTE"] = categoria_durante

    categoria_relevante = df["CATEGORIA_ROL_SUBROGADO"].where(df["ES_SUBROGACION"], df["CATEGORIA_FUNCION_ADICIONAL"])
    df["ES_COINCIDENTE_CONTRATO"] = np.where(
        df["CATEGORIA_CARGO_CONTRATO_DURANTE"].isna(), pd.NA,
        df["CATEGORIA_CARGO_CONTRATO_DURANTE"] == categoria_relevante,
    )

    columnas = [
        "IDPERSONA", "IDESTRUCTURAORGANICA", "UNIDAD_FUNCION", "FUNCION_ADICIONAL",
        "CATEGORIA_FUNCION_ADICIONAL", "ES_SUBROGACION", "ROL_SUBROGADO", "CATEGORIA_ROL_SUBROGADO",
        "NIVEL_FUNCION", "DETALLE_NIVEL_FUNCION",
        "FECHA_DESDE", "FECHA_HASTA", "DURACION_DIAS",
        "ES_REPRESENTANTE_ESTUDIANTIL", "ES_RUIDO_CALIDAD_DATOS", "ES_DUPLICADO_EXACTO",
        "ES_RUIDO_FUERA_DE_POBLACION",
        "TIPOEMPLEADO_CONTRATO_DURANTE", "CATEGORIA_CARGO_CONTRATO_DURANTE", "ES_COINCIDENTE_CONTRATO",
    ]
    return df[columnas].sort_values(["IDPERSONA", "FECHA_DESDE"], kind="stable").reset_index(drop=True)


def construir_features_funciones_adicionales(funciones_adicionales: pd.DataFrame) -> pd.DataFrame:
    """Resume `procesar_registro_autoridades` a una fila por IDPERSONA, pensada para
    fusionarse a las features de trayectoria (ver DEC-012 en context/DECISION_LOG.md).

    Excluye de los conteos `ES_REPRESENTANTE_ESTUDIANTIL`, `ES_RUIDO_CALIDAD_DATOS` y
    `ES_DUPLICADO_EXACTO=True` (se conservan en la tabla de detalle para trazabilidad,
    no aquí). NO reemplaza `CATEGORIA_CARGO_ACTUAL`/`GRUPO_PRINCIPAL` ni
    `TUVO_ROL_ADICIONAL_SIMULTANEO` (DEC-011, inferido de solapes de contrato) - es una
    fuente distinta y complementaria (autoridades/designaciones explicitas registradas),
    no un reemplazo del heuristico de DEC-011.

    Features:
    - TUVO_FUNCION_ADICIONAL: alguna vez tuvo una funcion adicional registrada (de
      cualquier tipo, incluye subrogaciones).
    - N_FUNCIONES_ADICIONALES, N_CATEGORIAS_FUNCION_ADICIONAL_DISTINTAS.
    - TUVO_SUBROGACION, N_SUBROGACIONES.
    - TUVO_FUNCION_NO_COINCIDENTE_CON_CONTRATO: alguna vez ejercio una funcion/subrogacion
      cuya categoria NO coincidia con su contrato vigente en ese momento (la señal
      "docente ejerciendo funcion administrativa, o viceversa, sin cambiar de contrato").
      NA tratado como no-coincidente=False (sin contrato solapado no se puede afirmar
      que hubo divergencia).
    - CATEGORIA_FUNCION_ADICIONAL_MAS_RECIENTE: para mostrarse como atributo/afinidad en
      el dashboard (mismo principio de DEC-009/DEC-011: no es una categoria de
      agrupamiento nueva).

    DEC-021: tambien excluye `ES_RUIDO_FUERA_DE_POBLACION` - si `procesar_registro_
    autoridades` recibio `poblacion_ids`, ninguna de estas filas debe generar una fila
    de resumen para una persona fuera de la poblacion declarada del proyecto.
    """
    col_poblacion = (
        ~funciones_adicionales["ES_RUIDO_FUERA_DE_POBLACION"]
        if "ES_RUIDO_FUERA_DE_POBLACION" in funciones_adicionales.columns
        else True
    )
    validas = funciones_adicionales[
        ~funciones_adicionales["ES_REPRESENTANTE_ESTUDIANTIL"]
        & ~funciones_adicionales["ES_RUIDO_CALIDAD_DATOS"]
        & ~funciones_adicionales["ES_DUPLICADO_EXACTO"]
        & col_poblacion
    ].sort_values(["IDPERSONA", "FECHA_DESDE"], kind="stable")

    if len(validas) == 0:
        return pd.DataFrame(columns=[
            "IDPERSONA", "TUVO_FUNCION_ADICIONAL", "N_FUNCIONES_ADICIONALES",
            "N_CATEGORIAS_FUNCION_ADICIONAL_DISTINTAS", "TUVO_SUBROGACION", "N_SUBROGACIONES",
            "TUVO_FUNCION_NO_COINCIDENTE_CON_CONTRATO", "CATEGORIA_FUNCION_ADICIONAL_MAS_RECIENTE",
        ])

    resumen = validas.groupby("IDPERSONA").agg(
        N_FUNCIONES_ADICIONALES=("FUNCION_ADICIONAL", "size"),
        N_CATEGORIAS_FUNCION_ADICIONAL_DISTINTAS=("CATEGORIA_FUNCION_ADICIONAL", "nunique"),
        N_SUBROGACIONES=("ES_SUBROGACION", "sum"),
        TUVO_FUNCION_NO_COINCIDENTE_CON_CONTRATO=("ES_COINCIDENTE_CONTRATO", lambda s: bool((s == False).any())),
        CATEGORIA_FUNCION_ADICIONAL_MAS_RECIENTE=("CATEGORIA_FUNCION_ADICIONAL", "last"),
    ).reset_index()
    resumen["TUVO_FUNCION_ADICIONAL"] = True
    resumen["TUVO_SUBROGACION"] = resumen["N_SUBROGACIONES"] > 0
    resumen["N_SUBROGACIONES"] = resumen["N_SUBROGACIONES"].astype(int)

    columnas = [
        "IDPERSONA", "TUVO_FUNCION_ADICIONAL", "N_FUNCIONES_ADICIONALES",
        "N_CATEGORIAS_FUNCION_ADICIONAL_DISTINTAS", "TUVO_SUBROGACION", "N_SUBROGACIONES",
        "TUVO_FUNCION_NO_COINCIDENTE_CON_CONTRATO", "CATEGORIA_FUNCION_ADICIONAL_MAS_RECIENTE",
    ]
    return resumen[columnas]


def construir_mapa_siglas_unidad(registro_autoridades: pd.DataFrame) -> dict:
    """Construye un mapeo {NOMBRE_UNIDAD_completo: SIGLAS} a partir de las columnas
    `NOMBRE`/`SIGLAS` de `registro_autoridades.csv` (DEC-022, ver context/DECISION_LOG.md).

    Motivo: el modelo de embeddings (multilingual-e5-base) no conoce las siglas
    institucionales de ESPOL como abreviaturas de su nombre completo - la similitud coseno
    entre el embedding de "GTSI" y el de "GERENCIA DE TECNOLOGIAS Y SISTEMAS DE INFORMACION"
    es ~0.79, indistinguible del piso de anisotropia entre dos textos NO relacionados
    (~0.75-0.86, ver DEC-019). Una consulta semantica que use la sigla ("persona que trabaje
    en GTSI...") no podia encontrar a nadie aunque el documento ya mencionara el nombre
    completo de la unidad (fix de UNIDAD en `construir_eventos_trayectoria`, este mismo
    DEC-022), porque el modelo no sabe que son la misma entidad. Incluir la sigla real junto
    al nombre completo en el texto (no solo el nombre) resuelve esto por coincidencia
    literal, sin inventar informacion: la sigla es un dato institucional real, no derivado.

    Cobertura: 70 de 72 nombres de unidad distintos en `historial_laboral_personas.csv`
    tienen una sigla conocida por coincidencia exacta de texto (97%); los 2 restantes
    simplemente no llevan sigla en el texto (no es un error, solo no hay abreviatura
    conocida para esa unidad).
    """
    mapa = registro_autoridades[["SIGLAS", "NOMBRE"]].dropna().drop_duplicates(subset=["NOMBRE"])
    return dict(zip(mapa["NOMBRE"], mapa["SIGLAS"]))


def _unidad_con_sigla(unidad, mapa_siglas: dict | None):
    if pd.isna(unidad) or not mapa_siglas:
        return unidad
    sigla = mapa_siglas.get(unidad)
    return f"{unidad} ({sigla})" if sigla else unidad


def _nivel_por_nombre_cargo(nombre_cargo) -> str | None:
    """Red de seguridad para clasificar CARGO_ESPOL_GRADO/POSGRADO en
    `construir_eventos_trayectoria` cuando `NIVEL_FUNCION` (columnas `GRADO`/`POSGRADO`
    de `registro_autoridades.csv`) no viene poblado pero el nombre del cargo lo dice
    explicitamente (confirmado con el usuario 2026-09-10: "si el nombre del cargo hace
    referencia [a grado o posgrado], tomalo asi... no asumamos" en caso contrario).
    Casos reales encontrados sin `GRADO`/`POSGRADO` poblado: "Coordinador general de
    postgrado" (44 filas), "Decano de grado" (4 filas). Se busca "posgrado"/"postgrado"
    ANTES que "grado" a secas (substring de ambos) para no clasificar por error un cargo
    de posgrado como si fuera de grado."""
    if not isinstance(nombre_cargo, str):
        return None
    texto = nombre_cargo.lower()
    if "posgrado" in texto or "postgrado" in texto:
        return "POSGRADO"
    if "grado" in texto:
        return "GRADO"
    return None


def construir_eventos_trayectoria(
    tramos_rol: pd.DataFrame,
    funciones_adicionales: pd.DataFrame,
    experiencia_externa: pd.DataFrame | None = None,
    eventos_puntuales: pd.DataFrame | None = None,
    mapa_siglas_unidad: dict | None = None,
) -> pd.DataFrame:
    """Unifica en una sola linea de tiempo por persona los tipos de eventos de trayectoria
    disponibles (ver DEC-014 en context/DECISION_LOG.md): cargo estructural dentro de
    ESPOL (`tramos_rol`, DEC-011), funciones adicionales/subrogaciones
    (`funciones_adicionales`, DEC-012), experiencia laboral externa previa/paralela
    (`experiencia_externa`, opcional) y contratos puntuales/por proyecto dentro de ESPOL
    (`eventos_puntuales`, opcional, ver DEC-018). Pensada para reutilizarse tanto en la
    construccion del documento semantico (07_embeddings) como en la vista de trayectoria
    del dashboard (08_dashboard) - una sola fuente de verdad, no dos implementaciones
    separadas.

    Reglas:
    - De `funciones_adicionales` se excluyen `ES_REPRESENTANTE_ESTUDIANTIL`,
      `ES_RUIDO_CALIDAD_DATOS`, `ES_DUPLICADO_EXACTO=True` (igual que
      `construir_features_funciones_adicionales`) y las que coinciden con el contrato
      vigente (`ES_COINCIDENTE_CONTRATO=True`): esas no aportan un evento nuevo, ya estan
      representadas por el tramo de ESPOL correspondiente - evita mostrar "Docente" y
      "Función: Docente" como si fueran dos cosas distintas.
    - De `experiencia_externa` se excluyen filas sin `CARGO` o sin `FECHADESDE` (no hay
      nada que narrar). Es opcional: si no se pasa, la linea de tiempo queda solo con
      eventos dentro de ESPOL.
    - `eventos_puntuales` (salida de `extraer_eventos_puntuales`, DEC-018): contratos de
      `CATEGORIAS_PUNTUALES` (p.ej. servicios profesionales por proyecto) dentro de ESPOL,
      excluidos por diseño de `tramos_rol`/ESTADO estructural (DEC-004) porque no deben
      generar transiciones de rol falsas - pero SIN esto, estos contratos no aparecian en
      NINGUN lado de la linea de tiempo, incluyendo el mas reciente si sigue vigente (bug
      reportado por un usuario sobre su propio registro: aparecia como si hubiera dejado
      de trabajar en la fecha en que termino su ultimo tramo ESTRUCTURAL, aunque su
      contrato puntual seguia vigente). Se consolidan tramos consecutivos/solapados de la
      misma `CATEGORIA_CARGO` (misma tolerancia que `construir_tramos_rol`) para no
      mostrar cada renovacion anual como una barra separada. Vigencia se calcula con
      `calcular_fecha_fin_efectiva` (respeta `ESTADOCONTRATO` abierto), no con
      `FECHAFINCONTRATO` crudo, que puede estar poblada con una fecha futura de cierre de
      periodo aunque el contrato siga activo.

    Devuelve: IDPERSONA, TIPO_EVENTO, FECHA_INICIO, FECHA_FIN (NaT si vigente), CATEGORIA
    (codigo interno, p.ej. CATEGORIA_CARGO), DESCRIPCION (texto real del cargo/contrato -
    ver nota abajo), UNIDAD, ES_VIGENTE - ordenado por IDPERSONA y FECHA_INICIO.

    `DESCRIPCION` para eventos CARGO_ESPOL* (2026-09-10, bug reportado por el usuario):
    es el texto REAL del cargo (`CARGO_TRAMO` en tramos estructurales, `CARGO` en
    contratos puntuales dentro de ESPOL) - NUNCA el nombre generico de
    `NOMBRES_CATEGORIA_CARGO` (que agrupa docenas de textos de cargo bajo una misma
    categoria de analisis para el clustering, p.ej. "Tecnico operativo / mantenimiento"
    agrupa tanto "TECNICOS ESPECIALIZADOS - EJECUCION DE ACTIVIDADES" como otros cargos
    similares). Caso real: persona 655517, su tramo de
    "TECNICOS ESPECIALIZADOS - EJECUCION DE ACTIVIDADES" se mostraba como el nombre de
    categoria generico, no el cargo real que tuvo. `NOMBRES_CATEGORIA_CARGO` solo se usa
    como respaldo si el texto real viene vacio (no deberia pasar en la practica).

    `TIPO_EVENTO` (2026-09-10, decision confirmada por el usuario): todo lo que ocurre
    dentro de ESPOL se unifica en una sola familia `CARGO_ESPOL*` (ya no existe
    `CONTRATO_PUNTUAL` como categoria aparte: un contrato de servicios profesionales, un
    tramo estructural y una coordinacion academica se presentan todos como "cargo en
    ESPOL", diferenciados solo por grado/posgrado cuando se conoce) - y EXPERIENCIA_EXTERNA
    se separa en Ecuador/exterior. Objetivo: que la timeline del dashboard no mezcle en
    una sola fila cosas conceptualmente distintas (ej. un cargo de grado y uno de
    posgrado simultaneos), sin fragmentar en demasiadas categorias:
    - `CARGO_ESPOL_GRADO` / `CARGO_ESPOL_POSGRADO`: viene de TRES fuentes distintas,
      segun cual aplique a ese evento:
      (a) tramo estructural (`tramos_rol`) con `NIVELDOCENCIA_TRAMO` =
          "DOCENTE PREGRADO"/"DOCENTE POSGRADO" respectivamente;
      (b) contrato puntual dentro de ESPOL (`eventos_puntuales`) con el mismo campo
          `NIVELDOCENCIA` poblado - EN LA PRACTICA, toda la docencia de posgrado cae en
          la categoria `DOCENTE_CONTRATADO_SERVICIOS_CIVILES` (no en un tramo
          estructural), asi que sin (b) el evento CARGO_ESPOL_POSGRADO nunca se
          generaria;
      (c) funcion/subrogacion (`funciones_adicionales`) con `NIVEL_FUNCION` poblado
          (derivado de las columnas `GRADO`/`POSGRADO` del crudo
          `registro_autoridades.csv`, agregadas 2026-09-10) - confirmado con el usuario
          que estas designaciones (coordinador de carrera, de programa de posgrado, de
          practicas empresariales, de vinculacion con la sociedad, de acreditacion
          internacional - se detecta por la columna poblada, no por el nombre del cargo,
          asi que cubre automaticamente si el registro agrega mas casos) son cargos de
          dedicacion continua, no designaciones puntuales: NUNCA generan
          `FUNCION_ADICIONAL`/`SUBROGACION`, siempre `CARGO_ESPOL_GRADO`/`_POSGRADO`. El
          nombre de la carrera/programa (`DETALLE_NIVEL_FUNCION`) se agrega a
          `DESCRIPCION` para texto legible (ej. "Coordinador de carrera — Ingenieria
          Industrial").
      `CARGO_ESPOL` (sin sufijo): cualquier vinculo dentro de ESPOL sin nivel conocido -
      incluye tanto tramos estructurales sin `NIVELDOCENCIA` (la mayoria de cargos
      administrativos) como contratos puntuales sin ese dato (servicios profesionales,
      tribunales, etc. - antes `CONTRATO_PUNTUAL` generico, ahora fusionado aqui) y
      funciones/subrogaciones SIN `NIVEL_FUNCION` (Director, Decano, miembro de consejo,
      etc. - esas SI siguen siendo `FUNCION_ADICIONAL`/`SUBROGACION`, ver abajo).
    - `FUNCION_ADICIONAL` / `SUBROGACION`: designaciones sin `NIVEL_FUNCION` conocido -
      es decir, cualquier funcion/subrogacion que NO sea una de las coordinaciones de
      grado/posgrado descritas arriba. No tienen variante GRADO/POSGRADO: si alguna vez
      aparece una funcion/subrogacion con `NIVEL_FUNCION` poblado que NO deba tratarse
      como cargo, hay que revisar esta regla con el usuario (confirmado 2026-09-10: por
      ahora, tener `NIVEL_FUNCION` poblado implica ser cargo, no funcion adicional).
    - `EXPERIENCIA_EXTERNA_ECUADOR` / `EXPERIENCIA_EXTERNA_EXTERIOR`: segun `PAIS` en
      `experiencia_externa` (columna `PAIS`, no `IDPAIS`) valga "ECUADOR" o cualquier
      otro valor no nulo respectivamente; si `PAIS` es nulo, se usa `EXPERIENCIA_EXTERNA`
      generico.
    """
    eventos = []

    for _, r in tramos_rol.iterrows():
        nivel = r.get("NIVELDOCENCIA_TRAMO")
        if pd.notna(nivel) and nivel == "DOCENTE PREGRADO":
            tipo_cargo = "CARGO_ESPOL_GRADO"
        elif pd.notna(nivel) and nivel == "DOCENTE POSGRADO":
            tipo_cargo = "CARGO_ESPOL_POSGRADO"
        else:
            tipo_cargo = "CARGO_ESPOL"
        eventos.append({
            "IDPERSONA": r["IDPERSONA"], "TIPO_EVENTO": tipo_cargo,
            "FECHA_INICIO": r["TRAMO_INICIO"], "FECHA_FIN": r["TRAMO_FIN"],
            "CATEGORIA": r["CATEGORIA_CARGO"], "TIPOEMPLEADO": r["TIPOEMPLEADO_DESC"],
            # DEC-022 (ver context/DECISION_LOG.md): antes esto era pd.NA fijo - la unidad/
            # dependencia real (ej. "GERENCIA DE TECNOLOGIAS Y SISTEMAS DE INFORMACION")
            # nunca llegaba al texto de trayectoria del cargo estructural, aunque el dato
            # ya existia en tramos_rol.csv desde DEC-016 (UNIDAD_TRAMO). Sin esto, ninguna
            # busqueda semantica que combine "trabaja en <unidad>" con otra condicion podia
            # encontrar a nadie por su unidad actual - solo coincidia por la otra condicion.
            # `_unidad_con_sigla` agrega la sigla real (p.ej. "(GTSI)") cuando se conoce -
            # el modelo de embeddings no sabe que la sigla y el nombre completo son la misma
            # entidad (similitud ~0.79, igual al ruido de anisotropia entre textos NO
            # relacionados), asi que sin la sigla explicita una consulta con la sigla no
            # podia encontrar a nadie de esa unidad aunque el nombre completo ya estuviera.
            "UNIDAD": _unidad_con_sigla(r.get("UNIDAD_TRAMO", pd.NA), mapa_siglas_unidad),
            # DESCRIPCION usa el texto REAL del cargo (CARGO_TRAMO: el CARGO del contrato
            # mas reciente dentro del tramo, ver construir_tramos_rol) - no el nombre
            # generico de CATEGORIA_CARGO (NOMBRES_CATEGORIA_CARGO), que agrupa muchos
            # cargos distintos bajo una misma etiqueta de analisis para el clustering.
            # Bug reportado por el usuario (2026-09-10, persona 655517): su tramo de
            # "TECNICOS ESPECIALIZADOS - EJECUCION DE ACTIVIDADES" se mostraba en la
            # timeline como "Tecnico operativo / mantenimiento" (el nombre de la
            # categoria agrupadora, no el cargo real) - confirmado que el texto real es
            # mas util en esta vista. NOMBRES_CATEGORIA_CARGO solo se usa como respaldo
            # si CARGO_TRAMO viene vacio (no deberia pasar en la practica).
            "DESCRIPCION": r["CARGO_TRAMO"] if pd.notna(r.get("CARGO_TRAMO")) else (
                NOMBRES_CATEGORIA_CARGO.get(r["CATEGORIA_CARGO"], r["CATEGORIA_CARGO"])
            ),
            "ES_VIGENTE": bool(pd.isna(r["TRAMO_FIN"])),
        })

    validas = funciones_adicionales[
        ~funciones_adicionales["ES_REPRESENTANTE_ESTUDIANTIL"]
        & ~funciones_adicionales["ES_RUIDO_CALIDAD_DATOS"]
        & ~funciones_adicionales["ES_DUPLICADO_EXACTO"]
        & (funciones_adicionales["ES_COINCIDENTE_CONTRATO"] != True)  # noqa: E712 (True real, no solo truthy)
    ]
    for _, r in validas.iterrows():
        es_sub = bool(r["ES_SUBROGACION"])
        nivel_funcion = r.get("NIVEL_FUNCION")
        # Confirmado con el usuario (2026-09-10): una designacion con NIVEL_FUNCION
        # poblado (coordinador de carrera/programa de posgrado/practicas empresariales/
        # vinculacion con la sociedad/acreditacion internacional - u otro caso futuro con
        # GRADO/POSGRADO poblado) es un CARGO de dedicacion continua, no una funcion
        # adicional puntual - nunca genera FUNCION_ADICIONAL_GRADO/POSGRADO ni
        # SUBROGACION_GRADO/POSGRADO, siempre CARGO_ESPOL_GRADO/POSGRADO. Si NIVEL_FUNCION
        # no viene poblado, se revisa el nombre del cargo como red de seguridad
        # (`_nivel_por_nombre_cargo`) antes de asumir que es funcion adicional generica -
        # NUNCA se asume nivel sin evidencia explicita (ni columna ni nombre).
        nombre_cargo = r["ROL_SUBROGADO"] if es_sub else r["FUNCION_ADICIONAL"]
        nivel_por_nombre = _nivel_por_nombre_cargo(nombre_cargo) if pd.isna(nivel_funcion) else None
        nivel_efectivo = nivel_funcion if pd.notna(nivel_funcion) else nivel_por_nombre
        if nivel_efectivo == "GRADO":
            tipo_funcion = "CARGO_ESPOL_GRADO"
        elif nivel_efectivo == "POSGRADO":
            tipo_funcion = "CARGO_ESPOL_POSGRADO"
        else:
            tipo_funcion = "SUBROGACION" if es_sub else "FUNCION_ADICIONAL"
        descripcion = nombre_cargo
        detalle_nivel = r.get("DETALLE_NIVEL_FUNCION")
        if pd.notna(detalle_nivel):
            descripcion = f"{descripcion} — {detalle_nivel}"
        eventos.append({
            "IDPERSONA": r["IDPERSONA"], "TIPO_EVENTO": tipo_funcion,
            "FECHA_INICIO": r["FECHA_DESDE"], "FECHA_FIN": r["FECHA_HASTA"],
            "CATEGORIA": r["CATEGORIA_ROL_SUBROGADO"] if es_sub else r["CATEGORIA_FUNCION_ADICIONAL"],
            "TIPOEMPLEADO": pd.NA, "UNIDAD": r["UNIDAD_FUNCION"],
            "DESCRIPCION": descripcion,
            "ES_VIGENTE": bool(pd.isna(r["FECHA_HASTA"])),
        })

    if eventos_puntuales is not None and len(eventos_puntuales):
        punt = eventos_puntuales.dropna(subset=["IDPERSONA", "FECHAINICIOCONTRATO"]).copy()
        punt["_FIN_EFECTIVO"] = calcular_fecha_fin_efectiva(punt)
        punt = punt.sort_values(["IDPERSONA", "FECHAINICIOCONTRATO"], kind="stable")
        tiene_unidad_punt = "NOMBRE_UNIDAD" in punt.columns
        tiene_nivel_punt = "NIVELDOCENCIA" in punt.columns

        tramos_puntuales: list[dict] = []
        for id_persona, grupo in punt.groupby("IDPERSONA", sort=False):
            actual = None
            for _, fila in grupo.iterrows():
                inicio, fin, categoria = fila["FECHAINICIOCONTRATO"], fila["_FIN_EFECTIVO"], fila["CATEGORIA_CARGO"]
                if actual is not None and actual["_CATEGORIA"] == categoria:
                    fin_actual_cmp = pd.Timestamp.max if pd.isna(actual["_FIN"]) else actual["_FIN"]
                    continua = fin_actual_cmp >= inicio or (
                        not pd.isna(actual["_FIN"])
                        and _continuacion_por_corte_de_mes(actual["_FIN"], inicio)
                    )
                    if continua:
                        fin_nuevo_cmp = pd.Timestamp.max if pd.isna(fin) else fin
                        if fin_nuevo_cmp > fin_actual_cmp:
                            actual["_FIN"] = fin
                        actual["_CARGO"] = fila["CARGO"]
                        if tiene_unidad_punt:
                            actual["_UNIDAD"] = fila["NOMBRE_UNIDAD"]
                        if tiene_nivel_punt:
                            actual["_NIVELDOCENCIA"] = fila["NIVELDOCENCIA"]
                        continue
                if actual is not None:
                    tramos_puntuales.append(actual)
                actual = {
                    "_IDPERSONA": id_persona, "_INICIO": inicio, "_FIN": fin,
                    "_CATEGORIA": categoria, "_CARGO": fila["CARGO"],
                    "_UNIDAD": fila["NOMBRE_UNIDAD"] if tiene_unidad_punt else pd.NA,
                    "_NIVELDOCENCIA": fila["NIVELDOCENCIA"] if tiene_nivel_punt else pd.NA,
                }
            if actual is not None:
                tramos_puntuales.append(actual)

        for t in tramos_puntuales:
            nivel_punt = t.get("_NIVELDOCENCIA")
            if pd.notna(nivel_punt) and nivel_punt == "DOCENTE PREGRADO":
                tipo_punt = "CARGO_ESPOL_GRADO"
            elif pd.notna(nivel_punt) and nivel_punt == "DOCENTE POSGRADO":
                tipo_punt = "CARGO_ESPOL_POSGRADO"
            else:
                # Confirmado con el usuario (2026-09-10): ya no existe una lane separada
                # "Contrato puntual (ESPOL)" - cualquier vinculo dentro de ESPOL sin nivel
                # de docencia conocido se presenta como CARGO_ESPOL generico, igual que un
                # tramo estructural sin NIVELDOCENCIA.
                tipo_punt = "CARGO_ESPOL"
            eventos.append({
                "IDPERSONA": t["_IDPERSONA"], "TIPO_EVENTO": tipo_punt,
                "FECHA_INICIO": t["_INICIO"], "FECHA_FIN": t["_FIN"],
                "CATEGORIA": t["_CATEGORIA"], "TIPOEMPLEADO": pd.NA,
                "UNIDAD": _unidad_con_sigla(t.get("_UNIDAD", pd.NA), mapa_siglas_unidad),
                # Mismo criterio que el bloque de tramos_rol arriba: texto real del cargo
                # (_CARGO) primero, nombre generico de categoria solo como respaldo.
                "DESCRIPCION": t["_CARGO"] if pd.notna(t.get("_CARGO")) else (
                    NOMBRES_CATEGORIA_CARGO.get(t["_CATEGORIA"], t["_CATEGORIA"])
                ),
                "ES_VIGENTE": bool(pd.isna(t["_FIN"])),
            })

    if experiencia_externa is not None:
        ext = experiencia_externa[
            experiencia_externa["CARGO"].notna() & experiencia_externa["FECHADESDE"].notna()
        ]
        for _, r in ext.iterrows():
            vigente = bool(r["VIGENTE"]) if "VIGENTE" in ext.columns and pd.notna(r.get("VIGENTE")) else bool(pd.isna(r.get("FECHAHASTA")))
            pais = r.get("PAIS")
            if pd.notna(pais) and str(pais).strip().upper() == "ECUADOR":
                tipo_ext = "EXPERIENCIA_EXTERNA_ECUADOR"
            elif pd.notna(pais):
                tipo_ext = "EXPERIENCIA_EXTERNA_EXTERIOR"
            else:
                tipo_ext = "EXPERIENCIA_EXTERNA"
            eventos.append({
                "IDPERSONA": r["IDPERSONA"], "TIPO_EVENTO": tipo_ext,
                "FECHA_INICIO": r["FECHADESDE"], "FECHA_FIN": r.get("FECHAHASTA"),
                "CATEGORIA": r.get("CATEGORIAEXPERIENCIADESCRIPCION"), "TIPOEMPLEADO": pd.NA,
                "UNIDAD": r.get("INSTITUCION"), "DESCRIPCION": r["CARGO"],
                "ES_VIGENTE": vigente,
            })

    columnas = ["IDPERSONA", "TIPO_EVENTO", "FECHA_INICIO", "FECHA_FIN", "CATEGORIA",
                "TIPOEMPLEADO", "UNIDAD", "DESCRIPCION", "ES_VIGENTE"]
    if not eventos:
        return pd.DataFrame(columns=columnas)
    df = pd.DataFrame(eventos)[columnas]
    return df.sort_values(["IDPERSONA", "FECHA_INICIO"], kind="stable").reset_index(drop=True)


def detectar_transiciones_rol(tramos_rol: pd.DataFrame) -> pd.DataFrame:
    """A partir de `construir_tramos_rol`, arma una fila por par de tramos consecutivos
    de la misma persona cuya `CATEGORIA_CARGO` cambia (una transicion de rol observada).

    `GAP_DIAS` es la distancia entre el fin del tramo de origen y el inicio del tramo de
    destino (puede ser negativa si se solapan, p.ej. por contratos simultaneos en
    unidades distintas); un gap grande no descarta la transicion, solo advierte que no
    fue inmediata (p.ej. un reingreso años despues a otro rol) - queda a criterio del
    analisis posterior filtrar por `GAP_DIAS` si se quiere distinguir ambos casos.

    Devuelve: IDPERSONA, TIPOEMPLEADO_ORIGEN, CATEGORIA_ORIGEN, TIPOEMPLEADO_DESTINO,
    CATEGORIA_DESTINO, TIPO_TRANSICION (AA_A_AA/AA_A_DD/DD_A_AA/DD_A_DD),
    FECHA_FIN_ORIGEN, FECHA_INICIO_DESTINO, GAP_DIAS.
    """
    filas = []
    ordenado = tramos_rol.sort_values(["IDPERSONA", "TRAMO_INICIO"], kind="stable")
    for id_persona, grupo in ordenado.groupby("IDPERSONA", sort=False):
        grupo = grupo.reset_index(drop=True)
        for i in range(len(grupo) - 1):
            origen, destino = grupo.iloc[i], grupo.iloc[i + 1]
            if origen["CATEGORIA_CARGO"] == destino["CATEGORIA_CARGO"]:
                continue
            fin_origen = origen["TRAMO_FIN"]
            inicio_destino = destino["TRAMO_INICIO"]
            gap_dias = (inicio_destino - fin_origen).days if not pd.isna(fin_origen) else pd.NA
            filas.append({
                "IDPERSONA": id_persona,
                "TIPOEMPLEADO_ORIGEN": origen["TIPOEMPLEADO_DESC"],
                "CATEGORIA_ORIGEN": origen["CATEGORIA_CARGO"],
                "TIPOEMPLEADO_DESTINO": destino["TIPOEMPLEADO_DESC"],
                "CATEGORIA_DESTINO": destino["CATEGORIA_CARGO"],
                "TIPO_TRANSICION": (
                    f"{'AA' if origen['TIPOEMPLEADO_DESC'] == 'ADMINISTRATIVO' else 'DD'}"
                    "_A_"
                    f"{'AA' if destino['TIPOEMPLEADO_DESC'] == 'ADMINISTRATIVO' else 'DD'}"
                ),
                "FECHA_FIN_ORIGEN": fin_origen,
                "FECHA_INICIO_DESTINO": inicio_destino,
                "GAP_DIAS": gap_dias,
            })
    columnas = [
        "IDPERSONA", "TIPOEMPLEADO_ORIGEN", "CATEGORIA_ORIGEN", "TIPOEMPLEADO_DESTINO",
        "CATEGORIA_DESTINO", "TIPO_TRANSICION", "FECHA_FIN_ORIGEN", "FECHA_INICIO_DESTINO", "GAP_DIAS",
    ]
    return pd.DataFrame(filas, columns=columnas) if filas else pd.DataFrame(columns=columnas)


def construir_features_trayectoria(
    tramos_rol: pd.DataFrame,
    transiciones_rol: pd.DataFrame,
    roles_adicionales_simultaneos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Construye una tabla de features de trayectoria **por persona** (una fila por
    IDPERSONA) a partir de `construir_tramos_rol` y `detectar_transiciones_rol`, pensada
    para fusionarse al dataset de modelado/clustering (ver DEC-006 en
    `context/DECISION_LOG.md`: las features de trayectoria deben alimentar el clustering,
    no quedar como analisis aparte).

    Features:
    - N_TRAMOS_ROL: cantidad de tramos de rol estructural que tuvo la persona.
    - N_CATEGORIAS_ROL_DISTINTAS: cantidad de `CATEGORIA_CARGO` distintas por las que pasó.
    - CATEGORIA_CARGO_ACTUAL: la categoria del tramo vigente (`TRAMO_FIN` nulo); si no
      tiene tramo vigente, la del tramo mas reciente por `TRAMO_INICIO`.
    - TIPOEMPLEADO_CATEGORIA_ACTUAL: el `TIPOEMPLEADO_DESC` del *mismo tramo* usado para
      `CATEGORIA_CARGO_ACTUAL` (no se recalcula por separado desde otra fuente). Como
      `CATEGORIA_CARGO` ya se clasifica por rama dentro de `clasificar_categoria_cargo`
      (nunca se comparten reglas entre AA y DD), esta columna es, por construccion, siempre
      consistente con `CATEGORIA_CARGO_ACTUAL` — a diferencia de `TIPOEMPLEADO_ACTUAL_DESC`
      de `historial_laboral_features.csv` (calculado por separado, sobre el ultimo contrato
      por fecha), que puede no coincidir en rama si el contrato mas reciente de una persona
      es de categoria puntual o de ruido de calidad de datos (ver DEC-010 en
      `context/DECISION_LOG.md`). Usar esta columna, no `TIPOEMPLEADO_ACTUAL_DESC`, como
      nivel 1 de la jerarquia AA/DD cuando se agrupa por `CATEGORIA_CARGO_ACTUAL`.
    - ANIOS_EN_CATEGORIA_ACTUAL: antigüedad en la categoria actual, en años (fin efectivo
      -hoy si vigente- menos `TRAMO_INICIO`, entre 365.25).
    - CATEGORIA_CARGO_PRIMERA: la categoria de su primer tramo (punto de entrada a la
      institucion, dentro de la ventana de datos disponible).
    - ES_TRAYECTORIA_ESTABLE: True si nunca tuvo una transicion de rol (`N_TRAMOS_ROL<=1`
      o todos los tramos son de la misma categoria).
    - N_TRANSICIONES_ROL, N_TRANSICIONES_AA_A_DD, N_TRANSICIONES_DD_A_AA: conteos de
      transiciones totales y por tipo (ver `detectar_transiciones_rol`).
    - TUVO_TRANSICION_AA_A_DD, TUVO_TRANSICION_DD_A_AA: version booleana de los conteos
      anteriores (mas robusta para clustering que el conteo crudo, que es sensible al
      patron de "encargos cortos" documentado en DEC-004/`04_trayectorias.ipynb`).
    - ANIOS_DESDE_ULTIMA_TRANSICION: años desde la transicion de rol mas reciente (NA si
      nunca tuvo una).
    - TUVO_ROL_ADICIONAL_SIMULTANEO: True si `roles_adicionales_simultaneos` (ver
      `resolver_roles_simultaneos`, DEC-011) tiene al menos un registro para la persona —
      alguna vez ejercio un rol (tipicamente de autoridad) en paralelo a su cargo
      estructural, sin que eso cuente como transicion. Parametro opcional: si no se pasa
      `roles_adicionales_simultaneos`, queda en False para todos (compatibilidad).
    - N_ROLES_ADICIONALES_SIMULTANEOS_DISTINTOS: cantidad de `CATEGORIA_CARGO` distintas
      entre esos roles adicionales.
    - CATEGORIA_ROL_ADICIONAL_MAS_RECIENTE: la categoria del rol adicional simultaneo mas
      reciente (NA si `TUVO_ROL_ADICIONAL_SIMULTANEO=False`) — pensada para mostrarse como
      atributo/afinidad en el dashboard (ver DEC-009), no como una categoria de agrupamiento
      nueva.
    - CARGO_ACTUAL_ESTRUCTURAL, UNIDAD_ACTUAL_ESTRUCTURAL (DEC-016): el `CARGO_TRAMO`/
      `UNIDAD_TRAMO` (texto original, ver `construir_tramos_rol`) del *mismo tramo* usado
      para `CATEGORIA_CARGO_ACTUAL` — a diferencia de `CARGO_ACTUAL`/`UNIDAD_ACTUAL_NOMBRE`
      de `dataset_personas_features.csv` (calculados por separado, sobre el ultimo contrato
      por fecha SIN excluir categorias puntuales/de ruido), estos siempre corresponden al
      cargo estructural real que determina el perfil de la persona - mismo motivo que
      `TIPOEMPLEADO_CATEGORIA_ACTUAL` en DEC-010.
    - VIGENTE_TRAMO_ESTRUCTURAL (DEC-017): True si el tramo usado para `CATEGORIA_CARGO_ACTUAL`
      (`actual`) sigue vigente hoy (`TRAMO_FIN` nulo); False si `CATEGORIA_CARGO_ACTUAL` viene
      del ultimo tramo estructural ya finalizado porque la persona no tiene ninguno activo en
      este momento. Util para decidir si `CARGO_ACTUAL_ESTRUCTURAL` sigue reflejando lo que la
      persona hace hoy, o si conviene mostrar en su lugar un contrato puntual vigente (ver
      `construir_contrato_puntual_vigente`) — sin que esto cambie `CLUSTER`/
      `CATEGORIA_CARGO_ACTUAL`, que siguen basados en el tramo estructural.

    Personas sin tramos de rol (p.ej. solo tuvieron contratos de categorias puntuales,
    ver `CATEGORIAS_PUNTUALES`) no aparecen en el resultado — se dejan sin features de
    trayectoria en vez de forzar valores, y quien fusione esta tabla debe decidir el
    tratamiento de esos nulos (no se asume 0 por defecto).
    """
    hoy = pd.Timestamp.today().normalize()

    tramos = tramos_rol.sort_values(["IDPERSONA", "TRAMO_INICIO"], kind="stable").copy()
    tramos["_FIN_CMP"] = tramos["TRAMO_FIN"].fillna(hoy)
    tramos["_VIGENTE"] = tramos["TRAMO_FIN"].isna()

    filas = []
    for id_persona, grupo in tramos.groupby("IDPERSONA", sort=False):
        vigente = grupo[grupo["_VIGENTE"]]
        actual = vigente.iloc[-1] if len(vigente) else grupo.iloc[-1]
        primera = grupo.iloc[0]
        # max(..., 0): un tramo "POR EJECUTARSE" (calcular_fecha_fin_efectiva) puede
        # iniciar unos dias despues de "hoy" y quedar marcado vigente antes de empezar;
        # se trata como antiguedad 0 en la categoria, no como error.
        anios_actual = max((actual["_FIN_CMP"] - actual["TRAMO_INICIO"]).days / 365.25, 0)

        filas.append({
            "IDPERSONA": id_persona,
            "N_TRAMOS_ROL": len(grupo),
            "N_CATEGORIAS_ROL_DISTINTAS": grupo["CATEGORIA_CARGO"].nunique(),
            "CATEGORIA_CARGO_ACTUAL": actual["CATEGORIA_CARGO"],
            "TIPOEMPLEADO_CATEGORIA_ACTUAL": actual["TIPOEMPLEADO_DESC"],
            "CARGO_ACTUAL_ESTRUCTURAL": actual.get("CARGO_TRAMO"),
            "UNIDAD_ACTUAL_ESTRUCTURAL": actual.get("UNIDAD_TRAMO"),
            "VIGENTE_TRAMO_ESTRUCTURAL": bool(actual["_VIGENTE"]),
            "ANIOS_EN_CATEGORIA_ACTUAL": round(anios_actual, 2),
            "CATEGORIA_CARGO_PRIMERA": primera["CATEGORIA_CARGO"],
            "ES_TRAYECTORIA_ESTABLE": bool(grupo["CATEGORIA_CARGO"].nunique() <= 1),
        })
    features = pd.DataFrame(filas)

    if len(transiciones_rol):
        resumen_trans = (
            transiciones_rol.groupby("IDPERSONA")
            .agg(
                N_TRANSICIONES_ROL=("TIPO_TRANSICION", "size"),
                N_TRANSICIONES_AA_A_DD=("TIPO_TRANSICION", lambda s: (s == "AA_A_DD").sum()),
                N_TRANSICIONES_DD_A_AA=("TIPO_TRANSICION", lambda s: (s == "DD_A_AA").sum()),
                ULTIMA_TRANSICION_FECHA=("FECHA_INICIO_DESTINO", "max"),
            )
            .reset_index()
        )
        resumen_trans["TUVO_TRANSICION_AA_A_DD"] = resumen_trans["N_TRANSICIONES_AA_A_DD"] > 0
        resumen_trans["TUVO_TRANSICION_DD_A_AA"] = resumen_trans["N_TRANSICIONES_DD_A_AA"] > 0
        # clip a 0: un tramo "POR EJECUTARSE" (ver calcular_fecha_fin_efectiva) puede
        # iniciar unos dias despues de "hoy", lo que daria un "años desde" negativo -
        # se trata como una transicion recien ocurrida (0), no como error.
        anios_desde = (hoy - pd.to_datetime(resumen_trans["ULTIMA_TRANSICION_FECHA"])).dt.days / 365.25
        resumen_trans["ANIOS_DESDE_ULTIMA_TRANSICION"] = round(anios_desde.clip(lower=0), 2)
        resumen_trans = resumen_trans.drop(columns=["ULTIMA_TRANSICION_FECHA"])
        features = features.merge(resumen_trans, on="IDPERSONA", how="left")
        for c in ["N_TRANSICIONES_ROL", "N_TRANSICIONES_AA_A_DD", "N_TRANSICIONES_DD_A_AA"]:
            features[c] = features[c].fillna(0).astype(int)
        for c in ["TUVO_TRANSICION_AA_A_DD", "TUVO_TRANSICION_DD_A_AA"]:
            features[c] = features[c].fillna(False)

    if roles_adicionales_simultaneos is not None and len(roles_adicionales_simultaneos):
        resumen_ras = (
            roles_adicionales_simultaneos.sort_values(["IDPERSONA", "TRAMO_INICIO"], kind="stable")
            .groupby("IDPERSONA")
            .agg(
                N_ROLES_ADICIONALES_SIMULTANEOS_DISTINTOS=("CATEGORIA_CARGO", "nunique"),
                CATEGORIA_ROL_ADICIONAL_MAS_RECIENTE=("CATEGORIA_CARGO", "last"),
            )
            .reset_index()
        )
        resumen_ras["TUVO_ROL_ADICIONAL_SIMULTANEO"] = True
        features = features.merge(resumen_ras, on="IDPERSONA", how="left")
        features["TUVO_ROL_ADICIONAL_SIMULTANEO"] = features["TUVO_ROL_ADICIONAL_SIMULTANEO"].fillna(False)
        features["N_ROLES_ADICIONALES_SIMULTANEOS_DISTINTOS"] = (
            features["N_ROLES_ADICIONALES_SIMULTANEOS_DISTINTOS"].fillna(0).astype(int)
        )
    else:
        features["TUVO_ROL_ADICIONAL_SIMULTANEO"] = False
        features["N_ROLES_ADICIONALES_SIMULTANEOS_DISTINTOS"] = 0
        features["CATEGORIA_ROL_ADICIONAL_MAS_RECIENTE"] = pd.NA

    return features


def _cambio_respecto_anterior(serie: pd.Series) -> pd.Series:
    """Serie booleana: True donde el valor difiere del inmediato anterior (la
    primera fila siempre es True). Dos nulos consecutivos cuentan como "sin
    cambio" (a diferencia de comparar con != directamente, donde NaN != NaN
    es True)."""
    anterior = serie.shift()
    return ~((serie == anterior) | (serie.isna() & anterior.isna()))


def construir_features_historial_laboral(
    df: pd.DataFrame, periodos_continuos: pd.DataFrame, incluir_rmu: bool = False
) -> pd.DataFrame:
    """Construye una tabla de features por IDPERSONA a partir del historial laboral
    (contratos individuales) y sus periodos continuos ya calculados
    (`calcular_periodos_continuos`), pensada como insumo de clustering/perfilamiento.

    Incluye, cuando las columnas de origen existen en `df`:
    - N_REGISTROS_HISTORIAL: cantidad cruda de filas/registros de
      historialaboralpersonas.csv para la persona (incluye movimientos
      administrativos que no son un contrato nuevo, ver TIPO mas abajo).
    - N_CONTRATOS_TOTAL: cantidad de "contratos" entendidos como cambios reales
      de CARGO o de RMU a lo largo de la linea de tiempo (dos filas consecutivas
      con el mismo cargo y la misma RMU se cuentan como un solo contrato). Es
      mas representativo que N_REGISTROS_HISTORIAL porque el CSV crudo puede
      traer varias filas para lo que en la practica es el mismo contrato.
    - Antiguedad: fecha de primer ingreso, antiguedad efectiva (suma de dias de
      periodos continuos, sin contar brechas reales) y antiguedad de calendario
      (primer ingreso a hoy o al fin del ultimo periodo), numero de periodos
      continuos y de reingresos, y si tiene vinculacion vigente.
    - Tipo de empleado: rol actual, si ha sido docente y administrativo a la vez,
      y anios de experiencia aproximados por rol: suma de dias de contrato de
      ese tipo (fin efectivo, o hoy si sigue vigente, menos inicio) dividida
      entre 365.25 (para promediar anios bisiestos) y redondeada a 2 decimales.
      Es un numero decimal de anios, no anios+meses: p.ej. 5.01 son ~5 anios y
      ~4 dias (0.01 * 365.25 ~= 3.65 dias), y 0.5 equivale a medio anio (~6
      meses). Puede sobreestimarse levemente si hay contratos simultaneos del
      mismo tipo, ya que no se fusiona solapamiento dentro de un mismo rol.
    - Dedicacion docente (TIPODEDICACION): la mas reciente, la mas frecuente y
      cuantas distintas tuvo (solo si la columna existe, ej. no en muestras solo
      administrativas donde se elimina por nulidad).
    - Cargos: cantidad de cargos distintos, cargo actual, cargo mas frecuente,
      y si en algun anio calendario tuvo mas de un cargo distinto.
    - Movilidad: cantidad de unidades distintas por IDESTRUCTURAORGANICA (no por
      IDUNIDAD/IDUNIDADACADEMICAFIS, identificadores de estructuras anteriores
      menos confiables), nombre de la unidad actual (NOMBRE_UNIDAD), cantidad de
      facultades distintas y si en algun momento paso por rectorado/vicerrectorado
      (deteccion por texto en NOMBRE_UNIDAD: "FACULTAD" / "RECTORADO").
    - Regimen laboral: regimen inicial y actual (descripcion), y cantidad de
      regimenes distintos.
    - RMU (solo si incluir_rmu=True): inicial, actual, minimo, maximo, promedio,
      crecimiento absoluto y porcentual, y numero de cambios de RMU entre
      contratos consecutivos.
    - Estabilidad contractual: proporcion de contratos finalizados
      (ESTADOCONTRATO == 'FF') sobre el total, considerando solo filas con
      TIPO == 'V' (vinculacion) si la columna TIPO existe. TIPO == 'M' suele
      corresponder a movimientos (vacaciones, licencias, etc.) y no a una
      desvinculacion real, pero esa clasificacion aun no esta depurada del
      todo, por lo que de momento solo se filtra por 'V' sin mas tratamiento.

    `incluir_rmu` (default False): las features de RMU se omiten por defecto,
    porque el historico mezcla montos en sucres y en dolares (transicion
    monetaria de Ecuador, ano 2000) sin una conversion/normalizacion aun
    implementada, lo que haria enganosas comparaciones de evolucion o magnitud
    de RMU entre distintas epocas. Pasar incluir_rmu=True solo cuando se tenga
    resuelta esa conversion.
    """
    requeridas = ["IDPERSONA", "FECHAINICIOCONTRATO"]
    faltantes = [c for c in requeridas if c not in df.columns]
    if faltantes:
        raise KeyError(f"Faltan columnas requeridas: {faltantes}")

    trabajo = df.dropna(subset=["IDPERSONA", "FECHAINICIOCONTRATO"]).copy()
    trabajo["_FECHAFIN_EFECTIVA"] = calcular_fecha_fin_efectiva(trabajo)
    hoy = pd.Timestamp.today().normalize()
    trabajo["_DURACION_DIAS_CONTRATO"] = (
        trabajo["_FECHAFIN_EFECTIVA"].fillna(hoy) - trabajo["FECHAINICIOCONTRATO"]
    ).dt.days + 1
    trabajo["_ANIO_INICIO"] = trabajo["FECHAINICIOCONTRATO"].dt.year
    trabajo = trabajo.sort_values(["IDPERSONA", "FECHAINICIOCONTRATO"], kind="stable")

    filas = []
    for id_persona, grupo in trabajo.groupby("IDPERSONA", sort=False):
        primero, ultimo = grupo.iloc[0], grupo.iloc[-1]
        feats = {"IDPERSONA": id_persona, "N_REGISTROS_HISTORIAL": len(grupo)}

        columnas_contrato = [c for c in ("CARGO", "RMU") if c in grupo.columns]
        if columnas_contrato:
            cambios = pd.Series(False, index=grupo.index)
            for c in columnas_contrato:
                cambios = cambios | _cambio_respecto_anterior(grupo[c])
            feats["N_CONTRATOS_TOTAL"] = int(cambios.sum())
        else:
            feats["N_CONTRATOS_TOTAL"] = len(grupo)

        if "CARGO" in grupo.columns:
            feats["N_CARGOS_DISTINTOS"] = grupo["CARGO"].nunique(dropna=True)
            feats["CARGO_ACTUAL"] = ultimo.get("CARGO", pd.NA)
            no_nulos = grupo["CARGO"].dropna()
            feats["CARGO_MAS_FRECUENTE"] = no_nulos.mode().iloc[0] if len(no_nulos) else pd.NA
            cargos_por_anio = grupo.groupby("_ANIO_INICIO")["CARGO"].nunique(dropna=True)
            feats["MULTIPLES_CARGOS_MISMO_ANIO"] = bool((cargos_por_anio > 1).any())

        if "IDESTRUCTURAORGANICA" in grupo.columns:
            feats["N_UNIDADES_DISTINTAS"] = grupo["IDESTRUCTURAORGANICA"].nunique(dropna=True)

        if "NOMBRE_UNIDAD" in grupo.columns:
            feats["UNIDAD_ACTUAL_NOMBRE"] = ultimo.get("NOMBRE_UNIDAD", pd.NA)
            nombres_unidad = grupo["NOMBRE_UNIDAD"].dropna()
            es_facultad = nombres_unidad.str.contains("FACULTAD", case=False, na=False)
            es_rectorado = nombres_unidad.str.contains("RECTORADO", case=False, na=False)
            feats["N_FACULTADES_DISTINTAS"] = nombres_unidad[es_facultad].nunique(dropna=True)
            feats["PASO_POR_RECTORADO"] = bool(es_rectorado.any())

        if "IDREGIMENLABORAL_DESC" in grupo.columns:
            feats["N_REGIMENES_DISTINTOS"] = grupo["IDREGIMENLABORAL_DESC"].nunique(dropna=True)
            feats["REGIMEN_INICIAL_DESC"] = primero.get("IDREGIMENLABORAL_DESC", pd.NA)
            feats["REGIMEN_ACTUAL_DESC"] = ultimo.get("IDREGIMENLABORAL_DESC", pd.NA)

        if "TIPOEMPLEADO_DESC" in grupo.columns:
            tipos = set(grupo["TIPOEMPLEADO_DESC"].dropna().unique())
            feats["TIPOEMPLEADO_ACTUAL_DESC"] = ultimo.get("TIPOEMPLEADO_DESC", pd.NA)
            feats["ES_DOCENTE_ADMIN_MIXTO"] = len(tipos) > 1
            for tipo in ("DOCENTE", "ADMINISTRATIVO"):
                dias = grupo.loc[grupo["TIPOEMPLEADO_DESC"] == tipo, "_DURACION_DIAS_CONTRATO"].sum()
                feats[f"ANIOS_EXPERIENCIA_{tipo}"] = round(dias / 365.25, 2)

            if "TIPODEDICACION" in grupo.columns:
                docentes = grupo[grupo["TIPOEMPLEADO_DESC"] == "DOCENTE"]
                dedic = docentes["TIPODEDICACION"].dropna()
                feats["DEDICACION_DOCENTE_ACTUAL"] = dedic.iloc[-1] if len(dedic) else pd.NA
                feats["DEDICACION_DOCENTE_MAS_FRECUENTE"] = dedic.mode().iloc[0] if len(dedic) else pd.NA
                feats["N_DEDICACIONES_DOCENTE_DISTINTAS"] = dedic.nunique()

        if incluir_rmu and "RMU" in grupo.columns:
            rmu = grupo["RMU"].dropna()
            if len(rmu):
                inicial, actual = rmu.iloc[0], rmu.iloc[-1]
                feats["RMU_INICIAL"] = inicial
                feats["RMU_ACTUAL"] = actual
                feats["RMU_MIN"] = rmu.min()
                feats["RMU_MAX"] = rmu.max()
                feats["RMU_PROMEDIO"] = round(rmu.mean(), 2)
                feats["RMU_CRECIMIENTO_ABS"] = actual - inicial
                feats["RMU_CRECIMIENTO_PCT"] = round((actual - inicial) / inicial * 100, 2) if inicial else pd.NA
                feats["N_CAMBIOS_RMU"] = int((rmu.diff().dropna() != 0).sum())

        if "ESTADOCONTRATO" in grupo.columns:
            base_vinculacion = grupo[grupo["TIPO"] == "V"] if "TIPO" in grupo.columns else grupo
            feats["PROPORCION_CONTRATOS_FINALIZADOS"] = (
                round((base_vinculacion["ESTADOCONTRATO"] == "FF").mean(), 2) if len(base_vinculacion) else pd.NA
            )

        filas.append(feats)

    features = pd.DataFrame(filas)

    if periodos_continuos is not None and not periodos_continuos.empty:
        fin_cmp = periodos_continuos["PERIODO_FIN"].fillna(hoy)
        resumen_periodos = (
            periodos_continuos.assign(_FIN_CMP=fin_cmp)
            .groupby("IDPERSONA")
            .agg(
                FECHA_PRIMER_INGRESO=("PERIODO_INICIO", "min"),
                FECHA_ULTIMO_PERIODO_FIN=("_FIN_CMP", "max"),
                N_PERIODOS_CONTINUOS=("PERIODO_INICIO", "size"),
                ANTIGUEDAD_EFECTIVA_DIAS=("PERIODO_DURACION_DIAS", "sum"),
                VIGENTE_ACTUALMENTE=("PERIODO_VIGENTE", "any"),
            )
            .reset_index()
        )
        resumen_periodos["ANTIGUEDAD_EFECTIVA_ANIOS"] = round(
            resumen_periodos["ANTIGUEDAD_EFECTIVA_DIAS"] / 365.25, 2
        )
        resumen_periodos["ANTIGUEDAD_CALENDARIO_DIAS"] = (
            resumen_periodos["FECHA_ULTIMO_PERIODO_FIN"] - resumen_periodos["FECHA_PRIMER_INGRESO"]
        ).dt.days + 1
        resumen_periodos["ANTIGUEDAD_CALENDARIO_ANIOS"] = round(
            resumen_periodos["ANTIGUEDAD_CALENDARIO_DIAS"] / 365.25, 2
        )
        resumen_periodos["N_REINGRESOS"] = resumen_periodos["N_PERIODOS_CONTINUOS"] - 1
        features = features.merge(resumen_periodos, on="IDPERSONA", how="left")

    return features
