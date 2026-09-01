"""Regenera notebooks explicados, con ejemplos y verificaciones visibles."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks" / "preprocesamiento"
SOURCES = [
    ("01_capacitaciones_todas", "capacitacionestodas.csv", "capacitaciones"),
    ("02_carga_academica_disponible", "cargaacademicadisponible.csv", "carga_academica"),
    ("03_carga_politecnica_disponible", "cargapolitecnicadisponible.csv", "carga_politecnica"),
    ("04_catalogo_actividades_carga", "catalogoactividadescarga.csv", "catalogo_actividades"),
    ("05_catalogo_idiomas", "catalogoidiomas.csv", "catalogo_idiomas"),
    ("06_certificados_todos", "certificadostodos.csv", "capacitaciones"),
    ("07_datos_personales_ultimos_5_anios", "datos_personales_ultimos_5anios.csv", "personas"),
    ("08_experiencia_externa", "experenciaexterna.csv", "experiencia_externa"),
    ("09_heteroevaluacion_disponible", "heteroevaluaciondisponible.csv", "heteroevaluacion"),
    ("10_historia_laboral_personas", "historialaboralpersonas.csv", "historia_laboral"),
    ("11_idiomas_personas", "idiomaspersonas.csv", "idiomas"),
    ("12_mencion_honor", "mencionhonor.csv", "menciones"),
    ("13_ponentes_todos", "ponentestodos.csv", "capacitaciones"),
    ("14_proyectos_investigacion_disponible", "proyectosinvestigaciondisponible.csv", "proyectos"),
    ("15_proyectos_vinculacion_disponible", "proyectosvinculaciondisponible.csv", "proyectos"),
    ("16_proyecto_grado", "proyecto_grado.csv", "proyecto_grado"),
    ("17_publicaciones", "publicaciones.csv", "publicaciones"),
    ("18_reporte_titulaciones_educacion", "ReporteTitulacionesEducacion.csv", "titulaciones"),
]
CONTEXT = {
    "capacitaciones": "capacitaciones, certificados o participaciones como ponente. Sirve para caracterizar formación y actividad extracurricular.",
    "carga_academica": "carga académica, cursos, horas y capacidad. Aporta evidencia de actividad docente.",
    "carga_politecnica": "actividades de carga politécnica y responsabilidades institucionales.",
    "catalogo_actividades": "un catálogo de actividades, útil como tabla de referencia para interpretar códigos.",
    "catalogo_idiomas": "un catálogo de niveles de idioma, útil como tabla de referencia.",
    "personas": "datos personales históricos. Se tratan con cautela por contener información sensible.",
    "experiencia_externa": "experiencia laboral fuera de ESPOL. El diccionario disponible permite explicar códigos de categoría y rol académico.",
    "heteroevaluacion": "heteroevaluación: promedios y participación de estudiantes.",
    "historia_laboral": "historial laboral institucional: contratos, cargos y dedicación.",
    "idiomas": "idiomas declarados por las personas, sin inferir equivalencias no documentadas.",
    "menciones": "menciones de honor y reconocimientos.",
    "proyectos": "proyectos de investigación o vinculación y sus roles.",
    "proyecto_grado": "dirección de trabajos de titulación.",
    "publicaciones": "publicaciones y sus metadatos académicos.",
    "titulaciones": "titulaciones, niveles y áreas de formación.",
}
def md(value):
    return {"cell_type": "markdown", "metadata": {}, "source": value.splitlines(keepends=True)}
def py(value):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": value.splitlines(keepends=True)}
def notebook(slug, source, kind):
    cells = [
      md(f"""# {slug.replace("_", " ").title()}

## Propósito

Esta fuente contiene **{CONTEXT[kind]}**

Forma parte de la base de conocimiento para perfiles multidimensionales del personal. No se usa aquí para clasificar, predecir ni tomar decisiones sobre personas."""),
      md("""## Reglas de seguridad y conservación

- No se eliminan filas ni columnas de origen.
- No se imputan valores faltantes.
- Los identificadores se mantienen como texto para proteger ceros iniciales y códigos.
- La fuente original no se modifica; el resultado se guarda como un archivo nuevo.
- Una fecha o cantidad sólo se convierte si puede interpretarse; la versión original siempre permanece disponible."""),
      md("""## Convención de las variables nuevas

| Sufijo | Significado | Ejemplo |
| --- | --- | --- |
| __FECHA | Fecha interpretada | FECHAINICIO__FECHA |
| __FECHA_VALIDA | Indica si la fecha fue interpretable | FECHAINICIO__FECHA_VALIDA |
| __NUMERICO | Copia numérica de una cantidad | DURACION__NUMERICO |
| __NUMERICO_VALIDO | Indica si el número fue interpretable | DURACION__NUMERICO_VALIDO |

De esta forma, un valor problemático no se pierde ni se modifica silenciosamente."""),
      py("""from pathlib import Path
import sys
import pandas as pd

# Buscar la raíz del proyecto para que funcione desde VS Code o Jupyter.
ROOT = Path.cwd().resolve()
while ROOT != ROOT.parent and not (ROOT / "data" / "cruda").exists():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "notebooks" / "preprocesamiento"))
from _preprocesamiento_comun import process_source
"""),
      md("""## 1. Ejemplos reales de la fuente

Se carga una muestra sin transformaciones. Revise nombres de columnas, códigos y formatos antes de usar cualquier variable en un análisis."""),
      py(f"""fuente = ROOT / "data" / "cruda" / "{source}"
salida = ROOT / "data" / "processed" / "{slug}.parquet"

# Lectura exploratoria: todos los campos se conservan como texto.
datos_crudos = pd.read_csv(fuente, dtype="string", keep_default_na=False, encoding="utf-8-sig")
print(f"Filas: {{len(datos_crudos):,}} | Columnas: {{len(datos_crudos.columns):,}}")
datos_crudos.head(5)
"""),
      md("""## 2. Diagnóstico inicial

Esta tabla no altera datos: muestra vacíos y un ejemplo real de cada campo. Úsela para decidir, con expertos institucionales, qué variables son pertinentes."""),
      py("""perfil = pd.DataFrame({
    "tipo_leido": datos_crudos.dtypes.astype(str),
    "vacios_en_origen": (datos_crudos == "").sum(),
    "ejemplo": [datos_crudos[c].dropna().iloc[0] if len(datos_crudos[c].dropna()) else pd.NA for c in datos_crudos.columns],
})
perfil
"""),
      md("""## 3. Limpieza y transformación aplicada

El proceso hace únicamente estas operaciones:

1. Añade FILA_ORIGEN para trazabilidad.
2. Quita espacios de borde y convierte textos vacíos a NA.
3. Para campos de fecha, crea fecha, año, mes e indicador de validez en columnas adicionales.
4. Para cantidades identificables, crea una copia numérica y un indicador de validez.
5. Calcula variables específicas sólo cuando hay columnas suficientes: por ejemplo duración entre fechas, tasa de participación de heteroevaluación o descripciones de códigos de experiencia externa del TXT proporcionado.

No se estandarizan categorías ambiguas ni se eliminan posibles atípicos: esas decisiones requieren validación institucional."""),
      py(f"""# Ejecutar el preprocesamiento conservador.
reporte = process_source(fuente, salida, kind="{kind}")
pd.Series(reporte)
"""),
      md("""## 4. Revisar las variables derivadas

Las siguientes celdas enumeran y muestran ejemplos de las nuevas columnas. Verifique que tengan sentido para esta fuente antes de incorporarlas a la tabla integrada de perfiles."""),
      py("""datos_procesados = pd.read_parquet(salida)
nuevas = [c for c in datos_procesados.columns if c not in datos_crudos.columns and c != "FILA_ORIGEN"]
print(f"Columnas nuevas: {len(nuevas)}")
pd.DataFrame({"variable_nueva": nuevas})
"""),
      md("""## 5. Verificación final y entregables

La verificación debe mostrar cero filas eliminadas y True en la conservación de columnas. Además del Parquet se genera un archivo de calidad JSON con nulos por campo, criterios aplicados y trazabilidad."""),
      py("""verificacion = pd.DataFrame({
    "comprobacion": ["filas de origen", "filas procesadas", "filas eliminadas", "columnas de origen conservadas"],
    "resultado": [len(datos_crudos), len(datos_procesados), len(datos_crudos) - len(datos_procesados), set(datos_crudos.columns).issubset(datos_procesados.columns)],
})
display(verificacion)
display(datos_procesados[nuevas].head(5) if nuevas else pd.DataFrame())
"""),
    ]
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
NOTEBOOKS.mkdir(parents=True, exist_ok=True)
for slug, source, kind in SOURCES:
    target = NOTEBOOKS / f"{slug}.ipynb"
    target.write_text(json.dumps(notebook(slug, source, kind), ensure_ascii=False, indent=2), encoding="utf-8")
    print(target.name)

