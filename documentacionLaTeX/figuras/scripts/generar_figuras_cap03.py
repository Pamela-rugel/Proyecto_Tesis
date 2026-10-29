"""Figuras del Capítulo 3 (Resultados y análisis) generadas desde la versión vigente de perfiles.

Lee `data/perfiles/clustering/actual.json` y, de esa versión, `<ámbito>/dimensiones.parquet`,
`<ámbito>/perfil_conjunto_mapa.parquet` y `<ámbito>/patrones_globales.parquet`. Solo produce
agregados y coordenadas sin identificar: ninguna figura muestra nombres ni identificadores.

Uso (desde la raíz del repositorio):
    .venv/Scripts/python documentacionLaTeX/figuras/scripts/generar_figuras_cap03.py

Salidas en `documentacionLaTeX/figuras/`:
    cap03_cobertura_dimensiones.pdf   % de personas con al menos un registro por dimensión
    cap03_nivel_dimensiones.pdf       estado de registros y nivel por dimensión y ámbito
    cap03_mapa_docentes.pdf           mapa t-SNE del perfil completo, un panel por perfil amplio
    cap03_mapa_administrativos.pdf    ídem para el personal administrativo
    cap03_vigentes_dimensiones.pdf    % del personal vigente con al menos un registro por dimensión
    cap03_patrones_<dimensión>.pdf    mapa t-SNE de patrones, tarjeta por patrón y perfil de variables

Las figuras de patrones usan los mismos datos y colores que la vista por dimensión del dashboard
(mapa `patrones`, solo vigentes, paleta `PALETA_PATRONES`). La persona representativa de cada
patrón se muestra anonimizada ("Persona A", "Persona B"...) y solo con los valores de las variables.
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
# Rótulos cortos de los componentes para la tarjeta de la persona representativa (si falta, se usa
# la descripción de perfiles.dimensiones).
ROTULO_CORTO = {
    "tesis_dirigidas": {"tesis": "tesis", "estudiantes": "estudiantes",
                        "tesis_investigacion_doctorado": "de investigación o doctorado"},
}


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


def figura_mapa(version: Path, ambito: str) -> None:
    """Un panel por perfil amplio: sus integrantes en azul sobre el resto del ámbito en gris.

    Con 5–7 perfiles un solo diagrama de dispersión necesitaría más tonos de los que se
    distinguen entre sí, por eso se usan paneles pequeños (sin coordenadas de interpretación:
    t-SNE solo sirve para visualizar)."""
    mapa = pd.read_parquet(version / ambito / "perfil_conjunto_mapa.parquet")
    grupos = pd.read_parquet(version / ambito / "patrones_globales.parquet")[["persona_id", "patron_global"]]
    d = mapa.merge(grupos, on="persona_id", how="inner")
    perfiles = sorted(d["patron_global"].unique())
    columnas = 3
    filas = int(np.ceil(len(perfiles) / columnas))
    fig, ejes = plt.subplots(filas, columnas, figsize=(6.3, 2.05 * filas))
    ejes = np.atleast_1d(ejes).ravel()
    for ax, p in zip(ejes, perfiles):
        resto = d[d["patron_global"] != p]
        grupo = d[d["patron_global"] == p]
        ax.scatter(resto["x"], resto["y"], s=2, color=GRIS_FONDO, linewidths=0, rasterized=True)
        ax.scatter(grupo["x"], grupo["y"], s=3, color=AZUL, linewidths=0, rasterized=True)
        ax.set_title(f"Perfil amplio {p + 1} · {len(grupo):,} personas ({100 * len(grupo) / len(d):.0f} %)".replace(",", " "),
                     fontsize=7.5, color=TINTA, loc="left")
        ax.set_xticks([])
        ax.set_yticks([])
        for lado in ax.spines.values():
            lado.set_visible(False)
    for ax in ejes[len(perfiles):]:
        ax.set_visible(False)
    fig.tight_layout()
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


def _valores_representante(dimension: str, persona_id: int) -> dict[str, float]:
    """Valores sin transformar de los componentes de la dimensión para una persona (desde sus evidencias)."""
    from perfiles.dimensiones import DIMENSIONES, componentes_crudos

    tipos = set(DIMENSIONES[dimension]["tipos"])
    filas = []
    for archivo in (RAIZ / "data" / "evidencias").glob("*/evidencias_*.csv"):
        e = pd.read_csv(archivo, encoding="utf-8-sig", usecols=["persona_id", "tipo_id", "atributos"])
        filas.append(e[(e["persona_id"] == persona_id) & e["tipo_id"].isin(tipos)])
    comp, _ = componentes_crudos(pd.concat(filas), [persona_id])
    sin_log = {"formacion__nivel_maximo", "formacion__titulo_exterior", "formacion__posgrado_en_curso",
               "idiomas__idiomas_extranjeros", "idiomas__nivel_maximo"}
    salida = {}
    for c in DIMENSIONES[dimension]["componentes"]:
        v = comp.loc[persona_id, f"{dimension}__{c}"]
        salida[c] = float(v if f"{dimension}__{c}" in sin_log else np.expm1(v))
    return salida


def _formato(v: float) -> str:
    return f"{v:.0f}" if abs(v - round(v)) < 0.05 else f"{v:.1f}".replace(".", ",")


def figura_patrones_dimension(version: Path, dimension: str, ambito: str = "todos") -> None:
    """Mapa t-SNE de patrones (solo vigentes, como el dashboard), una tarjeta por patrón (tamaño,
    vigentes, nombre y persona representativa anonimizada) y el perfil de las variables consideradas
    (posición de cada patrón frente al promedio de la dimensión, en desviaciones estándar)."""
    from perfiles.dimensiones import DIMENSIONES

    info = json.loads((version / ambito / "micro_dimensiones.json").read_text(encoding="utf-8"))[dimension]
    patrones = info["patrones"]["patrones"]
    total = sum(p["tamano"] for p in patrones)
    colores = {p["id"]: PALETA_PATRONES[p["id"] % len(PALETA_PATRONES)] for p in patrones}

    mapa = pd.read_parquet(version / ambito / "mapas_dimension.parquet")
    mapa = mapa[(mapa["dimension"] == dimension) & (mapa["mapa"] == "patrones")]
    asignacion = pd.read_parquet(version / ambito / "patrones_dimension.parquet")
    asignacion = asignacion[asignacion["dimension"] == dimension][["persona_id", "patron"]]
    vigente = pd.read_parquet(version / ambito / "personas.parquet")[["persona_id", "vigente"]]
    puntos = mapa.merge(asignacion, on="persona_id").merge(vigente, on="persona_id")
    puntos = puntos[puntos["vigente"]]

    fig = plt.figure(figsize=(6.3, 6.6))
    rejilla = fig.add_gridspec(2, 2, height_ratios=[1.1, 1], width_ratios=[1, 1.1], hspace=0.22, wspace=0.12)

    # (a) mapa
    ax = fig.add_subplot(rejilla[0, 0])
    for p in patrones:
        g = puntos[puntos["patron"] == p["id"]]
        ax.scatter(g["x"], g["y"], s=9, color=colores[p["id"]], edgecolors="white", linewidths=0.3, rasterized=True)
        if len(g):
            cx, cy = g["x"].median(), g["y"].median()
            ax.text(cx, cy, f"P{p['id'] + 1}", fontsize=8, fontweight="bold", color=TINTA, ha="center", va="center",
                    bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "edgecolor": colores[p["id"]], "linewidth": 1.2})
    ax.set_xticks([])
    ax.set_yticks([])
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_title(f"(a) Mapa t-SNE · {len(puntos)} personas vigentes", fontsize=8, loc="left", color=TINTA)

    # (b) tarjetas
    ax = fig.add_subplot(rejilla[0, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title(f"(b) {len(patrones)} patrones · {total} personas con registros", fontsize=8, loc="left", color=TINTA)
    alto = 1 / len(patrones)
    componentes = DIMENSIONES[dimension]["componentes"]
    rotulo = {c: ROTULO_CORTO.get(dimension, {}).get(c, componentes[c][1].split(" (")[0].lower()) for c in componentes}
    for i, p in enumerate(patrones):
        top = 1 - i * alto
        color = colores[p["id"]]
        ax.add_patch(plt.Rectangle((0, top - alto + 0.015), 0.012, alto - 0.03, color=color, transform=ax.transAxes, clip_on=False))
        nombre = textwrap.fill(p["nombre"], 46)
        ax.text(0.04, top - 0.012, f"P{p['id'] + 1}", fontsize=8, fontweight="bold", color=TINTA, va="top")
        ax.text(0.13, top - 0.012, nombre, fontsize=7, color=TINTA, va="top")
        lineas_nombre = nombre.count("\n") + 1
        y_barra = top - 0.012 - 0.042 * lineas_nombre - 0.02
        fraccion = p["tamano"] / total
        ax.add_patch(plt.Rectangle((0.04, y_barra - 0.012), 0.42, 0.024, color="#ecebe6", transform=ax.transAxes))
        ax.add_patch(plt.Rectangle((0.04, y_barra - 0.012), 0.42 * fraccion, 0.024, color=color, transform=ax.transAxes))
        ax.text(0.49, y_barra, f"{p['tamano']} personas ({100 * fraccion:.0f} %) · {p['tamano_vigentes']} vigentes",
                fontsize=6.5, color=TINTA_2, va="center")
        valores = _valores_representante(dimension, p["representante_id"])
        partes = [f"{_formato(valores[c])} {rotulo[c]}" for c in componentes]
        rep = textwrap.fill(f"Persona representativa {chr(65 + i)}: {' · '.join(partes)}", 64)
        ax.text(0.04, y_barra - 0.03, rep, fontsize=6.3, color=TINTA_2, va="top", style="italic")

    # (c) perfil de las variables consideradas
    ax = fig.add_subplot(rejilla[1, :])
    variables = [c["componente"] for c in patrones[0]["componentes"]]
    descripcion = {c["componente"]: c["descripcion"].split(" (")[0] for c in patrones[0]["componentes"]}
    y = np.arange(len(variables))
    desplazamiento = np.linspace(-0.24, 0.24, len(patrones))
    for d_, p in zip(desplazamiento, patrones):
        z = {c["componente"]: c["z"] for c in p["componentes"]}
        valores = [z[v] for v in variables]
        ax.hlines(y + d_, 0, valores, color=colores[p["id"]], linewidth=1.6)
        ax.scatter(valores, y + d_, s=26, color=colores[p["id"]], edgecolors="white", linewidths=0.6, zorder=3,
                   label=f"P{p['id'] + 1}")
    ax.axvline(0, color=TINTA_2, linewidth=0.8)
    ax.set_yticks(y, [textwrap.fill(descripcion[v], 30) for v in variables], fontsize=7.5)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)
    limite = max(abs(c["z"]) for p in patrones for c in p["componentes"]) + 0.3
    ax.set_xlim(-limite, limite)
    ax.set_xlabel("← por debajo del promedio de la dimensión · por encima →  (desviaciones estándar)", fontsize=7.5)
    ax.xaxis.grid(True, color="#e6e5e0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=len(patrones), frameon=False, fontsize=7,
              handletextpad=0.2, columnspacing=0.8, borderaxespad=0.1)
    ax.set_title("(c) Variables consideradas y posición de cada patrón", fontsize=8, loc="left", color=TINTA)

    fig.savefig(SALIDA / f"cap03_patrones_{dimension}.pdf", dpi=300)
    plt.close(fig)


def main() -> None:
    configurar_estilo()
    version = version_vigente()
    nombres = nombres_dimensiones(version)
    orden = cobertura(version, "todos").sort_values(ascending=False).index.tolist()
    figura_cobertura(version, nombres, orden)
    figura_nivel(version, nombres, orden)
    for ambito in ["docentes", "administrativos"]:
        figura_mapa(version, ambito)
    figura_vigentes(version, nombres)
    for dimension in DIMENSIONES_PATRONES:
        figura_patrones_dimension(version, dimension)
    print(f"Figuras generadas con la versión {version.name} en {SALIDA}")


if __name__ == "__main__":
    main()
