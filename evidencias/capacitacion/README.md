# Evidencias de Capacitación y certificación

Mismo esquema que las demás secciones: `evidencia_id | persona_id | tipo_id | texto | atributos`.
El formato de los atributos está en [../ATRIBUTOS.md](../ATRIBUTOS.md).

- **Ejecución:** `evidencias_capacitacion.ipynb`, o `python -m evidencias.capacitacion.construir`
  (unos 15 segundos).
- **Salidas:** una carpeta por tipo, cada una con sus evidencias, su reporte y sus registros
  no considerados:
  - `data/evidencias/capacitaciones/`: `evidencias_capacitaciones.csv`,
    `reporte_evidencias_capacitaciones.json`, `registros_no_considerados.csv` (`CAPACITACION`).
  - `data/evidencias/certificaciones/`: `evidencias_certificaciones.csv`,
    `reporte_evidencias_certificaciones.json`, `registros_no_considerados.csv` (`CERTIFICACION`).
- **Población:** personas con al menos una evidencia de trayectoria.

| Tipo | Fuente | Qué contiene | Estado |
|---|---|---|---|
| `CAPACITACION` | `capacitaciones_todas.csv` | Cursos, talleres, seminarios, charlas, congresos como asistente, pasantías… (21 tipos de evento) | ✅ |
| `CERTIFICACION` | `certificados_todos.csv` | Certificaciones acreditadas: operador SERCOP, CISCO, CertiProf, auditor ISO… | ✅ |

`capacitaciones_todas`, `certificados_todos` y `ponentes_todos` (sección Investigación) son tablas
distintas del mismo sistema: no comparten `IDCAPACITACION`.

## Reglas comunes (decisiones del usuario, 2026-09-28)

| Regla | Detalle |
|---|---|
| Unidad de evidencia | Persona + nombre casi idéntico (similitud ≥ 0.95, la misma regla que publicaciones y ponencias) |
| Participaciones | Las repeticiones del mismo curso se agrupan en `participaciones`: una por fechas + tipo de evento + país + modalidad + certificador + asistencia/aprobación + códigos, con su número de registros |
| Limpieza del nombre | Solo básica (la de ponencias): espacios, comillas envolventes y puntuación final |
| Texto | `NOMBRE, Tipo: …, Certificado por: …, País: …, Modalidad: …`, solo con lo que existe |
| Certificador en el texto | Sin "ESPOL" ni su nombre largo: "CISE - ESPOL" → "CISE"; si solo era ESPOL, se omite. También se omite si ya está en el nombre. En los atributos queda tal cual |
| País | Solo si es del exterior |
| Solo en atributos | Fechas, horas, asistencia/aprobación, códigos sin catálogo e IDs de origen |
| Horas | `DURACION` = 0 se toma como no declarado (null). Hay valores anómalos (9600, 8760) que se guardan tal cual |
| Fechas | Tal cual. Si una participación no tiene fin, cuenta su inicio para `fecha_fin`. Fechas invertidas: la participación se marca `fechas_inconsistentes` |
| Cursos masivos | `n_personas_mismo_curso`: cuántas personas de la población tienen ese curso (permite bajarle el peso a los muy comunes). Se conservan los masivos técnicos (ISO 50001, Power BI, contratación pública…) |
| Códigos sin catálogo | `codigos_area_capacitacion` (DI, OT, PE, TA, SE) y `codigos_tipo_conocimiento` (-1 a 4) |
| No se copian | `REFARCHIVO*`, `NAMEARCHDOC`, `FECHAASCENSO`, `ENESCALAFON`, `IDUSUARIO`, `ORIGENINGRESO` y demás campos administrativos |

### No son evidencia (quedan en `registros_no_considerados.csv` con su motivo)

| Motivo | Detalle |
|---|---|
| Curso institucional obligatorio sin contenido temático | Lista cerrada revisada con el usuario: Ética pública, Ética en la administración pública, Ética institucional, Ética y valores, Código de ética, Valores en acción, (Re)inducción y Programa de (re)inducción (con o sin año), Inducción para profesores (no titulares), Somos Roca Madre y Perfil Administrativo Politécnico (PAP). **Motivo:** los toma casi todo el personal (Ética pública: 931 personas) y no dicen nada del perfil. **Sí son evidencia** las inducciones a un rol ("Inducción a tutores de prácticas…") y los cursos de ética con tema ("Ética pública y participación ciudadana") |
| Nombre sin tema | "CURSO", "TALLER", "CAPACITACIÓN", "CERTIFICADO", "CERTIFICATE OF PARTICIPATION"… o nombre vacío |
| Registro de título | "CERTIFICADO DE REGISTRO DE TÍTULO" (SENESCYT): no es una certificación; el título ya está en Formación |
| Ya registrado como ponencia | La misma persona + nombre + fecha de inicio ya es evidencia de `PONENCIA`: se registró como ponente y como asistente |
| Ya registrado como certificación | La misma persona + nombre + fecha de inicio ya es evidencia de `CERTIFICACION` |
| Inicio en el futuro | Hoy no hay casos |

## CAPACITACION

- El tipo de evento va al texto ("Tipo: Curso", "Tipo: Pasantía"). "OTROS" no se escribe.
- **La asistencia sí es capacitación:** se conservan asistencias y aprobaciones
  (`tipos_certificado`), a diferencia de ponencias, donde asistir no es ser ponente.
- Sin `vigente`: un curso es un hecho puntual.

## CERTIFICACION

- Sin tipo de evento en el texto (todas son certificaciones).
- `vigente` = la `fecha_fin` aún no llega. En muchas certificaciones esa fecha es el
  **vencimiento** (SERCOP: 2 años; CORFOPYM: 4); en otras es solo el fin del curso. Por eso
  `vigente: false` significa "la fecha de fin ya pasó", no necesariamente "vencida".
