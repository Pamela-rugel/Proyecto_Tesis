# Diccionario de evidencias

Este documento explica **cómo se guardan las evidencias** y **qué significa cada atributo**
de cada tipo. Sirve para quien vaya a usarlas en búsqueda, filtros o análisis.

---

## 1. Cómo se guardan

Cada tipo de evidencia se guarda en su propia carpeta, como un CSV (UTF-8 con BOM):

| Tipo (`tipo_id`) | Archivo |
|---|---|
| `TRAYECTORIA_CARGO_ESTRUCTURAL`, `TRAYECTORIA_CONTRATO_PUNTUAL`, `TRAYECTORIA_FUNCION_ADICIONAL`, `TRAYECTORIA_EXPERIENCIA_EXTERNA` | `data/evidencias/trayectoria/evidencias_trayectoria.csv` |
| `FORMACION_TITULO`, `FORMACION_EN_CURSO` | `data/evidencias/formacion/evidencias_formacion.csv` |
| `PROYECTO_INVESTIGACION` | `data/evidencias/investigacion/evidencias_investigacion.csv` |
| `PROYECTO_VINCULACION` | `data/evidencias/vinculacion/evidencias_vinculacion.csv` |
| `PUBLICACION` | `data/evidencias/publicaciones/evidencias_publicaciones.csv` |
| `TESIS_DIRIGIDA` | `data/evidencias/tesis_dirigidas/evidencias_tesis_dirigidas.csv` |
| `PONENCIA` | `data/evidencias/ponencias/evidencias_ponencias.csv` |
| `CAPACITACION` | `data/evidencias/capacitaciones/evidencias_capacitaciones.csv` |
| `CERTIFICACION` | `data/evidencias/certificaciones/evidencias_certificaciones.csv` |
| `IDIOMA` | `data/evidencias/idiomas/evidencias_idiomas.csv` |
| `MENCION_HONOR` | `data/evidencias/menciones_honor/evidencias_menciones_honor.csv` |
| `DOCENCIA_MATERIA`, `ACTIVIDAD_CARGA` | `data/evidencias/docencia/evidencias_docencia.csv` |

Cada carpeta tiene además:
- `reporte_evidencias_*.json`: conteos, exclusiones y validación.
- `registros_no_considerados.csv`: qué se dejó fuera y por qué.

Todos los CSV tienen **las mismas 5 columnas**:

| Columna | Qué es |
|---|---|
| `evidencia_id` | Identificador único de la evidencia. Es estable: la misma evidencia conserva su ID entre corridas |
| `persona_id` | IDPERSONA de la persona a quien pertenece |
| `tipo_id` | Tipo de evidencia (ver secciones abajo) |
| `texto` | Descripción breve en lenguaje natural, pensada para el embedding. No tiene IDs ni fechas |
| `atributos` | Un JSON (como texto) con los datos estructurados de la evidencia |

### Cómo leer los atributos
```python
import json, pandas as pd
ev = pd.read_csv("data/evidencias/publicaciones/evidencias_publicaciones.csv")
ev["attrs"] = ev["atributos"].map(json.loads)            # dict por fila
planos = pd.json_normalize(ev["attrs"].tolist())          # una columna por atributo
```

### Convenciones de los valores
- **`null`** significa que el dato no existe en la fuente. Nunca se inventa un valor.
- **Fechas:** texto `AAAA-MM-DD`.
  - `fecha_inicio` y `fecha_fin` existen en todos los tipos, salvo `IDIOMA` (sin fechas),
    `MENCION_HONOR` (hechos puntuales: lista `fechas`), `DOCENCIA_MATERIA` (semestres: lista
    `periodos`) y `ACTIVIDAD_CARGA` (lista `anios`).
  - Si una evidencia agrupa varios momentos, `fecha_inicio` es el primero y `fecha_fin` el
    último.
  - En cargos y proyectos, `fecha_fin` en null significa **vigente** (sigue en curso). En
    experiencia externa y vinculación sin fechas, significa **desconocido**.
  - En publicaciones, tesis, ponencias y capacitaciones no hay vigencia: son hechos puntuales.
    En certificaciones, `vigente` dice si la `fecha_fin` aún no llega.
- **Listas:** sin repetidos. Si un campo puede tener varios valores (varias unidades, varios
  roles), es una lista aunque tenga uno solo.
- **Detalle anidado:** cuando una evidencia agrupa varias ocurrencias del mismo ítem, el
  detalle de cada una va en una lista de objetos: `periodos` (cargos y proyectos), `versiones`
  (publicaciones), `sustentaciones` (tesis) o `participaciones` (ponencias, capacitaciones y
  certificaciones).
- **`vigente`**, **`duracion_*`** y **`es_significativo`** se calculan con la fecha de
  ejecución (`fecha_corte` en el reporte). Nunca cuentan tiempo futuro.
- **`_origen`:** trazabilidad (archivo fuente e IDs de origen). No está pensado para
  análisis; sirve para volver al registro original.
- **`fechas_inconsistentes: true`** aparece cuando la fuente trae el fin antes del inicio.
  En ese caso la duración queda en null.

---

## 2. Trayectoria

### TRAYECTORIA_CARGO_ESTRUCTURAL
**Qué es:** el rol principal de la persona en ESPOL (nombramiento o contrato continuo).
**Una evidencia =** un cargo en una unidad. Si lo ocupó varias veces con saltos, cada vez es
un periodo.
**Texto:** `CARGO (niveles), UNIDAD (SIGLA)`, por ejemplo `DECANO(A), DECANATO DE POSGRADO (DPOS)`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| cargo | Nombre del cargo tal como lo registra Talento Humano | texto | `"DECANO(A)"` |
| unidad / unidad_sigla | Unidad donde ejerció el cargo y su sigla | texto o null | `"DECANATO DE POSGRADO"` / `"DPOS"` |
| categorias_cargo | Categoría de análisis del cargo (la más reciente primero) | lista de texto | `["AUTORIDAD_ACADEMICA_SUPERIOR"]` |
| tipos_empleado | Docente o administrativo | lista de texto | `["DOCENTE"]` |
| niveles_docencia | Grado y/o posgrado, si se conoce (hoy siempre vacío, ver README) | lista | `[]` |
| n_contratos | Contratos que forman el cargo en total | entero | `12` |
| fecha_inicio / fecha_fin | Primer inicio / último fin (null = sigue vigente) | fecha | `"2017-11-13"` / `null` |
| vigente | Si lo ejerce hoy | bool | `true` |
| n_periodos | Cuántas veces lo ejerció (con saltos entre medio) | entero | `1` |
| duracion_total_anios | Suma de años ejercidos | decimal | `5.0` |
| periodos | Detalle de cada vez | lista de objetos | ver abajo |

**Cada periodo:** `inicio`, `fin`, `duracion_anios`, `es_paralelo` (si coincidió con otro
cargo de la persona), `es_significativo` (si duró 3 meses o más) y `nivel_docencia`.

### TRAYECTORIA_CONTRATO_PUNTUAL
**Qué es:** actividad acotada en ESPOL que convive con el cargo principal: servicios
profesionales, docencia por contrato civil (toda la de posgrado), profesor honorario,
tribunales.
**Una evidencia =** un contrato (mismo nombre) en una unidad. Las renovaciones separadas por
menos de 60 días forman un solo periodo.
**Texto:** el nombre del contrato si es una actividad concreta (`PROFESOR INVITADO (grado),
FACULTAD… (FCNM)`), o una descripción si el contrato solo nombra la modalidad (`Contrato civil
de profesor (posgrado)`, `Contrato de servicios profesionales (actividades de capacitación),
DIRECCIÓN DE ADMISIONES (ADM)`).

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| contrato | Nombre del contrato en la fuente | texto | `"PROFESOR INVITADO"` |
| contrato_generico | Si el nombre solo dice la modalidad ("PRESTACIÓN SERVICIOS PROFESIONALES") | bool | `false` |
| unidad / unidad_sigla | Unidad del contrato | texto o null | `"FACULTAD DE CIENCIAS NATURALES Y MATEMÁTICAS"` / `"FCNM"` |
| categorias | Categoría de análisis del contrato | lista de texto | `["DOCENTE_HONORARIO_ESPECIAL"]` |
| tipos_empleado | Docente o administrativo | lista de texto | `["DOCENTE"]` |
| niveles_docencia | Grado y/o posgrado | lista | `["GRADO"]` |
| n_contratos | Total de contratos (renovaciones) | entero | `4` |
| fecha_inicio, fecha_fin, vigente, n_periodos, duracion_total_anios | Igual que en cargo estructural | | |
| periodos | Detalle de cada periodo | lista de objetos | ver abajo |

**Cada periodo:** `inicio`, `fin`, `duracion_anios`, `n_contratos`, `nivel_docencia`,
`es_paralelo` (si coincidió con un cargo u otro contrato) y `es_significativo`.

### TRAYECTORIA_FUNCION_ADICIONAL
**Qué es:** designaciones del registro de autoridades (director, decano, coordinaciones,
miembro de consejo) y subrogaciones.
**Una evidencia =** un tipo de función en una unidad (o ser subrogante de un tipo de rol en una
unidad). Cada designación es un periodo.
**Texto:** `Coordinador de carrera (Ingeniería Mecánica), FACULTAD… (FIMCP)` o
`Decano (subrogación), FACULTAD DE CIENCIAS DE LA VIDA (FCV)`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| funcion | Función o rol subrogado | texto | `"Coordinador de carrera"` |
| es_subrogacion | Si fue un reemplazo temporal | bool | `false` |
| rol_subrogado | Rol que reemplazó (solo en subrogaciones) | texto o null | `null` |
| categoria | Categoría de análisis de la función | lista de texto | `["JEFATURA_SUPERVISION_OPERATIVA"]` |
| unidad / unidad_sigla | Unidad de la designación | texto o null | `"FIMCP"` |
| niveles_funcion | Grado y/o posgrado (en coordinaciones) | lista | `["GRADO"]` |
| carreras_programas | Carreras o programas que coordinó | lista de texto | `["Ingeniería Mecánica"]` |
| tratado_como_cargo | Si es una coordinación de dedicación continua (se trata como cargo) | bool | `true` |
| fecha_inicio, fecha_fin, vigente, n_periodos | Igual que en cargo estructural | | |
| duracion_total_dias | Suma de días | entero | `321` |
| periodos | Detalle de cada designación | lista de objetos | ver abajo |

**Cada periodo:** `inicio`, `fin`, `duracion_dias`, `nivel_funcion`, `nivel_funcion_origen`
(`"columna"` o `"nombre_cargo"`), `detalle_nivel` (carrera o programa),
`coincide_con_contrato`, `tipo_empleado_durante` y `categoria_cargo_durante` (el cargo que
tenía mientras tanto).

### TRAYECTORIA_EXPERIENCIA_EXTERNA
**Qué es:** experiencia laboral declarada fuera del historial de ESPOL.
**Una evidencia =** un registro (no se agrupa).
**Texto:** `CARGO, INSTITUCIÓN`, más el país solo si es del exterior, por ejemplo `Asesor
Técnico, Pemex Transformación Industrial, México`. Si la institución es ESPOL o una unidad suya,
va sin "ESPOL" (`INSTRUCTOR, CENAIM`; solo el cargo si era ESPOL misma).

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| fecha_inicio / fecha_fin | Inicio y salida (null en fin = **sin fecha registrada**, no significa vigente) | fecha | `"2005-07-01"` / `null` |
| cargo | Cargo declarado | texto | `"PROFESOR"` |
| institucion | Empleador (null si era desconocido) | texto o null | `"UNIVERSIDAD SANTA MARIA"` |
| pais / es_exterior | País y si es fuera de Ecuador | texto / bool | `"ECUADOR"` / `false` |
| tipo_institucion | Pública o privada | texto o null | `"PRIVADA"` |
| relacion_laboral | Tipo de contrato | texto o null | `"CONTRATO CON RELACIÓN DE DEPENDENCIA"` |
| tiempo_dedicacion | Dedicación | texto o null | `"TIEMPO COMPLETO"` |
| categoria_experiencia | Académica o administrativa (69 % "POR CLASIFICAR") | texto o null | `"ACADEMICA"` |
| rol_academico | Rol docente declarado (casi siempre vacío) | texto o null | `"PROFESOR"` |
| duracion_anios | Años (null si no hay fecha de salida) | decimal o null | `5.5` |
| institucion_es_espol | Si la institución declarada es ESPOL o una unidad suya (incluido CENAIM). No lo son ESPOL-TECH, FUNDESPOL, ESPOLTEL y demás entidades con personería propia | bool | `true` |

---

## 3. Formación académica

### FORMACION_TITULO y FORMACION_EN_CURSO
**Qué es:** títulos obtenidos, y estudios no terminados (cursando, egresado, en proceso de
graduación).
**Una evidencia =** un título. Si la persona tiene tercer o cuarto nivel, solo se muestran
esos; si no, el bachillerato; si tampoco, la primaria.
**Texto:** `TÍTULO (estado), INSTITUCIÓN, País, CINE: …, Subárea CINE: …, Frascati: …,
Subárea Frascati: …`. El estado solo aparece en los estudios en curso y el país solo si es
del exterior.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| titulo | Nombre del título | texto | `"Magíster en Telecomunicaciones"` |
| nivel | Nivel educativo | texto | `"CUARTO NIVEL"` |
| grado_academico | Deducido del título (solo en cuarto nivel): DOCTORADO, MAESTRIA, ESPECIALIZACION, OTRO | texto o null | `"MAESTRIA"` |
| estado | Estado en la fuente | texto o null | `"Graduado"`, `"Cursando"` |
| institucion / es_espol | Institución y si es ESPOL | texto / bool | `"ESCUELA SUPERIOR POLITÉCNICA DEL LITORAL"` / `true` |
| pais / es_exterior | País y si es fuera de Ecuador | texto / bool | `"ECUADOR"` / `false` |
| fecha_inicio / fecha_fin | Siempre null / fecha de graduación | fecha | `null` / `"2016-09-23"` |
| area_cine, subarea_cine | Área temática CINE (español) | texto o null | `"Ingeniería, industria y construcción"` |
| area_frascati, subarea_frascati | Área temática Frascati (inglés) | texto o null | `"Engineering and Technology"` |
| validado_th | Si Talento Humano validó el título | bool o null | `true` |
| n_registros_fusionados | Registros duplicados unidos en este título | entero | `1` |

---

## 4. Investigación y producción académica

### PROYECTO_INVESTIGACION
**Qué es:** participación en proyectos de investigación.
**Una evidencia =** un proyecto (por nombre). Si el mismo proyecto tiene varios IDs (fases o
renovaciones), cada uno es un periodo con su propio rol.
**Texto:** `NOMBRE (roles), Tipo de investigación: Aplicada, UNIDAD (SIGLA), Institución
externa: …, País: …, CINE: …, Frascati: …`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| nombre | Nombre del proyecto | texto | `"ESTUDIO DE DEFORMACIÓN DEL TERRENO…"` |
| rol / roles | Rol de mayor jerarquía / todos los roles que tuvo | texto / lista | `"DIRECTOR"` / `["DIRECTOR", "CO-DIRECTOR"]` |
| estado | Estado según la fuente (no define la vigencia) | texto | `"APROBADO Y EN EJECUCIÓN"` |
| tipos_investigacion | Básica, aplicada o desarrollo | lista | `["Aplicada"]` |
| tipos_proyecto | Investigación u otros | lista | `["Investigacion"]` |
| unidades_espol | Unidades de ESPOL participantes, una por elemento (la fuente las trae unidas por comas y se separan) | lista de `{unidad, sigla}` | `[{"unidad": "FACULTAD DE INGENIERÍA EN CIENCIAS DE LA TIERRA", "sigla": "FICT"}]` |
| instituciones_externas | Socios externos, uno por elemento; el lugar queda pegado a su institución | lista de texto | `["UNIVERSIDAD DE GANTE", "UNIVERSIDAD AUSTRAL DE CHILE, VALDIVIA, CHILE"]` |
| paises / es_exterior | Países y si alguno es fuera de Ecuador | lista / bool | `["ECUADOR"]` / `false` |
| financiado_por | Quién financia, uno por elemento | lista de texto | `["ESPOL", "SENESCYT"]` |
| financiamiento_externo | Código de financiamiento (0/1/2, sin catálogo) | lista | `[0]` |
| area_cine, subarea_cine, area_cine_secundaria, subarea_cine_secundaria | Áreas CINE | texto o null | `"Ciencias naturales, matemáticas y estadística"` |
| area_frascati, subarea_frascati, area_frascati_secundaria, subarea_frascati_secundaria | Áreas Frascati | texto o null | `"Natural Sciences"` |
| fecha_inicio, fecha_fin, vigente, n_periodos, duracion_total_anios | Fechas del proyecto (vigencia solo por fechas) | | |
| periodos | Detalle por ID de proyecto | lista de objetos | ver abajo |

**Cada periodo:** `id_proyecto`, `inicio`, `fin`, `duracion_anios`, `vigente`, `rol`,
`roles`, `rol_codigos`, `estado`, `tipo_investigacion`, `tipo_proyecto`, `unidades_espol`,
`instituciones_externas`, `pais`, `es_exterior`, `financiado_por` y `financiamiento_externo`
(las tres listas, de texto).

### PROYECTO_VINCULACION
**Qué es:** participación en proyectos de vinculación con la sociedad.
**Una evidencia =** un proyecto (por nombre, sin el sufijo "(Gastos Generales)").
**Texto:** `NOMBRE, Roles: tutor, director de proyecto, Programa: …`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| nombre | Nombre del proyecto | texto | `"Fortalecimiento a comunidades del Golfo de Guayaquil"` |
| nombres_similares | Otras formas en que aparece el nombre (p. ej. con "(Gastos Generales)") | lista de texto | `["… (Gastos Generales)"]` |
| roles | Tutor, director de proyecto o director de programa | lista | `["TUTOR"]` |
| programas | Programas de vinculación relacionados | lista de texto | `["Programa de crecimiento social y educativo"]` |
| fecha_inicio / fecha_fin | Fechas (null si la fuente no las tiene) | fecha o null | `"2018-03-01"` / `null` |
| vigente | Si está en curso (null = sin fechas, desconocido) | bool o null | `false` |
| n_periodos, duracion_total_anios | Cantidad de IDs y años sumados | entero / decimal o null | `1` / `1.2` |
| codigos_colaboracion | Código de colaboración (sin catálogo) | lista | `[0]` |
| periodos | Detalle por ID de proyecto | lista de objetos | ver abajo |

**Cada periodo:** `id_proyecto`, `nombre_original`, `inicio`, `fin`, `duracion_anios`,
`vigente`, `fechas_inconsistentes`, `roles`, `programa`, `codigo_colaboracion` y `url`.

### PUBLICACION
**Qué es:** artículos, capítulos, libros y artículos de conferencia.
**Una evidencia =** una publicación (por título). Si el mismo título se registró con otro
tipo, lugar o año, cada registro es una versión.
**Texto:** `TÍTULO, Tipo: …, Publicado en: …, Indexación: …`. No lleva cuartiles, factores,
años, ISSN ni participación, que solo están en los atributos.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| titulo | Título | texto | `"ENERGY REPORTS…"` |
| tipos_publicacion | Tipos según la fuente | lista | `["ARTÍCULO CIENTÍFICO (SCOPUS/WOS)"]` |
| participaciones | Autor, coautor, editor… | lista | `["CoAutor"]` |
| publicado_en | Revista, *proceedings* o libro | lista de texto | `["MATERIALS ADVANCES"]` |
| indexada | Si alguna versión está indexada | bool o null | `true` |
| bases_indexacion | Scopus, WoS, Latindex… | lista de texto | `["Scimago Journal Rank (scopus)"]` |
| cuartiles_sjr / cuartiles_citescore | Cuartiles (`Q1`–`Q4`, `SQ`) | lista | `["Q1"]` |
| estados | Publicado o aceptado (vacío si la fuente no lo trae) | lista | `["Publicado"]` |
| anios | Años de publicación | lista de enteros | `[2024]` |
| fecha_inicio / fecha_fin | Siempre null (solo existe el año) | null | `null` |
| n_versiones | Registros distintos de la misma publicación | entero | `1` |
| n_coautores_espol / coautores_espol | Otras personas de la población que registraron la misma publicación | entero / lista de IDPERSONA | `1` / `[60112]` |
| versiones | Detalle de cada registro | lista de objetos | ver abajo |

**Cada versión:** `anio`, `tipo_publicacion`, `participacion`, `publicado_en`, `estado`,
`indexada`, `base_indexacion`, `cuartil_sjr`, `factor_sjr_reportado`, `cuartil_citescore`,
`factor_citescore_reportado`, `revision_pares`, `evento_institucion`, `issn_isbn`, `url` e
`ids_publicacion`. Los factores de impacto se guardan **como texto, tal cual vienen**, porque
la fuente mezcla formatos ("1,980", "1.46", "037").

### TESIS_DIRIGIDA
**Qué es:** trabajos de titulación de posgrado que la persona dirigió, incluidos los exámenes
complexivos con tema. La fuente solo tiene posgrado.
**Una evidencia =** una tesis (por título). Los estudiantes que la sustentaron se agrupan en
`sustentaciones`.
**Texto:** `TÍTULO, Nivel: Maestría profesional, Programa: …, Unidad: … (SIGLA)`. El título ya
viene limpio, sin comillas ni marcas de modalidad ("EXAMEN COMPLEXIVO", "CURRICULUM COMPLETO –
MSIG – PROM. …"). Los títulos que tras la limpieza no tienen tema no son evidencia.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| titulo | Título limpio | texto | `"Diseño de un Manual de Protocolos para la Adquisición de Máquinas de Anestesia"` |
| titulos_originales | Cómo aparece el título en la fuente | lista de texto | `["Diseño de un Manual… - Examen Complexivo"]` |
| modalidad | TRABAJO_DE_TITULACION, EXAMEN_COMPLEXIVO o CURRICULUM_COMPLETO | texto | `"EXAMEN_COMPLEXIVO"` |
| niveles_formacion | Maestría profesional, maestría de investigación o doctorado | lista | `["Maestría Profesional"]` |
| programas | Programa de posgrado | lista de texto | `["Maestría en Ingeniería Biomédica"]` |
| unidades | Unidades del programa | lista de `{unidad, sigla}` | `[{"unidad": "Escuela de Postgrado en Administración de Empresas", "sigla": "ESPAE"}]` |
| fecha_inicio / fecha_fin | Siempre null / última fecha de sustentación | fecha | `null` / `"2024-06-12"` |
| n_sustentaciones | Sustentaciones distintas (fecha, programa, promoción) | entero | `1` |
| n_estudiantes | Estudiantes que la sustentaron en total | entero | `2` |
| promociones | Cohortes | lista de enteros | `[36]` |
| n_codirectores_espol / codirectores_espol | Otras personas de la población que dirigieron la misma tesis | entero / lista de IDPERSONA | `0` / `[]` |
| sustentaciones | Detalle de cada sustentación | lista de objetos | ver abajo |

**Cada sustentación:** `fecha`, `nivel_formacion`, `programa`, `unidad`, `promocion` y
`n_estudiantes`.

### PONENCIA
**Qué es:** participación como ponente en congresos y eventos académicos. La fuente no trae el
título de la ponencia: el nombre es casi siempre el del evento y a veces el de la ponencia o
solo una sigla ("CLADEA", "REDU 2015").
**Una evidencia =** un evento (por nombre casi idéntico y con los mismos números sustantivos).
Sus ediciones y registros repetidos (p. ej. "II" y "III CONGRESO INTERNACIONAL DE BIOTECNOLOGÍA Y
BIODIVERSIDAD") se agrupan en `participaciones`, y los números de edición quedan en `ediciones`.
**Texto:** `NOMBRE, Organizado por: …, País: …`. El organizador va sin "ESPOL" ("CIBE-ESPOL"
→ "CIBE"; si solo era ESPOL, se omite) y se omite si ya aparece en el nombre o si es una variante
de escritura de otro organizador ("ICMME" tras "ICCMME"); el país, si es del exterior. Modalidad y horas solo están en los atributos.
**No son evidencia:** los certificados de asistencia y los registros que no son un evento (un
cargo, un programa, un sistema o un comité); quedan en `registros_no_considerados.csv`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| nombre | Nombre limpio (el más frecuente entre sus registros) | texto | `"DATA SCIENCE, STATISTICS & VISUALISATION 2017 (DSSV 2017)"` |
| nombres_originales | Cómo aparece el nombre en la fuente (incluye otras ediciones) | lista de texto | `["DATA SCIENCE, … 2017 (DSSV 2017)", "DATA SCIENCE, … 2018 (DSSV 2018)"]` |
| ediciones | Años o números de edición de los nombres agrupados | lista de texto | `["II", "III"]`, `["7TH", "2022", "8TH", "2023"]` |
| fecha_inicio / fecha_fin | Inicio de la primera participación / fin de la última (si una no tiene fin, cuenta su inicio) | fecha | `"2017-07-12"` / `"2018-07-11"` |
| n_participaciones | Participaciones distintas (fechas, país, modalidad, organizador) | entero | `2` |
| n_registros | Filas de la fuente agrupadas (puede haber varias en el mismo evento) | entero | `2` |
| paises | Países donde se realizó | lista de texto | `["PORTUGAL", "AUSTRIA"]` |
| es_exterior | Si alguna participación fue fuera de Ecuador | bool | `true` |
| modalidades | VIRTUAL o PRESENCIAL (vacía si la fuente no lo dice) | lista | `["VIRTUAL"]` |
| organizadores | Quién organizó o certificó, texto tal cual | lista de texto | `["Universidad de Sevilla"]` |
| horas_total | Suma de horas declaradas; null si ninguna las declara (0 en la fuente = no declarado) | número o null | `24.0` |
| tipos_certificado | APROBACION cuando la fuente lo indica (las asistencias no son evidencia) | lista | `[]` |
| codigos_area_capacitacion | Código de la fuente DI, OT o PE, sin catálogo | lista | `["DI"]` |
| n_coponentes_espol / coponentes_espol | Otras personas de la población que registraron el mismo evento con la misma fecha de inicio (no necesariamente la misma ponencia) | entero / lista de IDPERSONA | `2` / `[…]` |
| participaciones | Detalle de cada participación | lista de objetos | ver abajo |

**Cada participación:** `fecha_inicio`, `fecha_fin`, `pais`, `modalidad`, `organizador`,
`horas`, `tipo_certificado`, `codigo_area_capacitacion`, `n_registros` e `ids_capacitacion`.
Las fechas se guardan tal cual; algunos registros traen rangos de meses o años para un congreso.

---

## 5. Capacitación y certificación

Los dos tipos comparten reglas y atributos. Una evidencia = un curso o certificación (por
nombre casi idéntico); sus repeticiones se agrupan en `participaciones`.

**Texto:** `NOMBRE, Tipo: …, Certificado por: …, País: …, Modalidad: …`, solo con lo que existe.
- `Tipo:` solo en capacitación ("Curso", "Taller", "Pasantía"…; "OTROS" no se escribe).
- `Certificado por:` sin "ESPOL" ("CISE - ESPOL" → "CISE"); se omite si solo era ESPOL o si ya
  está en el nombre. En los atributos queda tal cual viene.
- `País:` solo si es del exterior.
- Fechas, horas, asistencia/aprobación y códigos solo están en los atributos.

**No son evidencia** (quedan en `registros_no_considerados.csv` con su motivo): los cursos
institucionales obligatorios sin contenido temático (ética pública, valores en acción,
inducción/reinducción, Somos Roca Madre, PAP), los nombres sin tema ("CURSO", "CERTIFICADO"),
el registro de título SENESCYT, y lo que ya es ponencia o certificación.

### CAPACITACION
**Qué es:** cursos, talleres, seminarios, charlas, congresos como asistente, pasantías y demás
formación continua. Incluye asistencias y aprobaciones.

Ejemplo: `JORNADAS DE ACTUALIZACIÓN EN ANTROPOLOGÍA FORENSE, Tipo: Curso, Certificado por: ESCUELA
NACIONAL DE ANTROPOLOGÍA E HISTORIA, País: México`

### CERTIFICACION
**Qué es:** certificaciones acreditadas (operador SERCOP, CISCO, CertiProf, auditor ISO…).

Ejemplo: `SCRUM FOUNDATIONS PROFESSIONAL CERTIFICATE SFPC, Certificado por: CERTIPROF, Modalidad: Virtual`

### Atributos (ambos tipos)

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| nombre | Nombre limpio (el más frecuente entre sus registros) | texto | `"JORNADAS DE ACTUALIZACIÓN EN ANTROPOLOGÍA FORENSE"` |
| nombres_originales | Cómo aparece el nombre en la fuente | lista de texto | `["JORNADAS DE ACTUALIZACIÓN EN ANTROPOLOGÍA FORENSE"]` |
| tipos_evento | **Solo capacitación.** Curso, taller, seminario, congreso… | lista | `["CURSO"]` |
| fecha_inicio / fecha_fin | Inicio de la primera participación / fin de la última (si una no tiene fin, cuenta su inicio) | fecha | `"2013-04-15"` / `"2013-04-19"` |
| vigente | **Solo certificación.** Si la `fecha_fin` aún no llega. A veces esa fecha es el vencimiento (SERCOP: 2 años) y a veces solo el fin del curso | bool o null | `false` |
| n_participaciones | Participaciones distintas (fechas, tipo, país, modalidad, certificador…) | entero | `1` |
| n_registros | Filas de la fuente agrupadas | entero | `1` |
| paises | Países donde se realizó | lista de texto | `["MÉXICO"]` |
| es_exterior | Si alguna participación fue fuera de Ecuador | bool | `true` |
| modalidades | VIRTUAL o PRESENCIAL (vacía si la fuente no lo dice) | lista | `["VIRTUAL"]` |
| certificado_por | Quién certificó, tal cual viene (con "ESPOL" si lo trae) | lista de texto | `["ESCUELA NACIONAL DE ANTROPOLOGÍA E HISTORIA"]` |
| horas_total | Suma de horas declaradas; null si ninguna las declara (0 en la fuente = no declarado). Hay valores anómalos que se guardan tal cual | número o null | `40.0` |
| tipos_certificado | ASISTENCIA o APROBACION | lista | `["ASISTENCIA"]` |
| codigos_area_capacitacion | Código de la fuente DI, OT, PE, TA o SE, sin catálogo | lista | `[]` |
| codigos_tipo_conocimiento | Código de la fuente de -1 a 4, sin catálogo | lista de texto | `["2"]` |
| n_personas_mismo_curso | Cuántas personas de la población tienen un curso con ese mismo nombre. Sirve para bajarle el peso a los muy comunes | entero | `1` |
| participaciones | Detalle de cada participación | lista de objetos | ver abajo |

**Cada participación:** `fecha_inicio`, `fecha_fin`, `tipo_evento`, `pais`, `modalidad`,
`certificado_por`, `horas`, `tipo_certificado`, `codigo_area_capacitacion`,
`codigo_tipo_conocimiento`, `n_registros`, `ids_capacitacion` y, si la fuente trae el fin antes
del inicio, `fechas_inconsistentes: true`.

---

## 6. Idiomas

### IDIOMA
**Qué es:** un idioma que la persona declara, con sus niveles. El español como lengua nativa no
es evidencia; otro idioma marcado como nativo sí.
**Una evidencia =** persona + idioma. Si lo registró varias veces, cada tipo de nivel es una
lista con todos los niveles que declaró, de mayor a menor.
**Texto:** `IDIOMA, Conversación: …, Lectura: …, Escritura: …, MCER: …`, con el mayor nivel
declarado de cada uno y solo con lo que existe, por ejemplo
`INGLÉS, Conversación: intermedio, Lectura: intermedio, Escritura: intermedio, MCER: B2`.
El nivel "Ninguna" nunca se escribe. La comprensión no va al texto (la fuente la llena siempre
con "B" desde 2021).
**Sin fechas:** es el único tipo sin `fecha_inicio` ni `fecha_fin`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| idioma | Nombre del idioma (en "OTRO", el de la descripción, unificado) | texto | `"INGLÉS"` |
| nombres_originales | Cómo aparece en la fuente | lista de texto | `["INGLES"]`, `["OTRO: Kichwa"]` |
| niveles_conversacion, niveles_lectura, niveles_escritura | Todos los niveles autodeclarados, de mayor a menor: AVANZADO, INTERMEDIO, BÁSICO, NINGUNA | lista | `["AVANZADO", "INTERMEDIO"]` |
| niveles_comprension | Tal cual la fuente (casi siempre BÁSICO o vacía; no es fiable) | lista | `["BÁSICO"]` |
| niveles_mcer | Niveles MCER (A1–C2) declarados, de mayor a menor | lista | `["B2"]` |
| es_lengua_nativa | Si algún registro lo marca nativo (null = ningún registro trae el dato) | bool o null | `false` |
| tiene_archivo_respaldo | Si algún registro tiene un documento adjunto | bool | `false` |

---

## 7. Reconocimientos

### MENCION_HONOR
**Qué es:** menciones, premios, distinciones, becas, honores de graduación (cum laude, mejor
egresado), años de servicio y demás reconocimientos declarados. Es un solo tipo: el nombre ya
dice qué es.
**Una evidencia =** persona + nombre casi idéntico y con los mismos números sustantivos
("25 AÑOS" y "30 AÑOS" son evidencias distintas). Las ediciones del mismo reconocimiento (años,
"XV EDICIÓN") sí se agrupan y quedan en `ediciones`. Las veces que la recibió se cuentan en
`n_veces`.
**Texto:** `NOMBRE, Tipo: …, Otorgado por: …, País: …`, solo con lo que existe, por ejemplo
`PREMIO AL MEJOR LIBRO DE TEXTO, Otorgado por: UNIVERSIDAD SIMÓN BOLÍVAR, País: Venezuela`.
La institución va sin "ESPOL" (se omite si solo era ESPOL o si ya está en el nombre) y el país
solo si es del exterior. Las fechas solo están en los atributos, como lista `fechas` (no hay
`fecha_inicio`/`fecha_fin`: una mención no es un periodo).
**No son evidencia:** los registros cuyo nombre de mención es un nombre de persona (dato
personal; el nombre no se copia a `registros_no_considerados.csv`) y "N.A.".

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| nombre | Nombre limpio (el más frecuente entre sus registros) | texto | `"DIPLOMA DE HONOR AL MÉRITO DOCENTE"` |
| nombres_originales | Cómo aparece en la fuente | lista de texto | `["MERITO DOCENTE", "MÉRITO DOCENTE"]` |
| ediciones | Años o números de edición que distinguen las veces que la recibió, tal cual aparecen en el nombre | lista de texto | `["XV", "XVI"]`, `["2005-2006", "2006-2007"]` |
| tipos | MENCIÓN (M) o PREMIO (P) según la fuente; vacía si no lo trae (74 % de los registros) | lista | `["PREMIO"]` |
| n_veces | Cuántas veces la recibió (registros agrupados) | entero | `2` |
| fechas | Cada fecha distinta en que la recibió, de la más antigua a la más reciente (sin las fechas imposibles de la fuente) | lista de fechas | `["2008-10-24", "2011-11-28"]` |
| instituciones | Quién la otorgó, tal cual viene (con "ESPOL" si lo trae) | lista de texto | `["ESPOL"]` |
| paises | País (traducido de `IDPAIS`) | lista de texto | `["ECUADOR"]` |
| es_exterior | Si algún país es fuera de Ecuador | bool | `false` |
| tiene_archivo_respaldo | Si algún registro tiene un documento adjunto | bool | `true` |

---

## 8. Docencia

### DOCENCIA_MATERIA
**Qué es:** una materia que la persona dictó (carga académica, 1998–2026).
**Una evidencia =** persona + nombre de materia casi idéntico y con los mismos números
sustantivos ("CÁLCULO I" y "CÁLCULO II" son evidencias distintas). El paréntesis final del nombre
(malla, carrera o jornada: "(2005)", "(AUDIT.)", "(TN)") no separa materias: va a `variantes`.
Cada periodo académico en que la dictó es un periodo.
**Texto:** `MATERIA, UNIDAD (SIGLA)`, por ejemplo `ECUACIONES DIFERENCIALES, Facultad de Ciencias
Naturales y Matemáticas (FCNM)`. La unidad va sin "ESPOL".
**Sin fechas de inicio y fin:** los periodos van en `periodos`.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| materia | Nombre limpio (el más frecuente entre sus cursos) | texto | `"MATEMÁTICAS FINANCIERAS"` |
| nombres_originales | Cómo aparece en la fuente | lista de texto | `["ECUACIONES DIFERENCIALES (2005)", "ECUACIONES DIFERENCIALES"]` |
| variantes | Contenido del paréntesis final quitado del nombre (malla, carrera, jornada) | lista de texto | `["2005"]`, `["AUDIT."]` |
| codigos | Códigos de la materia (cambian con la malla) | lista de texto | `["ECOG2001", "MATG2008"]` |
| unidades | Unidad que dicta la materia | lista de `{unidad, sigla}` | `[{"unidad": "Facultad de Ciencias Naturales y Matemáticas", "sigla": "FCNM"}]` |
| componentes | PRINCIPAL (paralelo P) y/o PRACTICO (paralelo G: 101, 102…) que dictó. No es grado/posgrado | lista | `["PRINCIPAL", "PRACTICO"]` |
| n_periodos / periodos | Periodos en que la dictó, sin repetir: "2021-1S", "2021-2S", "2021-0S" (intensivo), "2005-MOD" (módulo corto) o solo el año si no hay fechas | entero / lista | `13` / `["2017-1S", "…"]` |
| n_paralelos | Paralelos dictados en total | entero | `32` |
| n_estudiantes_total | Estudiantes registrados, una vez por paralelo principal | entero | `519` |
| es_compartida | Si en algún semestre la compartió con otro docente (porcentaje < 100) | bool | `false` |
| tipos_profesor | Código de la fuente (T, C, S), sin catálogo | lista | `["T"]` |
| detalle_periodos | Detalle de cada semestre | lista de objetos | ver abajo |

**Cada periodo:** `periodo`, `codigos`, `paralelos`, `componentes`, `estudiantes`, `porcentaje`,
`tipos_profesor`, `termino_deducido` (el término se dedujo de las fechas: periodos anteriores a 2019)
e `ids_curso`. Hay uno por periodo académico, aunque dos compartan etiqueta (varios módulos de un año).

### ACTIVIDAD_CARGA
**Qué es:** una actividad no lectiva asignada en la carga politécnica (2013–2026): coordinaciones,
jefaturas de laboratorio, proyectos institucionales, comités, material didáctico, tutorías,
consejerías, investigación por horas…
**Una evidencia =** en funciones con objeto propio, persona + función + tema; en funciones de
rutina, persona + función (los temas, casi siempre la carrera, van en una lista).
**Texto:** `FUNCIÓN (tema), UNIDAD (SIGLA)`, por ejemplo `Jefe de laboratorio de docencia
(CLIMATIZACIÓN Y AIRE ACONDICIONADO), Facultad de Ingeniería en Mecánica y Ciencias de la
Producción (FIMCP)`. En rutina, hasta tres temas separados por `;`.
**No son evidencia:** permisos personales (datos sensibles, no se copian), la asistencia a
reuniones, las cargas no aprobadas desde 2015 y las funciones ya registradas en
`TRAYECTORIA_FUNCION_ADICIONAL`. Los temas se cortan donde la descripción menciona una situación
personal.

| Atributo | Qué significa | Tipo | Ejemplo |
|---|---|---|---|
| funcion | Función normalizada (sin cuotas de horas) | texto | `"Jefe de laboratorio de docencia"` |
| clase_funcion | CON_OBJETO (una evidencia por tema) o RUTINA (temas en lista) | texto | `"CON_OBJETO"` |
| tema | Tema de la evidencia (solo CON_OBJETO; null si no hay) | texto o null | `"CLIMATIZACIÓN Y AIRE ACONDICIONADO"` |
| temas | Temas encontrados, el más frecuente primero, sin repetir | lista de texto | `["OCEANOGRAFÍA"]` |
| codigos_materia | Códigos de materia que la descripción traía; en el texto se muestran con su nombre (enlazan con `DOCENCIA_MATERIA.codigos`) | lista de texto | `["FISG1006"]` |
| funciones_catalogo | Nombres de catálogo agrupados en la función | lista de texto | `["JEFE DE LABORATORIO  DE DOCENCIA (MIN 2H - MAX 5H)"]` |
| actividades | DOCENCIA, GESTION, INVESTIGACION, VINCULACION | lista | `["GESTION"]` |
| unidades | Unidad de la carga | lista de `{unidad, sigla}` | `[{"unidad": "Facultad de Ingeniería en Mecánica y Ciencias de la Producción", "sigla": "FIMCP"}]` |
| niveles | PREGRADO o POSTGRADO | lista | `["PREGRADO"]` |
| anios / n_anios | Años en que la tuvo | lista / entero | `[2024, 2025, 2026]` / `3` |
| horas_total | Suma de horas asignadas (semanales o anuales según `periodicidad` del detalle) | decimal | `15.0` |
| n_personas_misma_funcion | Personas de la población con la misma función (para bajar el peso de las muy comunes) | entero | `778` |
| detalle | Un elemento por año y función: `anio`, `terminos`, `actividad`, `funcion_catalogo`, `tema` (ya limpio; nunca la descripción original), `horas`, `periodicidad`, `nivel` | lista de objetos | |
