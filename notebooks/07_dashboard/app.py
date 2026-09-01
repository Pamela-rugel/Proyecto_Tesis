"""
Dashboard de perfiles del personal docente y administrativo de ESPOL.

Ejecutar con:
    d:\\Proyecto_Tesis\\.venv\\Scripts\\streamlit run notebooks\\07_dashboard\\app.py

Consume los datasets generados por `07_dashboard.ipynb` (`data/dashboard/`) y, para la búsqueda
semántica opcional, los embeddings de `06_embeddings` (`data/embeddings/`). No incluye nombres
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


@st.cache_resource
def get_embeddings():
    return lib.load_embeddings()


@st.cache_data
def get_corpus() -> pd.DataFrame:
    return lib.load_corpus_texto()


@st.cache_resource
def get_text_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")


def cluster_color(cluster: int) -> str:
    return CLUSTER_COLORS[int(cluster) % len(CLUSTER_COLORS)]

def render_persona_ficha(persona: pd.Series, resumen: pd.DataFrame, labels: dict):
    cluster = int(persona["CLUSTER"])
    perfil = persona["PERFIL_NOMBRE"]
    st.markdown(f"### Persona `{int(persona['IDPERSONA'])}`")
    st.markdown(
        f"**Perfil asignado:** :orange[{perfil}]  (cluster {cluster})"
    )

    cols = st.columns(4)
    campos = [
        ("Tipo de empleado", persona.get("TIPOEMPLEADO_ACTUAL_DESC")),
        ("Cargo actual", persona.get("CARGO_ACTUAL")),
        ("Unidad actual", persona.get("UNIDAD_ACTUAL_NOMBRE")),
        ("Vigente actualmente", "Sí" if persona.get("VIGENTE_ACTUALMENTE") else "No"),
    ]
    for col, (label, value) in zip(cols, campos):
        val_str = "-" if pd.isna(value) else str(value)
        col.markdown(
            f"<p style='color: #6c757d; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.2rem;'>{label}</p>"
            f"<p style='font-size: 1.15rem; font-weight: 700; line-height: 1.25;'>{val_str}</p>",
            unsafe_allow_html=True
        )

    cols2 = st.columns(4)
    metricas_num = [
        ("Antigüedad efectiva (años)", persona.get("ANTIGUEDAD_EFECTIVA_ANIOS")),
        ("Nivel académico máximo", persona.get("NIVEL_ACADEMICO_MAXIMO")),
        ("Horas de docencia (total)", persona.get("TOTAL_HORAS_DOCENCIA")),
        ("Publicaciones", persona.get("NUM_PUBLICACIONES")),
    ]
    for col, (label, value) in zip(cols2, metricas_num):
        val_str = "-" if pd.isna(value) else str(value)
        col.markdown(
            f"<p style='color: #6c757d; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.2rem;'>{label}</p>"
            f"<p style='font-size: 1.15rem; font-weight: 700; line-height: 1.25;'>{val_str}</p>",
            unsafe_allow_html=True
        )

    st.markdown("**Comparación con la institución** (percentil de la persona sobre el total de la población)")
    disponibles = [f for f in lib.RADAR_FEATURES if f in persona.index]
    personas_all = get_personas()
    radar_vals = []
    for f in disponibles:
        serie = personas_all[f]
        val = persona[f]
        pct = float((serie < val).mean()) if pd.notna(val) else 0.0
        radar_vals.append(pct)
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=radar_vals + radar_vals[:1], theta=disponibles + disponibles[:1], fill="toself", name="Esta persona"))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 1])), showlegend=False, height=400,
                       margin=dict(l=40, r=40, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Percentil respecto a las 2213 personas de la población (0 = valor mas bajo, 1 = valor mas alto). "
    )

    n_textos = persona.get("N_REGISTROS_TEXTO")
    if pd.notna(n_textos) and n_textos and n_textos > 0:
        st.markdown(f"**Cobertura de texto para búsqueda semántica:** {int(n_textos)} registros de "
                    f"{int(persona.get('N_FUENTES_DISTINTAS', 0))} fuentes distintas.")
        corpus = get_corpus()
        muestra = corpus[corpus["IDPERSONA"] == persona["IDPERSONA"]].head(8)
        if not muestra.empty:
            with st.expander("Ver texto fuente (publicaciones, proyectos, capacitaciones, ...)"):
                st.dataframe(muestra[["FUENTE", "TEXTO"]], use_container_width=True, hide_index=True)
    else:
        st.caption("Esta persona no tiene texto disponible para búsqueda semántica.")


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
        "equipos, planificación académica y administrativa. Basado en K-Means (K=5) sobre 100 "
        "variables de trayectoria institucional."
    )

    tab_resumen, tab_perfiles, tab_persona, tab_equipos, tab_semantica = st.tabs([
        "Resumen general",
        "Explorar perfiles",
        "Buscar persona",
        "Formar equipos / comisiones",
        "Búsqueda semántica",
    ])

    # --- Resumen general -----------------------------------------------
    with tab_resumen:
        c1, c2, c3 = st.columns(3)
        c1.metric("Personas en el modelo", f"{len(personas):,}")
        c2.metric("Perfiles (clusters)", resumen["CLUSTER"].nunique())
        c3.metric("Con texto para búsqueda semántica", f"{(personas['N_REGISTROS_TEXTO'] > 0).sum():,}")

        fig = px.bar(
            resumen.sort_values("CLUSTER"),
            x="PERFIL_NOMBRE", y="N_PERSONAS", color="PERFIL_NOMBRE",
            color_discrete_sequence=CLUSTER_COLORS,
            text="PCT_POBLACION",
            labels={"PERFIL_NOMBRE": "Perfil", "N_PERSONAS": "N personas"},
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(showlegend=False, xaxis_title=None, height=450)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Composición por tipo de empleado dentro de cada perfil**")
        tab_tipo = (
            pd.crosstab(personas["PERFIL_NOMBRE"], personas["TIPOEMPLEADO_ACTUAL_DESC"], normalize="index") * 100
        ).round(1)
        st.dataframe(tab_tipo, use_container_width=True)

    # --- Explorar perfiles -----------------------------------------------
    with tab_perfiles:
        cluster_sel = st.selectbox(
            "Selecciona un perfil",
            options=sorted(resumen["CLUSTER"]),
            format_func=lambda c: f"{c} — {lib.PERFIL_NOMBRES[c]}",
        )
        fila = resumen[resumen["CLUSTER"] == cluster_sel].iloc[0]
        st.subheader(fila["PERFIL_NOMBRE"])
        st.markdown(f"**{int(fila['N_PERSONAS'])} personas** ({fila['PCT_POBLACION']}% de la población)")
        st.write(fila["DESCRIPCION"])

        feats = top_features[top_features["CLUSTER"] == cluster_sel].copy()
        feats["FEATURE_LABEL"] = feats["FEATURE"].map(lambda f: labels.get(f, f))
        fig = go.Figure()
        fig.add_trace(go.Bar(y=feats["FEATURE_LABEL"], x=feats["VALUE_CLUSTER"], name="Este perfil", orientation="h",
                              marker_color=cluster_color(cluster_sel)))
        fig.add_trace(go.Bar(y=feats["FEATURE_LABEL"], x=feats["VALUE_GLOBAL"], name="Institución (global)", orientation="h",
                              marker_color="lightgray"))
        fig.update_layout(barmode="group", height=420, title="Variables más distintivas de este perfil",
                           yaxis=dict(autorange="reversed"), margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Comparación de mediana (o proporción) del perfil vs. la mediana institucional global, para las "
            "variables con mayor tamaño de efecto (`IMPORTANCE`, ver `cluster_characterization.csv`)."
        )

        st.markdown("**Personas de este perfil (muestra)**")
        muestra_cols = ["IDPERSONA"] + [c for c in lib.METRICAS_CLAVE if c in personas.columns]
        st.dataframe(
            personas[personas["CLUSTER"] == cluster_sel][muestra_cols].head(50),
            use_container_width=True, hide_index=True,
        )

    # --- Buscar persona ---------------------------------------------------
    with tab_persona:
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
            resultado = resultado[resultado["VIGENTE_ACTUALMENTE"] == True]  # noqa: E712
        elif vigente_sel == "Solo no vigentes":
            resultado = resultado[resultado["VIGENTE_ACTUALMENTE"] == False]  # noqa: E712
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
            "Describe libremente el conocimiento o experiencia que buscas (p. ej. *\"experiencia en "
            "aprendizaje automático aplicado a imágenes médicas\"*). Se compara contra los embeddings de "
            "texto profesional/académico (publicaciones, proyectos, ponencias, capacitaciones, etc.) de "
            "cada persona."
        )
        consulta = st.text_input("Consulta", placeholder="Ej: experiencia en gestión de proyectos de vinculación con la comunidad")
        top_n = st.slider("Número de resultados", min_value=3, max_value=25, value=10)

        if consulta:
            with st.spinner("Buscando..."):
                ids, matrix = get_embeddings()
                modelo = get_text_model()
                q = modelo.encode([consulta], normalize_embeddings=True)[0]
                sims = matrix @ q
                top_idx = np.argsort(-sims)[:top_n]
                resultados = pd.DataFrame({"IDPERSONA": ids[top_idx], "SIMILITUD": sims[top_idx]})
                resultados = resultados.merge(
                    personas[["IDPERSONA", "CLUSTER", "PERFIL_NOMBRE", "TIPOEMPLEADO_ACTUAL_DESC", "CARGO_ACTUAL"]],
                    on="IDPERSONA", how="left",
                )
            st.dataframe(resultados, use_container_width=True, hide_index=True)

            corpus = get_corpus()
            with st.expander("Ver fragmentos de texto de los primeros resultados"):
                for _, row in resultados.head(5).iterrows():
                    st.markdown(f"**IDPERSONA `{int(row['IDPERSONA'])}`** (similitud {row['SIMILITUD']:.3f})")
                    muestra = corpus[corpus["IDPERSONA"] == row["IDPERSONA"]].head(3)
                    st.dataframe(muestra[["FUENTE", "TEXTO"]], use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()
