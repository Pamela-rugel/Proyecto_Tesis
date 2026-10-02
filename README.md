# Proyecto_Tesis
Proyecto Tesis - Maestría de Ciencia de Datos

**Sistema de generación de perfiles del personal docente y administrativo de ESPOL para la
asignación inteligente de tareas.**

## Estructura (el número indica el orden del pipeline)

| Carpeta | Qué hace | Salida principal |
|---|---|---|
| `01_preprocesamiento_features/` | Carpeta `01_preprocesamiento/` (limpieza de cada fuente) y los notebooks `02_integracion_datos`, `03_construccion_features`, `04_trayectorias` y `05_preparacion_modelado` | `data/processed/`, `data/features/`, `data/trayectorias/` |
| `02_evidencias/` | Paquete `evidencias`: convierte los datos en evidencias individuales (un cargo, un título, una materia…) | `data/evidencias/` |
| `03_perfiles/` | Paquete `perfiles`: embeddings de las evidencias, tres vistas por persona, SNF, grupos y subgrupos ([METODOLOGIA.md](03_perfiles/METODOLOGIA.md)) | `data/perfiles/` |
| `04_busqueda_semantica/` | Paquete `busqueda`: búsqueda de personas por consulta en lenguaje natural sobre las evidencias ([IMPLEMENTACION.md](04_busqueda_semantica/IMPLEMENTACION.md)) | `data/busqueda/` |
| `dashboard_react/` | Vista web (API FastAPI de solo lectura + React) | — |

Otras carpetas: `data/` (datos, no versionados salvo excepciones), `context/` (contexto y
decisiones del proyecto, no versionado), `documentacion/`, `stack/` (Docker).

## Instalación

```bash
pip install -r requirements.txt     # dependencias (entorno Python global de notebooks)
python -m pip install -e . --no-deps
```

La segunda línea es necesaria: las carpetas `02_evidencias/` y `03_perfiles/` se importan como
paquetes `evidencias` y `perfiles` (Python no permite nombres que empiecen con un número; el
mapeo está en `pyproject.toml`). El dashboard usa su propio entorno `.venv` y no necesita esta
instalación.

## Orden de ejecución

1. `01_preprocesamiento_features/01_preprocesamiento/*.ipynb` (limpieza de cada fuente) y luego, en `01_preprocesamiento_features/`, los notebooks `02_integracion_datos` → `03_construccion_features` → `04_trayectorias` → `05_preparacion_modelado`.
2. Evidencias (cada carpeta de `02_evidencias/` tiene su notebook), en este orden: trayectoria →
   formación → investigación → capacitación → idiomas → reconocimientos → docencia. Requiere
   `data/raw/defunciones_identificadas.txt`.
3. Perfiles: `python -m perfiles.embeddings` y `python -m perfiles.construir` (o el notebook
   `03_perfiles/clustering_perfiles.ipynb`).
4. Búsqueda: requiere `GROQ_API_KEY`; `python -m busqueda.buscar "consulta"` o la vista `/busqueda`.
5. Dashboard: ver `dashboard_react/README.md`.

En Windows, los notebooks se ejecutan con
`PYTHONUTF8=1 python -m jupyter execute --inplace --timeout=-1 <notebook>`.
