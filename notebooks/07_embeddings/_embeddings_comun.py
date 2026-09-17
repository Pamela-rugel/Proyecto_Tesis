"""Utilidades compartidas para la construccion del documento semantico por persona y su
embedding (ver DEC-014 en context/DECISION_LOG.md).

Separado deliberadamente de `_preprocesamiento_comun.py`: ese modulo sirve a los notebooks
01-06 (limpieza, features estructuradas, clustering); este sirve solo a 07_embeddings, para
no mezclar el proceso de embeddings con las features del clustering (instruccion explicita
del usuario). Reutiliza `construir_eventos_trayectoria`/`NOMBRES_CATEGORIA_CARGO` de
`_preprocesamiento_comun.py` (ya calculados en 04_trayectorias.ipynb) en vez de duplicar esa
logica.

Arquitectura (DEC-014):
    datos -> informacion integrada de la persona -> DOCUMENTO SEMANTICO POR PERSONA -> embedding

No genera el embedding a partir de features numericas ni concatena todas las columnas: cada
persona recibe un documento de texto narrativo, construido por secciones (trayectoria,
formacion, experiencia externa, docencia, investigacion, funciones adicionales, capacitacion,
certificaciones, idiomas, reconocimientos), y ES ESE DOCUMENTO el que se codifica.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

NOTEBOOK_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = NOTEBOOK_DIR.parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
TRAYECTORIAS_DIR = PROJECT_ROOT / "data" / "trayectorias"


def _continuacion_por_corte_de_mes(fin_actual: pd.Timestamp, inicio_siguiente: pd.Timestamp) -> bool:
    """Copia local de la misma tolerancia de brecha corta de
    `_preprocesamiento_comun._continuacion_por_corte_de_mes` (no se importa ese modulo aqui a
    proposito, ver docstring del archivo: este modulo no debe depender del de clustering).
    Dos tramos se tratan como continuos si el primero termina un dia antes de que inicie el
    segundo, o si termina en los ultimos 3 dias de un mes y el segundo inicia el dia 1 del
    mes calendario siguiente (corte administrativo tipico de fin de mes/fin de periodo)."""
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


# ---------------------------------------------------------------------------
# Utilidades de texto
# ---------------------------------------------------------------------------

def _anio(fecha) -> str:
    if pd.isna(fecha):
        return ""
    try:
        return str(pd.Timestamp(fecha).year)
    except (ValueError, TypeError):
        return ""


def _rango_anios(inicio, fin, vigente_texto="actualidad") -> str:
    a_ini, a_fin = _anio(inicio), _anio(fin)
    if not a_ini and not a_fin:
        return ""
    if not a_fin:
        return f"desde {a_ini}" if a_ini else ""
    if not a_ini:
        return f"hasta {a_fin}"
    if a_ini == a_fin:
        return f"en {a_ini}"
    return f"{a_ini}-{a_fin}"


def _lista_items(items: list[str], maximo: int = 12) -> str:
    """Une una lista de items de texto en una sola cadena, deduplicada y acotada (evita
    documentos desproporcionadamente largos para personas con historiales muy extensos -
    el modelo de embeddings tiene un limite de contexto, ver seccion de decisiones)."""
    vistos, unicos = set(), []
    for it in items:
        it = str(it).strip()
        if it and it.upper() not in vistos:
            vistos.add(it.upper())
            unicos.append(it)
    if len(unicos) > maximo:
        return "; ".join(unicos[:maximo]) + f"; y {len(unicos) - maximo} más"
    return "; ".join(unicos)


# ---------------------------------------------------------------------------
# Carga de fuentes (cada una devuelve un DataFrame filtrado a la poblacion pedida)
# ---------------------------------------------------------------------------

def _leer(nombre: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / nombre, low_memory=False, **kwargs)


# ---------------------------------------------------------------------------
# Seccion: trayectoria (cronologica, ESPOL + externa + funciones adicionales)
# ---------------------------------------------------------------------------

def _texto_evento_principal(desc: str, tipo_evento: str, unidad, fecha_inicio, fecha_fin, es_vigente: bool) -> str:
    rango = _rango_anios(fecha_inicio, fecha_fin)
    if not desc:
        return ""
    if tipo_evento == "CARGO_ESPOL":
        # DEC-022 (ver context/DECISION_LOG.md): antes `unidad` se ignoraba aqui - un cargo
        # estructural dentro de ESPOL nunca mencionaba la unidad/dependencia real (p.ej.
        # "GERENCIA DE TECNOLOGIAS Y SISTEMAS DE INFORMACION"), aunque el dato ya llegaba
        # disponible desde `construir_eventos_trayectoria`. Sin esto, ninguna busqueda
        # semantica que combinara "trabaja en <unidad>" con otra condicion (p.ej. "trabaja
        # en GTSI y apunta a ser docente") podia encontrar a la persona por su unidad
        # actual - solo coincidia por la otra condicion de la consulta.
        verbo = "Es" if es_vigente else "Fue"
        unidad_txt = f" en {unidad}" if pd.notna(unidad) else ""
        return (f"{verbo} {desc}{unidad_txt} en ESPOL ({rango})." if rango
                else f"{verbo} {desc}{unidad_txt} en ESPOL.")
    unidad_txt = f" en {unidad}" if pd.notna(unidad) else ""
    return (f"Trabajó como {desc}{unidad_txt}, fuera de ESPOL ({rango})." if rango
            else f"Trabajó como {desc}{unidad_txt}, fuera de ESPOL.")


def _consolidar_tramos_consecutivos(principales: pd.DataFrame) -> list[tuple]:
    """Fusiona en el texto (no en `tramos_rol.csv`) tramos CONSECUTIVOS *en fecha* de la
    misma categoria que `construir_tramos_rol`/`resolver_roles_simultaneos` no lograron
    unir (p.ej. gaps administrativos cortos que quedaron entre renovaciones de contrato
    tras retirar una subrogacion, ver DEC-011) - sin esto, una persona con muchas
    subrogaciones cortas puede terminar con decenas de tramos fragmentados del MISMO
    cargo, repitiendo la misma frase muchas veces. Solo fusiona tramos ADYACENTES en el
    orden cronologico Y sin una brecha real entre ellos (misma categoria pero separados por
    meses/años NO se fusionan: serian narrados como una sola frase con fechas incorrectas -
    ver DEC-020 en context/DECISION_LOG.md, bug donde un contrato vigente con FECHA_FIN nula
    se fusionaba con un tramo anterior ya finalizado y "heredaba" su fecha fin, perdiendo la
    vigencia en el texto). No se pierde ningun cambio de rol real - solo se deja de narrar
    cada fragmento CONTIGUO por separado. Devuelve una lista de (fecha_inicio_ordenamiento,
    texto)."""
    filas = principales.sort_values("FECHA_INICIO").to_dict("records")
    grupos = []
    for r in filas:
        clave = (r["TIPO_EVENTO"], r["CATEGORIA"], r.get("UNIDAD"))
        continua = False
        if grupos and grupos[-1]["_clave"] == clave:
            anterior = grupos[-1]
            fin_anterior = anterior["FECHA_FIN"]
            if pd.isna(fin_anterior):
                # el grupo anterior ya quedo marcado vigente (sin fecha fin) - cualquier
                # evento posterior de la misma categoria es, por definicion, una
                # continuacion (no puede haber un tramo "despues" de uno sin fin).
                continua = True
            else:
                continua = (
                    fin_anterior + pd.Timedelta(days=1) == r["FECHA_INICIO"]
                    or _continuacion_por_corte_de_mes(fin_anterior, r["FECHA_INICIO"])
                )
        if continua:
            actual = grupos[-1]
            if pd.isna(r["FECHA_FIN"]) or (pd.notna(actual["FECHA_FIN"]) and r["FECHA_FIN"] > actual["FECHA_FIN"]):
                actual["FECHA_FIN"] = r["FECHA_FIN"]
            actual["ES_VIGENTE"] = actual["ES_VIGENTE"] or r["ES_VIGENTE"]
        else:
            grupos.append({
                "_clave": clave, "DESCRIPCION": r["DESCRIPCION"], "TIPO_EVENTO": r["TIPO_EVENTO"],
                "UNIDAD": r.get("UNIDAD"), "FECHA_INICIO": r["FECHA_INICIO"], "FECHA_FIN": r["FECHA_FIN"],
                "ES_VIGENTE": r["ES_VIGENTE"],
            })

    items = []
    for g in grupos:
        desc = str(g["DESCRIPCION"]) if pd.notna(g["DESCRIPCION"]) else ""
        texto = _texto_evento_principal(desc, g["TIPO_EVENTO"], g["UNIDAD"], g["FECHA_INICIO"], g["FECHA_FIN"], g["ES_VIGENTE"])
        if texto:
            items.append((g["FECHA_INICIO"], texto))
    return items


def _texto_evento_agrupado(tipo_evento: str, grupo: pd.DataFrame) -> str:
    """Narra un grupo de eventos del MISMO tipo+categoria (p.ej. varias subrogaciones del
    cargo de Decano, o varios contratos puntuales del mismo tipo con brechas cortas entre
    renovaciones, ver DEC-018/DEC-020) en una sola frase compacta, sin perder informacion:
    se conserva el conteo, el rango de fechas total (incluyendo si el mas reciente sigue
    vigente - `vigente_alguna`, DEC-020) y las unidades distintas donde ocurrieron - solo
    se deja de listar cada instancia individual por separado. Necesario porque algunas
    personas acumulan muchas designaciones/contratos cortos del mismo tipo (ver DEC-011/
    `encargos cortos`) que, listados uno por uno, dominan el documento sin aportar
    informacion nueva mas alla de "ocurrio varias veces"."""
    desc = str(grupo["DESCRIPCION"].iloc[0]) if pd.notna(grupo["DESCRIPCION"].iloc[0]) else ""
    if not desc:
        return ""
    unidades = _lista_items(list(grupo["UNIDAD"].dropna().unique()), maximo=3)
    vigente_alguna = bool(grupo["ES_VIGENTE"].any())
    # DEC-020: si el evento mas reciente del grupo sigue vigente (ES_VIGENTE=True, FECHA_FIN
    # nula), el rango debe decir "actualidad", no la fecha fin de una instancia ANTERIOR ya
    # finalizada - antes se usaba fillna(FECHA_INICIO) + max(), que nunca podia producir un
    # NaT y por lo tanto nunca mostraba "actualidad" para el grupo.
    fin_max = pd.NaT if vigente_alguna else grupo["FECHA_FIN"].fillna(grupo["FECHA_INICIO"]).max()
    rango = _rango_anios(grupo["FECHA_INICIO"].min(), fin_max)
    n = len(grupo)
    donde = f" ({unidades})" if unidades else ""
    cuando = f", {rango}" if rango else ""

    if tipo_evento == "FUNCION_ADICIONAL":
        verbo = "ejerce" if vigente_alguna else "ejerció"
        if n == 1:
            return f"Adicionalmente {verbo} la función de {desc}{donde}{cuando}."
        return f"Adicionalmente {verbo} la función de {desc} en {n} ocasiones{donde}{cuando}."
    if tipo_evento == "SUBROGACION":
        if n == 1:
            return f"Subrogó brevemente el cargo de {desc}{donde}{cuando}."
        return f"Subrogó brevemente el cargo de {desc} en {n} ocasiones{donde}{cuando}."
    # CONTRATO_PUNTUAL (DEC-018/DEC-020): contrato puntual/por proyecto dentro de ESPOL,
    # distinto del cargo estructural continuo - se agrupa igual que subrogaciones/funciones
    # cuando hay varias renovaciones con brechas cortas entre ellas.
    verbo = "mantiene" if vigente_alguna else "tuvo"
    if n == 1:
        return f"Adicionalmente {verbo} un {desc.lower()} en ESPOL{cuando}."
    return f"Adicionalmente {verbo} un {desc.lower()} en ESPOL, en {n} periodos{cuando}."


def _seccion_trayectoria(eventos: pd.DataFrame, diversidad_trayectoria: pd.DataFrame | None = None) -> pd.Series:
    """`eventos` = salida de `pc.construir_eventos_trayectoria` (ya cargada por el
    llamador). Construye una narrativa cronologica por persona conservando la relacion
    temporal real entre eventos (no se inventan secuencias si faltan fechas: un evento sin
    FECHA_INICIO valida simplemente no se puede ordenar y se omite del texto).

    Los cargos estructurales (`CARGO_ESPOL`) y la experiencia externa se narran uno por
    uno, sin perdida (consolidando solo tramos verdaderamente CONTIGUOS en fecha, ver
    `_consolidar_tramos_consecutivos`/DEC-020). Las funciones adicionales/subrogaciones y
    los contratos puntuales/por proyecto dentro de ESPOL (`CONTRATO_PUNTUAL`, DEC-018) se
    agrupan por (TIPO_EVENTO, CATEGORIA): varias instancias del mismo tipo se resumen en
    una sola frase con el conteo y el rango de fechas (correctamente "actualidad" si la mas
    reciente sigue vigente, DEC-020), en vez de repetirse una por una - conserva toda la
    informacion (nada se descarta), solo la hace mas compacta para que no domine el
    documento de las personas con historiales de designacion/contratacion muy densos.

    `diversidad_trayectoria` (opcional, feature engineering de movilidad de carrera, ver
    DECISION_LOG.md): DataFrame con columnas `IDPERSONA`, `ENTROPIA_CATEGORIA_CARGO`,
    `N_CATEGORIAS_ROL_DISTINTAS`, `TURBULENCIA_TRAMOS`, `DURACION_MEDIANA_TRAMO_ANIOS` (de
    `features_trayectoria_persona.csv`). Cuando se pasa, se agregan hasta dos oraciones
    condicionales al final de la seccion, cada una independiente de la otra (una persona
    puede tener ambas, ninguna, o solo una):

    - **Diversidad** (entropia en el TERCIL SUPERIOR de la poblacion, calculado una sola
      vez sobre este parametro, no re-computado por persona): la mayoria de personas tiene
      entropia 0 (una sola categoria de cargo en toda su carrera, ya bien narrada por las
      oraciones de cargo/fecha existentes), y agregarles una oracion boilerplate de
      "diversidad" no aportaria señal real a la busqueda semantica.
    - **Estabilidad** (correccion 2026-09-16, caso de uso real: busqueda de "director de
      talento humano" pidiendo explicitamente "sin rotacion de 2-3 meses, cierta
      estabilidad en varios lugares" - el embedding NO puede aplicar un umbral numerico
      exacto como "2-3 meses no vale", eso vive en el filtro estructurado de /api/equipos,
      pero SI puede mejorar el ranking semantico narrando el patron en texto): requiere
      AMBAS condiciones a la vez, `TURBULENCIA_TRAMOS` en el TERCIL INFERIOR (poca
      rotacion/pocos cambios erraticos) Y `DURACION_MEDIANA_TRAMO_ANIOS` en el TERCIL
      SUPERIOR (permanencia larga tipica por cargo) de la poblacion con datos validos -
      exigir ambas evita narrar "estable" a alguien con un unico tramo corto reciente
      (turbulencia NA, tratada como no evaluable para esta oracion, no como "estable por
      defecto"). Personas sin al menos 2 tramos no tienen `TURBULENCIA_TRAMOS` (NA real,
      ver DEC-027) y por eso nunca reciben esta oracion — no hay suficiente historial para
      afirmar un patron de estabilidad, sea cual sea la duracion de su unico tramo."""
    eventos = eventos.dropna(subset=["FECHA_INICIO"]).sort_values(["IDPERSONA", "FECHA_INICIO"])

    umbral_entropia_alta = None
    umbral_turbulencia_baja = None
    umbral_duracion_alta = None
    metricas_por_persona: dict[int, tuple] = {}
    if diversidad_trayectoria is not None and len(diversidad_trayectoria):
        positivas = diversidad_trayectoria.loc[
            diversidad_trayectoria["ENTROPIA_CATEGORIA_CARGO"] > 0, "ENTROPIA_CATEGORIA_CARGO"
        ]
        if len(positivas):
            umbral_entropia_alta = positivas.quantile(2 / 3)

        if "TURBULENCIA_TRAMOS" in diversidad_trayectoria.columns:
            turbulencias_validas = diversidad_trayectoria["TURBULENCIA_TRAMOS"].dropna()
            if len(turbulencias_validas):
                umbral_turbulencia_baja = turbulencias_validas.quantile(1 / 3)
        if "DURACION_MEDIANA_TRAMO_ANIOS" in diversidad_trayectoria.columns:
            duraciones_validas = diversidad_trayectoria["DURACION_MEDIANA_TRAMO_ANIOS"].dropna()
            if len(duraciones_validas):
                umbral_duracion_alta = duraciones_validas.quantile(2 / 3)

        cols_extra = [c for c in ("TURBULENCIA_TRAMOS", "DURACION_MEDIANA_TRAMO_ANIOS") if c in diversidad_trayectoria.columns]
        metricas_por_persona = {
            row.IDPERSONA: (
                row.ENTROPIA_CATEGORIA_CARGO, row.N_CATEGORIAS_ROL_DISTINTAS,
                getattr(row, "TURBULENCIA_TRAMOS", pd.NA) if "TURBULENCIA_TRAMOS" in cols_extra else pd.NA,
                getattr(row, "DURACION_MEDIANA_TRAMO_ANIOS", pd.NA) if "DURACION_MEDIANA_TRAMO_ANIOS" in cols_extra else pd.NA,
            )
            for row in diversidad_trayectoria.itertuples(index=False)
        }

    resultado: dict[int, str] = {}
    for idp, grupo in eventos.groupby("IDPERSONA", sort=False):
        items: list[tuple] = []

        principales = grupo[grupo["TIPO_EVENTO"].isin(["CARGO_ESPOL", "EXPERIENCIA_EXTERNA"])]
        items.extend(_consolidar_tramos_consecutivos(principales))

        extra = grupo[grupo["TIPO_EVENTO"].isin(["FUNCION_ADICIONAL", "SUBROGACION", "CONTRATO_PUNTUAL"])]
        for (tipo_evento, _categoria), g2 in extra.groupby(["TIPO_EVENTO", "CATEGORIA"], dropna=False, sort=False):
            texto = _texto_evento_agrupado(tipo_evento, g2)
            if texto:
                items.append((g2["FECHA_INICIO"].min(), texto))

        if items:
            items.sort(key=lambda t: t[0])
            texto_trayectoria = " ".join(texto for _, texto in items)

            if idp in metricas_por_persona:
                entropia, n_categorias, turbulencia, duracion_mediana = metricas_por_persona[idp]

                if umbral_entropia_alta is not None and pd.notna(entropia) and entropia >= umbral_entropia_alta:
                    texto_trayectoria += (
                        f" Su trayectoria en ESPOL muestra una alta diversidad de roles, "
                        f"con paso por {int(n_categorias)} categorías distintas de cargo."
                    )

                if (
                    umbral_turbulencia_baja is not None and umbral_duracion_alta is not None
                    and pd.notna(turbulencia) and pd.notna(duracion_mediana)
                    and turbulencia <= umbral_turbulencia_baja and duracion_mediana >= umbral_duracion_alta
                ):
                    texto_trayectoria += (
                        " Su trayectoria en ESPOL muestra alta estabilidad, con permanencia "
                        "prolongada en sus cargos y baja rotación entre posiciones."
                    )

            resultado[idp] = texto_trayectoria

    return pd.Series(resultado, name="TRAYECTORIA")


# ---------------------------------------------------------------------------
# Otras secciones (cada una: tabla cruda -> texto por persona)
# ---------------------------------------------------------------------------

def _seccion_formacion(poblacion: set[int]) -> pd.Series:
    df = _leer("reporte_titulaciones_educacion.csv")
    # No se usa parse_dates de read_csv: si una sola fila tiene una fecha mal formada,
    # pandas puede descartar el parseo de TODA la columna silenciosamente y dejarla como
    # texto (visto con experiencia_externa.csv en esta misma sesion) - pd.to_datetime con
    # errors="coerce" explicito es robusto a eso.
    df["FechaGraduacion"] = pd.to_datetime(df["FechaGraduacion"], format="mixed", errors="coerce")
    df = df.rename(columns={"IdPersona": "IDPERSONA"})
    # Solo titulaciones GRADUADAS: no se narra formacion en curso o abandonada como un
    # logro completado (decision tecnica conservadora).
    df = df[df["IDPERSONA"].isin(poblacion) & (df["Estado"] == "Graduado") & df["Titulo"].notna()]
    orden_nivel = {"CUARTO NIVEL": 0, "TERCER NIVEL": 1, "BACHILLERATO": 2, "PRIMARIA": 3}
    df["_ORDEN"] = df["Nivel"].map(orden_nivel).fillna(9)

    textos = {}
    for idp, grupo in df.sort_values(["IDPERSONA", "_ORDEN"]).groupby("IDPERSONA", sort=False):
        items = []
        for _, r in grupo.iterrows():
            partes = [str(r["Titulo"]).strip().title()]
            if pd.notna(r.get("Institucion")):
                partes.append(str(r["Institucion"]).strip().title())
            anio = _anio(r.get("FechaGraduacion"))
            if anio:
                partes.append(anio)
            items.append(" - ".join(partes))
        textos[idp] = _lista_items(items, maximo=8)
    return pd.Series(textos, name="FORMACION")


def _seccion_docencia(poblacion: set[int]) -> pd.Series:
    df = _leer("carga_academica_disponible.csv")
    df = df[df["IDPERSONA"].isin(poblacion) & df["NOMMATERIA"].notna()]
    if len(df) == 0:
        return pd.Series(dtype=object, name="DOCENCIA")

    resumen = df.groupby("IDPERSONA").agg(
        MATERIAS=("NOMMATERIA", lambda s: _lista_items(list(s), maximo=15)),
        ANIO_MIN=("ANIO", "min"), ANIO_MAX=("ANIO", "max"),
        N_UNIDADES=("NOMBREUNIDAD", "nunique"),
    )

    def _texto(r):
        rango = _rango_anios(f"{int(r['ANIO_MIN'])}-01-01", f"{int(r['ANIO_MAX'])}-12-31") if pd.notna(r["ANIO_MIN"]) else ""
        base = f"Ha impartido las materias: {r['MATERIAS']}."
        if rango:
            base += f" Actividad docente {rango}."
        return base

    return resumen.apply(_texto, axis=1).rename("DOCENCIA")


def _seccion_investigacion(poblacion: set[int]) -> pd.Series:
    proy = _leer("proyectos_investigacion_disponible.csv")
    proy = proy[proy["IDPERSONA"].isin(poblacion) & proy["NOMBRE"].notna()]

    def _texto_proyecto(r):
        areas = [str(r[c]) for c in ("STRAREACAMPOAMPLIO", "STRAREAFRASCATI") if pd.notna(r.get(c))]
        area_txt = f" ({areas[0]})" if areas else ""
        return f"{r['NOMBRE']}{area_txt}"

    proy_txt = (
        proy.assign(_TXT=proy.apply(_texto_proyecto, axis=1))
        .groupby("IDPERSONA")["_TXT"].apply(lambda s: _lista_items(list(s), maximo=8))
    )

    pub = _leer("publicaciones.csv")
    pub = pub[pub["IDPERSONA"].isin(poblacion) & pub["TITULO"].notna()]
    pub_txt = pub.groupby("IDPERSONA")["TITULO"].apply(lambda s: _lista_items(list(s), maximo=10))

    tesis = _leer("proyecto_grado.csv").rename(columns={"IDDIRECTOR": "IDPERSONA"})
    tesis = tesis[tesis["IDPERSONA"].isin(poblacion) & tesis["NOMBRETRABAJOTITULACION"].notna()]
    tesis_txt = tesis.groupby("IDPERSONA")["NOMBRETRABAJOTITULACION"].apply(lambda s: _lista_items(list(s), maximo=6))

    ponencias = _leer("ponentes_todos.csv")
    ponencias = ponencias[ponencias["IDPERSONA"].isin(poblacion) & ponencias["NOMBRE"].notna()]
    pon_txt = ponencias.groupby("IDPERSONA")["NOMBRE"].apply(lambda s: _lista_items(list(s), maximo=8))

    ids = set(proy_txt.index) | set(pub_txt.index) | set(tesis_txt.index) | set(pon_txt.index)
    salida = {}
    for idp in ids:
        partes = []
        if idp in proy_txt.index and proy_txt[idp]:
            partes.append(f"Proyectos de investigación: {proy_txt[idp]}.")
        if idp in pub_txt.index and pub_txt[idp]:
            partes.append(f"Publicaciones: {pub_txt[idp]}.")
        if idp in tesis_txt.index and tesis_txt[idp]:
            partes.append(f"Trabajos de titulación dirigidos: {tesis_txt[idp]}.")
        if idp in pon_txt.index and pon_txt[idp]:
            partes.append(f"Ponencias presentadas: {pon_txt[idp]}.")
        if partes:
            salida[idp] = " ".join(partes)
    return pd.Series(salida, name="INVESTIGACION")


def _seccion_vinculacion(poblacion: set[int]) -> pd.Series:
    df = _leer("proyectos_vinculacion_disponible.csv")
    df = df[df["IDPERSONA"].isin(poblacion) & df["NOMBREPROYECTO"].notna()]
    if len(df) == 0:
        return pd.Series(dtype=object, name="VINCULACION")
    txt = df.groupby("IDPERSONA")["NOMBREPROYECTO"].apply(lambda s: _lista_items(list(s), maximo=8))
    return txt.apply(lambda t: f"Proyectos de vinculación con la sociedad: {t}." if t else pd.NA).dropna().rename("VINCULACION")


def _seccion_capacitacion(poblacion: set[int]) -> pd.Series:
    cap = _leer("capacitaciones_todas.csv")
    cap = cap[cap["IDPERSONA"].isin(poblacion) & cap["NOMBRE"].notna()]
    cap_txt = cap.groupby("IDPERSONA")["NOMBRE"].apply(lambda s: _lista_items(list(s), maximo=15))

    cert = _leer("certificados_todos.csv")
    cert = cert[cert["IDPERSONA"].isin(poblacion) & cert["NOMBRE"].notna()]
    cert_txt = cert.groupby("IDPERSONA")["NOMBRE"].apply(lambda s: _lista_items(list(s), maximo=10))

    ids = set(cap_txt.index) | set(cert_txt.index)
    salida = {}
    for idp in ids:
        partes = []
        if idp in cap_txt.index and cap_txt[idp]:
            partes.append(f"Capacitación recibida: {cap_txt[idp]}.")
        if idp in cert_txt.index and cert_txt[idp]:
            partes.append(f"Certificaciones: {cert_txt[idp]}.")
        if partes:
            salida[idp] = " ".join(partes)
    return pd.Series(salida, name="CAPACITACION")


def _seccion_idiomas(poblacion: set[int]) -> pd.Series:
    df = _leer("idiomas_personas.csv")
    df = df[df["IDPERSONA"].isin(poblacion) & df["IDIOMA"].notna()]
    # La lengua nativa no aporta como "habilidad" a destacar en busqueda semantica de
    # experiencia/competencia (casi siempre espanol) - se conserva solo el resto.
    if "LENGUANATIVA" in df.columns:
        df = df[df["LENGUANATIVA"] != 1]
    if len(df) == 0:
        return pd.Series(dtype=object, name="IDIOMAS")

    def _nivel(r):
        return str(r["NIVELMCER"]) if pd.notna(r.get("NIVELMCER")) else ""

    df = df.assign(_TXT=df.apply(lambda r: f"{r['IDIOMA']}" + (f" (nivel {_nivel(r)})" if _nivel(r) else ""), axis=1))
    txt = df.groupby("IDPERSONA")["_TXT"].apply(lambda s: _lista_items(list(s), maximo=6))
    return txt.apply(lambda t: f"Idiomas adicionales: {t}." if t else pd.NA).dropna().rename("IDIOMAS")


# ---------------------------------------------------------------------------
# Embedding de TRAYECTORIA PROFESIONAL (capa nueva, separada del embedding general)
#
# Arquitectura (ver docstring del modulo): reutiliza `tramos_rol.csv` (ya construido en
# `04_trayectorias.ipynb` via `pc.construir_tramos_rol`) como fuente de cargo/unidad/fechas,
# y el conocimiento estructurado existente (`personas_dashboard.csv` o
# `dataset_personas_features.csv`) SOLO para el estado de vigencia (VIGENTE_ACTUALMENTE /
# VIGENTE_TRAMO_ESTRUCTURAL) que ya se calcula alli - no se recalculan variables que ya
# existen en otro lado del pipeline (turbulencia/entropia/duracion mediana de TODOS los
# tramos siguen viviendo en `features_trayectoria_persona.csv`, ver DEC-027; esta seccion
# calcula variables NUEVAS y mas finas: cargo+unidad consolidados, no solo CATEGORIA_CARGO).
#
# No se genera un CSV estructurado nuevo aparte: las variables objetivas de esta seccion
# son un insumo intermedio para la PLANTILLA DE TEXTO (ver `construir_documento_trayectoria`
# mas abajo), igual que el resto de secciones de este modulo no persisten sus tablas
# intermedias por separado.
# ---------------------------------------------------------------------------

# Umbral configurable (pedido explicito): duracion minima, en meses, para que un cargo
# cuente como "significativo" en los indicadores de trayectoria (N_CARGOS_SIGNIFICATIVOS,
# estabilidad). Un cargo por debajo del umbral SIGUE apareciendo en la secuencia cronologica
# del texto (no se elimina el tramo, ver `_secuencia_cronologica_texto`) - el umbral solo
# afecta que variables lo cuentan como "cargo significativo" para permanencia/estabilidad.
MIN_MESES_CARGO_SIGNIFICATIVO = 3

# Tolerancia de receso (dias) para consolidar dos tramos consecutivos de MISMO cargo+unidad
# separados por una brecha corta - mismo problema y mismo valor que ya corrige
# `dashboard_react/backend/main.py::_TOLERANCIA_RECESO_ACADEMICO` (contratacion docente por
# periodo academico/semestral: `tramos_rol.csv` solo fusiona por CATEGORIA_CARGO, asi que un
# "Profesor Pregrado" con 22 tramos semestrales del mismo cargo/unidad separados por
# vacaciones aparece como 22 cargos distintos si no se vuelve a consolidar aqui). Separado
# como constante propia (no se importa del backend: ese modulo no es una dependencia de
# `notebooks/07_embeddings`, mismo principio de separacion que el resto de este archivo).
TOLERANCIA_RECESO_DIAS_CARGO = 90


def _meses_entre(inicio, fin) -> float:
    """Duracion en meses (30.44 dias/mes en promedio, igual criterio que dias/365.25 para
    anios usado en el resto del proyecto) entre dos fechas. `fin` puede ser NaT (tramo
    vigente): se usa hoy como fin efectivo, igual criterio que `construir_features_
    historial_laboral`/`construir_features_trayectoria` en `_preprocesamiento_comun.py`."""
    fin_efectivo = pd.Timestamp.today().normalize() if pd.isna(fin) else fin
    return (fin_efectivo - inicio).days / 30.44


def _consolidar_tramos_cargo_unidad(tramos_persona: pd.DataFrame) -> pd.DataFrame:
    """Consolida, dentro de los tramos de UNA persona (ya ordenados por TRAMO_INICIO), los
    que representan el MISMO cargo real: mismo `CARGO_TRAMO` (texto) + mismo `UNIDAD_TRAMO`
    + continuos o separados solo por un receso corto (`TOLERANCIA_RECESO_DIAS_CARGO`).

    Regla pedida explicitamente (evitar falsos "cambios de cargo" por particularidades del
    dato, p.ej. contratacion por periodo academico/semestral):
    - mismo cargo + misma unidad + consecutivos/solapados/receso corto -> se consolidan en
      un solo tramo consolidado (mismo cargo, mismo periodo ampliado).
    - mismo cargo + distinta unidad -> NO se consolidan: es un cambio de unidad (se cuenta
      aparte en N_CAMBIOS_UNIDAD, nunca como cambio de cargo).
    - distinto cargo (misma o distinta unidad) -> NO se consolidan: es un cambio de cargo.

    Devuelve una fila por tramo CONSOLIDADO: CARGO, UNIDAD, INICIO, FIN (NaT si el ultimo
    tramo del grupo sigue vigente), CATEGORIA_CARGO (del tramo mas reciente del grupo, para
    conservar la categorizacion de rol), N_TRAMOS_ORIGEN (cuantos tramos de `tramos_rol.csv`
    se fusionaron - diagnostico/trazabilidad, no se usa en el texto).

    Rastreo en PARALELO por clave (cargo, unidad) - mismo patron que `pc.construir_tramos_
    rol`/`pc.construir_tramos_unidad` (`abiertos_por_categoria`/`abiertos_por_unidad`): sin
    esto, un cargo largo que se ve interrumpido en la linea cronologica por OTRO cargo
    intercalado (p.ej. una coordinacion breve en medio de 10 anios de "Profesor Pregrado",
    caso real IDPERSONA 3519) cortaria el grupo del primer cargo para siempre en cuanto
    aparece el segundo, en vez de retomarlo cuando "Profesor Pregrado" vuelve a aparecer
    despues. El resultado final se ordena por INICIO al final, no por orden de cierre."""
    columnas = ["CARGO", "UNIDAD", "INICIO", "FIN", "CATEGORIA_CARGO", "N_TRAMOS_ORIGEN"]
    if tramos_persona.empty:
        return pd.DataFrame(columns=columnas)

    filas = tramos_persona.sort_values("TRAMO_INICIO").to_dict("records")
    abiertos_por_clave: dict[tuple, dict] = {}
    cerrados: list[dict] = []
    for r in filas:
        cargo = str(r["CARGO_TRAMO"]).strip() if pd.notna(r["CARGO_TRAMO"]) else ""
        unidad = str(r["UNIDAD_TRAMO"]).strip() if pd.notna(r["UNIDAD_TRAMO"]) else ""
        inicio, fin = r["TRAMO_INICIO"], r["TRAMO_FIN"]
        clave = (cargo, unidad)
        actual = abiertos_por_clave.get(clave)

        continua = False
        if actual is not None:
            if pd.isna(actual["FIN"]):
                # tramo abierto de esta clave ya vigente (sin fin): cualquier tramo
                # posterior de la MISMA clave es, por definicion, una continuacion.
                continua = True
            else:
                gap_dias = (inicio - actual["FIN"]).days
                continua = gap_dias <= 0 or gap_dias <= TOLERANCIA_RECESO_DIAS_CARGO

        if continua:
            if pd.isna(fin) or (pd.notna(actual["FIN"]) and fin > actual["FIN"]):
                actual["FIN"] = fin
            actual["CATEGORIA_CARGO"] = r["CATEGORIA_CARGO"]  # el mas reciente del grupo
            actual["N_TRAMOS_ORIGEN"] += 1
            continue

        # No continua: si habia un grupo abierto de esta clave, se cierra (pasa a
        # `cerrados`) y se abre uno nuevo de la misma clave (reinicio real, brecha larga).
        if actual is not None:
            cerrados.append(actual)
        abiertos_por_clave[clave] = {
            "CARGO": cargo, "UNIDAD": unidad, "INICIO": inicio, "FIN": fin,
            "CATEGORIA_CARGO": r["CATEGORIA_CARGO"], "N_TRAMOS_ORIGEN": 1,
        }

    cerrados.extend(abiertos_por_clave.values())
    if not cerrados:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(cerrados)[columnas].sort_values("INICIO").reset_index(drop=True)


def _variables_objetivas_trayectoria(tramos_consolidados: pd.DataFrame) -> dict:
    """Calcula las variables objetivas de trayectoria (seccion 4 del pedido) a partir de los
    tramos YA CONSOLIDADOS de una persona (ver `_consolidar_tramos_cargo_unidad`). No
    duplica `N_CARGOS_DISTINTOS`/`N_UNIDADES_DISTINTAS` del conocimiento estructurado
    existente (esas cuentan sobre TODO el historial de contratos, no sobre tramos
    consolidados por cargo+unidad real) - estas son deliberadamente mas finas."""
    if tramos_consolidados.empty:
        return {
            "N_CARGOS_TOTAL": 0, "N_CARGOS_SIGNIFICATIVOS": 0,
            "N_CAMBIOS_CARGO": 0, "N_CAMBIOS_UNIDAD": 0,
            "DURACION_MEDIA_CARGO_ANIOS": np.nan, "DURACION_MEDIANA_CARGO_ANIOS": np.nan,
            "DURACION_MAX_CARGO_ANIOS": np.nan,
            "N_UNIDADES_TOTAL": 0, "N_UNIDADES_SIGNIFICATIVAS": 0,
            "PROPORCION_CARGOS_SIGNIFICATIVOS": np.nan,
        }

    t = tramos_consolidados.copy()
    t["DURACION_MESES"] = t.apply(lambda r: _meses_entre(r["INICIO"], r["FIN"]), axis=1)
    t["DURACION_ANIOS"] = t["DURACION_MESES"] / 12
    t["ES_SIGNIFICATIVO"] = t["DURACION_MESES"] >= MIN_MESES_CARGO_SIGNIFICATIVO

    n_cargos_total = len(t)
    significativos = t[t["ES_SIGNIFICATIVO"]]
    n_cargos_significativos = len(significativos)

    # Cambios de cargo/unidad: se miden sobre los tramos CONSOLIDADOS ya sin fragmentacion
    # espuria (misma logica pedida: cambio de cargo = CARGO distinto entre tramos
    # consecutivos; cambio de unidad = UNIDAD distinta entre tramos consecutivos, sin
    # importar si el cargo tambien cambio - ambos conteos son independientes, una
    # transicion puede contar en ninguno, uno o ambos a la vez).
    n_cambios_cargo = 0
    n_cambios_unidad = 0
    for i in range(1, len(t)):
        if t.iloc[i]["CARGO"] != t.iloc[i - 1]["CARGO"]:
            n_cambios_cargo += 1
        if t.iloc[i]["UNIDAD"] != t.iloc[i - 1]["UNIDAD"]:
            n_cambios_unidad += 1

    unidades_todas = set(u for u in t["UNIDAD"] if u)
    unidades_significativas = set(u for u in significativos["UNIDAD"] if u)

    return {
        "N_CARGOS_TOTAL": n_cargos_total,
        "N_CARGOS_SIGNIFICATIVOS": n_cargos_significativos,
        "N_CAMBIOS_CARGO": n_cambios_cargo,
        "N_CAMBIOS_UNIDAD": n_cambios_unidad,
        "DURACION_MEDIA_CARGO_ANIOS": round(t["DURACION_ANIOS"].mean(), 2),
        "DURACION_MEDIANA_CARGO_ANIOS": round(t["DURACION_ANIOS"].median(), 2),
        "DURACION_MAX_CARGO_ANIOS": round(t["DURACION_ANIOS"].max(), 2),
        "N_UNIDADES_TOTAL": len(unidades_todas),
        "N_UNIDADES_SIGNIFICATIVAS": len(unidades_significativas),
        "PROPORCION_CARGOS_SIGNIFICATIVOS": (
            round(n_cargos_significativos / n_cargos_total, 3) if n_cargos_total else np.nan
        ),
    }


# Umbrales de ESTABILIDAD (configurables, revisados contra la distribucion real de
# `DURACION_MEDIANA_CARGO_ANIOS`/`PROPORCION_CARGOS_SIGNIFICATIVOS` sobre la poblacion antes
# de fijarlos - ver notebook, seccion de calibracion). Regla explicita y transparente, NO
# una etiqueta arbitraria: se exigen AMBAS condiciones a la vez (misma logica ya usada en
# `_seccion_trayectoria` para la oracion de "alta estabilidad" del embedding GENERAL, DEC-016
# del feature engineering de movilidad) para no llamar "estable" a alguien con datos
# insuficientes o con un patron mixto.
UMBRAL_ESTABILIDAD_DURACION_MEDIANA_ANIOS = 2.0
UMBRAL_ESTABILIDAD_PROPORCION_SIGNIFICATIVOS = 0.7
UMBRAL_BAJA_ESTABILIDAD_DURACION_MEDIANA_ANIOS = 0.5

# Umbrales de MOVILIDAD (mismo principio: configurables, no escondidos en la funcion).
UMBRAL_ALTA_MOVILIDAD_N_CAMBIOS_CARGO = 3
UMBRAL_ALTA_MOVILIDAD_N_CAMBIOS_UNIDAD = 2


def _describir_estabilidad(v: dict) -> str:
    """Genera la descripcion de estabilidad (seccion 5 del pedido) a partir de las
    variables objetivas ya calculadas - reglas simples y explicitas, basadas en
    `DURACION_MEDIANA_CARGO_ANIOS` y `PROPORCION_CARGOS_SIGNIFICATIVOS` (revisadas contra la
    distribucion real de la poblacion antes de fijar los umbrales, ver notebook). No emite
    una etiqueta si no hay evidencia suficiente (menos de 1 cargo significativo, o
    duracion/proporcion no calculables)."""
    dur_mediana = v["DURACION_MEDIANA_CARGO_ANIOS"]
    proporcion = v["PROPORCION_CARGOS_SIGNIFICATIVOS"]
    if v["N_CARGOS_TOTAL"] == 0 or pd.isna(dur_mediana) or pd.isna(proporcion):
        return ""

    if (
        dur_mediana >= UMBRAL_ESTABILIDAD_DURACION_MEDIANA_ANIOS
        and proporcion >= UMBRAL_ESTABILIDAD_PROPORCION_SIGNIFICATIVOS
    ):
        return (
            "Su trayectoria presenta permanencias relativamente prolongadas en sus cargos, "
            f"con una duración mediana de {dur_mediana:.1f} años por cargo."
        )
    if (
        dur_mediana <= UMBRAL_BAJA_ESTABILIDAD_DURACION_MEDIANA_ANIOS
        and proporcion < UMBRAL_ESTABILIDAD_PROPORCION_SIGNIFICATIVOS
    ):
        return (
            "Su trayectoria está formada principalmente por períodos cortos, "
            f"con una duración mediana de {dur_mediana:.1f} años por cargo."
        )
    return (
        f"Su trayectoria combina cargos de distinta duración, con una mediana de "
        f"{dur_mediana:.1f} años por cargo."
    )


def _describir_movilidad(v: dict) -> str:
    """Genera la descripcion de movilidad (seccion 5 del pedido): distingue cambios de
    cargo (funcional) de cambios de unidad (organizacional), sin mezclarlos en un solo
    numero (pedido explicito: "no confundas un cambio de unidad con un cambio de cargo")."""
    n_cargo = v["N_CAMBIOS_CARGO"]
    n_unidad = v["N_CAMBIOS_UNIDAD"]
    if v["N_CARGOS_TOTAL"] == 0:
        return ""

    alta_cargo = n_cargo >= UMBRAL_ALTA_MOVILIDAD_N_CAMBIOS_CARGO
    alta_unidad = n_unidad >= UMBRAL_ALTA_MOVILIDAD_N_CAMBIOS_UNIDAD

    if alta_cargo and alta_unidad:
        return (
            f"Ha ocupado varios cargos a lo largo de su trayectoria ({n_cargo} cambios de "
            f"cargo), con cambios entre distintas unidades ({n_unidad} cambios de unidad)."
        )
    if alta_cargo and not alta_unidad:
        return (
            f"Ha ocupado varios cargos distintos ({n_cargo} cambios de cargo), "
            "manteniéndose dentro de la misma unidad."
        )
    if not alta_cargo and alta_unidad:
        return (
            f"Ha mantenido el mismo cargo, pero ha pasado por distintas unidades "
            f"({n_unidad} cambios de unidad)."
        )
    return "Ha permanecido durante varios años en un mismo cargo y unidad, sin cambios frecuentes."


def _insights_trayectoria(v: dict) -> list[str]:
    """Insights derivados automaticamente de las variables objetivas (seccion 7 del
    pedido) - reglas explicitas, no descripciones subjetivas. Cada insight es
    independiente: una persona puede recibir varios, uno solo, o ninguno."""
    insights = []
    dur_mediana = v["DURACION_MEDIANA_CARGO_ANIOS"]
    dur_max = v["DURACION_MAX_CARGO_ANIOS"]

    if pd.notna(dur_max) and dur_max >= UMBRAL_ESTABILIDAD_DURACION_MEDIANA_ANIOS * 2:
        insights.append(
            f"Permanencia prolongada en al menos un cargo (máximo {dur_max:.1f} años)."
        )
    if v["N_CAMBIOS_CARGO"] >= UMBRAL_ALTA_MOVILIDAD_N_CAMBIOS_CARGO:
        insights.append(f"Múltiples cambios de cargo a lo largo de su trayectoria ({v['N_CAMBIOS_CARGO']}).")
    if v["N_CAMBIOS_UNIDAD"] >= UMBRAL_ALTA_MOVILIDAD_N_CAMBIOS_UNIDAD:
        insights.append(f"Múltiples cambios de unidad a lo largo de su trayectoria ({v['N_CAMBIOS_UNIDAD']}).")
    if v["N_UNIDADES_SIGNIFICATIVAS"] <= 1 and v["N_CARGOS_SIGNIFICATIVOS"] >= 1:
        insights.append("Trayectoria concentrada en una sola unidad.")
    elif v["N_UNIDADES_SIGNIFICATIVAS"] >= 3:
        insights.append(f"Trayectoria distribuida entre varias unidades ({v['N_UNIDADES_SIGNIFICATIVAS']}).")
    if pd.notna(v["PROPORCION_CARGOS_SIGNIFICATIVOS"]) and v["PROPORCION_CARGOS_SIGNIFICATIVOS"] < 0.5:
        insights.append("Predominio de períodos cortos en su historial de cargos.")
    elif pd.notna(v["PROPORCION_CARGOS_SIGNIFICATIVOS"]) and v["PROPORCION_CARGOS_SIGNIFICATIVOS"] >= 0.9:
        insights.append("Predominio de períodos prolongados en su historial de cargos.")

    return insights


def _secuencia_cronologica_texto(tramos_consolidados: pd.DataFrame, maximo: int = 10) -> str:
    """Secuencia cronologica de cargos/unidades (seccion 4/6 del pedido) - lista TODOS los
    tramos consolidados (no solo los significativos: un cargo corto sigue aportando
    contexto a la secuencia, aunque no cuente para los indicadores de estabilidad, ver
    seccion 3 del pedido: 'no elimines esos periodos del historial textual'). Se acota a
    `maximo` para documentos con muchisimos cargos (mismo criterio que `_lista_items`)."""
    if tramos_consolidados.empty:
        return ""
    t = tramos_consolidados.sort_values("INICIO")
    items = []
    for _, r in t.iterrows():
        rango = _rango_anios(r["INICIO"], r["FIN"])
        unidad_txt = f" en {r['UNIDAD']}" if r["UNIDAD"] else ""
        cargo_txt = r["CARGO"] if r["CARGO"] else "cargo sin especificar"
        items.append(f"{cargo_txt}{unidad_txt} ({rango})" if rango else f"{cargo_txt}{unidad_txt}")
    if len(items) > maximo:
        primero, ultimos = items[0], items[-(maximo - 1):]
        return "; ".join([primero, f"... ({len(items) - maximo} cargos intermedios omitidos) ...", *ultimos])
    return "; ".join(items)


def construir_tramos_cargo_unidad_persona(
    tramos_rol: pd.DataFrame,
    poblacion: set[int] | None = None,
) -> pd.DataFrame:
    """Expone, como tabla estructurada (una fila por tramo consolidado por persona), el
    mismo resultado intermedio que `construir_documento_trayectoria` calcula para armar el
    texto (`_consolidar_tramos_cargo_unidad`) - pensado para que el backend del dashboard
    pueda mostrar "periodos, cargos y unidades" en la ficha de una persona sin volver a
    calcular nada (reutiliza la MISMA consolidacion cargo+unidad+receso corto que ya valida
    la seccion 7 de este notebook, no una version aparte).

    Devuelve: IDPERSONA, CARGO, UNIDAD, INICIO (fecha), FIN (fecha, NaT si vigente),
    DURACION_ANIOS, ES_SIGNIFICATIVO (bool, segun MIN_MESES_CARGO_SIGNIFICATIVO),
    ES_PARALELO (bool) - True si este tramo se solapa en fecha con otro tramo consolidado
    DISTINTO (cargo o unidad distintos) de la MISMA persona; permite detectar, p.ej., un
    Profesor Titular que en paralelo ejerce como Director de una unidad distinta (mismo
    patron que ya resuelve `pc.resolver_roles_simultaneos` a nivel de CATEGORIA_CARGO, pero
    aqui a nivel de cargo+unidad consolidado, mas fino).
    """
    ids = poblacion if poblacion is not None else set(tramos_rol["IDPERSONA"].unique())
    columnas = ["IDPERSONA", "CARGO", "UNIDAD", "INICIO", "FIN", "DURACION_ANIOS", "ES_SIGNIFICATIVO", "ES_PARALELO"]

    filas = []
    for idp, grupo in tramos_rol[tramos_rol["IDPERSONA"].isin(ids)].groupby("IDPERSONA", sort=False):
        consolidados = _consolidar_tramos_cargo_unidad(grupo)
        if consolidados.empty:
            continue
        t = consolidados.copy()
        t["DURACION_MESES"] = t.apply(lambda r: _meses_entre(r["INICIO"], r["FIN"]), axis=1)
        t["DURACION_ANIOS"] = round(t["DURACION_MESES"] / 12, 2)
        t["ES_SIGNIFICATIVO"] = t["DURACION_MESES"] >= MIN_MESES_CARGO_SIGNIFICATIVO

        fin_cmp = t["FIN"].fillna(pd.Timestamp.today().normalize())
        es_paralelo = []
        for i in range(len(t)):
            solapa_con_otro = False
            for j in range(len(t)):
                if i == j:
                    continue
                # mismo INICIO/FIN exactos con distinto cargo o unidad = paralelo real; se
                # exige ademas que no sean el mismo cargo+unidad (eso ya se habria fusionado
                # en la consolidacion) - basta con overlap de rango de fechas.
                solapan_fechas = t["INICIO"].iloc[i] <= fin_cmp.iloc[j] and t["INICIO"].iloc[j] <= fin_cmp.iloc[i]
                if solapan_fechas:
                    solapa_con_otro = True
                    break
            es_paralelo.append(solapa_con_otro)
        t["ES_PARALELO"] = es_paralelo
        t["IDPERSONA"] = idp
        filas.append(t[columnas])

    if not filas:
        return pd.DataFrame(columns=columnas)
    return pd.concat(filas, ignore_index=True).sort_values(["IDPERSONA", "INICIO"]).reset_index(drop=True)


def construir_documento_trayectoria(
    tramos_rol: pd.DataFrame,
    estado_vigencia: pd.DataFrame,
    poblacion: set[int] | None = None,
) -> pd.DataFrame:
    """Construye el DOCUMENTO DE TRAYECTORIA PROFESIONAL por persona (capa nueva, separada
    del documento semantico general de `construir_documentos_semanticos`).

    Parametros:
    - `tramos_rol`: salida de `pc.construir_tramos_rol` (ya calculada en
      `04_trayectorias.ipynb`) - columnas IDPERSONA, CATEGORIA_CARGO, TRAMO_INICIO,
      TRAMO_FIN, CARGO_TRAMO, UNIDAD_TRAMO. Fuente unica de cargo/unidad/fechas (pedido
      explicito, seccion 2) - no se recalculan tramos desde el historial crudo.
    - `estado_vigencia`: DataFrame con IDPERSONA, CARGO_ACTUAL, UNIDAD_ACTUAL_NOMBRE,
      VIGENTE_TRAMO_ESTRUCTURAL (o VIGENTE_ACTUALMENTE) - el conocimiento estructurado
      EXISTENTE (`personas_dashboard.csv`/`dataset_personas_features.csv`), reutilizado
      solo para el estado actual (pedido explicito, seccion 1: no recalcular lo que ya
      existe). Si una columna no esta disponible, esa parte de "Estado actual" queda vacia
      en vez de inventarse.
    - `poblacion`: IDs a incluir (por defecto, todas las de `tramos_rol`). Personas sin
      ningun tramo de rol (ver `pc.CATEGORIAS_PUNTUALES`, DEC-004) no reciben documento de
      trayectoria - mismo criterio ya usado para `features_trayectoria_persona.csv`.

    Devuelve una fila por IDPERSONA con: DOCUMENTO_TRAYECTORIA_TEXTO (el texto a embeber) y
    las variables objetivas calculadas (para diagnostico/validacion, no para re-embeber).
    """
    ids = poblacion if poblacion is not None else set(tramos_rol["IDPERSONA"].unique())
    vigencia_por_persona = (
        estado_vigencia.set_index("IDPERSONA") if estado_vigencia is not None and len(estado_vigencia)
        else pd.DataFrame().reindex(columns=["CARGO_ACTUAL", "UNIDAD_ACTUAL_NOMBRE", "VIGENTE_TRAMO_ESTRUCTURAL"])
    )

    filas = []
    for idp, grupo in tramos_rol[tramos_rol["IDPERSONA"].isin(ids)].groupby("IDPERSONA", sort=False):
        consolidados = _consolidar_tramos_cargo_unidad(grupo)
        v = _variables_objetivas_trayectoria(consolidados)

        cargo_actual = unidad_actual = None
        estado_vigencia_txt = "no determinado"
        if idp in vigencia_por_persona.index:
            fila_vig = vigencia_por_persona.loc[idp]
            cargo_actual = fila_vig.get("CARGO_ACTUAL")
            unidad_actual = fila_vig.get("UNIDAD_ACTUAL_NOMBRE")
            vigente = fila_vig.get("VIGENTE_TRAMO_ESTRUCTURAL", fila_vig.get("VIGENTE_ACTUALMENTE"))
            if pd.notna(vigente):
                estado_vigencia_txt = "vigente" if bool(vigente) else "no vigente"

        descripcion_estabilidad = _describir_estabilidad(v)
        descripcion_movilidad = _describir_movilidad(v)
        insights = _insights_trayectoria(v)
        secuencia = _secuencia_cronologica_texto(consolidados)

        bloques = ["TRAYECTORIA PROFESIONAL"]
        if cargo_actual and pd.notna(cargo_actual):
            unidad_txt = f" en {unidad_actual}" if unidad_actual and pd.notna(unidad_actual) else ""
            bloques.append(
                f"Estado actual: Actualmente ocupa el cargo de {cargo_actual}{unidad_txt} "
                f"y su estado de vigencia es {estado_vigencia_txt}."
            )
        if v["N_CARGOS_SIGNIFICATIVOS"] > 0:
            bloques.append(
                f"Trayectoria: Ha ocupado {v['N_CARGOS_SIGNIFICATIVOS']} cargos significativos "
                "a lo largo de su trayectoria."
            )
        if secuencia:
            bloques.append(f"Secuencia profesional: {secuencia}.")
        if v["N_CARGOS_TOTAL"] > 0:
            bloques.append(
                f"Movilidad: Ha realizado {v['N_CAMBIOS_CARGO']} cambios de cargo y "
                f"{v['N_CAMBIOS_UNIDAD']} cambios de unidad. Ha desarrollado su trayectoria "
                f"en {v['N_UNIDADES_SIGNIFICATIVAS']} unidades."
            )
        if pd.notna(v["DURACION_MEDIA_CARGO_ANIOS"]):
            bloques.append(
                f"Permanencia: La duración media de sus cargos es de "
                f"{v['DURACION_MEDIA_CARGO_ANIOS']:.1f} años y la duración mediana es de "
                f"{v['DURACION_MEDIANA_CARGO_ANIOS']:.1f} años. Su cargo de mayor duración "
                f"se mantuvo durante {v['DURACION_MAX_CARGO_ANIOS']:.1f} años."
            )
        if descripcion_estabilidad:
            bloques.append(f"Estabilidad: {descripcion_estabilidad}")
        if descripcion_movilidad:
            bloques.append(f"Movilidad profesional: {descripcion_movilidad}")
        if insights:
            bloques.append("Patrones de trayectoria: " + " ".join(insights))

        documento = "\n".join(bloques)
        filas.append({
            "IDPERSONA": idp,
            "DOCUMENTO_TRAYECTORIA_TEXTO": documento if len(bloques) > 1 else "",
            **v,
        })

    columnas_base = ["IDPERSONA", "DOCUMENTO_TRAYECTORIA_TEXTO"]
    columnas_variables = [
        "N_CARGOS_TOTAL", "N_CARGOS_SIGNIFICATIVOS", "N_CAMBIOS_CARGO", "N_CAMBIOS_UNIDAD",
        "DURACION_MEDIA_CARGO_ANIOS", "DURACION_MEDIANA_CARGO_ANIOS", "DURACION_MAX_CARGO_ANIOS",
        "N_UNIDADES_TOTAL", "N_UNIDADES_SIGNIFICATIVAS", "PROPORCION_CARGOS_SIGNIFICATIVOS",
    ]
    if not filas:
        return pd.DataFrame(columns=columnas_base + columnas_variables)
    return pd.DataFrame(filas)[columnas_base + columnas_variables]


def _seccion_reconocimientos(poblacion: set[int]) -> pd.Series:
    df = _leer("mencion_honor.csv")
    df["FECHA"] = pd.to_datetime(df["FECHA"], format="mixed", errors="coerce")
    df = df[df["IDPERSONA"].isin(poblacion) & df["NOMBREMENCION"].notna()]
    if len(df) == 0:
        return pd.Series(dtype=object, name="RECONOCIMIENTOS")

    def _texto(r):
        anio = _anio(r.get("FECHA"))
        inst = f" ({r['INSTITUCION']})" if pd.notna(r.get("INSTITUCION")) else ""
        return f"{r['NOMBREMENCION']}{inst}" + (f", {anio}" if anio else "")

    df = df.assign(_TXT=df.apply(_texto, axis=1))
    txt = df.groupby("IDPERSONA")["_TXT"].apply(lambda s: _lista_items(list(s), maximo=6))
    return txt.apply(lambda t: f"Reconocimientos: {t}." if t else pd.NA).dropna().rename("RECONOCIMIENTOS")


# ---------------------------------------------------------------------------
# Ensamblado final
# ---------------------------------------------------------------------------

SECCIONES_ORDEN = [
    "TRAYECTORIA", "FORMACION", "DOCENCIA", "INVESTIGACION", "VINCULACION",
    "CAPACITACION", "IDIOMAS", "RECONOCIMIENTOS",
]

ETIQUETAS_SECCION = {
    "TRAYECTORIA": "Trayectoria",
    "FORMACION": "Formación académica",
    "DOCENCIA": "Docencia",
    "INVESTIGACION": "Investigación",
    "VINCULACION": "Vinculación",
    "CAPACITACION": "Capacitación",
    "IDIOMAS": "Idiomas",
    "RECONOCIMIENTOS": "Reconocimientos",
}


# Presupuesto de palabras del documento completo. El modelo de embeddings (E5, 512 tokens,
# ver seccion de decisiones) trunca silenciosamente lo que exceda su contexto; en vez de
# depender de ese truncamiento implicito (que cortaria a mitad de frase y castigaria
# siempre a las secciones finales sin importar su relevancia), se recorta explicitamente
# por seccion completa, empezando por la de menor prioridad (RECONOCIMIENTOS) hacia la de
# mayor (TRAYECTORIA nunca se recorta). Margen conservador bajo 512 tokens: el español
# tokenizado con subwords produce ~1.3 tokens/palabra en promedio.
PRESUPUESTO_PALABRAS = 380


def construir_documentos_semanticos(
    poblacion: set[int],
    eventos_trayectoria: pd.DataFrame,
    diversidad_trayectoria: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Construye el documento semantico por persona (ver DEC-014): una fila por IDPERSONA
    con el texto completo (`DOCUMENTO_TEXTO`) listo para embeber, mas metadata estructurada
    (`SECCIONES_INCLUIDAS`, `SECCIONES_RECORTADAS`, `N_CARACTERES`, `N_PALABRAS`) que NO
    entra al texto pero es util para filtrar/depurar en el dashboard.

    Solo se incluyen secciones con informacion real por persona - una persona sin
    publicaciones simplemente no tiene la seccion "Investigación" en su documento (no se
    fuerza texto vacio ni placeholders). Si el documento ensamblado excede
    `PRESUPUESTO_PALABRAS`, se recortan secciones completas de menor prioridad (el orden de
    `SECCIONES_ORDEN`, de atras hacia adelante) hasta que quepa - afecta solo al ~20% de la
    poblacion con historiales mas extensos, y siempre recorta lo menos distintivo primero
    (reconocimientos/idiomas/capacitación), nunca la trayectoria ni la formación.

    `diversidad_trayectoria` (opcional): pasado tal cual a `_seccion_trayectoria` (ver su
    docstring) para narrar diversidad de rol solo en el tercil superior de entropia.
    """
    secciones = {
        "TRAYECTORIA": _seccion_trayectoria(eventos_trayectoria, diversidad_trayectoria),
        "FORMACION": _seccion_formacion(poblacion),
        "DOCENCIA": _seccion_docencia(poblacion),
        "INVESTIGACION": _seccion_investigacion(poblacion),
        "VINCULACION": _seccion_vinculacion(poblacion),
        "CAPACITACION": _seccion_capacitacion(poblacion),
        "IDIOMAS": _seccion_idiomas(poblacion),
        "RECONOCIMIENTOS": _seccion_reconocimientos(poblacion),
    }

    todos_ids = sorted(poblacion)
    filas = []
    for idp in todos_ids:
        bloques, incluidas = [], []
        for clave in SECCIONES_ORDEN:
            serie = secciones[clave]
            texto = serie.get(idp) if idp in serie.index else None
            if texto and str(texto).strip():
                bloques.append((clave, f"{ETIQUETAS_SECCION[clave]}: {texto}"))
                incluidas.append(clave)

        recortadas = []
        while bloques and sum(len(b[1].split()) for b in bloques) > PRESUPUESTO_PALABRAS and len(bloques) > 1:
            clave_recortada, _ = bloques.pop()
            recortadas.append(clave_recortada)

        documento = "\n".join(b[1] for b in bloques)
        filas.append({
            "IDPERSONA": idp,
            "DOCUMENTO_TEXTO": documento,
            "SECCIONES_INCLUIDAS": ", ".join(c for c, _ in bloques),
            "SECCIONES_RECORTADAS": ", ".join(reversed(recortadas)),
            "N_SECCIONES": len(bloques),
            "N_CARACTERES": len(documento),
            "N_PALABRAS": len(documento.split()) if documento else 0,
        })

    return pd.DataFrame(filas)
