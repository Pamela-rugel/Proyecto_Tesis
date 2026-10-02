"""Genera el diagrama del proceso de búsqueda (04_busqueda_semantica/img/proceso_busqueda.png).

Uso (raíz del proyecto):  python -m busqueda.diagrama
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from busqueda.comun import CANDIDATOS_POR_TIPO, JUEZ, MODELO_LLM, UMBRALES

SALIDA = Path(__file__).resolve().parent / "img" / "proceso_busqueda.png"
AZUL, VERDE, NARANJA, MORADO, GRIS, ROJO, TEAL = "#1f77b4", "#2ca02c", "#e8590c", "#6741d9", "#64748b", "#c92a2a", "#0b7285"


def caja(ax, x, y, w, h, titulo, texto, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015", linewidth=1.8,
                                edgecolor=color, facecolor=color + "14"))
    ax.text(x + w / 2, y + h - 0.018, titulo, ha="center", va="top", fontsize=11.5, fontweight="bold", color="#0f172a")
    ax.text(x + w / 2, y + h - 0.045, texto, ha="center", va="top", fontsize=9.4, color="#334155", linespacing=1.4)


def flecha(ax, x1, y1, x2, y2, color=GRIS):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=15, linewidth=1.6, color=color,
                                 shrinkA=2, shrinkB=2))


def etapa(ax, y, texto, color="#94a3b8"):
    ax.text(0.015, y, texto, ha="left", va="center", fontsize=9, color=color, fontweight="bold", rotation=90)


def main() -> None:
    fig = plt.figure(figsize=(13, 17), dpi=150)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.5, 0.985, "Búsqueda semántica de personas a partir de evidencias", ha="center", va="top", fontsize=17,
            fontweight="bold", color="#0B2545")
    ax.text(0.5, 0.963, "La evidencia es la unidad de búsqueda; la persona se obtiene al final, con su explicación",
            ha="center", va="top", fontsize=10.5, color=GRIS)

    etapa(ax, 0.905, "CONSULTA")
    caja(ax, 0.06, 0.865, 0.88, 0.075, "Búsqueda abierta",
         "«experiencia en IA, proyectos de investigación en aprendizaje automático y docencia en programación»\n"
         "único filtro en pantalla: vigentes / no vigentes / todos (si la consulta lo menciona, prevalece la consulta)", AZUL)

    etapa(ax, 0.79, "A · INTERPRETACIÓN")
    caja(ax, 0.06, 0.725, 0.88, 0.115, f"LLM ({MODELO_LLM}, Groq) → JSON validado (pydantic, esquema estricto)",
         "solo recibe la consulta y un catálogo de 17 tipos con ejemplos SINTÉTICOS · temperatura 0 · razonamiento «low» · caché\n"
         "C1 [obligatoria] inteligencia artificial → títulos, publicaciones, proyectos…\n"
         "C2 [obligatoria] tema: aprendizaje automático (machine learning) → proyectos, publicaciones, tesis\n"
         "C3 [obligatoria] tema: programación → materias dictadas, actividades de carga\n"
         "+ requisitos de persona (formación, idiomas) · años mínimos por capacidad · vigencia · respaldo sin LLM", NARANJA)
    flecha(ax, 0.5, 0.863, 0.5, 0.842)

    etapa(ax, 0.62, "B · RECUPERACIÓN")
    caja(ax, 0.06, 0.585, 0.27, 0.11, "Universo de personas",
         "vigencia (DEC-047…049)\n+ requisitos de persona\n(doctorado, inglés avanzado…)", GRIS)
    caja(ax, 0.36, 0.585, 0.58, 0.11, "Por capacidad × por tipo de evidencia",
         "denso exacto bge-m3 (tema y reformulación en el formato del tipo)\n"
         "+ BM25 del tema (siglas, nombres propios) → fusión RRF (k = 60)\n"
         f"posición dentro del tipo (percentil) → {CANDIDATOS_POR_TIPO} candidatos por tipo", VERDE)
    flecha(ax, 0.5, 0.723, 0.195, 0.697)
    flecha(ax, 0.5, 0.723, 0.65, 0.697)
    flecha(ax, 0.33, 0.64, 0.36, 0.64)

    etapa(ax, 0.49, "C · RELEVANCIA")
    caja(ax, 0.06, 0.445, 0.88, 0.11, f"Relevancia de cada evidencia candidata (juez = «{JUEZ}», umbral {UMBRALES[JUEZ]})",
         "percentil: solo la recuperación · cross-encoder: BAAI/bge-reranker-v2-m3 sobre el TEMA\n"
         "fusión: RRF entre el orden del reranker y el de la recuperación (sin pesos)\n"
         "el juez y el umbral se eligieron con la evaluación known-item (no a mano)", MORADO)
    flecha(ax, 0.65, 0.583, 0.5, 0.557)

    etapa(ax, 0.355, "D · RANKING")
    caja(ax, 0.06, 0.305, 0.43, 0.115, "De evidencias a personas",
         "persona × capacidad = su MEJOR evidencia\n(el número de evidencias no suma)\n"
         "requisitos de años: unión de intervalos\nde las evidencias relevantes", ROJO)
    caja(ax, 0.51, 0.305, 0.43, 0.115, "Orden de personas",
         "1) nº de capacidades obligatorias cubiertas\n2) media geométrica de las obligatorias\n(«AND suave»)\n"
         "3) deseables", ROJO)
    flecha(ax, 0.5, 0.443, 0.275, 0.422, ROJO)
    flecha(ax, 0.49, 0.36, 0.51, 0.36, ROJO)

    etapa(ax, 0.215, "E · RESULTADO")
    caja(ax, 0.06, 0.155, 0.88, 0.12, "Resultado explicado (React · /busqueda)",
         "«Entendí: …» · por persona: ✓/✗ por capacidad, relevancia alta/media/baja, 1–2 evidencias con tipo y fechas,\n"
         "años verificados o «no verificables» · ficha y trayectoria al hacer clic · grupo del clustering SOLO como contexto\n"
         "nunca se muestra el coseno · «ausencia de evidencia ≠ ausencia de capacidad»", TEAL)
    flecha(ax, 0.725, 0.303, 0.5, 0.277, TEAL)

    caja(ax, 0.06, 0.03, 0.88, 0.1, "Evaluación (evaluacion.py)",
         "known-item: 80 consultas parafraseadas por el LLM desde títulos de publicaciones y nombres de materias (información pública)\n"
         "recall@10 / MRR — denso global (línea base) 0,34 / 0,20 · híbrido global 0,35 / 0,16 · por tipo + percentil 0,41 / 0,16\n"
         "por tipo + fusión 0,56 / 0,37 · por tipo + cross-encoder 0,65 / 0,49  ← elegido", GRIS)
    SALIDA.parent.mkdir(exist_ok=True)
    fig.savefig(SALIDA, dpi=150, facecolor="white")
    print(SALIDA)


if __name__ == "__main__":
    main()
