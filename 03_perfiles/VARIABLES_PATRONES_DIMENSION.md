# Variables de los patrones por dimensión: origen y cálculo

> Fecha: 2026-10-17 · Versión de resultados: `20261014-0025_a61ceb40`

## Cómo leer este documento

Cada variable de los patrones por dimensión pasa por dos etapas de código: `02_evidencias` arma el JSON `atributos` de cada evidencia desde `data/processed/`, y `03_perfiles` cuenta esos atributos por persona y corre KMeans.

En cada tabla:

- **Columna en `processed/`**: la columna original de la fuente.
- **Regla en `02_evidencias`**: cómo se convierte en un campo de `atributos`, en el constructor `02_evidencias/<carpeta>/<tipo>.py`.
- **Cálculo por persona**: lo que hace `componentes_crudos` en `03_perfiles/dimensiones.py` (líneas 155-245) al recorrer las evidencias de la persona.

Transformaciones finales:

- Todos los conteos pasan por log1p, salvo las 5 variables marcadas **(sin log)**.
- Una persona entra en una dimensión si tiene al menos 1 evidencia de esos tipos. En Docencia, una actividad de carga solo cuenta si tiene horas de docencia.
- La matriz persona × variables que entra al KMeans se calcula en memoria y no se guarda en disco.

## Flujo de archivos en data/

Los datos recorren cuatro carpetas; solo la tabla de conteos por persona no queda en disco.

1. **`data/raw/`**: extractos institucionales originales (por ejemplo `proyectosinvestigaciondisponible.csv`, `publicaciones.csv`).
2. **`data/processed/`**: el mismo contenido limpio y tipado, generado por los notebooks de `01_preprocesamiento_features/01_preprocesamiento/` (por ejemplo 15 y 17). No elimina filas: limpia textos, convierte fechas y S/N a 1/0, y quita columnas vacías o constantes. La trayectoria sale de `data/trayectorias/` (notebook 04).
3. **`data/evidencias/<tipo>/`**: aquí se crea `atributos`. Cada carpeta tiene `evidencias_<tipo>.csv` (columnas `evidencia_id`, `persona_id`, `tipo_id`, `texto`, `atributos`), un `reporte_evidencias_<tipo>.json` con los conteos de cada filtro y `registros_no_considerados.csv` con lo excluido y su motivo.
4. **En memoria** (`python -m perfiles.construir`): conteos por persona, proporciones, estandarización z y KMeans.
5. **`data/perfiles/clustering/<versión>/<ámbito>/`**: `micro_dimensiones.json` (patrones, z del centroide y media real de cada variable, k, silueta, ARI) y `patrones_dimension.parquet` (patrón y afinidades de cada persona). La versión actual está en `actual.json`.

Para rastrear una evidencia hacia atrás, su `atributos._origen` indica el archivo de `processed/` y los IDs de las filas que la formaron.

Ejemplo de Investigación:

| Etapa | Proyectos | Publicaciones |
| --- | --- | --- |
| raw | 6 768 filas, 1 230 personas | 8 757 filas, 942 personas |
| processed | 6 768 filas | 8 757 filas |
| filas de la población (3 164 personas con trayectoria) | 6 673 | 8 697 |
| evidencias | 6 373 (1 186 personas) | 7 797 (923 personas) |
| personas en el patrón (ámbito todos) | 1 247 (proyectos o publicaciones) | |

## Investigación y producción académica

### 1. Investigación

Evidencias: `data/evidencias/investigacion/evidencias_investigacion.csv` y `data/evidencias/publicaciones/evidencias_publicaciones.csv`. Constructores: `02_evidencias/investigacion/proyecto_investigacion.py` y `publicacion.py`.

| Variable | Tipo | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- | --- |
| proyectos | PROYECTO_INVESTIGACION | (filas) | `proyectos_investigacion_disponible.csv` → `NOMBRE` | 1 evidencia = persona + nombre normalizado; IDs con el mismo nombre = periodos | +1 por evidencia |
| proyectos_dirigidos | PROYECTO_INVESTIGACION | `roles` | `ROLPROYECTO` | se unen los roles de todos los periodos | +1 si `roles` incluye DIRECTOR o CO-DIRECTOR |
| publicaciones | PUBLICACION | (filas) | `publicaciones.csv` → `TITULO` | 1 evidencia = persona + título con similitud ≥ 0,95; los registros repetidos = versiones | +1 por evidencia |
| publicaciones_q1q2 | PUBLICACION | `cuartiles_sjr` | `CUARTIL` | `--` → vacío; se unen los cuartiles de todas las versiones | +1 si alguna versión es Q1 o Q2 |
| publicaciones_autor | PUBLICACION | `participaciones` | `STRTIPOPARTICIPACION` | se unen las de todas las versiones | +1 si incluye "Autor"; solo se usa como numerador de una proporción |

### 2. Ponencias

Evidencias: `data/evidencias/ponencias/evidencias_ponencias.csv`. Constructor: `02_evidencias/investigacion/ponencia.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| ponencias | (filas) | `ponentes_todos.csv` → `NOMBRE` | 1 evidencia = persona + nombre del evento casi idéntico; se excluyen las asistencias (`TIPOCERTIFICADO = AS`) | +1 |
| ponencias_exterior | `es_exterior` | `NOMBREPAIS` | verdadero si algún país ≠ ECUADOR | +1 si es exterior |

### 3. Vinculación

Evidencias: `data/evidencias/vinculacion/evidencias_vinculacion.csv`. Constructor: `02_evidencias/investigacion/proyecto_vinculacion.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| proyectos | (filas) | `proyectos_vinculacion_disponible.csv` → `NOMBRE` | 1 evidencia = persona + nombre, sin el sufijo "(Gastos Generales)" | +1 |
| proyectos_dirigidos | `roles` | `ROLPROYECTO` | todos los roles, sin jerarquía | +1 si algún rol contiene "DIRECTOR" |
| anios | `duracion_total_anios` | `FECHAINICIO`, `FECHAFIN` | suma de la duración de cada periodo (hasta la fecha de corte); sin fechas = null | se suman los años de todos sus proyectos |

### 4. Tesis dirigidas

Evidencias: `data/evidencias/tesis_dirigidas/evidencias_tesis_dirigidas.csv`. Constructor: `02_evidencias/investigacion/tesis_dirigida.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| tesis | (filas) | `proyecto_grado.csv` → `NOMBRETRABAJOTITULACION`, `IDDIRECTOR` | 1 evidencia = director + título casi idéntico; los títulos genéricos ("EXAMEN COMPLEXIVO…") se excluyen | +1 |
| estudiantes | `n_estudiantes` | una fila por estudiante | cantidad de filas agrupadas en la tesis | se suma |
| tesis_investigacion_doctorado | `niveles_formacion` | `NIVELFORMACION` | niveles de sus sustentaciones | +1 si el texto contiene "INVESTIGACI" o "DOCTORADO" |

## Docencia, formación y desarrollo

### 5. Docencia

Evidencias: `data/evidencias/docencia/evidencias_docencia.csv`. Constructores: `02_evidencias/docencia/materia.py` y `actividad_carga.py`.

| Variable | Tipo | Atributo | Columna de origen | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- | --- |
| materias | DOCENCIA_MATERIA | (filas) | 4 extractos de carga académica en `data/raw/` → nombre de la materia | 1 evidencia = persona + materia casi idéntica (CÁLCULO I ≠ CÁLCULO II); desde 2015 solo cursos con APROBADO = S | +1 |
| semestres | DOCENCIA_MATERIA | `n_periodos` | periodo académico (TERM) | semestres distintos en que dictó la materia | se suma |
| estudiantes | DOCENCIA_MATERIA | `n_estudiantes_total` | `NUMREGISTRADOS` | una vez por paralelo principal | se suma |
| horas_carga_docencia | ACTIVIDAD_CARGA | `detalle[].horas`, `detalle[].actividad` | `carga_politecnica_disponible.csv` → `NUMHORAS`, `ACTIVIDAD` | D → DOCENCIA, A → GESTION, I → INVESTIGACION, V → VINCULACION | se suman las horas con actividad = DOCENCIA |

### 6. Formación

Evidencias: `data/evidencias/formacion/evidencias_formacion.csv`. Constructores: `02_evidencias/formacion/titulo.py`, `en_curso.py` y `comun.py`.

| Variable | Tipo | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- | --- |
| nivel_maximo (sin log) | FORMACION_TITULO | `nivel`, `grado_academico` | `reporte_titulaciones_educacion.csv` → `Nivel` y título | `grado_academico` se deduce del texto del título (DOCTOR/PHD → DOCTORADO, MAGISTER/MSC → MAESTRIA…) | máximo de: doctorado 4 · maestría 3 · otro cuarto nivel 2,5 · tercer nivel 2 · técnico 1,5 · bachiller 1 · sin registro 0 |
| posgrados | FORMACION_TITULO | `nivel` | `Nivel` | solo Estado = Graduado (o vacío en bachillerato) | +1 si `nivel` contiene "CUARTO" |
| titulo_exterior (sin log) | FORMACION_TITULO | `es_exterior` | `Pais` | país ≠ ECUADOR | 1 si tiene algún título del exterior |
| posgrado_en_curso (sin log) | FORMACION_EN_CURSO | `nivel` | `Nivel`, `Estado` (Cursando, Egresado…) | no se cuenta si ya tiene ese título terminado | 1 si está cursando un cuarto nivel |

### 7. Capacitación

Evidencias: `data/evidencias/capacitaciones/evidencias_capacitaciones.csv`. Constructores: `02_evidencias/capacitacion/capacitacion.py` y `comun.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| cursos | (filas) | `capacitaciones_todas.csv` → `NOMBRE` | 1 evidencia = persona + nombre casi idéntico; no repite lo que ya es ponencia o certificación | +1 |
| horas | `horas_total` | `DURACION` | suma de las participaciones con horas > 0 | se suma |
| cursos_exterior | `es_exterior` | `NOMBREPAIS` | algún país ≠ ECUADOR | +1 |

### 8. Certificaciones

Evidencias: `data/evidencias/certificaciones/evidencias_certificaciones.csv`. Constructores: `02_evidencias/capacitacion/certificacion.py` y `comun.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| certificaciones | (filas) | `certificados_todos.csv` → `NOMBRE` | igual que capacitación | +1 |
| vigentes | `vigente` | `FECHAFIN` | `FECHAFIN` ≥ fecha de corte | +1 si está vigente |
| horas | `horas_total` | `DURACION` | igual que capacitación | se suma |

### 9. Idiomas

Evidencias: `data/evidencias/idiomas/evidencias_idiomas.csv`. Constructor: `02_evidencias/idiomas/idioma.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| idiomas_extranjeros (sin log) | `idioma` | `idiomas_personas.csv` → `IDIOMA` (u OTRO + `DESCRIPCION`) | 1 evidencia = persona + idioma; el español nativo no es evidencia | n.º de idiomas distintos del español |
| nivel_maximo (sin log) | `niveles_conversacion`, `niveles_lectura`, `niveles_escritura`, `niveles_mcer` | `NIVELCONVERSACION`, `NIVELLECTURA`, `NIVELESCRITURA`, `NIVELMCER` | A/I/B/N → AVANZADO/INTERMEDIO/BÁSICO/NINGUNA | máximo de: avanzado 3 · intermedio 2 · básico 1; MCER C 3 · B 2 · A 1 |

### 10. Reconocimientos

Evidencias: `data/evidencias/menciones_honor/evidencias_menciones_honor.csv`. Constructor: `02_evidencias/reconocimientos/mencion_honor.py`.

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| menciones | `n_veces` | `mencion_honor.csv` → `NOMBRE` | 1 evidencia = persona + nombre casi idéntico; `n_veces` = cuántas veces la recibió | se suma `n_veces` |
| menciones_exterior | `es_exterior` | `PAIS` | algún país ≠ ECUADOR | se suma `n_veces` si es del exterior |

## Trayectoria laboral

Ambas dimensiones leen `data/evidencias/trayectoria/evidencias_trayectoria.csv`. Constructores en `02_evidencias/trayectoria/`.

### 11. Trayectoria en ESPOL

| Variable | Tipo | Atributo | Archivo de origen | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- | --- |
| anios | TRAYECTORIA_CARGO_ESTRUCTURAL | `duracion_total_anios` | `data/trayectorias/tramos_rol.csv` | 1 evidencia = persona + cargo + unidad (recesos de hasta 90 días no cortan el periodo); se suma la duración de sus periodos | se suman los años de todos sus cargos |
| cargos | TRAYECTORIA_CARGO_ESTRUCTURAL + TRAYECTORIA_CONTRATO_PUNTUAL | (filas) | `tramos_rol.csv`, `data/trayectorias/eventos_puntuales_cargo.csv` | contrato puntual: 1 evidencia = persona + contrato + unidad | +1 por cada una |
| funciones_adicionales | TRAYECTORIA_FUNCION_ADICIONAL | (filas) | `data/trayectorias/funciones_adicionales_persona.csv` (del registro de autoridades) | 1 evidencia = persona + función + unidad; se excluyen las que coinciden con un contrato del mismo cargo | +1 |

### 12. Experiencia externa

| Variable | Atributo | Columna en processed/ | Regla en 02_evidencias | Cálculo por persona |
| --- | --- | --- | --- | --- |
| anios | `duracion_anios` | `experiencia_externa.csv` → `FECHADESDE`, `FECHAHASTA` | solo se calcula si hay `FECHAHASTA` | se suma |
| experiencias | (filas) | 1 fila = 1 evidencia | ya fusionadas en el notebook 08 | +1 |
| exterior | `es_exterior` | `PAIS` | país ≠ ECUADOR | +1 |
| academica | `categoria_experiencia` | `CATEXPERIENCIA_DESC` | texto tal cual | +1 si es "ACADEMICA" |

## Del atributo al patrón

Los patrones de actividad usan los componentes anteriores más unas proporciones que describen cómo participa la persona sin depender del volumen. Están en `PROPORCIONES` (`03_perfiles/micro_dimensiones.py`) y se calculan con los conteos reales (DEC-061):

- **Proporciones "parte de"** (casos / total, p. ej. Q1Q2 / publicaciones): contracción bayesiana empírica beta-binomial, (casos + a) / (total + a + b), con a y b ajustados por máxima verosimilitud en el ámbito. Sin denominador quedan en la media del grupo (no penalizan) y con pocos casos se suavizan. a, b y el número de personas sin denominador quedan en `micro_dimensiones.json` → `contraccion_proporciones`.
- **Tasas** (estudiantes por tesis o materia, horas por curso, funciones por cargo): sin denominador toman la media de quienes sí lo tienen.

| Dimensión | Proporciones |
| --- | --- |
| Investigación | dirigidos / proyectos · Q1Q2 / publicaciones · autor / publicaciones |
| Ponencias | exterior / ponencias |
| Vinculación | dirigidos / proyectos |
| Tesis dirigidas | investigación o doctorado / tesis · estudiantes / tesis (log) |
| Capacitación | exterior / cursos · horas / curso (log) |
| Certificaciones | vigentes / certificaciones |
| Reconocimientos | exterior / menciones |
| Experiencia externa | exterior / experiencias · académica / experiencias |
| Trayectoria en ESPOL | funciones adicionales / cargos (log) |
| Docencia | estudiantes / materia (log) |

Formación e Idiomas no tienen proporciones.

Pasos en `03_perfiles`, por ámbito y dimensión:

1. `componentes_crudos` (`dimensiones.py`, línea 155) recorre las evidencias y acumula los conteos por persona; aplica log1p (línea 240).
2. `variables_patron` (`micro_dimensiones.py`, línea 71) toma los componentes y agrega las proporciones.
3. `patrones_dimension` (`micro_dimensiones.py`) filtra a quienes tienen al menos 1 evidencia, estandariza (z) en el ámbito, elige k entre 3 y 6 = mayor silueta entre los k con estabilidad ARI ≥ 0,9 (grupos de al menos el 3 % o 10 personas) y corre KMeans.
4. `construir.py` llama a todo una vez por ámbito (líneas 319 y 343) y guarda los resultados.

## Reglas que conviene revisar

Ocho reglas pueden distorsionar los patrones; la primera se corrigió en DEC-061.

- [x] **Proporciones con denominador 0.** Resuelto en DEC-061 (contracción beta-binomial: sin denominador = media del grupo). Antes, quien no tenía publicaciones recibía 0 en Q1Q2 / publicaciones y autor / publicaciones (26 % en Investigación, ámbito todos) y formaba un patrón propio.
- [ ] **Significado de "Autor" frente a "CoAutor".** No se sabe si "Autor" en la fuente es primer autor, autor de correspondencia o autor único. Hay que confirmarlo con quien administra el sistema antes de interpretar un patrón con eso.
- [ ] **Experiencia externa, años.** Un trabajo externo sin fecha de salida, incluido el actual, suma 0 años.
- [ ] **Años de Trayectoria y Vinculación.** Se suman las duraciones de cada evidencia, así que dos cargos o proyectos simultáneos cuentan dos veces el mismo tiempo.
- [ ] **Vinculación, dirigidos.** "Contiene DIRECTOR" también acepta otros roles; hay que revisar la lista real de `ROLPROYECTO`.
- [ ] **"Alguna versión" o "algún periodo".** Un solo Q1 o un solo DIRECTOR en una versión o periodo hace contar toda la evidencia.
- [ ] **Formación, grado académico.** Se deduce por palabras del título (DR, MSC…); la fuente no lo trae.
- [ ] **Tipos de publicación.** Un artículo de difusión pesa lo mismo que uno Scopus/WoS.
