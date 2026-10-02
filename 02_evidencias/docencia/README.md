# Evidencias de Docencia

Fuentes: cuatro extractos de la carga académica en `data/raw/` (`carga_academica_1.csv`,
`cargaacademicadisponible.csv`, `carga_academica_2.csv`, `carga_academica_3.csv`), que juntos
cubren 1998–2026. Mismo esquema que las demás secciones:
`evidencia_id | persona_id | tipo_id | texto | atributos`. El formato de los atributos está en
[../ATRIBUTOS.md](../ATRIBUTOS.md).

- **Ejecución:** `evidencias_docencia.ipynb`, o `python -m evidencias.docencia.construir`.
- **Salidas:** en `data/evidencias/docencia/`:
  - `evidencias_docencia.csv`
  - `reporte_evidencias_docencia.json`
  - `registros_no_considerados.csv`

## DOCENCIA_MATERIA (decisiones del usuario, 2026-09-30, DEC-041)

| Regla | Detalle |
|---|---|
| Población | Solo personas con al menos una evidencia de trayectoria |
| Fuentes | Los cuatro extractos se solapan. Se consolidan por persona + curso + periodo: valores del extracto de mayor prioridad (1 < original < 2 < 3), `NUMREGISTRADOS` el mayor (el extracto antiguo trae 0 en cursos aún sin matrícula), `APROBADO` = S si algún extracto lo aprueba. El archivo 1 es el único con historial anterior a 2017 y no trae `TERM`, nombre de unidad ni `TIPOPROFESOR` |
| Datos personales | Identificación, nombre, correos y la observación libre se descartan al leer |
| Unidad de evidencia | Persona + nombre de materia casi idéntico (≥ 0.95) y con los mismos números sustantivos ("CÁLCULO I" ≠ "CÁLCULO II"). El código cambia con la malla (MECG1022 → MECG1043): los códigos van en una lista |
| Variantes del nombre | El paréntesis final ("MÉTODOS NUMÉRICOS (2005)", "CONTABILIDAD GUBERNAMENTAL (AUDIT.)", "UTILITARIOS AVANZADOS(TN)") marca malla, carrera, jornada o programa, no otra materia. Se quita del nombre y del texto y se guarda en `variantes`; el nombre tal cual queda en `nombres_originales` |
| Periodos | Cada periodo académico: "2021-1S", "2021-2S", "2021-0S" (intensivo), "2005-MOD" (módulo corto de CELEX o de los programas de tecnología) o solo el año si la fuente no trae fechas (11 periodos de 2002–2003). Sin `fecha_inicio`/`fecha_fin`. Los periodos sin `TERM` (antes de 2019) se deducen por sus fechas —la regla acierta en los 23 periodos que sí lo traen— y quedan marcados con `termino_deducido`. `periodos` no repite etiquetas; cada periodo queda en `detalle_periodos` |
| APROBADO | Antes de 2015 vale N en el 100 % de los cursos: solo se registraban los aprobados, así que todos cuentan. Desde 2015 solo cuentan los cursos con S; N o vacío no son evidencia |
| TIPOCURSO | P = paralelo principal, G = componente práctico (paralelos 101, 102…). Interpretación del usuario, coherente con los datos: ninguna materia tiene solo G y las que no tienen práctica solo tienen P. **No** indica grado o posgrado. Va en `componentes` |
| Estudiantes | Se cuentan una vez por paralelo principal (el práctico tiene los mismos) |
| Horas | No se usan: el mismo curso trae horas distintas en cada extracto |
| Texto | `MATERIA, UNIDAD (SIGLA)`; la unidad sin "ESPOL" (si era ESPOL misma, se omite) |
| No son evidencia | Cursos que empiezan después de la fecha de corte, cursos sin nombre y, desde 2015, cursos sin APROBADO = S |
| Nombre | Se quita el sufijo administrativo "-PERMISO UATH" |
| Unidades antiguas sin nombre | Identificadas por el prefijo de sus códigos y sus materias, con el nombre de la facultad actual cuando hay sucesora (confirmado por el usuario): ICM (15010), ICF (15009) e ICQ (15011) → FCNM; FMAR (15006) y 15293 (la antigua FIMCBOR) → FIMCM. Sin sucesora clara conservan su nombre: CELEX (15255), PROTCOM (15258), PROTAL (15257), PROTEL (15259), PROTMEC (15260) y el Programa de Tecnología Pesquera (15261). La 15012 (18 cursos) queda sin unidad. Es el mismo criterio que la fuente aplica a ICHE → FCSH y FIMP → FIMCP |
| Heteroevaluación | No se usa (decisión del usuario): ni la nota ni el historial de materias |

## ACTIVIDAD_CARGA (decisiones del usuario, 2026-09-30, DEC-043)

Fuente: `data/processed/carga_politecnica_disponible.csv` (2013–2026), las actividades no lectivas
de la carga: función de catálogo (`NOMFUNCION`), descripción libre (`DESCFUNCION`), actividad
(D docencia, A gestión, I investigación, V vinculación) y horas.

| Regla | Detalle |
|---|---|
| Función | El nombre de catálogo sin cuotas de horas ni paréntesis; las muy parecidas (≥ 0.88) se unen a la más frecuente (327 nombres → 188 funciones). "CONSEJERÍA ACADÉMICA" = "CONSEJERO ACADÉMICO" |
| Tema | La descripción sin las palabras de la función o del rol al inicio, sin entregables ("INFORME…", "LISTADO DE ESTUDIANTES", "1. …"), requisitos ("AL MENOS DOS PUBLICACIONES…"), cuotas ("1 PAO", "2H"), códigos de actividad ("(GES )") ni lo que sigue a "REPORTA A" (puede nombrar a otra persona). Una sigla o nombre de unidad no es tema |
| Funciones con objeto propio | Coordinador de materia, jefe de laboratorio, responsable de proyecto, comités y coordinaciones de posgrado, material didáctico, seminarios, estudios doctorales… (139 funciones): una evidencia por persona + función + tema (tema casi idéntico y mismos números sustantivos) |
| Funciones de rutina | Consejería, tutorías, investigador por horas, apoyo académico, salidas de campo, exámenes, tribunales (27 funciones): una evidencia por persona + función, con los temas (casi siempre la carrera) en una lista. `n_personas_misma_funcion` permite bajarles el peso |
| Sin tema | La función sola es evidencia ("Investigador", "Diseño de cursos") |
| Códigos de materia | Si el tema es solo un código, se reemplaza por el nombre de la materia de la carga académica ("FISG1006" → "FÍSICA: ELECTRICIDAD Y MAGNETISMO"); si ya trae el nombre, el código se quita ("MUESTREO (ESTG1006)" → "MUESTREO"). El código queda en `codigos_materia`. Solo cuentan los códigos que existen en la carga académica (así "ISO9001" no se toca) |
| Texto | `FUNCIÓN (tema), UNIDAD (SIGLA)`; en rutina, hasta 3 temas separados por `;` |
| Periodos | Lista de años (`anios`); sin `fecha_inicio`/`fecha_fin` |
| Unidades antiguas | Con el nombre de la facultad actual, como en materias: FIMCBOR → FIMCM; institutos y departamentos de ciencias (ICM, ICF, ICQ) → FCNM |
| **Permisos: no son evidencia** | Maternal, lactancia, recién nacido, discapacidad, paternidad, sabático (178 filas). Datos sensibles: en `registros_no_considerados.csv` no se copia ni la función ni la descripción |
| **Situaciones personales en otras funciones** | Si una descripción menciona una situación personal ("QUIEN ESTÁ CON PERMISO POR MATERNIDAD", "TRABAJA HASTA EL … POR…", "SU INCORPORACIÓN DESPUÉS DEL PERMISO…"), el tema se corta ahí. La construcción falla si algún texto final menciona una (`SITUACION_PERSONAL`) |
| No son evidencia | "Asistencia y participación en reuniones…" (genérica); registros de sistema ("ELIMINAR TUTOR…"); año inválido; desde 2015, cargas no aprobadas (antes de 2015 casi todo figura sin aprobar: la aprobación empezó en 2015, misma regla que las materias) |
| Repetidas con trayectoria | Si la misma persona ya tiene la función en `TRAYECTORIA_FUNCION_ADICIONAL` (sin contar subrogaciones), no se repite aquí: autoridades, coordinaciones de carrera, posgrado, prácticas, vinculación y acreditación, consejos directivo y politécnico (3237 filas) |

## Pendiente
- `TIPOPROFESOR` (T / C / S) se guarda sin interpretar; el archivo 1 no lo trae.
- `ACTIVIDAD_CARGA`: la descripción libre puede traer nombres de personas (estudiantes, colegas)
  que no se pueden detectar de forma fiable.
