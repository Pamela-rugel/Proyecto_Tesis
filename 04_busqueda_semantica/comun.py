"""Rutas, parámetros y catálogo de tipos de evidencia de la búsqueda."""
from __future__ import annotations

from perfiles.comun import DATA_DIR  # noqa: F401 (misma raíz de datos que perfiles)

BUSQUEDA_DIR = DATA_DIR / "busqueda"
ARCHIVO_REGISTRO = BUSQUEDA_DIR / "consultas.jsonl"

# --- Modelos -------------------------------------------------------------------------------
MODELO_EMBEDDING = "BAAI/bge-m3"            # el mismo de las evidencias (03_perfiles)
MODELO_RERANKER = "BAAI/bge-reranker-v2-m3"  # cross-encoder multilingüe, sin entrenamiento
MODELO_LLM = "openai/gpt-oss-120b"           # Groq; elegido con la prueba de interpretación
MODELO_LLM_ALTERNO = "openai/gpt-oss-20b"    # si el principal está limitado (7/7 válidas en la prueba)
# Plan gratuito de Groq, POR MODELO: 1 000 solicitudes/día, 8 000 tokens/minuto y 200 000
# tokens/día. Una interpretación usa ~2 900 tokens → ~3 consultas NUEVAS por minuto y ~68 por día
# y modelo (las repetidas salen de la caché). Ante un 429 por minuto se espera y se reintenta;
# si la cuota diaria se agotó se pasa al modelo alterno; si ambos fallan, respaldo sin LLM.

# --- Parámetros (DISENO.md; los marcados [Validar] se evalúan en evaluacion.py) -------------
RRF_K = 60                  # constante estándar de Reciprocal Rank Fusion (Cormack et al., 2009)
BM25_K1, BM25_B = 1.5, 0.75  # valores estándar de BM25 (Robertson y Zaragoza, 2009)
CANDIDATOS_POR_TIPO = 40    # textos candidatos por capacidad y tipo que pasan al reranker [Validar]
# Cómo se mide la relevancia de cada evidencia candidata ("juez") y desde qué valor una capacidad
# se considera cubierta. Se eligen con la evaluación (evaluacion.py), no a mano:
#   percentil      posición dentro de su tipo en la recuperación (denso + BM25), sin reranker
#   cross_encoder  probabilidad del reranker
#   fusion         RRF entre el orden del reranker y el de la recuperación, escalado a (0, 1]
# Resultado de la evaluación known-item (80 consultas, 01/10/2026; data/busqueda/evaluacion/):
#   recall@10 / MRR: denso global 0.34 / 0.195 · percentil 0.41 / 0.156 · fusion 0.56 / 0.371 ·
#   cross_encoder 0.65 / 0.493 → se elige cross_encoder. Su umbral casi no cambia el resultado entre
#   0.05 y 0.7 (consultas de una capacidad); 0.3 está en la meseta y deja dentro aciertos claros
#   que el reranker puntúa 0.38–0.5 en títulos cortos. [Validar] con consultas de varias capacidades.
JUECES = ("percentil", "cross_encoder", "fusion")
JUEZ = "cross_encoder"
UMBRALES = {"percentil": 0.99, "cross_encoder": 0.3, "fusion": 0.7}
EVIDENCIAS_POR_CAPACIDAD = 3  # evidencias que se muestran por capacidad en la explicación
N_RESULTADOS = 30

# --- Catálogo de tipos para el LLM: descripción + ejemplo SINTÉTICO con el formato real ------
# (no se envían textos reales de evidencias a la API)
TIPOS = {
    "TRAYECTORIA_CARGO_ESTRUCTURAL": ("Cargo de planta ocupado en ESPOL", "ANALISTA DE SISTEMAS 2, GERENCIA DE TECNOLOGÍAS (GTSI)"),
    "TRAYECTORIA_CONTRATO_PUNTUAL": ("Contrato ocasional en ESPOL (servicios profesionales, cátedra)", "Contrato civil de profesor (posgrado)"),
    "TRAYECTORIA_FUNCION_ADICIONAL": ("Función adicional: coordinación, dirección, subrogación", "Coordinador de carrera (Computación), FACULTAD DE INGENIERÍA (FIEC)"),
    "TRAYECTORIA_EXPERIENCIA_EXTERNA": ("Trabajo fuera de ESPOL", "INGENIERO DE DATOS, Empresa XYZ S.A., Ecuador"),
    "ACTIVIDAD_CARGA": ("Actividad de la carga horaria (docencia, gestión, investigación, vinculación)", "Tutoría académica de proyecto integrador, Facultad de Ingeniería (FIEC)"),
    "DOCENCIA_MATERIA": ("Materia dictada en ESPOL", "FUNDAMENTOS DE PROGRAMACIÓN, Facultad de Ingeniería (FIEC)"),
    "FORMACION_TITULO": ("Título obtenido", "MAGÍSTER EN CIENCIA DE DATOS, UNIVERSIDAD EJEMPLO, CINE: Tecnologías de la información"),
    "FORMACION_EN_CURSO": ("Estudios en curso", "DOCTORADO EN INFORMÁTICA (cursando), UNIVERSIDAD EJEMPLO, España"),
    "PROYECTO_INVESTIGACION": ("Proyecto de investigación", "DETECCIÓN DE ENFERMEDADES EN CULTIVOS CON VISIÓN POR COMPUTADOR (director), Tipo de investigación: Aplicada"),
    "PROYECTO_VINCULACION": ("Proyecto de vinculación con la sociedad", "Capacitación digital a comunidades rurales, Roles: tutor, Programa: Inclusión digital"),
    "PUBLICACION": ("Publicación científica", "DEEP LEARNING FOR SHRIMP DISEASE DETECTION, Tipo: Artículo científico, Publicado en: REVISTA EJEMPLO, Indexación: Scopus"),
    "TESIS_DIRIGIDA": ("Tesis dirigida a estudiantes", "Sistema de recomendación para bibliotecas, Nivel: Grado, Programa: Computación"),
    "PONENCIA": ("Ponencia en congreso", "CONGRESO INTERNACIONAL DE INTELIGENCIA ARTIFICIAL 2023"),
    "CAPACITACION": ("Curso o capacitación recibida", "PYTHON PARA ANÁLISIS DE DATOS, Tipo: Curso, Certificado por: PLATAFORMA EJEMPLO, Modalidad: Virtual"),
    "CERTIFICACION": ("Certificación profesional", "AWS CERTIFIED CLOUD PRACTITIONER, Certificado por: AMAZON WEB SERVICES, Modalidad: Virtual"),
    "IDIOMA": ("Idioma y nivel", "INGLÉS, Conversación: avanzado, Lectura: avanzado, Escritura: intermedio, MCER: C1"),
    "MENCION_HONOR": ("Mención de honor o premio", "MEJOR PROFESOR DE LA FACULTAD, Otorgado por: ESPOL"),
}
NOMBRE_TIPO = {
    "TRAYECTORIA_CARGO_ESTRUCTURAL": "Cargo de planta", "TRAYECTORIA_CONTRATO_PUNTUAL": "Contrato ocasional",
    "TRAYECTORIA_FUNCION_ADICIONAL": "Función adicional", "TRAYECTORIA_EXPERIENCIA_EXTERNA": "Experiencia externa",
    "ACTIVIDAD_CARGA": "Actividad de carga", "DOCENCIA_MATERIA": "Materia dictada", "FORMACION_TITULO": "Título",
    "FORMACION_EN_CURSO": "Formación en curso", "PROYECTO_INVESTIGACION": "Proyecto de investigación",
    "PROYECTO_VINCULACION": "Proyecto de vinculación", "PUBLICACION": "Publicación", "TESIS_DIRIGIDA": "Tesis dirigida",
    "PONENCIA": "Ponencia", "CAPACITACION": "Capacitación", "CERTIFICACION": "Certificación", "IDIOMA": "Idioma",
    "MENCION_HONOR": "Mención / premio",
}
