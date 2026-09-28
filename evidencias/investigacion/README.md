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
- **Población:** personas con al menos una evidencia de trayectoria.

| Tipo | Fuente | Estado |
|---|---|---|
| `PROYECTO_INVESTIGACION` | `proyectos_investigacion_disponible.csv` | ✅ |
| `PROYECTO_VINCULACION` | `proyectos_vinculacion_disponible.csv` | ✅ |
| `PUBLICACION` | `publicaciones.csv` | pendiente |
| `TESIS_DIRIGIDA` | `proyecto_grado.csv` | pendiente |
| `PONENCIA` | `ponentes_todos.csv` | pendiente |

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
