# Formato de atributos por tipo de evidencia

Esquema común: `evidencia_id | persona_id | tipo_id | texto | atributos (JSON)`.

Convenciones de valores:
- Fechas en ISO `YYYY-MM-DD` o `null`.
- `null` = dato no disponible.
- Listas sin repetidos.
- `_origen` = trazabilidad a la fuente (no es para análisis).

---

## TRAYECTORIA_CARGO_ESTRUCTURAL
Texto: `CARGO (niveles), UNIDAD (SIGLA)`

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| cargo | texto | `"DECANO(A)"` |
| unidad / unidad_sigla | texto \| null | `"DECANATO DE POSGRADO"` / `"DPOS"` |
| categorias_cargo | lista de texto | `["AUTORIDAD_ACADEMICA_SUPERIOR"]` |
| tipos_empleado | lista de texto | `["DOCENTE"]` |
| niveles_docencia | lista (`GRADO`, `POSGRADO`) | `[]` |
| n_contratos | entero | `12` |
| fecha_inicio / fecha_fin | fecha \| null | `"2017-11-13"` / `null` = vigente |
| vigente | bool | `false` |
| n_periodos | entero | `1` |
| duracion_total_anios | decimal | `5.0` |
| periodos | lista de objetos | ver abajo |

`periodos[]`: `{inicio, fin, duracion_anios, es_paralelo: bool, es_significativo: bool, nivel_docencia}`

## TRAYECTORIA_CONTRATO_PUNTUAL
Texto: `CONTRATO (niveles), UNIDAD (SIGLA)` o `Contrato de servicios profesionales (detalle), UNIDAD (SIGLA)`

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| contrato | texto | `"PROFESOR INVITADO"` |
| contrato_generico | bool | `false` |
| unidad / unidad_sigla | texto \| null | `"FACULTAD DE CIENCIAS NATURALES Y MATEMÁTICAS"` / `"FCNM"` |
| categorias | lista de texto | `["DOCENTE_HONORARIO_ESPECIAL"]` |
| tipos_empleado | lista de texto | `["DOCENTE"]` |
| niveles_docencia | lista (`GRADO`, `POSGRADO`) | `["GRADO"]` |
| n_contratos | entero | `4` |
| fecha_inicio / fecha_fin / vigente / n_periodos / duracion_total_anios | igual que en cargo estructural | |
| periodos | lista de objetos | ver abajo |

`periodos[]`: `{inicio, fin, duracion_anios, n_contratos, nivel_docencia, es_paralelo: bool, es_significativo: bool}`

## TRAYECTORIA_FUNCION_ADICIONAL
Texto: `FUNCIÓN (carreras), UNIDAD (SIGLA)` o `ROL (subrogación), UNIDAD (SIGLA)`

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| funcion | texto | `"Coordinador de carrera"` |
| es_subrogacion | bool | `false` |
| rol_subrogado | texto \| null | `null` |
| categoria | lista de texto | `["JEFATURA_SUPERVISION_OPERATIVA"]` |
| unidad / unidad_sigla | texto \| null | `"FACULTAD DE INGENIERÍA MECÁNICA…"` / `"FIMCP"` |
| niveles_funcion | lista (`GRADO`, `POSGRADO`) | `["GRADO"]` |
| carreras_programas | lista de texto | `["Ingeniería Mecánica"]` |
| tratado_como_cargo | bool | `true` |
| fecha_inicio / fecha_fin / vigente / n_periodos | igual que en cargo estructural | |
| duracion_total_dias | entero | `321` |
| periodos | lista de objetos | ver abajo |

`periodos[]`: `{inicio, fin, duracion_dias, nivel_funcion, nivel_funcion_origen: "columna"|"nombre_cargo"|null, detalle_nivel, coincide_con_contrato: bool|null, tipo_empleado_durante, categoria_cargo_durante}`

## TRAYECTORIA_EXPERIENCIA_EXTERNA
Texto: `CARGO, INSTITUCIÓN, País` (el país solo si es del exterior)

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| fecha_inicio / fecha_fin | fecha \| null | `"2005-07-01"` / `null` = sin fecha de salida (no significa vigente) |
| cargo | texto | `"PROFESOR"` |
| institucion | texto \| null | `"UNIVERSIDAD SANTA MARIA"` |
| pais | texto \| null | `"ECUADOR"` |
| es_exterior | bool \| null | `false` |
| tipo_institucion | texto \| null | `"PRIVADA"` |
| relacion_laboral | texto \| null | `"CONTRATO CON RELACIÓN DE DEPENDENCIA"` |
| tiempo_dedicacion | texto \| null | `"TIEMPO COMPLETO"` |
| categoria_experiencia | texto \| null | `"ACADEMICA"` |
| rol_academico | texto \| null | `"PROFESOR"` |
| duracion_anios | decimal \| null | `5.5` (null sin fecha de fin) |
| institucion_es_espol | bool | `false` |

---

## PROYECTO_INVESTIGACION
Texto: `NOMBRE (roles), Tipo de investigación: …, UNIDAD (SIGLA), Institución externa: …, País: …, CINE: …, Subárea CINE: …, CINE secundaria: …, Frascati: …, …`
- El país solo aparece si es del exterior.
- Solo se mencionan las áreas disponibles.

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| nombre | texto | `"ESTUDIO DE DEFORMACIÓN DEL TERRENO…"` |
| rol | `DIRECTOR` \| `CO-DIRECTOR` \| `PARTICIPANTE` | `"DIRECTOR"` (el de mayor jerarquía) |
| roles | lista de texto | `["DIRECTOR", "CO-DIRECTOR"]` |
| estado | texto | `"APROBADO Y EN EJECUCIÓN"` (el de la fuente, periodo más reciente; no define la vigencia) |
| tipos_investigacion | lista (`Aplicada`, `Básica`, `Desarrollo`) | `["Aplicada"]` |
| tipos_proyecto | lista (`Investigacion`, `Otros`) | `["Investigacion"]` |
| unidades_espol | lista de `{unidad, sigla}` | `[{"unidad": "FACULTAD DE INGENIERÍA EN CIENCIAS DE LA TIERRA", "sigla": "FICT"}]` |
| instituciones_externas | lista de texto | `["UNIVERSIDAD DE GANTE"]` |
| paises | lista de texto | `["ECUADOR"]` |
| es_exterior | bool | `false` (true si algún país no es Ecuador) |
| financiado_por | lista de texto | `["ESPOL", "SENESCYT"]` |
| financiamiento_externo | lista de códigos `0`/`1`/`2` | `[0]` (sin catálogo) |
| area_cine / subarea_cine (+ `_secundaria`) | texto \| null | `"Ciencias naturales, matemáticas y estadística"` |
| area_frascati / subarea_frascati (+ `_secundaria`) | texto \| null | `"Natural Sciences"` |
| fecha_inicio / fecha_fin | fecha \| null | `"2018-01-08"` / `"2026-10-01"` |
| vigente | bool | `true` (solo por fechas: sin fin o con fin aún no llegado) |
| n_periodos | entero | `2` (IDs de proyecto con el mismo nombre) |
| duracion_total_anios | decimal | `8.71` |
| periodos | lista de objetos | ver abajo |

`periodos[]`: `{id_proyecto, inicio, fin, duracion_anios, vigente, rol, roles, rol_codigos: [1..4], estado, tipo_investigacion, tipo_proyecto, unidad_espol, institucion_externa, pais, es_exterior, financiado_por, financiamiento_externo}`

## PROYECTO_VINCULACION
Texto: `NOMBRE, Roles: tutor, director de proyecto, Programa: …` (`Programas: A; B` si hay varios)

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| nombre | texto | `"Fortalecimiento a comunidades del Golfo de Guayaquil"` (sin el sufijo "(Gastos Generales)") |
| nombres_similares | lista de texto | `["Fortalecimiento a comunidades del Golfo de Guayaquil. (Gastos Generales)"]` (variantes con contenido distinto) |
| roles | lista (`TUTOR`, `DIRECTOR DE PROYECTO`, `DIRECTOR DE PROGRAMA`) | `["TUTOR", "DIRECTOR DE PROYECTO"]` |
| programas | lista de texto | `["Programa de crecimiento social y educativo"]` |
| fecha_inicio / fecha_fin | fecha \| null | `null` si el proyecto no tiene fechas |
| vigente | bool \| null | `null` = sin fechas (desconocido) |
| n_periodos | entero | `1` |
| duracion_total_anios | decimal \| null | `1.2` |
| codigos_colaboracion | lista de códigos | `[0]` (sin catálogo) |
| periodos | lista de objetos | ver abajo |

`periodos[]`: `{id_proyecto, nombre_original, inicio, fin, duracion_anios, vigente, fechas_inconsistentes: bool, roles, programa, codigo_colaboracion, url}`

---

## FORMACION_TITULO y FORMACION_EN_CURSO
Texto: `TÍTULO (estado), INSTITUCIÓN, País, CINE: …, Subárea CINE: …, Frascati: …, Subárea Frascati: …`
- El estado solo aparece en los estudios en curso.
- El país solo aparece si es del exterior.
- Las áreas solo aparecen si existen.

| Propiedad | Tipo | Ejemplo |
|---|---|---|
| titulo | texto | `"Magíster en Telecomunicaciones"` |
| nivel | `TERCER NIVEL` \| `CUARTO NIVEL` \| `BACHILLERATO` \| `PRIMARIA` | `"CUARTO NIVEL"` |
| grado_academico | `DOCTORADO` \| `MAESTRIA` \| `ESPECIALIZACION` \| `OTRO` \| null | `"MAESTRIA"` (derivado del título; solo en cuarto nivel) |
| estado | texto \| null | `"Graduado"`, `"Cursando"`, `"Egresado"`, `"En proceso de Graduación"`, `"A Prueba"`, `null` |
| institucion | texto \| null | `"ESCUELA SUPERIOR POLITÉCNICA DEL LITORAL"` |
| es_espol | bool | `true` |
| pais | texto \| null | `"ECUADOR"` |
| es_exterior | bool \| null | `false` |
| fecha_inicio | null | siempre `null` (la fuente no la tiene) |
| fecha_fin | fecha \| null | `"2016-09-23"` (fecha de graduación) |
| area_cine / subarea_cine | texto \| null | `"Ingeniería, industria y construcción"` / `"Ingeniería y profesiones afines"` |
| area_frascati / subarea_frascati | texto \| null | `"Engineering and Technology"` / `"Electrical engineering, …"` |
| validado_th | bool \| null | `true` |
| n_registros_fusionados | entero | `1` (más de 1 si se unificaron duplicados) |

`_origen`: `{fuente, id_programa, cod_carrera, registros: [{id_titulacion, titulo, institucion, fecha_graduacion}]}`
