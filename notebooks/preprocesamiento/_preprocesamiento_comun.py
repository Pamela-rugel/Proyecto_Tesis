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
