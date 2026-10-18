# Proyecto_Tesis
Proyecto Tesis - Maestría de Ciencia de Datos

**Sistema de generación de perfiles del personal docente y administrativo de ESPOL para la
asignación inteligente de tareas.**

## Estructura (el número indica el orden del pipeline)

En carpetas y notebooks, el prefijo numérico es el orden en que se ejecutan.

| Carpeta | Qué hace | Salida principal |
|---|---|---|
| `01_preprocesamiento_features/` | `01_preprocesamiento/`: limpieza de cada fuente institucional; `02_trayectorias.ipynb`: tramos de rol y eventos de la trayectoria en ESPOL | `data/processed/`, `data/trayectorias/` |
| `02_evidencias/` | Paquete `evidencias`: convierte los datos en evidencias individuales (un cargo, un título, una materia…) | `data/evidencias/` |
| `03_perfiles/` | Paquete `perfiles`: embeddings de las evidencias, intensidad por dimensión, temas y patrones de actividad, perfil completo y patrones globales ([DOCUMENTACION_PERFILES.md](03_perfiles/DOCUMENTACION_PERFILES.md)) | `data/perfiles/` |
| `04_busqueda_semantica/` | Paquete `busqueda`: búsqueda de personas por consulta en lenguaje natural sobre las evidencias ([IMPLEMENTACION.md](04_busqueda_semantica/IMPLEMENTACION.md)) | `data/busqueda/` |
| `dashboard_react/` | Vista web (API FastAPI de solo lectura + React) | — |

Otras carpetas: `data/` (datos, no versionados salvo excepciones), `context/` (contexto y
decisiones del proyecto, no versionado), `documentacion/`, `stack/` (Docker) y `_historico/`
(notebooks y registros del enfoque anterior, fuera del flujo; ver su README).

```
data/raw/ ─► 01_preprocesamiento/ ─► data/processed/ ─┬─► 02_trayectorias.ipynb ─► data/trayectorias/ ─┐
                                                       └──────────────────────────────────────────────┴─► 02_evidencias/ ─► data/evidencias/
data/evidencias/ ─► 03_perfiles/ ─► data/perfiles/ ─┬─► dashboard_react/ (pestaña Perfiles)
                 └─► 04_busqueda_semantica/ ─► data/busqueda/ ─┴─► dashboard_react/ (pestaña Búsqueda)
```

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

### 1. Limpieza de fuentes: `01_preprocesamiento_features/01_preprocesamiento/`

Leen `data/raw/` y escriben `data/processed/`. Están numerados por la sección de evidencias que
alimentan, en el orden del paso 2. Solo hay una dependencia entre ellos: `03` usa la salida de `01`.

| Notebook | Produce (`data/processed/`) | Lo usa |
|---|---|---|
| **Trayectoria y población** | | |
| `01_datos_personales_ultimos_5anios` | `datos_personales_ultimos_5anios.csv`, `personas_excluidas.csv` | población del proyecto (todas las secciones) |
| `02_historial_laboral_personas` | `historial_laboral_personas.csv`, `historial_laboral_features.csv` | `02_trayectorias`; vigencia y cargo actual en perfiles y dashboard |
| `03_experiencia_externa` | `experiencia_externa.csv` | `02_trayectorias`, evidencias de trayectoria |
| `04_registro_autoridades` | `registro_autoridades.csv` | `02_trayectorias`, evidencias de trayectoria e investigación (siglas de unidades) |
| **Formación** | | |
| `05_reporte_titulaciones_educacion` | `reporte_titulaciones_educacion.csv` | evidencias de formación |
| **Investigación** | | |
| `06_proyectos_investigacion_disponible` | `proyectos_investigacion_disponible.csv` | evidencias de investigación |
| `07_proyectos_vinculacion_disponible` | `proyectos_vinculacion_disponible.csv` | evidencias de vinculación |
| `08_publicaciones` | `publicaciones.csv` | evidencias de publicaciones |
| `09_proyecto_grado` | `proyecto_grado.csv` | evidencias de tesis dirigidas |
| `10_ponentes_todos` | `ponentes_todos.csv` | evidencias de ponencias |
| **Capacitación** | | |
| `11_capacitaciones_todas` | `capacitaciones_todas.csv` | evidencias de capacitación |
| `12_certificados_todos` | `certificados_todos.csv` | evidencias de certificación |
| **Idiomas** | | |
| `13_catalogo_idiomas` | `catalogo_idiomas.csv` | evidencias de idiomas |
| `14_idiomas_personas` | `idiomas_personas.csv` | evidencias de idiomas |
| **Reconocimientos** | | |
| `15_mencion_honor` | `mencion_honor.csv` | evidencias de reconocimientos |
| **Docencia** | | |
| `16_carga_politecnica_disponible` | `carga_politecnica_disponible.csv` | evidencias de docencia (actividades de carga); las materias se leen de `data/raw/` |
| **Sin uso en el flujo actual** | | |
| `17_carga_academica_disponible` | `carga_academica_disponible.csv` | — (las evidencias de docencia leen la carga académica de `data/raw/`) |
| `18_catalogo_actividades_carga` | `catalogo_actividades_carga.csv` | — |
| `19_heteroevaluacion_disponible` | `heteroevaluacion_disponible.csv` | — (evaluaciones; fuente posible a futuro) |

### 2. Trayectoria en ESPOL: `01_preprocesamiento_features/02_trayectorias.ipynb`

Lee `historial_laboral_personas`, `experiencia_externa` y `registro_autoridades` y escribe
`data/trayectorias/` (`tramos_rol.csv`, `eventos_puntuales_cargo.csv`,
`funciones_adicionales_persona.csv`…), que usan las evidencias de trayectoria.

### 3. Evidencias: `02_evidencias/<sección>/NN_evidencias_<sección>.ipynb`

O `python -m evidencias.<sección>.construir`. Escriben `data/evidencias/<sección>/`. Requiere
`data/raw/defunciones_identificadas.txt`. **Trayectoria va primero**: sus evidencias definen la
población que usan las demás secciones; el resto puede ir en cualquier orden.

`01_evidencias_trayectoria` → `02_evidencias_formacion` → `03_evidencias_investigacion` →
`04_evidencias_capacitacion` → `05_evidencias_idiomas` → `06_evidencias_reconocimientos` →
`07_evidencias_docencia`

(Las carpetas de `02_evidencias/` no llevan número porque son módulos de Python.)

### 4. Perfiles: `03_perfiles/01_construir_perfiles.ipynb`

O `python -m perfiles.embeddings` y luego `python -m perfiles.construir`. Escribe
`data/perfiles/embeddings*/` y una versión nueva en `data/perfiles/clustering/<versión>/`, y
apunta `data/perfiles/clustering/actual.json` a ella. **Después hay que reiniciar el backend del
dashboard**: guarda en memoria la versión que leyó al arrancar.

### 5. Búsqueda semántica: `04_busqueda_semantica/`

Usa las evidencias y sus embeddings. Requiere `GROQ_API_KEY`; `python -m busqueda.buscar "consulta"`
o la pestaña Búsqueda del dashboard.

### 6. Dashboard: `dashboard_react/`

Ver `dashboard_react/README.md`. Solo lee los resultados de los pasos 3 a 5.

En Windows, los notebooks se ejecutan con
`PYTHONUTF8=1 python -m jupyter execute --inplace --timeout=-1 <notebook>`.
