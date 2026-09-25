"""
Dashboard de perfiles del personal docente y administrativo de ESPOL.

Ejecutar con:
    d:\\Proyecto_Tesis\\.venv\\Scripts\\streamlit run notebooks\\08_dashboard\\app.py

Consume los datasets generados por `08_dashboard.ipynb` (`data/dashboard/`) y, para la búsqueda
semántica opcional, los embeddings de `07_embeddings` (`data/embeddings/`). No incluye nombres
reales: toda persona se identifica únicamente por `IDPERSONA` (ver DEC-003 / limitaciones en el
notebook).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

st.set_page_config(
    page_title="Perfiles de Personal ESPOL",
    page_icon="🎓",
    layout="wide",
)

CLUSTER_COLORS = px.colors.qualitative.Set2


# ---------------------------------------------------------------------------
# Carga de datos (cacheada)
# ---------------------------------------------------------------------------

@st.cache_data
def get_personas() -> pd.DataFrame:
    return lib.load_personas_dashboard()


@st.cache_data
def get_resumen() -> pd.DataFrame:
    return lib.load_cluster_resumen()


@st.cache_data
def get_top_features() -> pd.DataFrame:
    return lib.load_cluster_top_features()


@st.cache_data
def get_feature_labels() -> dict:
    return lib.feature_label_map()


@st.cache_data
def get_dendrograma() -> np.ndarray:
    return lib.load_dendrograma_centroides()


@st.cache_data
def get_pca() -> pd.DataFrame:
    return lib.load_pca_personas()


@st.cache_resource
def get_embeddings():
    return lib.load_embeddings()


@st.cache_data
def get_corpus() -> pd.DataFrame:
    return lib.load_corpus_texto()


@st.cache_data
def get_documento_semantico() -> pd.DataFrame:
    return lib.load_documento_semantico()


@st.cache_data
def get_eventos_trayectoria() -> pd.DataFrame:
    return lib.load_eventos_trayectoria()


@st.cache_resource
def get_text_model():
    from sentence_transformers import SentenceTransformer

    # DEC-028: mismo modelo usado para generar embeddings_personas.csv (documento
    # semantico completo por persona) - debe ser el mismo modelo para que la consulta
    # y los documentos vivan en el mismo espacio vectorial. BGE-M3 no usa prefijos.
    return SentenceTransformer("BAAI/bge-m3")


def cluster_color(cluster: int) -> str:
    return lib.PERFIL_COLORES.get(int(cluster), CLUSTER_COLORS[int(cluster) % len(CLUSTER_COLORS)])


_STOPWORDS_ES = {
    "de", "la", "el", "en", "que", "y", "a", "los", "las", "un", "una", "con", "para",
    "por", "su", "es", "se", "del", "al", "lo", "como", "más", "o", "sin", "sobre",
}


def _mejor_evidencia(consulta: str, documento: str, max_oraciones: int = 2) -> str:
    """Heuristica de evidencia por solapamiento lexico (NO es lo que "vio" el embedding
    internamente - la similitud del embedding captura significado, no solo palabras
    compartidas): de las oraciones del documento semantico de la persona, elige las que
    comparten mas palabras con la consulta. Transparente y verificable por el usuario
    (a diferencia de un puntaje de similitud, que no es interpretable de forma absoluta -
    ver DEC-019 en context/DECISION_LOG.md), aunque no es una explicacion exacta de por
    que el modelo de embeddings califico a esta persona como relevante."""
    if not documento or not isinstance(documento, str):
        return ""
    palabras_consulta = {w for w in consulta.lower().split() if w not in _STOPWORDS_ES and len(w) > 2}
    if not palabras_consulta:
        return documento[:220] + ("…" if len(documento) > 220 else "")

    oraciones = [o.strip() for o in documento.replace("\n", " ").split(". ") if o.strip()]
    puntajes = []
    for o in oraciones:
        palabras_oracion = {w.strip(".,;:()") for w in o.lower().split()}
        solape = len(palabras_consulta & palabras_oracion)
        if solape:
            puntajes.append((solape, o))
    if not puntajes:
        return documento[:220] + ("…" if len(documento) > 220 else "")
    puntajes.sort(key=lambda t: -t[0])
    mejores = [o for _, o in puntajes[:max_oraciones]]
    return " (…) ".join(mejores)


def render_dendrograma_perfiles(Z: np.ndarray, resumen: pd.DataFrame):
    """Dendrograma de los perfiles finales (ver DEC-007): que tan cerca/lejos esta cada
    perfil de los demas, calculado sobre los centroides del clustering (no cambia el
    modelo ni la asignacion de persona a perfil, es solo una vista adicional)."""
    from scipy.cluster.hierarchy import dendrogram

    nombres = dict(zip(resumen["CLUSTER"], resumen["PERFIL_NOMBRE"]))
    etiquetas = [f"{c} — {nombres.get(c, c)}" for c in sorted(nombres)]
    dend = dendrogram(Z, labels=etiquetas, no_plot=True)

    fig = go.Figure()
    for xs, ys in zip(dend["icoord"], dend["dcoord"]):
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#4C72B0"), hoverinfo="skip", showlegend=False))

    tick_pos = [5 + 10 * i for i in range(len(dend["ivl"]))]
    fig.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(tickmode="array", tickvals=tick_pos, ticktext=dend["ivl"], tickangle=0),
        yaxis=dict(title="distancia (ward) entre centroides"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Perfiles unidos a menor distancia son más parecidos entre sí en el espacio completo de "
        "variables usado para el clustering. No implica que las personas dentro de perfiles cercanos "
        "sean intercambiables — la distancia es entre los centroides (promedios), no entre personas."
    )


def _asignar_subfilas(df: pd.DataFrame) -> pd.Series:
    """Empaqueta eventos que se solapan en fecha dentro de la MISMA `LANE` en sub-filas
    distintas (0, 1, 2...), para que dos contratos simultaneos (ej. dos cargos de grado a
    la vez) se dibujen en barras separadas verticalmente en vez de superpuestas - pedido
    explicito del usuario 2026-09-10 ("siento que ahora se mezcla todo"). Algoritmo greedy
    de intervalos: dentro de cada `LANE`, ordenado por `FECHA_INICIO`, cada evento se
    asigna a la primera sub-fila cuyo ultimo evento ya haya terminado antes de que este
    empiece; si ninguna esta libre, abre una sub-fila nueva. No reordena entre lanes."""
    subfila = pd.Series(0, index=df.index, dtype=int)
    for _, grupo in df.groupby("LANE", sort=False):
        fin_por_subfila: list[pd.Timestamp] = []
        for idx in grupo.sort_values("FECHA_INICIO").index:
            inicio = df.loc[idx, "FECHA_INICIO"]
            fin = df.loc[idx, "FECHA_FIN_EFECTIVA"]
            asignada = None
            for i, fin_ocupado in enumerate(fin_por_subfila):
                if inicio >= fin_ocupado:
                    asignada = i
                    break
            if asignada is None:
                asignada = len(fin_por_subfila)
                fin_por_subfila.append(fin)
            else:
                fin_por_subfila[asignada] = fin
            subfila.loc[idx] = asignada
    return subfila


def render_timeline_trayectoria(eventos_persona: pd.DataFrame):
    """Timeline (Gantt) de la trayectoria de una persona: cargo estructural en ESPOL
    (separado en Grado/Posgrado cuando el dato lo permite), contratos puntuales dentro de
    ESPOL (DEC-018), funciones adicionales/subrogaciones (DEC-012, distinguidas del
    contrato) y experiencia externa (separada en Ecuador/Exterior) - todas del mismo
    `eventos_trayectoria_persona.csv` que alimenta el documento semantico (DEC-014), aquí
    presentado como datos estructurados, no como el texto ya ensamblado.

    DEC-018: un evento vigente (`ES_VIGENTE=True`, `FECHA_FIN` nula) se extiende hasta hoy
    para dibujarse, pero antes eso no se comunicaba en ningun lado visible (el tooltip solo
    mostraba la fecha de hoy como si fuera un cierre real) - ahora el tooltip dice
    explicitamente "Actualidad" en vez de la fecha calculada cuando el evento sigue
    vigente, y se muestra el rango fecha inicio-fin como texto legible.

    2026-09-10: dos contratos simultaneos de la MISMA categoria (ej. dos cargos de grado a
    la vez) se apilan en sub-filas dentro de la misma `LANE` (ver `_asignar_subfilas`) en
    vez de superponerse visualmente - se dibuja con `go.Bar` horizontal en vez de
    `px.timeline` porque este ultimo no soporta sub-filas dentro de una categoria del eje
    Y sin duplicar la etiqueta."""
    if eventos_persona.empty:
        st.caption("No hay eventos de trayectoria (cargos, funciones, experiencia externa) registrados para esta persona.")
        return

    hoy = pd.Timestamp.today().normalize()
    df = eventos_persona.sort_values("FECHA_INICIO").copy()
    # Defensa adicional: garantiza datetime64 aunque la fuente venga como texto (ver
    # leccion de esta sesion sobre parse_dates fallando en silencio con fechas mal
    # formadas en el origen) - lib.load_eventos_trayectoria ya lo hace, esto es un respaldo.
    df["FECHA_INICIO"] = pd.to_datetime(df["FECHA_INICIO"], format="mixed", errors="coerce")
    df["FECHA_FIN"] = pd.to_datetime(df["FECHA_FIN"], format="mixed", errors="coerce")
    df["_VIGENTE"] = df["FECHA_FIN"].isna()
    df["FECHA_FIN_EFECTIVA"] = df["FECHA_FIN"].fillna(hoy)
    df.loc[df["FECHA_FIN_EFECTIVA"] <= df["FECHA_INICIO"], "FECHA_FIN_EFECTIVA"] = (
        df["FECHA_INICIO"] + pd.Timedelta(days=30)
    )
    df["LANE"] = df["TIPO_EVENTO"].map(lib.ETIQUETA_TIPO_EVENTO)
    df["DETALLE"] = df.apply(
        lambda r: str(r["DESCRIPCION"]) + (f" — {r['UNIDAD']}" if pd.notna(r.get("UNIDAD")) else ""), axis=1
    )
    df["RANGO_TEXTO"] = df.apply(
        lambda r: f"{r['FECHA_INICIO']:%b %Y} – "
        + ("Actualidad" if r["_VIGENTE"] else f"{r['FECHA_FIN']:%b %Y}"),
        axis=1,
    )
    df["SUBFILA"] = _asignar_subfilas(df)

    # Cada LANE ocupa tantas filas visuales como su maximo de sub-filas simultaneas
    # (1 si nunca hay solape); las lanes se apilan de arriba a abajo en el orden en que
    # aparecen (primera aparicion por FECHA_INICIO), y dentro de cada una, SUBFILA=0 va
    # arriba. `FILA_Y` es la posicion vertical final (entero, una por barra dibujada).
    orden_lanes = list(dict.fromkeys(df.sort_values("FECHA_INICIO")["LANE"]))
    alto_por_lane = df.groupby("LANE")["SUBFILA"].max().add(1)
    offset_lane = {}
    acumulado = 0
    for lane in orden_lanes:
        offset_lane[lane] = acumulado
        acumulado += int(alto_por_lane[lane])
    df["FILA_Y"] = df.apply(lambda r: offset_lane[r["LANE"]] + r["SUBFILA"], axis=1)
    total_filas = acumulado

    # Etiquetas del eje Y: una por LANE, centrada en sus sub-filas (si tiene 2 sub-filas
    # ocupando las posiciones 3 y 4, la etiqueta se centra en 3.5) - las sub-filas no
    # llevan etiqueta propia, siguen leyendose como "la misma categoria".
    tickvals = [offset_lane[lane] + (alto_por_lane[lane] - 1) / 2 for lane in orden_lanes]

    fig = go.Figure()
    for tipo_evento, grupo in df.groupby("TIPO_EVENTO", sort=False):
        # go.Bar con eje X tipo fecha necesita la duracion en milisegundos (numero), no un
        # Timedelta - a diferencia de px.timeline, que hace esta conversion internamente.
        # Sin esto, plotly.io.to_json falla ("Object of type timedelta is not JSON
        # serializable") al primer evento con solape real (detectado con AppTest,
        # persona 96, CARGO_ESPOL_POSGRADO).
        duracion_ms = (grupo["FECHA_FIN_EFECTIVA"] - grupo["FECHA_INICIO"]).dt.total_seconds() * 1000
        fig.add_trace(go.Bar(
            base=grupo["FECHA_INICIO"],
            x=duracion_ms,
            y=grupo["FILA_Y"],
            orientation="h",
            name=lib.ETIQUETA_TIPO_EVENTO.get(tipo_evento, tipo_evento),
            marker_color=lib.COLOR_TIPO_EVENTO.get(tipo_evento, "#999999"),
            customdata=grupo[["DETALLE", "RANGO_TEXTO"]],
            hovertemplate="%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
            width=0.7,
        ))
    fig.update_traces(marker_line_width=0)
    fig.update_xaxes(type="date")
    fig.update_yaxes(
        autorange="reversed", title=None, tickmode="array",
        tickvals=tickvals, ticktext=orden_lanes,
    )
    fig.add_vline(x=hoy, line_dash="dot", line_color="#E63946", line_width=1.5)
    fig.add_annotation(x=hoy, y=1.0, yref="paper", text="Hoy", showarrow=False,
                        font=dict(color="#E63946", size=11), yanchor="bottom")
    fig.update_layout(
        height=170 + 42 * total_filas, showlegend=True, barmode="overlay",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    st.plotly_chart(fig, use_container_width=True)
    if df["_VIGENTE"].any():
        vigentes = df.loc[df["_VIGENTE"], "LANE"].unique().tolist()
        st.caption(f"🟢 Vigente hasta la actualidad: {', '.join(vigentes)} (línea punteada roja = hoy).")


def _render_seccion_trayectoria_extra(clave: str, datos) -> None:
    """Renderiza cada sub-seccion de la ficha (formacion/docencia/investigacion/...) con
    el formato mas legible para su forma de datos - todas via `lib.*_persona`, la misma
    fuente estructurada detras del documento semantico (DEC-014)."""
    if clave == "formacion":
        st.dataframe(
            datos.rename(columns={"Titulo": "Título", "Institucion": "Institución",
                                   "Pais": "País", "FechaGraduacion": "Graduación"}),
            use_container_width=True, hide_index=True,
        )
    elif clave == "docencia":
        st.dataframe(
            datos.rename(columns={"NOMMATERIA": "Materia", "ANIO_MIN": "Desde", "ANIO_MAX": "Hasta",
                                   "N_PERIODOS": "N° periodos", "UNIDAD": "Unidad"}),
            use_container_width=True, hide_index=True,
        )
    elif clave == "investigacion":
        if len(datos["proyectos"]):
            st.markdown("**Proyectos de investigación**")
            st.dataframe(datos["proyectos"].rename(columns={
                "NOMBRE": "Proyecto", "STRAREACAMPOAMPLIO": "Área", "FECHAINICIO": "Desde",
                "FECHAFIN": "Hasta", "ESTADO_PROYECTO": "Estado"}), use_container_width=True, hide_index=True)
        if len(datos["publicaciones"]):
            st.markdown("**Publicaciones**")
            st.dataframe(datos["publicaciones"].rename(columns={
                "TITULO": "Título", "ANIO": "Año", "TIPOPUBLICACION": "Tipo", "CUARTIL": "Cuartil"}),
                use_container_width=True, hide_index=True)
        if len(datos["tesis_dirigidas"]):
            st.markdown("**Trabajos de titulación dirigidos**")
            st.dataframe(datos["tesis_dirigidas"].rename(columns={
                "NOMBRETRABAJOTITULACION": "Trabajo de titulación", "FECHASUSTENTACION": "Sustentación",
                "NIVELFORMACION": "Nivel"}), use_container_width=True, hide_index=True)
        if len(datos["ponencias"]):
            st.markdown("**Ponencias**")
            st.dataframe(datos["ponencias"].rename(columns={
                "NOMBRE": "Ponencia", "FECHAINICIO": "Fecha", "NOMBREPAIS": "País"}),
                use_container_width=True, hide_index=True)
    elif clave == "vinculacion":
        st.dataframe(datos.rename(columns={
            "NOMBREPROYECTO": "Proyecto", "NOMBREPROGRAMA": "Programa",
            "FECHAINICIO": "Desde", "FECHAFIN": "Hasta"}), use_container_width=True, hide_index=True)
    elif clave == "capacitacion":
        if len(datos["capacitaciones"]):
            st.markdown(f"**Capacitación** ({len(datos['capacitaciones'])} registros)")
            st.dataframe(datos["capacitaciones"].rename(columns={
                "NOMBRE": "Nombre", "FECHAINICIO": "Fecha", "TIPOCAPACITACION": "Tipo", "NOMBREPAIS": "País"}),
                use_container_width=True, hide_index=True, height=min(320, 46 + 36 * len(datos["capacitaciones"])))
        if len(datos["certificaciones"]):
            st.markdown("**Certificaciones**")
            st.dataframe(datos["certificaciones"].rename(columns={
                "NOMBRE": "Nombre", "FECHAINICIO": "Fecha", "CERTIFICADOPOR": "Certificado por"}),
                use_container_width=True, hide_index=True)
    elif clave == "idiomas":
        st.dataframe(datos.rename(columns={
            "IDIOMA": "Idioma", "NIVELLECTURA": "Lectura", "NIVELESCRITURA": "Escritura",
            "NIVELCONVERSACION": "Conversación", "NIVELMCER": "Nivel MCER"}),
            use_container_width=True, hide_index=True)
    elif clave == "reconocimientos":
        st.dataframe(datos.rename(columns={
            "NOMBREMENCION": "Mención", "INSTITUCION": "Institución", "FECHA": "Fecha"}),
            use_container_width=True, hide_index=True)


def render_persona_ficha(
    persona: pd.Series, resumen: pd.DataFrame, labels: dict,
    coincidencia_semantica: dict | None = None,
):
    """`coincidencia_semantica` (opcional): {"rango": int, "consulta": str} — cuando la ficha
    se abre desde un resultado de búsqueda semántica, muestra un único bloque que combina *por
    qué coincidió el texto* (evidencia semántica) con *los datos estructurales* de la persona,
    en vez de repetir la evidencia dos veces (una en la tabla de resultados, otra en la ficha)
    como pasaba antes (pedido explícito del usuario, 2026-09-09). No incluye un puntaje de
    similitud (DEC-019): no es interpretable como porcentaje de relevancia absoluta, ver
    metodología — solo se muestra el orden (#N) dentro de los resultados de esa búsqueda."""
    idp = int(persona["IDPERSONA"])
    cluster_val = persona.get("CLUSTER")
    tiene_perfil = pd.notna(cluster_val) and int(cluster_val) != -1

    st.markdown(f"### Persona `{idp}`")
    if coincidencia_semantica is not None:
        st.success(
            f"💬 Resultado #{coincidencia_semantica['rango']} para tu búsqueda "
            f"*\"{coincidencia_semantica['consulta']}\"*. Ver por qué en "
            "\"¿Por qué coincide?\", más abajo."
        )
    if tiene_perfil:
        st.markdown(f"**Perfil:** :orange[{persona['PERFIL_NOMBRE']}]  (cluster {int(cluster_val)})")
    else:
        motivo = lib.motivo_sin_perfil(idp)
        st.caption(
            "Sin perfil/cluster asignado — esta persona no tiene un cargo estructural en ESPOL. "
            + (motivo or "No se encontró un motivo específico en los datos.")
        )
    if persona.get("TUVO_FUNCION_ADICIONAL"):
        rol_reciente = persona.get("CATEGORIA_FUNCION_ADICIONAL_MAS_RECIENTE")
        legible = lib.NOMBRES_CATEGORIA_CARGO.get(rol_reciente, str(rol_reciente).replace("_", " ").title()) \
            if pd.notna(rol_reciente) else "una función adicional"
        st.caption(
            f"ℹ️ Además de su cargo, ha ejercido **{legible}** en paralelo en algún momento "
            "(ver Trayectoria abajo — distinto de un cambio de tipo de empleado)."
        )
    if persona.get("CARGO_ES_CONTRATO_PUNTUAL_VIGENTE"):
        st.caption(
            "ℹ️ Su cargo estructural más reciente ya finalizó; \"Cargo actual\"/\"Unidad actual\" "
            "abajo corresponden a un **contrato vigente de tipo puntual/servicios profesionales** "
            "(ver DEC-017), no a un cargo estructural continuo — por eso no determina su perfil/cluster."
        )

    cols = st.columns(4)
    campos = [
        ("Tipo de empleado", persona.get("TIPOEMPLEADO_ACTUAL_DESC")),
        ("Cargo actual", persona.get("CARGO_ACTUAL")),
        ("Unidad actual", persona.get("UNIDAD_ACTUAL_NOMBRE")),
        ("Vigente actualmente", "Sí" if persona.get("VIGENTE_MOSTRAR") else "No"),
    ]
    for col, (label, value) in zip(cols, campos):
        val_str = "-" if pd.isna(value) else str(value)
        col.markdown(
            f"<p style='color: #6c757d; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.2rem;'>{label}</p>"
            f"<p style='font-size: 1.15rem; font-weight: 700; line-height: 1.25;'>{val_str}</p>",
            unsafe_allow_html=True
        )

    st.markdown("#### Trayectoria")
    eventos_persona = get_eventos_trayectoria()
    eventos_persona = eventos_persona[eventos_persona["IDPERSONA"] == idp]
    render_timeline_trayectoria(eventos_persona)

    secciones = []
    formacion = lib.formacion_persona(idp)
    if len(formacion):
        secciones.append(("🎓 Formación", "formacion", formacion))
    docencia = lib.docencia_persona(idp)
    if len(docencia):
        secciones.append(("📚 Docencia", "docencia", docencia))
    investigacion = lib.investigacion_persona(idp)
    if any(len(v) for v in investigacion.values()):
        secciones.append(("🔬 Investigación", "investigacion", investigacion))
    vinculacion = lib.vinculacion_persona(idp)
    if len(vinculacion):
        secciones.append(("🤝 Vinculación", "vinculacion", vinculacion))
    capacitacion = lib.capacitacion_persona(idp)
    if any(len(v) for v in capacitacion.values()):
        secciones.append(("📜 Capacitación", "capacitacion", capacitacion))
    idiomas = lib.idiomas_persona(idp)
    if len(idiomas):
        secciones.append(("🌐 Idiomas", "idiomas", idiomas))
    reconocimientos = lib.reconocimientos_persona(idp)
    if len(reconocimientos):
        secciones.append(("🏅 Reconocimientos", "reconocimientos", reconocimientos))

    if secciones:
        st.markdown("#### Perfil profesional")
        tabs_secciones = st.tabs([s[0] for s in secciones])
        for tab, (_, clave, datos) in zip(tabs_secciones, secciones):
            with tab:
                _render_seccion_trayectoria_extra(clave, datos)
    else:
        st.caption("No hay información adicional de formación/docencia/investigación registrada.")

    if tiene_perfil:
        st.markdown("#### Cluster / perfil de trayectoria")
        fila_cluster = resumen[resumen["CLUSTER"] == int(cluster_val)]
        if len(fila_cluster):
            st.caption(fila_cluster.iloc[0]["DESCRIPCION"])
        with st.expander("Comparación con la institución (percentil sobre variables clave)"):
            disponibles = [f for f in lib.RADAR_FEATURES if f in persona.index]
            personas_all = get_personas()
            radar_vals = []
            for f in disponibles:
                serie = personas_all[f]
                val = persona[f]
                pct = float((serie < val).mean()) if pd.notna(val) else 0.0
                radar_vals.append(pct)
            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(r=radar_vals + radar_vals[:1], theta=disponibles + disponibles[:1],
                                           fill="toself", name="Esta persona"))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False, height=380,
                               margin=dict(l=40, r=40, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"Percentil respecto a las {len(personas_all):,} personas de la población "
                       "(0 = valor más bajo, 1 = valor más alto).")

    n_textos = persona.get("N_REGISTROS_TEXTO")
    if pd.notna(n_textos) and n_textos and n_textos > 0:
        titulo_expander = (
            "¿Por qué coincide? (texto semántico + datos estructurales)"
            if coincidencia_semantica is not None
            else f"Evidencia de texto usada en búsqueda semántica ({int(n_textos)} registros)"
        )
        with st.expander(titulo_expander, expanded=coincidencia_semantica is not None):
            if coincidencia_semantica is not None:
                doc_texto = get_documento_semantico().set_index("IDPERSONA")["DOCUMENTO_TEXTO"].get(idp, "")
                evidencia = _mejor_evidencia(coincidencia_semantica["consulta"], doc_texto)
                if evidencia:
                    st.markdown(f"> {evidencia}")
                st.caption(
                    "**Texto semántico** — fragmentos del documento con el que se comparó tu consulta "
                    "(similitud de significado, no solo palabras clave; el fragmento resaltado arriba se "
                    "elige por coincidencia de palabras con tu búsqueda, como orientación — la comparación "
                    "real del modelo evalúa significado sobre el documento completo, no solo esas palabras):"
                )
            corpus = get_corpus()
            muestra = corpus[corpus["IDPERSONA"] == idp].head(10)
            if not muestra.empty:
                st.dataframe(muestra[["FUENTE", "TEXTO"]], use_container_width=True, hide_index=True)
            if coincidencia_semantica is not None:
                st.caption(
                    "**Datos estructurales** — cargo, unidad y perfil ya mostrados arriba "
                    "(cabecera y sección \"Perfil profesional\") son la misma fuente de verdad, "
                    "no un resumen aparte del texto de búsqueda."
                )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

def main():
    personas = get_personas()
    resumen = get_resumen()
    top_features = get_top_features()
    labels = get_feature_labels()

    st.title("🎓 Perfiles de Personal ESPOL")
    st.caption(
        "Prototipo de apoyo a la decisión — asignación de tareas, conformación de comisiones y "
        "equipos, planificación académica y administrativa. Estructura de 2 niveles: primero "
        "Administrativo/Docente, luego la categoría de cargo real de cada persona. El mapa de "
        "puntos permite explorar afinidad de trayectoria por cercanía, sin forzar categorías nuevas."
    )

    tab_resumen, tab_mapa, tab_persona, tab_equipos, tab_semantica = st.tabs([
        "Resumen general y perfiles",
        "Mapa de perfiles",
        "Buscar persona",
        "Formar equipos / comisiones",
        "💬 Búsqueda semántica (lenguaje libre)",
    ])

    # --- Resumen general + Explorar perfiles (combinadas) ------------------
    with tab_resumen:
        c1, c2, c3 = st.columns(3)
        c1.metric("Personas en el modelo", f"{len(personas):,}")
        c2.metric("Perfiles (clusters)", resumen["CLUSTER"].nunique())
        c3.metric("Con texto para búsqueda semántica", f"{(personas['N_REGISTROS_TEXTO'] > 0).sum():,}")

        orden_resumen = resumen.sort_values("CLUSTER")
        fig = px.bar(
            orden_resumen,
            x="PERFIL_NOMBRE", y="N_PERSONAS", color="PERFIL_NOMBRE",
            color_discrete_sequence=[cluster_color(c) for c in orden_resumen["CLUSTER"]],
            text="PCT_POBLACION",
            labels={"PERFIL_NOMBRE": "Perfil", "N_PERSONAS": "N personas"},
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(showlegend=False, xaxis_title=None, height=450)
        st.caption("Haz clic en una barra para ver el detalle de ese perfil más abajo.")
        seleccion_barra = st.plotly_chart(
            fig, use_container_width=True, on_select="rerun", selection_mode="points", key="resumen_bar",
        )

        st.markdown("---")
        puntos_barra = seleccion_barra.selection.points
        if not puntos_barra:
            st.info("Haz clic en una barra del gráfico de arriba para ver el detalle de ese perfil.")
        else:
            # El punto trae la categoria del eje x (PERFIL_NOMBRE), no un dato aparte:
            # mas robusto que custom_data para un grafico de barras (una barra = un
            # perfil), donde la forma exacta de "customdata" en el evento de seleccion
            # no es consistente entre versiones de Streamlit/Plotly.
            perfil_clic = puntos_barra[0]["x"]
            cluster_sel = int(orden_resumen.loc[orden_resumen["PERFIL_NOMBRE"] == perfil_clic, "CLUSTER"].iloc[0])
            fila = resumen[resumen["CLUSTER"] == cluster_sel].iloc[0]
            st.subheader(fila["PERFIL_NOMBRE"])
            st.markdown(f"**{int(fila['N_PERSONAS'])} personas** ({fila['PCT_POBLACION']}% de la población)")
            st.write(fila["DESCRIPCION"])

            feats = top_features[top_features["CLUSTER"] == cluster_sel].copy()
            feats["FEATURE_LABEL"] = feats["FEATURE"].map(lambda f: labels.get(f, f))
            fig_feats = go.Figure()
            fig_feats.add_trace(go.Bar(y=feats["FEATURE_LABEL"], x=feats["VALUE_CLUSTER"], name="Este perfil", orientation="h",
                                        marker_color=cluster_color(cluster_sel)))
            fig_feats.add_trace(go.Bar(y=feats["FEATURE_LABEL"], x=feats["VALUE_GLOBAL"], name="Institución (global)", orientation="h",
                                        marker_color="lightgray"))
            fig_feats.update_layout(barmode="group", height=420, title="Variables más distintivas de este perfil",
                                     yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_feats, use_container_width=True)
            st.caption(
                "Comparación de mediana (o proporción) del perfil vs. la mediana institucional global, para las "
                "variables con mayor tamaño de efecto (`IMPORTANCE`, ver `cluster_characterization.csv`)."
            )

            st.markdown("**Cargos reales que componen este perfil**")
            cargos_cluster = personas.loc[personas["CLUSTER"] == cluster_sel, "CARGO_ACTUAL"].dropna()
            if len(cargos_cluster):
                conteo_cargos = cargos_cluster.value_counts().reset_index()
                conteo_cargos.columns = ["CARGO_ACTUAL", "N_PERSONAS"]
                st.dataframe(conteo_cargos, use_container_width=True, hide_index=True, height=250)
                st.caption(
                    f"{cargos_cluster.nunique()} cargos distintos entre las {len(cargos_cluster)} personas de este "
                    "perfil con cargo actual registrado. El nombre del perfil es una síntesis interpretativa — "
                    "esta es la lista real de cargos que agrupa."
                )
            else:
                st.caption("Ninguna persona de este perfil tiene `CARGO_ACTUAL` registrado.")

            st.markdown("**Personas de este perfil (muestra)**")
            muestra_cols = ["IDPERSONA"] + [c for c in lib.METRICAS_CLAVE if c in personas.columns]
            st.dataframe(
                personas[personas["CLUSTER"] == cluster_sel][muestra_cols].head(50),
                use_container_width=True, hide_index=True,
            )

    # --- Mapa de perfiles (puntos clicables) ------------------------------
    with tab_mapa:
        
        tipo_filtro = st.radio(
            "Tipo de empleado", ["Todos", "Solo Administrativo", "Solo Docente"],
            horizontal=True, key="mapa_tipo_filtro",
        )
        perfiles_mapa = st.multiselect(
            "Categorías de cargo a mostrar (opcional)", options=sorted(resumen["CLUSTER"]),
            format_func=lambda c: f"{c} — {lib.PERFIL_NOMBRES[c]}", key="mapa_perfiles_filtro",
        )

        pca_df = get_pca().merge(
            personas[["IDPERSONA", "CLUSTER", "PERFIL_NOMBRE", "TIPOEMPLEADO_ACTUAL_DESC",
                      "VIGENTE_MOSTRAR", "CARGO_ACTUAL"]],
            on="IDPERSONA", how="inner",
        )
        # 5 personas sin TIPOEMPLEADO_ACTUAL_DESC (CLUSTER=-1, ver DEC-008) no tienen sub-perfil
        # asignado; se excluyen del mapa en vez de mostrarlas sin color/perfil.
        pca_df = pca_df[pca_df["CLUSTER"] != -1]
        if tipo_filtro == "Solo Administrativo":
            pca_df = pca_df[pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "ADMINISTRATIVO"]
        elif tipo_filtro == "Solo Docente":
            pca_df = pca_df[pca_df["TIPOEMPLEADO_ACTUAL_DESC"] == "DOCENTE"]
        if perfiles_mapa:
            pca_df = pca_df[pca_df["CLUSTER"].isin(perfiles_mapa)]

        pca_df = pca_df.sort_values("CLUSTER")
        fig_mapa = px.scatter(
            pca_df, x="PC1", y="PC2", color="PERFIL_NOMBRE",
            color_discrete_map={row["PERFIL_NOMBRE"]: cluster_color(row["CLUSTER"])
                                 for _, row in pca_df[["CLUSTER", "PERFIL_NOMBRE"]].drop_duplicates().iterrows()},
            custom_data=["IDPERSONA"],
            hover_data={"IDPERSONA": True, "PERFIL_NOMBRE": True, "TIPOEMPLEADO_ACTUAL_DESC": True,
                        "CARGO_ACTUAL": True, "VIGENTE_MOSTRAR": True, "PC1": False, "PC2": False},
        )
        fig_mapa.update_traces(marker=dict(size=6, opacity=0.7))
        fig_mapa.update_layout(height=560, legend_title=None)
        seleccion = st.plotly_chart(
            fig_mapa, use_container_width=True, on_select="rerun", selection_mode="points", key="mapa_scatter",
        )
        st.caption(f"{len(pca_df):,} personas mostradas de {len(personas):,} en el modelo.")

        puntos = seleccion.selection.points
        if puntos:
            id_clic = puntos[0]["customdata"][0]
            st.markdown("---")
            persona_clic = personas[personas["IDPERSONA"] == id_clic]
            if len(persona_clic):
                render_persona_ficha(persona_clic.iloc[0], resumen, labels)
        else:
            st.info("Haz clic en un punto del gráfico para ver la ficha de esa persona.")

    # --- Buscar persona ---------------------------------------------------
    with tab_persona:
        st.markdown(
            "#### 🔎 Consulta directa por identificador\n"
            "Ya conoces el `IDPERSONA` (por ejemplo, desde el mapa de perfiles o desde una lista "
            "exportada) y quieres ver su ficha completa. ¿Buscas a alguien por experiencia o "
            "conocimiento sin conocer su ID? Usa la pestaña **💬 Búsqueda semántica** en su lugar."
        )
        id_sel = st.selectbox("IDPERSONA", options=sorted(personas["IDPERSONA"].unique()))
        persona = personas[personas["IDPERSONA"] == id_sel].iloc[0]
        render_persona_ficha(persona, resumen, labels)

    # --- Formar equipos / comisiones --------------------------------------
    with tab_equipos:
        st.markdown(
            "Filtra candidatos por perfil y por criterios profesionales/institucionales para apoyar la "
            "conformación de una comisión o equipo."
        )
        perfiles_sel = st.multiselect(
            "Perfiles a incluir", options=sorted(resumen["CLUSTER"]),
            default=sorted(resumen["CLUSTER"]),
            format_func=lambda c: f"{c} — {lib.PERFIL_NOMBRES[c]}",
        )
        c1, c2, c3 = st.columns(3)
        vigente_sel = c1.selectbox("Vigencia", ["Cualquiera", "Solo vigentes", "Solo no vigentes"])
        tipo_sel = c2.multiselect("Tipo de empleado", options=sorted(personas["TIPOEMPLEADO_ACTUAL_DESC"].dropna().unique()))
        nivel_sel = c3.multiselect("Nivel académico máximo", options=sorted(personas["NIVEL_ACADEMICO_MAXIMO"].dropna().unique()))

        c4, c5 = st.columns(2)
        min_publicaciones = c4.number_input("Mínimo de publicaciones", min_value=0, value=0, step=1)
        min_exp_admin = c5.number_input("Mínimo de años de experiencia administrativa", min_value=0.0, value=0.0, step=0.5)

        resultado = personas[personas["CLUSTER"].isin(perfiles_sel)]
        if vigente_sel == "Solo vigentes":
            resultado = resultado[resultado["VIGENTE_MOSTRAR"] == True]  # noqa: E712
        elif vigente_sel == "Solo no vigentes":
            resultado = resultado[resultado["VIGENTE_MOSTRAR"] == False]  # noqa: E712
        if tipo_sel:
            resultado = resultado[resultado["TIPOEMPLEADO_ACTUAL_DESC"].isin(tipo_sel)]
        if nivel_sel:
            resultado = resultado[resultado["NIVEL_ACADEMICO_MAXIMO"].isin(nivel_sel)]
        if min_publicaciones:
            resultado = resultado[resultado["NUM_PUBLICACIONES"].fillna(0) >= min_publicaciones]
        if min_exp_admin:
            resultado = resultado[resultado["ANIOS_EXPERIENCIA_ADMINISTRATIVO"].fillna(0) >= min_exp_admin]

        st.markdown(f"**{len(resultado)} personas cumplen los criterios.**")
        cols_out = ["IDPERSONA"] + [c for c in lib.METRICAS_CLAVE if c in resultado.columns]
        st.dataframe(resultado[cols_out], use_container_width=True, hide_index=True)
        st.download_button(
            "Descargar candidatos (CSV)",
            data=resultado[cols_out].to_csv(index=False).encode("utf-8"),
            file_name="candidatos_equipo.csv",
            mime="text/csv",
        )

    # --- Búsqueda semántica -------------------------------------------------
    with tab_semantica:
        st.markdown(
            "#### 💬 Describe lo que buscas, en tus propias palabras\n"
            "A diferencia de \"🔎 Buscar por ID\" (que requiere saber el `IDPERSONA` exacto), aquí "
            "**describes libremente** el conocimiento, experiencia o trayectoria que necesitas y el "
            "sistema encuentra a las personas más afines por **significado**, no por palabras clave "
            "exactas — se compara contra el documento semántico de cada persona (trayectoria, "
            "formación, docencia, investigación, funciones adicionales, capacitación, idiomas, "
            "reconocimientos — ver DEC-014)."
        )
        ejemplos = [
            "experiencia en aprendizaje automático aplicado a imágenes médicas",
            "persona que haya trabajado fuera de ESPOL en el extranjero",
            "administración de servidores y redes",
            "gestión de proyectos de vinculación con la comunidad",
        ]
        st.caption("Ejemplos: " + " · ".join(f"*\"{e}\"*" for e in ejemplos))
        consulta = st.text_input(
            "Consulta", label_visibility="collapsed",
            placeholder="Ej: persona con experiencia en gestión de proyectos de vinculación con la comunidad",
        )
        top_n = st.slider("Número de resultados", min_value=3, max_value=25, value=10)

        if consulta:
            with st.spinner("Buscando..."):
                ids, matrix = get_embeddings()
                modelo = get_text_model()
                # DEC-028: BGE-M3 no usa prefijos (a diferencia de E5) - texto tal cual.
                q = modelo.encode([consulta], normalize_embeddings=True)[0]
                sims = matrix @ q
                top_idx = np.argsort(-sims)[:top_n]
                # DEC-019 (ver context/DECISION_LOG.md): NO se muestra la similitud coseno
                # cruda como "porcentaje de relevancia". Se midio empiricamente que, por
                # anisotropia del espacio de embeddings (propiedad conocida de modelos de
                # oraciones tipo e5/BERT), CUALQUIER par de textos no relacionados ya tiene
                # similitud coseno alta (~0.75-0.86) solo por la geometria del modelo, no por
                # relacion semantica real - mostrar eso como "84%" sugeriria una nocion de
                # relevancia absoluta que el numero no tiene; solo el ORDEN relativo entre
                # resultados es significativo. Patron dominante en productos reales de
                # busqueda semantica/RAG: mostrar orden + evidencia de texto, no un puntaje.
                resultados = pd.DataFrame({"IDPERSONA": ids[top_idx]})
                resultados.insert(0, "#", range(1, len(resultados) + 1))
                resultados = resultados.merge(
                    personas[["IDPERSONA", "CLUSTER", "PERFIL_NOMBRE", "TIPOEMPLEADO_ACTUAL_DESC", "CARGO_ACTUAL"]],
                    on="IDPERSONA", how="left",
                )
                documentos = get_documento_semantico().set_index("IDPERSONA")["DOCUMENTO_TEXTO"]
                resultados["Por qué coincide"] = resultados["IDPERSONA"].map(
                    lambda idp: _mejor_evidencia(consulta, documentos.get(idp, ""))
                )
            st.caption(
                "Ordenado del más al menos afín a tu consulta (no se muestra un puntaje de similitud: "
                "no es un porcentaje de relevancia interpretable de forma absoluta, ver metodología). "
                "👇 Selecciona una fila para ver el perfil profesional completo."
            )
            seleccion_resultado = st.dataframe(
                resultados, use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row", key="resultados_semantica",
                column_config={"#": st.column_config.NumberColumn("#", width="small")},
            )

            filas_sel = seleccion_resultado.selection.rows
            if filas_sel:
                fila_resultado = resultados.iloc[filas_sel[0]]
                id_sel_busqueda = int(fila_resultado["IDPERSONA"])
                st.markdown("---")
                persona_sel = personas[personas["IDPERSONA"] == id_sel_busqueda]
                if len(persona_sel):
                    render_persona_ficha(
                        persona_sel.iloc[0], resumen, labels,
                        coincidencia_semantica={
                            "consulta": consulta,
                            "rango": int(fila_resultado["#"]),
                        },
                    )

if __name__ == "__main__":
    main()
