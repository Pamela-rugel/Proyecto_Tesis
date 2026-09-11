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


def _seccion_trayectoria(eventos: pd.DataFrame) -> pd.Series:
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
    documento de las personas con historiales de designacion/contratacion muy densos."""
    eventos = eventos.dropna(subset=["FECHA_INICIO"]).sort_values(["IDPERSONA", "FECHA_INICIO"])

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
            resultado[idp] = " ".join(texto for _, texto in items)

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


def construir_documentos_semanticos(poblacion: set[int], eventos_trayectoria: pd.DataFrame) -> pd.DataFrame:
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
    """
    secciones = {
        "TRAYECTORIA": _seccion_trayectoria(eventos_trayectoria),
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
