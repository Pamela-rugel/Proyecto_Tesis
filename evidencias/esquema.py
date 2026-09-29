"""Esquema comun de evidencia y utilidades compartidas por todas las secciones.

Una evidencia es un item individual y trazable del perfil de una persona:

    evidencia_id  identificador estable del item (no de la persona)
    persona_id    IDPERSONA
    tipo_id       subtipo de evidencia (p.ej. TRAYECTORIA_CARGO_ESTRUCTURAL)
    texto         descripcion breve que se embebera despues - sin IDs ni fechas
    atributos     JSON con las caracteristicas estructuradas propias del subtipo

Las fechas son atributos (2026-09-27, decision del usuario): `fecha_inicio` y `fecha_fin`
en `atributos` (ISO o null; nunca se inventan). Cuando una evidencia agrupa varios periodos
(p.ej. el mismo cargo ejercido con saltos), `fecha_inicio` es el primer inicio, `fecha_fin`
el ultimo fin (null si algun periodo sigue abierto) y el detalle va en `periodos`.

Convencion de `atributos`: las claves de negocio van en snake_case; la clave reservada
`_origen` guarda la trazabilidad (archivo fuente y claves de la fila original), para que
cualquier columna no copiada a la evidencia pueda recuperarse desde su fuente.
"""
from __future__ import annotations

import hashlib
import json
import re

import numpy as np
import pandas as pd

COLUMNAS_EVIDENCIA = ["evidencia_id", "persona_id", "tipo_id", "texto", "atributos"]


def hoy() -> pd.Timestamp:
    return pd.Timestamp.today().normalize()


def generar_evidencia_id(prefijo: str, *partes) -> str:
    """ID determinista: el mismo item de la fuente produce siempre el mismo ID entre
    corridas (no depende del orden de filas ni de la fecha de ejecucion)."""
    clave = "|".join("" if valor_nulo(p) else str(p) for p in partes)
    return f"{prefijo}-{hashlib.sha1(clave.encode('utf-8')).hexdigest()[:12]}"


def valor_nulo(v) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def fecha_iso(v) -> str | None:
    if valor_nulo(v):
        return None
    return pd.Timestamp(v).strftime("%Y-%m-%d")


def texto_limpio(v) -> str | None:
    """Texto recortado, o None si esta vacio o es un marcador de desconocido."""
    if valor_nulo(v):
        return None
    s = str(v).strip()
    if not s or s.upper() in {"DESCONOCIDA", "DESCONOCIDO", "NAN", "NONE", "SIN_DATO"}:
        return None
    return s


def normalizar_para_comparar(texto) -> str:
    """Mayusculas, sin tildes ni signos, espacios simples - solo para COMPARAR textos."""
    import unicodedata
    if valor_nulo(texto):
        return ""
    s = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii").upper()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s)).strip()


def limpiar_para_mostrar(texto) -> str | None:
    """Texto para mostrar: espacios (incluidos saltos de linea) colapsados; None si vacio."""
    t = texto_limpio(texto)
    return re.sub(r"\s+", " ", t).strip() if t else None


_ESPOL = re.compile(r"\b(?:ESCUELA\s+SUPERIOR\s+POLIT[EÉ]CNICA\s+DEL\s+LITORAL|ESPOL)\b", re.IGNORECASE)
_CONECTOR_INICIO = re.compile(r"^(?:LA|EL|Y|E|&|DE)\s+", re.IGNORECASE)
_CONECTOR_FIN = re.compile(r"\s+(?:LA|EL|Y|E|&|DE)$", re.IGNORECASE)


def quitar_espol(texto) -> str | None:
    """Para el TEXTO de una evidencia (regla: sin 'ESPOL'): quita ESPOL o su nombre largo de
    una institucion y deja el resto ("CISE - ESPOL" -> "CISE", "CRUZ ROJA ECUATORIANA Y
    ESPOL" -> "CRUZ ROJA ECUATORIANA"). None si solo era ESPOL."""
    t = limpiar_para_mostrar(texto)
    if not t or not _ESPOL.search(t):
        return t  # sin ESPOL: el texto no se toca
    s = _ESPOL.sub("", t)
    s = re.sub(r"\(\s*\)", "", s)
    s = re.sub(r"\s+([,;])", r"\1", s)
    s = re.sub(r"\s*[-–—/]\s*(?=[,;]|$)", "", s)
    s = re.sub(r"(^|[,;(])\s*[-–—/,;]+\s*", r"\1", s)
    s = re.sub(r"\s*[-–—/]\s*[-–—/]\s*", " - ", s)
    s = re.sub(r"\s{2,}", " ", s).strip(" -–—/,;.")
    previo = None
    while previo != s:
        previo = s
        s = _CONECTOR_FIN.sub("", _CONECTOR_INICIO.sub("", s)).strip(" -–—/,;.")
    return s or None


def es_vigente(fin, fecha_corte: pd.Timestamp) -> bool:
    """Regla del proyecto: vigente si la fecha fin no existe o aun no ha ocurrido."""
    return valor_nulo(fin) or pd.Timestamp(fin) > fecha_corte


def duracion_anios(inicio, fin, fecha_corte: pd.Timestamp) -> float | None:
    """Duracion topada en la fecha de corte (nunca cuenta tiempo futuro)."""
    if valor_nulo(inicio):
        return None
    fin_efectivo = fecha_corte if es_vigente(fin, fecha_corte) else pd.Timestamp(fin)
    return round(max((fin_efectivo - pd.Timestamp(inicio)).days, 0) / 365.25, 2)


def duracion_dias(inicio, fin, fecha_corte: pd.Timestamp) -> int | None:
    """Duracion en dias exactos (fin - inicio), topada en la fecha de corte. Se calcula en
    dias directamente: derivarla de `duracion_anios` (redondeada a 2 decimales) pierde los
    periodos cortos (p.ej. una subrogacion de 1 dia quedaba en 0)."""
    if valor_nulo(inicio):
        return None
    fin_efectivo = fecha_corte if es_vigente(fin, fecha_corte) else pd.Timestamp(fin)
    return max((fin_efectivo - pd.Timestamp(inicio)).days, 0)


def unicos(valores) -> list:
    """Valores distintos no nulos, en orden de aparicion."""
    vistos, salida = set(), []
    for v in valores:
        if valor_nulo(v) or v is None:
            continue
        if v not in vistos:
            vistos.add(v)
            salida.append(v)
    return salida


def resumen_periodos(inicios: list, fines: list, fecha_corte: pd.Timestamp) -> dict:
    """Resumen de fechas de una evidencia que agrupa periodos (ya ordenados por inicio):
    primer inicio, ultimo fin (null si algun periodo sigue abierto), vigencia y duracion
    total (suma de las duraciones de cada periodo, topadas en la fecha de corte)."""
    abierto = any(valor_nulo(f) for f in fines)
    duraciones = [duracion_anios(i, f, fecha_corte) for i, f in zip(inicios, fines)]
    return {
        "fecha_inicio": fecha_iso(min(inicios)) if inicios else None,
        "fecha_fin": None if abierto or not fines else fecha_iso(max(fines)),
        "vigente": any(es_vigente(f, fecha_corte) for f in fines),
        "n_periodos": len(inicios),
        "duracion_total_anios": round(sum(d for d in duraciones if d is not None), 2),
    }


def _a_json_nativo(v):
    if isinstance(v, dict):
        return {k: _a_json_nativo(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_a_json_nativo(x) for x in v]
    if valor_nulo(v):
        return None
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return fecha_iso(v)
    if isinstance(v, np.bool_):
        return bool(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


def atributos_json(atributos: dict) -> str:
    return json.dumps(_a_json_nativo(atributos), ensure_ascii=False)


def nueva_evidencia(evidencia_id, persona_id, tipo_id, texto, atributos) -> dict:
    # Fechas invertidas (fin anterior al inicio): se conservan tal cual (no se inventa cual
    # de las dos es la correcta), se marcan, y la duracion queda sin calcular.
    ini, fin = atributos.get("fecha_inicio"), atributos.get("fecha_fin")
    if not valor_nulo(ini) and not valor_nulo(fin) and pd.Timestamp(ini) > pd.Timestamp(fin):
        atributos = {**atributos, "fechas_inconsistentes": True}
        for clave in ("duracion_anios", "duracion_dias", "duracion_total_anios"):
            if clave in atributos:
                atributos[clave] = None
    return {
        "evidencia_id": evidencia_id,
        "persona_id": int(persona_id),
        "tipo_id": tipo_id,
        "texto": texto,
        "atributos": atributos_json(atributos),
    }


def a_dataframe(filas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(filas, columns=COLUMNAS_EVIDENCIA)


def fechas_de_atributos(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    attrs = df["atributos"].map(json.loads)
    ini = pd.to_datetime(attrs.map(lambda a: a.get("fecha_inicio")), errors="coerce")
    fin = pd.to_datetime(attrs.map(lambda a: a.get("fecha_fin")), errors="coerce")
    return ini, fin


# Un marcador de nulo ocupando un valor completo del texto ("…, nan, …", "País: None"); no
# una palabra dentro de un nombre ("PERDIDA DESCONOCIDA DE INVENTARIOS")
_PATRON_MARCADOR = re.compile(r"(?:^|[,:;(]\s*)(?:DESCONOCIDA|nan|None|NaT)\s*(?:$|[,;)])")


def validar_evidencias(df: pd.DataFrame, tipos_validos: set[str], poblacion: set[int],
                       fecha_corte: pd.Timestamp | None = None,
                       exigir_fecha_inicio: bool = True) -> pd.DataFrame:
    """Chequeos de integridad del dataset de evidencias. Devuelve una fila por chequeo con
    el numero de evidencias que lo incumplen (0 = OK). No corrige nada.
    `exigir_fecha_inicio=False` para secciones cuya fuente no tiene fecha de inicio
    (p.ej. formacion: solo existe la fecha de graduacion)."""

    def _json_invalido(s):
        try:
            return not isinstance(json.loads(s), dict)
        except (TypeError, ValueError):
            return True

    invalido = df["atributos"].apply(_json_invalido)
    ini, fin = fechas_de_atributos(df[~invalido])
    texto = df["texto"].fillna("")
    marcadas = df.loc[~invalido, "atributos"].str.contains('"fechas_inconsistentes": true', regex=False)
    chequeos = {
        "columnas_esperadas": 0 if list(df.columns) == COLUMNAS_EVIDENCIA else len(df),
        "evidencia_id_nulo": int(df["evidencia_id"].isna().sum()),
        "evidencia_id_duplicado": int(df["evidencia_id"].duplicated().sum()),
        "persona_fuera_de_poblacion": int((~df["persona_id"].isin(poblacion)).sum()),
        "tipo_id_invalido": int((~df["tipo_id"].isin(tipos_validos)).sum()),
        "atributos_json_invalido": int(invalido.sum()),
        "fecha_inicio_nula": int(ini.isna().sum()) if exigir_fecha_inicio else 0,
        "fechas_invertidas_sin_marcar": int(((ini > fin) & ~marcadas).sum()),
        "fecha_inicio_futura": int((ini > (fecha_corte or hoy())).sum()),
        "texto_vacio": int((texto.str.strip() == "").sum()),
        "texto_con_marcador_nulo": int(texto.str.contains(_PATRON_MARCADOR).sum()),
        "texto_contiene_persona_id": int(sum(
            # numero suelto: no parte de "ISO 9001:2008" ni de una fecha o codigo
            bool(re.search(rf"(?<![\w\-:/.]){p}(?![\w\-:/.])", t)) for p, t in zip(df["persona_id"], texto)
        )),
    }
    return pd.DataFrame(
        [{"chequeo": k, "n_fallas": v, "ok": v == 0} for k, v in chequeos.items()]
    )
