"""Figuras del Capítulo 3 (Resultados y análisis) generadas desde la versión vigente de perfiles.

Lee `data/perfiles/clustering/actual.json` y, de esa versión, `<ámbito>/dimensiones.parquet`,
`<ámbito>/perfil_conjunto_mapa.parquet` y `<ámbito>/patrones_globales.parquet`. Solo produce
agregados y coordenadas sin identificar: ninguna figura muestra nombres ni identificadores.

Uso (desde la raíz del repositorio):
    .venv/Scripts/python documentacionLaTeX/figuras/scripts/generar_figuras_cap03.py

Salidas en `documentacionLaTeX/figuras/`:
    cap03_cobertura_dimensiones.pdf   % de personas con al menos un registro por dimensión
    cap03_nivel_dimensiones.pdf       estado de registros y nivel por dimensión y ámbito
    cap03_mapa_docentes.pdf           mapa t-SNE del perfil completo docente, un panel por perfil amplio
    cap03_vigentes_dimensiones.pdf    % del personal vigente con al menos un registro por dimensión
    cap03_mapa_patrones_<dimensión>.pdf  mapa t-SNE de los patrones de la dimensión
    datos/cap03_tesis_dirigidas_patrones.csv  tamaño y valores típicos de cada patrón de Tesis dirigidas

Los mapas de patrones usan las mismas coordenadas t-SNE y colores que la vista por dimensión del
dashboard (mapa `patrones`, paleta `PALETA_PATRONES`), con todas las personas con registros.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

RAIZ = Path(__file__).resolve().parents[3]
SALIDA = Path(__file__).resolve().parents[1]
FUENTES = RAIZ / "documentacionLaTeX" / "fuentes"
CLUSTERING = RAIZ / "data" / "perfiles" / "clustering"

# Mismo mínimo que el dashboard (main.MIN_REFERENCIA_NIVEL): sin nivel con < 40 personas con registros.
MIN_REFERENCIA_NIVEL = 40

# Paleta de referencia validada (validate_palette.js): categórica azul/naranja y rampa ordinal azul.
AZUL, NARANJA = "#2a78d6", "#eb6834"
RAMPA_NIVEL = ["#86b6ef", "#3987e5", "#184f95"]
GRIS_SIN = "#d9d8d3"
GRIS_FONDO = "#d4d3cd"
TINTA, TINTA_2 = "#0b0b0b", "#52514e"
# Paleta de patrones del dashboard (frontend/src/lib/colores.ts): validada para dispersión con
# codificación secundaria, por eso cada grupo lleva su rótulo P1…P6 en el mapa y en su tarjeta.
PALETA_PATRONES = ["#2a78d6", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7"]
DIMENSIONES_PATRONES = ["tesis_dirigidas"]  # se amplía a medida que se redacta cada dimensión


def configurar_estilo() -> None:
    for archivo in FUENTES.glob("arial*.ttf"):
        font_manager.fontManager.addfont(str(archivo))
    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 8.5,
        "axes.edgecolor": TINTA_2,
        "axes.labelcolor": TINTA,
        "xtick.color": TINTA_2,
        "ytick.color": TINTA,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "hatch.color": TINTA_2,
        "hatch.linewidth": 0.5,
        "pdf.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
    })


def version_vigente() -> Path:
    actual = json.loads((CLUSTERING / "actual.json").read_text(encoding="utf-8"))
    return CLUSTERING / actual["version"]


def nombres_dimensiones(version: Path) -> dict[str, str]:
    dims = json.loads((version / "dimensiones.json").read_text(encoding="utf-8"))
    return {k: v["nombre"] for k, v in dims.items()}


def cobertura(version: Path, ambito: str) -> pd.Series:
    """% de personas del ámbito con al menos una evidencia en cada dimensión."""
    d = pd.read_parquet(version / ambito / "dimensiones.parquet")
    return d.assign(con=d["n_evidencias"] > 0).groupby("dimension")["con"].mean() * 100


def estado_y_nivel(version: Path, ambito: str) -> pd.DataFrame:
    """Por dimensión, % del ámbito: sin registros, con registros sin nivel y tercios del nivel.

    El nivel es el del dashboard (DEC-060): percentil del índice solo entre quienes tienen
    registros, con rango medio en los empates."""
    d = pd.read_parquet(version / ambito / "dimensiones.parquet")
    n_ambito = d["persona_id"].nunique()
    filas = {}
    for dim, g in d.groupby("dimension"):
        con = g[g["indice"] > 0]
        fila = {"Sin registros": 100 * (g["n_evidencias"] == 0).sum() / n_ambito}
        con_sin_indice = ((g["n_evidencias"] > 0) & (g["indice"] <= 0)).sum()
        if len(con) >= MIN_REFERENCIA_NIVEL:
            nivel = 100 * (con["indice"].rank(method="average") - 0.5) / len(con)
            tercios = pd.cut(nivel, [0, 100 / 3, 200 / 3, 100], include_lowest=True)
            for etiqueta, n in zip(["Nivel 0–33", "Nivel 34–66", "Nivel 67–100"], tercios.value_counts(sort=False)):
                fila[etiqueta] = 100 * n / n_ambito
            fila["Con registros, sin nivel"] = 100 * con_sin_indice / n_ambito
        else:
            fila.update({"Nivel 0–33": 0.0, "Nivel 34–66": 0.0, "Nivel 67–100": 0.0})
            fila["Con registros, sin nivel"] = 100 * (g["n_evidencias"] > 0).sum() / n_ambito
        filas[dim] = fila
    return pd.DataFrame(filas).T


def figura_cobertura(version: Path, nombres: dict[str, str], orden: list[str]) -> None:
    doc = cobertura(version, "docentes").reindex(orden)
    adm = cobertura(version, "administrativos").reindex(orden)
    y = np.arange(len(orden))
    alto = 0.38
    fig, ax = plt.subplots(figsize=(6.2, 4.4))
    for desplazamiento, serie, color, etiqueta in [(-alto / 2, doc, AZUL, "Docentes"), (alto / 2, adm, NARANJA, "Administrativos")]:
        ax.barh(y + desplazamiento, serie.values, height=alto - 0.04, color=color, label=etiqueta)
        for yi, v in zip(y + desplazamiento, serie.values):
            ax.text(v + 1, yi, f"{v:.1f}".replace(".", ","), va="center", fontsize=7, color=TINTA_2)
    ax.set_yticks(y, [nombres[d] for d in orden])
    ax.invert_yaxis()
    ax.set_xlim(0, 110)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel("Personas del ámbito con al menos un registro (%)")
    ax.xaxis.grid(True, color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", frameon=False)
    fig.savefig(SALIDA / "cap03_cobertura_dimensiones.pdf")
    plt.close(fig)


def figura_nivel(version: Path, nombres: dict[str, str], orden: list[str]) -> None:
    orden = [d for d in orden if d != "idiomas"]  # Idiomas no tiene nivel (DEC-060)
    columnas = ["Sin registros", "Con registros, sin nivel", "Nivel 0–33", "Nivel 34–66", "Nivel 67–100"]
    colores = [GRIS_SIN, "white", *RAMPA_NIVEL]
    fig, ejes = plt.subplots(1, 2, figsize=(6.3, 3.9), sharey=True)
    for ax, ambito, titulo in zip(ejes, ["docentes", "administrativos"], ["Docentes", "Administrativos"]):
        tabla = estado_y_nivel(version, ambito).reindex(orden)[columnas]
        y = np.arange(len(orden))
        izquierda = np.zeros(len(orden))
        for col, color in zip(columnas, colores):
            ax.barh(y, tabla[col].values, left=izquierda, height=0.7, color=color, label=col,
                    edgecolor="white" if color != "white" else TINTA_2, linewidth=0.8 if color != "white" else 0.5,
                    hatch="////" if color == "white" else None)
            izquierda += tabla[col].values
        for yi, v in zip(y, tabla["Sin registros"].values):
            if v >= 9:
                ax.text(v / 2, yi, f"{v:.0f}".replace(".", ","), va="center", ha="center", fontsize=6.5, color=TINTA)
        ax.set_title(titulo, fontsize=9, color=TINTA, loc="left")
        ax.set_xlim(0, 100)
        ax.set_xticks(range(0, 101, 25))
        ax.set_xlabel("% de personas del ámbito")
        ax.tick_params(axis="y", length=0)
    ejes[0].set_yticks(np.arange(len(orden)), [nombres[d] for d in orden])
    ejes[0].invert_yaxis()
    manejadores, etiquetas = ejes[0].get_legend_handles_labels()
    fig.legend(manejadores, etiquetas, loc="lower center", ncol=5, frameon=False, fontsize=7,
               bbox_to_anchor=(0.55, 0.0), handlelength=1.2, columnspacing=1.0)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(SALIDA / "cap03_nivel_dimensiones.pdf")
    plt.close(fig)


# Nombres interpretativos de los perfiles amplios del personal docente (no los asigna el sistema, que
# usa códigos): se derivan de sus dimensiones destacadas y temas distintivos en patrones_globales.json.
NOMBRES_PERFILES_DOCENTES = {
    0: "Docencia y vinculación",
    1: "Tercer nivel y menor actividad docente",
    2: "Investigación y difusión",
    3: "Poca actividad académica registrada",
    4: "Docencia con varios cargos en ESPOL",
    5: "Economía y ciencias sociales",
}


def figura_mapa(version: Path, ambito: str, nombres: dict[int, str] | None = None) -> None:
    """Un panel por perfil amplio ("foto" del perfil): sus integrantes en su color del dashboard
    sobre el resto del ámbito en gris, con el nombre del perfil como título. Con 5–7 perfiles un
    solo diagrama de dispersión necesitaría más tonos de los que se distinguen entre sí, por eso se
    usan paneles pequeños (t-SNE solo sirve para visualizar)."""
    mapa = pd.read_parquet(version / ambito / "perfil_conjunto_mapa.parquet")
    grupos = pd.read_parquet(version / ambito / "patrones_globales.parquet")[["persona_id", "patron_global"]]
    d = mapa.merge(grupos, on="persona_id", how="inner")
    perfiles = sorted(d["patron_global"].unique())
    columnas = 3
    filas = int(np.ceil(len(perfiles) / columnas))
    fig, ejes = plt.subplots(filas, columnas, figsize=(6.3, 2.15 * filas))
    ejes = np.atleast_1d(ejes).ravel()
    for ax, p in zip(ejes, perfiles):
        color = PALETA_PATRONES[p % len(PALETA_PATRONES)]
        resto = d[d["patron_global"] != p]
        grupo = d[d["patron_global"] == p]
        ax.scatter(resto["x"], resto["y"], s=2, color=GRIS_FONDO, linewidths=0, rasterized=True)
        ax.scatter(grupo["x"], grupo["y"], s=3.5, color=color, linewidths=0, rasterized=True)
        titulo = f"P{p + 1} · " + textwrap.fill(nombres[p], 30, subsequent_indent="       ") if nombres else f"Perfil amplio {p + 1}"
        ax.set_title(titulo, fontsize=7.5, color=TINTA, loc="left", fontweight="bold")
        ax.text(0.0, -0.04, f"{len(grupo):,} personas ({100 * len(grupo) / len(d):.0f} %)".replace(",", " "),
                transform=ax.transAxes, fontsize=7, color=TINTA_2, va="top")
        ax.set_xticks([])
        ax.set_yticks([])
        for lado in ax.spines.values():
            lado.set_visible(False)
    for ax in ejes[len(perfiles):]:
        ax.set_visible(False)
    fig.tight_layout(h_pad=1.8)
    fig.savefig(SALIDA / f"cap03_mapa_{ambito}.pdf", dpi=300)
    plt.close(fig)


def figura_vigentes(version: Path, nombres: dict[str, str]) -> None:
    """% del personal vigente (ámbito todos) con al menos un registro en cada dimensión."""
    d = pd.read_parquet(version / "todos" / "dimensiones.parquet")
    vigente = pd.read_parquet(version / "todos" / "personas.parquet")[["persona_id", "vigente"]]
    d = d.merge(vigente, on="persona_id")
    d = d[d["vigente"]]
    n_vigentes = d["persona_id"].nunique()
    con = d.assign(con=d["n_evidencias"] > 0).groupby("dimension")["con"].sum().sort_values(ascending=False)
    pct = 100 * con / n_vigentes
    y = np.arange(len(con))
    fig, ax = plt.subplots(figsize=(6.2, 3.9))
    ax.barh(y, pct.values, height=0.62, color=AZUL)
    for yi, p, n in zip(y, pct.values, con.values):
        etiqueta = f"{p:.1f}".replace(".", ",") + f" % ({n:,})".replace(",", " ")
        ax.text(p + 1, yi, etiqueta, va="center", fontsize=7, color=TINTA_2)
    ax.set_yticks(y, [nombres[k] for k in con.index])
    ax.invert_yaxis()
    ax.set_xlim(0, 118)
    ax.set_xticks(range(0, 101, 20))
    ax.set_xlabel(f"Personal vigente con al menos un registro (%; total = {n_vigentes:,} personas)".replace(",", " "))
    ax.xaxis.grid(True, color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    fig.savefig(SALIDA / "cap03_vigentes_dimensiones.pdf")
    plt.close(fig)


def _valores_dimension(version: Path, dimension: str, ambito: str) -> pd.DataFrame:
    """Por persona con patrón en la dimensión: patrón, vigencia y valores sin transformar de los
    componentes (desde sus evidencias, con la misma función que usa perfiles.construir)."""
    from perfiles.dimensiones import DIMENSIONES, componentes_crudos

    asignacion = pd.read_parquet(version / ambito / "patrones_dimension.parquet")
    asignacion = asignacion[asignacion["dimension"] == dimension][["persona_id", "patron"]]
    vigente = pd.read_parquet(version / ambito / "personas.parquet")[["persona_id", "vigente"]]
    tipos = set(DIMENSIONES[dimension]["tipos"])
    evidencias = pd.concat(
        e[e["tipo_id"].isin(tipos)]
        for e in (pd.read_csv(a, encoding="utf-8-sig", usecols=["persona_id", "tipo_id", "atributos"])
                  for a in (RAIZ / "data" / "evidencias").glob("*/evidencias_*.csv")))
    comp, _ = componentes_crudos(evidencias, asignacion["persona_id"].tolist())
    columnas = [f"{dimension}__{c}" for c in DIMENSIONES[dimension]["componentes"]]
    valores = np.expm1(comp[columnas]).round()
    valores.columns = [c.split("__", 1)[1] for c in columnas]
    return asignacion.merge(vigente, on="persona_id").merge(valores, left_on="persona_id", right_index=True)


def _tesis_por_persona(version: Path, ambito: str = "todos") -> pd.DataFrame:
    d = _valores_dimension(version, "tesis_dirigidas", ambito)
    d["estudiantes_por_tesis"] = d["estudiantes"] / d["tesis"]
    d["prop_investigacion"] = 100 * d["tesis_investigacion_doctorado"] / d["tesis"]
    return d


def estadisticas_tesis(version: Path, ambito: str = "todos") -> pd.DataFrame:
    """Cifras de la sección de Tesis dirigidas (tamaño, vigentes, promedio y desviación estándar
    de cada variable, participación en el total y valores de la persona representativa de cada
    patrón). Se guardan en figuras/datos/ para que cada cifra del texto sea trazable."""
    d = _tesis_por_persona(version, ambito)
    info = json.loads((version / ambito / "micro_dimensiones.json").read_text(encoding="utf-8"))["tesis_dirigidas"]
    representante = {p["id"]: p["representante_id"] for p in info["patrones"]["patrones"]}
    variables = ["tesis", "estudiantes", "estudiantes_por_tesis", "tesis_investigacion_doctorado", "prop_investigacion"]
    filas = {}
    for clave, g in [*((f"P{p + 1}", g) for p, g in d.groupby("patron")), ("Total", d)]:
        fila = {"personas": len(g), "pct_personas": 100 * len(g) / len(d), "vigentes": int(g["vigente"].sum()),
                "pct_vigentes_del_patron": 100 * g["vigente"].mean(),
                "pct_con_tesis_investigacion": 100 * (g["tesis_investigacion_doctorado"] > 0).mean()}
        for v in variables:
            fila[f"media_{v}"] = g[v].mean()
            fila[f"de_{v}"] = g[v].std()
        for v in ["tesis", "estudiantes", "tesis_investigacion_doctorado"]:
            fila[f"pct_del_total_{v}"] = 100 * g[v].sum() / d[v].sum()
        if clave != "Total":
            r = d[d["persona_id"] == representante[int(clave[1:]) - 1]].iloc[0]
            for v in ["tesis", "estudiantes", "tesis_investigacion_doctorado"]:
                fila[f"representante_{v}"] = r[v]
        filas[clave] = fila
    tabla = pd.DataFrame(filas).T.round(2)
    (SALIDA / "datos").mkdir(exist_ok=True)
    tabla.to_csv(SALIDA / "datos" / "cap03_tesis_dirigidas_patrones.csv", encoding="utf-8")
    return tabla


def desapilar(puntos: pd.DataFrame) -> pd.DataFrame:
    """Reparte en espiral, solo para dibujar, a las personas con valores idénticos que caen en la
    misma coordenada t-SNE (mismo criterio que MapaDimension.desapilar del dashboard, DEC-060)."""
    xs, ys = puntos["x"].to_numpy(), puntos["y"].to_numpy()
    paso = 0.005 * max(np.ptp(xs), np.ptp(ys), 1e-6)
    angulo_aureo = np.pi * (3 - np.sqrt(5))
    puntos = puntos.sort_values("persona_id").copy()
    k = puntos.groupby([puntos["x"].round(2), puntos["y"].round(2)]).cumcount().to_numpy()
    r = paso * np.sqrt(k)
    puntos["x"] = puntos["x"] + r * np.cos(k * angulo_aureo)
    puntos["y"] = puntos["y"] + r * np.sin(k * angulo_aureo)
    return puntos


def _estilo_panel(ax) -> None:
    ax.grid(True, color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#9a998f")
    ax.tick_params(colors=TINTA_2, labelsize=7)


def figura_mapa_patrones(version: Path, dimension: str, ambito: str = "todos") -> None:
    """Mapa t-SNE de los patrones de una dimensión con todas las personas con registros (las mismas
    coordenadas y colores que la vista por dimensión del dashboard). Cada patrón lleva su rótulo
    P1…Pk en el mapa y en la leyenda (codificación secundaria al color)."""
    info = json.loads((version / ambito / "micro_dimensiones.json").read_text(encoding="utf-8"))[dimension]
    patrones = info["patrones"]["patrones"]
    mapa = pd.read_parquet(version / ambito / "mapas_dimension.parquet")
    mapa = mapa[(mapa["dimension"] == dimension) & (mapa["mapa"] == "patrones")]
    asignacion = pd.read_parquet(version / ambito / "patrones_dimension.parquet")
    puntos = desapilar(mapa.merge(asignacion[asignacion["dimension"] == dimension][["persona_id", "patron"]], on="persona_id"))

    fig, ax = plt.subplots(figsize=(5.6, 3.5))
    for p in patrones:
        color = PALETA_PATRONES[p["id"] % len(PALETA_PATRONES)]
        g = puntos[puntos["patron"] == p["id"]]
        ax.scatter(g["x"], g["y"], s=10, color=color, edgecolors="white", linewidths=0.3, rasterized=True,
                   label=f"Patrón {p['id'] + 1}")
        ax.text(g["x"].median(), g["y"].median(), f"P{p['id'] + 1}", fontsize=8, fontweight="bold", color=TINTA,
                ha="center", va="center",
                bbox={"boxstyle": "square,pad=0.2", "facecolor": "white", "edgecolor": color, "linewidth": 1.2})
    _estilo_panel(ax)
    ax.grid(False)
    ax.set_xlabel("t-SNE 1", fontsize=7.5, color=TINTA_2)
    ax.set_ylabel("t-SNE 2", fontsize=7.5, color=TINTA_2)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False, fontsize=7.5, markerscale=1.8,
              handletextpad=0.3, labelspacing=0.8)
    fig.savefig(SALIDA / f"cap03_mapa_patrones_{dimension}.pdf", dpi=300)
    plt.close(fig)


def main() -> None:
    configurar_estilo()
    version = version_vigente()
    nombres = nombres_dimensiones(version)
    orden = cobertura(version, "todos").sort_values(ascending=False).index.tolist()
    figura_cobertura(version, nombres, orden)
    figura_nivel(version, nombres, orden)
    figura_mapa(version, "docentes", NOMBRES_PERFILES_DOCENTES)
    figura_vigentes(version, nombres)
    for dimension in DIMENSIONES_PATRONES:
        figura_mapa_patrones(version, dimension)
    print(estadisticas_tesis(version).T.to_string())
    print(f"Figuras generadas con la versión {version.name} en {SALIDA}")


if __name__ == "__main__":
    main()
