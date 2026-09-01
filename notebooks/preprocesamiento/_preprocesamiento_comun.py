"""Utilidades comunes de preprocesamiento.

Proyecto de tesis: Sistema de Generacion de Perfiles del Personal Docente y
Administrativo en ESPOL para la asignacion inteligente de tareas.

Funciones compartidas por los notebooks de notebooks/preprocesamiento para
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
    DB2 (YYYY-MM-DD-HH.MM.SS.ffffff)."""
    s = serie.astype("string")
    normalizado = s.str.replace(_DB2_TS, r"\1 \2:\3:\4.\5", regex=True)
    return pd.to_datetime(normalizado, errors="coerce")


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
    usando data/raw/diccionarioexperienciaexterna.txt."""
    df = df.copy()
    if "CATEXPERIENCIA" in df.columns:
        df["CATEXPERIENCIA_DESC"] = df["CATEXPERIENCIA"].map(CATEGORIA_EXPERIENCIA)
    if "ROLACADEMICOEXPERIENCIA" in df.columns:
        df["ROLACADEMICOEXPERIENCIA_DESC"] = df["ROLACADEMICOEXPERIENCIA"].map(ROL_ACADEMICO_EXPERIENCIA)
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


def calcular_periodos_continuos(df: pd.DataFrame) -> pd.DataFrame:
    """Fusiona los contratos de historialaboralpersonas.csv en periodos continuos
    de vinculacion por IDPERSONA (replica AuxiliarObtenerHistoriaContinua del
    sistema origen).

    Reglas:
    - La fecha fin efectiva de un contrato es FECHADESVINCULACION si existe;
      si no, FECHAFINCONTRATO; si ninguna existe, el contrato esta vigente
      (sin fecha fin).
    - Los contratos de cada persona se procesan ordenados por
      FECHAINICIOCONTRATO. Dos contratos consecutivos se fusionan en el mismo
      periodo si se solapan (incluye un contrato totalmente contenido en el
      periodo actual, que simplemente se ignora sin retroceder el fin), son
      exactamente contiguos, o dejan una brecha corta tolerada por
      `_continuacion_por_corte_de_mes`.
    - Un periodo vigente (sin fecha fin) se preserva como vigente al fusionar:
      una fecha fin real nunca reemplaza una vigencia ya detectada.
    - Cualquier otra brecha cierra el periodo actual y abre uno nuevo.

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
    fin_efectivo = (
        trabajo["FECHADESVINCULACION"].copy()
        if "FECHADESVINCULACION" in trabajo.columns
        else pd.Series(pd.NaT, index=trabajo.index)
    )
    if "FECHAFINCONTRATO" in trabajo.columns:
        fin_efectivo = fin_efectivo.fillna(trabajo["FECHAFINCONTRATO"])
    trabajo["_FECHAFIN_EFECTIVA"] = fin_efectivo
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
                fin_nuevo_cmp = pd.Timestamp.max if pd.isna(fin) else fin
                if fin_nuevo_cmp > fin_actual_cmp:
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
    fin_efectivo = (
        trabajo["FECHADESVINCULACION"].copy()
        if "FECHADESVINCULACION" in trabajo.columns
        else pd.Series(pd.NaT, index=trabajo.index)
    )
    if "FECHAFINCONTRATO" in trabajo.columns:
        fin_efectivo = fin_efectivo.fillna(trabajo["FECHAFINCONTRATO"])
    trabajo["_FECHAFIN_EFECTIVA"] = fin_efectivo
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
