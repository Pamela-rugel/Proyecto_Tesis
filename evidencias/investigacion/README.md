# Evidencias de Investigación y producción académica

Mismo esquema que las demás secciones: `evidencia_id | persona_id | tipo_id | texto | atributos`.
El formato de los atributos está en [../ATRIBUTOS.md](../ATRIBUTOS.md).

- **Ejecución:** `evidencias_investigacion.ipynb`, o `python -m evidencias.investigacion.construir`.
- **Salidas:** una carpeta por tipo, cada una con sus evidencias, su reporte y sus registros
  no considerados:
  - `data/evidencias/investigacion/`: `evidencias_investigacion.csv`,
    `reporte_evidencias_investigacion.json`, `registros_no_considerados.csv`
    (`PROYECTO_INVESTIGACION`).
  - `data/evidencias/vinculacion/`: `evidencias_vinculacion.csv`,
    `reporte_evidencias_vinculacion.json`, `registros_no_considerados.csv`
    (`PROYECTO_VINCULACION`).
  - `data/evidencias/publicaciones/`: `evidencias_publicaciones.csv`,
    `reporte_evidencias_publicaciones.json`, `registros_no_considerados.csv` (`PUBLICACION`).
  - `data/evidencias/tesis_dirigidas/`: `evidencias_tesis_dirigidas.csv`,
    `reporte_evidencias_tesis_dirigidas.json`, `registros_no_considerados.csv` (`TESIS_DIRIGIDA`).
  - `data/evidencias/ponencias/`: `evidencias_ponencias.csv`,
    `reporte_evidencias_ponencias.json`, `registros_no_considerados.csv` (`PONENCIA`).
- **Población:** personas con al menos una evidencia de trayectoria.

| Tipo | Fuente | Estado |
|---|---|---|
| `PROYECTO_INVESTIGACION` | `proyectos_investigacion_disponible.csv` | ✅ |
| `PROYECTO_VINCULACION` | `proyectos_vinculacion_disponible.csv` | ✅ |
| `PUBLICACION` | `publicaciones.csv` | ✅ |
| `TESIS_DIRIGIDA` | `proyecto_grado.csv` | ✅ |
| `PONENCIA` | `ponentes_todos.csv` | ✅ |

## PROYECTO_INVESTIGACION (decisiones del usuario, 2026-09-28)

| Regla | Detalle |
|---|---|
| Unidad de evidencia | Persona + nombre de proyecto (normalizado) |
| Periodos | Cada ID de proyecto con ese nombre es un periodo, con su propio rol, estado, unidad, institución externa, país y financiamiento. Varias filas del mismo ID (la persona con varios roles) forman un solo periodo con `roles` |
| Vigencia | Solo por fechas: sin fecha de fin, vigente; con fecha de fin, vigente si aún no llega. `estado` es el dato de la fuente y no define la vigencia (1482 dicen "en ejecución" con fecha de fin pasada) |
| Inicio futuro | No es evidencia. Queda en `registros_no_considerados.csv` (persona, tipo, motivo, id de proyecto, nombre, fecha de inicio) |
| Texto | `NOMBRE (roles), Tipo de investigación, UNIDAD (SIGLA), Institución externa, País (si es del exterior), CINE, Subárea CINE, CINE secundaria, Frascati, …`, omitiendo lo que no existe |
| No se copian | `REFARCHIVO1-3` y `ENESCALAFON` (administrativos), y los códigos numéricos de área (se usa la versión en texto) |
| Códigos sin catálogo | `financiamiento_externo` (0/1/2) y `rol_codigos` (1–4; los códigos 2, 3 y 4 aparecen como PARTICIPANTE o CO-DIRECTOR) |

## PROYECTO_VINCULACION (decisiones del usuario, 2026-09-28)

| Regla | Detalle |
|---|---|
| Unidad de evidencia | Persona + nombre de proyecto. Para agrupar se quita el sufijo "(Gastos Generales)"; las variantes con contenido distinto quedan en `nombres_similares` |
| Periodos | Cada ID de proyecto es un periodo, con sus roles y su programa |
| Roles | Todos, sin jerarquía: `Roles: tutor, director de proyecto` en el texto y la lista `roles` en los atributos |
| Programas | Todos los relacionados: `Programa:` (o `Programas:` separados por `;`) |
| Sin fechas | Se conservan, con fechas, duración y `vigente` en null |
| Vigencia | Solo por fechas; sin ninguna fecha = null (desconocido) |
| Inicio futuro | No es evidencia; queda en `registros_no_considerados.csv` |
| Fechas invertidas | Se conservan; el periodo se marca `fechas_inconsistentes` y su duración queda null |
| Texto | `NOMBRE, Roles: …, Programa: …`, sin etiqueta de tipo al inicio (el tipo ya está en `tipo_id`) |
| Sin área temática | `IDAREACONOCIM` vacío en la fuente; el tema solo está en los nombres del proyecto y del programa |
| No se copian | Columnas vacías o constantes que ya quitó la limpieza (`TIPO`, `TABLA`, `ESTIMULO`, `ENESCALAFON`…) |

## PUBLICACION (decisiones del usuario, 2026-09-28)

| Regla | Detalle |
|---|---|
| Unidad de evidencia | Persona + título casi idéntico (similitud ≥ 0.95 sin tildes ni signos) |
| Versiones | Los registros con ese título son `versiones`. Los que solo difieren en el ID se unen en una versión con todos sus IDs; los que cambian de tipo, lugar, año, participación o estado quedan como versiones distintas |
| Texto | `TÍTULO, Tipo: …, Publicado en: …, Indexación: …` con todos los tipos y lugares. La indexación solo si el tipo no la dice ya. **No** van al texto: cuartiles, factores de impacto, años, ISSN/ISBN ni participación (ruido para el embedding) |
| Fechas | Solo el año (`anios`); `fecha_inicio`/`fecha_fin` null. Año inválido (< 1950) → no se incluye |
| Factores de impacto | Texto tal cual viene; el formato de origen es inconsistente ("1,980", "1.46", "037") y se mapeará después |
| Estado vacío | null; el código 0 de origen no tiene significado conocido |
| Coautores | `coautores_espol`: IDPERSONA de otras personas de la población que registraron el mismo título; `n_coautores_espol`: cuántas. La fuente no tiene lista de autores, así que no se ven los coautores externos ni los de ESPOL que no la registraron |
| No se copian | `REFARCHIVO1-3`, `ENESCALAFON`, y los códigos numéricos (`TIPOPUBLICACION`, `BASEINDEXACION`, …) que tienen versión en texto |

## TESIS_DIRIGIDA (decisiones del usuario, 2026-09-28)

Fuente: `proyecto_grado.csv`, **una fila por estudiante**. La persona es el director
(`IDDIRECTOR`); solo hay posgrado y no hay área temática ni identificador de estudiante.

| Regla | Detalle |
|---|---|
| Unidad de evidencia | Director + título casi idéntico (similitud ≥ 0.95) |
| Sustentaciones | Las filas (estudiantes) se agrupan en `sustentaciones`: una por fecha + programa + unidad + promoción + nivel, con su número de estudiantes. `fecha_fin` es la última sustentación |
| Limpieza del título | Espacios y saltos de línea, comillas que lo envuelven y las marcas de modalidad: "EXAMEN COMPLEXIVO" (al inicio o al final) y "CURRICULUM COMPLETO – MSIG – PROM. …". La modalidad pasa a `modalidad`; el original queda en `titulos_originales` |
| **Títulos genéricos: no considerados** | Los que, tras quitar la marca, no dicen nada o solo "FASE 2": "EXAMEN COMPLEXIVO - FASE 2" (2015–2018) y "CURRICULUM COMPLETO - MSIG …" (1998–2002), de 6 directores de la población. **Motivo:** no dicen sobre qué trató el trabajo, así que como texto de embedding serían idénticos entre sí (ruido). Se verificó que no coinciden en director + fecha ni en programa + fecha con ningún complexivo con tema, así que el tema no se puede recuperar. Quedan listados en `registros_no_considerados.csv` |
| Complexivos y currículum con tema | Sí son evidencia (`modalidad: EXAMEN_COMPLEXIVO` o `CURRICULUM_COMPLETO`): cada uno tiene su caso, proyecto o materia, p. ej. "CURRICULUM COMPLETO – MSIG - PROM. II - ESTRUCTURAS DE LA INFORMACIÓN PARA EL WEB" → "ESTRUCTURAS DE LA INFORMACIÓN PARA EL WEB" |
| Codirectores | `codirectores_espol`: otras personas de la población que dirigieron el mismo título; `n_codirectores_espol`: cuántas |
| Texto | `TÍTULO, Nivel: …, Programa: …, Unidad: … (SIGLA)`; varios valores separados por `;` |
| No se usan | Las 251 filas sin director (no se pueden asignar) y `URLACTA` (acta por estudiante en una red interna; ya la quitó la limpieza) |

## PONENCIA (decisiones del usuario, 2026-09-28)

Fuente: `ponentes_todos.csv`, una fila por registro (`IDCAPACITACION`). Es el subconjunto de
capacitaciones con evento de tipo CONGRESO; no se repite en `capacitaciones_todas` ni en
`certificados_todos`, así que no habrá doble conteo con la sección Capacitación. **No hay
título de la ponencia ni tipo de participación**: `NOMBRE` es casi siempre el evento, a veces
el título de la ponencia o una sigla.

| Regla | Detalle |
|---|---|
| Unidad de evidencia | Persona + nombre casi idéntico (similitud ≥ 0.95). Las ediciones del mismo evento ("II" y "III CONGRESO…", CLADEA 2019–2024) quedan juntas |
| Participaciones | Una por fechas + país + modalidad + organizador + certificado + código de área, con su número de registros (varias filas en el mismo congreso suelen ser varias ponencias, pero sin título no se distinguen) |
| Limpieza del nombre | Solo básica: espacios, comillas envolventes (o una comilla suelta en un extremo) y puntuación final. El nombre queda tal cual, sea evento, título o sigla |
| **Asistencias: no consideradas** | `TIPOCERTIFICADO = AS` (asistencia) o "CERTIFICATE FOR ATTENDING…" en el nombre. **Motivo:** asistir no es ser ponente. Nota: un registro "CERTIFICATE FOR PARTICIPATE AS AUTHOR…" viene marcado como asistencia y también queda fuera |
| **No son eventos: no considerados** | Lista explícita revisada a mano: "Coordinadora de Logística" (cargo), "MENTORING PROGRAM" (programa), "PORTAL WAP" (sistema, 2006–2016), "COMITE CONSULTIVO 2023 - CARRERA…" (comité). Los títulos de ponencia, siglas y "CURSO…" se conservan: en esta tabla la persona pudo dictarlos |
| Inicio futuro | No es evidencia; queda en `registros_no_considerados.csv` (hoy no hay casos) |
| Texto | `NOMBRE, Organizado por: …, País: …`. Organizador sin "ESPOL" ("CIBE-ESPOL" → "CIBE"; omitido si solo era ESPOL o si ya está en el nombre; en atributos, tal cual); país solo si es del exterior. Modalidad y horas solo en atributos |
| Fechas | Tal cual; sin `vigente` (evento puntual). Si una participación no tiene fin, cuenta su inicio para `fecha_fin`. Hay rangos anómalos (meses o años) que no se corrigen |
| Horas | `DURACION` = 0 se toma como no declarado (null) |
| Coponentes | `coponentes_espol`: otras personas de la población con el mismo evento y la misma fecha de inicio; `n_coponentes_espol`: cuántas. No implica la misma ponencia |
| Códigos sin catálogo | `codigos_area_capacitacion` (DI, OT, PE) |
| No se copian | `REFARCHIVO1-4`, `NAMEARCHDOC`, `FECHAASCENSO`, `ENESCALAFON` y demás campos administrativos. Las columnas vacías o constantes (`TIPOPARTICIPACION`, `INSTITUCION`, `TIPOEVENTO`…) ya las quitó la limpieza |
