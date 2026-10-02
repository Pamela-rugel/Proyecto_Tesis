"""Genera el diagrama del proceso multivista (perfiles/img/proceso_multivista.png).

Uso (raiz del proyecto):  python -m perfiles.diagrama_proceso
Los numeros del diagrama son los de la version documentada en perfiles/METODOLOGIA.md.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

SALIDA = Path(__file__).resolve().parent / "img" / "proceso_multivista.png"

AZUL, VERDE, NARANJA, MORADO, GRIS, ROJO = "#1f77b4", "#2ca02c", "#e8590c", "#6741d9", "#64748b", "#c92a2a"


def caja(ax, x, y, w, h, titulo, texto, color, fondo=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.018",
                                linewidth=1.8, edgecolor=color, facecolor=fondo or color + "14"))
    ax.text(x + w / 2, y + h - 0.022, titulo, ha="center", va="top", fontsize=11.5, fontweight="bold", color="#0f172a")
    ax.text(x + w / 2, y + h - 0.05, texto, ha="center", va="top", fontsize=9.8, color="#334155", linespacing=1.4)


def flecha(ax, x1, y1, x2, y2, color=GRIS, estilo="-|>", linea="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=estilo, mutation_scale=16, linewidth=1.6,
                                 color=color, shrinkA=2, shrinkB=2, linestyle=linea))


def etapa(ax, y, texto):
    ax.text(0.012, y, texto, ha="left", va="center", fontsize=9, color="#94a3b8", fontweight="bold", rotation=90)


def main() -> None:
    fig = plt.figure(figsize=(13, 17.5), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(0.5, 0.985, "Perfiles del personal: clustering multivista con SNF", ha="center", va="top",
            fontsize=17, fontweight="bold", color="#0B2545")
    ax.text(0.5, 0.962, "Evidencias + datos estructurados → tres vistas → redes de similitud → fusión → grupos y subgrupos",
            ha="center", va="top", fontsize=10.5, color=GRIS)

    # 1. datos
    etapa(ax, 0.885, "1 · DATOS")
    caja(ax, 0.06, 0.835, 0.56, 0.10, "Evidencias individuales",
         "126 070 evidencias · 3 164 personas · 17 tipos\n"
         "cada una: persona · tipo · TEXTO (lo que se lee) · ATRIBUTOS (fechas, niveles, roles…)", AZUL)
    caja(ax, 0.66, 0.835, 0.30, 0.10, "Estado de la persona",
         "historial laboral · NO es una vista\n"
         "tipo de empleado → separa los 3 ámbitos\n"
         "vigencia → quién se muestra (filtro)", GRIS)

    # 2. vistas
    etapa(ax, 0.70, "2 · TRES VISTAS")
    xs = [0.06, 0.37, 0.68]
    w = 0.28
    caja(ax, xs[0], 0.615, w, 0.165, "V1 · Trayectoria y gestión",
         "texto de cargos, contratos, funciones,\nexperiencia externa, actividades de carga\n"
         "↓ embedding bge-m3 (1 024 dim.)\n↓ promedio por tipo → entre tipos\n"
         "peso = 1 / log₂(1 + personas con ese texto)", VERDE)
    caja(ax, xs[1], 0.615, w, 0.165, "V2 · Académica y temática",
         "texto de títulos, proyectos, publicaciones,\ntesis, ponencias, materias, capacitaciones…\n"
         "↓ embedding bge-m3 (1 024 dim.)\n↓ promedio por tipo → entre tipos\n"
         "peso = 1 / log₂(1 + personas con ese texto)", NARANJA)
    caja(ax, xs[2], 0.615, w, 0.165, "V3 · Datos estructurados",
         "42 variables desde los ATRIBUTOS:\naños, proporción por tipo de cargo, nivel de\n"
         "formación, publicaciones Q1–Q2, horas de carga…\n↓ conteos y años en log(1+x)\n"
         "↓ estandarización z dentro de cada ámbito", MORADO)
    # las tres vistas salen de las evidencias (V3 de sus ATRIBUTOS); el estado NO es una vista
    for x in xs:
        flecha(ax, 0.34, 0.833, x + w / 2, 0.782, AZUL)

    # 3. redes por vista
    etapa(ax, 0.535, "3 · REDES")
    for x, c, t in zip(xs, (VERDE, NARANJA, MORADO), ("V1", "V2", "V3")):
        caja(ax, x, 0.48, w, 0.105, f"Red de similitud {t}",
             "distancia euclidiana entre personas\nkernel gaussiano con escala local\nK = 20 vecinos · μ = 0.5", c)
        flecha(ax, x + w / 2, 0.613, x + w / 2, 0.587, c)

    # 4. SNF
    etapa(ax, 0.405, "4 · FUSIÓN")
    caja(ax, 0.16, 0.355, 0.68, 0.10, "Similarity Network Fusion (SNF)",
         "cada red se actualiza con el promedio de las otras dos, solo a través de sus 20 vecinos:\n"
         "P_v ← S_v · (promedio de las otras P) · S_vᵀ   ·   20 iteraciones\n"
         "red fusionada W = promedio de las tres redes  (no se concatenan variables)", ROJO)
    for x in xs:
        flecha(ax, x + w / 2, 0.478, 0.5 + (x - 0.37) * 0.6, 0.457, ROJO)

    # 5. agrupamiento
    etapa(ax, 0.265, "5 · GRUPOS")
    caja(ax, 0.06, 0.205, 0.43, 0.125, "Grupos (clustering espectral sobre W)",
         "por ámbito: todos · administrativos · docentes\n"
         "k por eigengap del laplaciano normalizado, rango 4–12\n"
         "estabilidad: ARI en 10 submuestras del 90 %\n"
         "todos k=4 (ARI 0.96) · admin. k=5 (0.84) · docentes k=4 (0.99)", AZUL)
    caja(ax, 0.53, 0.205, 0.43, 0.125, "Subgrupos (segundo nivel)",
         "en cada grupo con ≥ 150 personas:\nSNF de nuevo SOLO con sus integrantes\n"
         "k por eigengap 2–8 · descritos frente al grupo padre", "#0b7285")
    flecha(ax, 0.40, 0.353, 0.275, 0.332, AZUL)
    flecha(ax, 0.49, 0.268, 0.53, 0.268, "#0b7285")

    # 6. salidas
    etapa(ax, 0.105, "6 · SALIDAS")
    salidas = [
        ("Pertenencia", "afinidad media a cada grupo,\nnormalizada · \"entre dos\ngrupos\" si 2.º ≥ 0.8 × 1.º"),
        ("Representante", "medoide en la red\n+ parecido de cada\npersona con él"),
        ("Descripción", "solo datos medidos: lift,\nrasgos (z), evidencias\ncompartidas, c-TF-IDF"),
        ("Mapa t-SNE", "1 − W/máx(W)\nperplexity 30\nsolo para visualizar"),
        ("Búsqueda", "30 vecinos por persona\ncentroides V1/V2\n(siguiente etapa)"),
    ]
    ancho = 0.15
    for i, (t, d) in enumerate(salidas):
        x = 0.07 + i * (ancho + 0.03)
        caja(ax, x, 0.045, ancho, 0.115, t, d, GRIS)
        flecha(ax, 0.5, 0.203, x + ancho / 2, 0.162)

    ax.text(0.5, 0.018, "Versionado por huella (evidencias + estado + embeddings + parámetros) · la vista React solo lee "
            "· apoyo a la decisión, no decisiones automáticas", ha="center", fontsize=8.5, color="#94a3b8")

    SALIDA.parent.mkdir(exist_ok=True)
    fig.savefig(SALIDA, dpi=150, facecolor="white")
    print(SALIDA)


if __name__ == "__main__":
    main()
