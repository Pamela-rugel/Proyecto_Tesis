# Evidencias de Trayectoria

Transforma las salidas ya depuradas de trayectoria (`01_preprocesamiento`, `04_trayectorias`)
en un dataset de **evidencias individuales** con el esquema común de `02_evidencias/esquema.py`:

```
evidencia_id | persona_id | tipo_id | texto | atributos (JSON)
```

Esta etapa **no** genera embeddings ni clustering.

## Ejecución

- Notebook: `evidencias_trayectoria.ipynb` (en esta carpeta).
- Consola (desde la raíz del proyecto): `python -m evidencias.trayectoria.construir`

Salidas en `data/evidencias/trayectoria/`:
- `evidencias_trayectoria.csv`
- `reporte_evidencias_trayectoria.json`: conteos por subtipo, exclusiones y validación.
- `personas_no_consideradas.csv`: personas de la población base que no entran al análisis, con su motivo.

Los atributos `vigente`, `duracion_*` y `es_significativo` dependen de la fecha de ejecución
(`fecha_corte`, registrada en el reporte).

## Estructura

| Archivo | Función |
|---|---|
| `fuentes.py` | carga los CSV depurados y la población (3195 personas); reutiliza `pc` y `ec`; ayudantes de texto |
| `cargo_estructural.py` | `TRAYECTORIA_CARGO_ESTRUCTURAL` |
| `contrato_puntual.py` | `TRAYECTORIA_CONTRATO_PUNTUAL` |
| `funcion_adicional.py` | `TRAYECTORIA_FUNCION_ADICIONAL` (incluye subrogaciones) |
| `experiencia_externa.py` | `TRAYECTORIA_EXPERIENCIA_EXTERNA` |
| `construir.py` | orquesta, aplica las exclusiones finales, valida y guarda |

## Formato de una evidencia (2026-09-27)

- **Fechas en `atributos`:** `fecha_inicio` y `fecha_fin`.
- **Agrupación:** una evidencia agrupa todos los **periodos** del mismo cargo en el mismo
  lugar, aunque haya saltos entre ellos. `fecha_inicio` es el primer inicio y `fecha_fin` el
  último fin, que queda `null` si algún periodo sigue abierto (vigente). En experiencia
  externa, `null` significa "sin fecha de salida registrada".
- **`periodos`:** lista con el detalle de cada periodo (inicio, fin, duración y lo propio de
  ese periodo). Arriba van una sola vez los datos comunes: cargo, unidad y sigla,
  categorías, tipos de empleado, niveles, `n_contratos` total, `n_periodos`, `vigente` y la
  duración total (suma de los periodos).
- **Texto:** sin verbos ni "ESPOL": `cargo, unidad (sigla)`, omitiendo lo que no se conoce.
  No lleva IDs ni fechas.
- **`atributos._origen`:** trazabilidad a la fuente. Toda columna no copiada se recupera desde ahí.
- **Excluido por diseño:** las métricas globales de carrera (entropía, turbulencia, número de
  cambios, estabilidad). Son de la persona, no de una evidencia.

| Subtipo | Una evidencia por | Ejemplo de texto |
|---|---|---|
| Cargo estructural | persona + cargo + unidad | `DECANO(A), DECANATO DE POSGRADO (DPOS)` |
| Contrato puntual | persona + contrato + unidad | `Contrato civil de profesor (posgrado)` · `PROFESOR INVITADO (grado y posgrado), FACULTAD … (FCNM)` · `Contrato de servicios profesionales (actividades de capacitación), DIRECCIÓN DE ADMISIONES (ADM)` |
| Función adicional | persona + tipo de función + unidad | `Decano, FACULTAD DE CIENCIAS NATURALES Y MATEMÁTICAS (FCNM)` · `Coordinador de carrera (Ingeniería Mecánica), FACULTAD … (FIMCP)` |
| Subrogación | persona + rol subrogado + unidad | `Decano (subrogación), FACULTAD DE CIENCIAS DE LA VIDA (FCV)` |
| Experiencia externa | registro (sin agrupar) | `PROFESOR, UNIVERSIDAD SANTA MARIA` · `Asesor Técnico, Pemex Transformación Industrial, México` |

## Reglas de calidad

- **Fechas:** se copian de la fuente; nunca se inventan ni se intercambian. Un fin anterior al
  inicio se corrige en el preprocesamiento: en contratos se ignora ese fin
  (`pc.calcular_fecha_fin_efectiva`) y en experiencia externa se deja vacío (notebook 08). Si
  aun así llega un caso invertido, se marca `fechas_inconsistentes: true`.
- **Periodos continuos:**
  - Cargo estructural: mismo cargo + unidad con recesos de hasta 90 días.
  - Contrato puntual: misma categoría + contrato + unidad + nivel con recesos de hasta 60 días
    (vacaciones entre periodos académicos).

### Registros de un solo día (ruido)

Un cargo de un solo día (inicio = fin) que no es una subrogación se considera ruido: suele ser
un acto administrativo, no un cargo ejercido. Se **marca** en la limpieza y el periodo se
**excluye** de las evidencias:

| Subtipo | Marca (limpieza, notebook 04) | Qué se excluye |
|---|---|---|
| Cargo estructural | `ES_TRAMO_UN_DIA` en `tramos_rol.csv` | el periodo de un solo día. Un tramo de un día pegado a otro del mismo cargo sí da continuidad |
| Contrato puntual | (se evalúa al consolidar) | el periodo de un solo día |
| Función adicional | `ES_DESIGNACION_UN_DIA` en `funciones_adicionales_persona.csv` | la designación de un día |
| Subrogación | — | nada: las subrogaciones de un día se conservan |
| Experiencia externa | — | nada: se conservan |

### Exclusiones finales

- **Inicio en el futuro:** una designación o contrato que todavía no empezó no es trayectoria.
  Cada subtipo descarta esos periodos antes de agrupar.
- **Evidencias idénticas:** si dos evidencias solo difieren en su ID y su `_origen`, se
  conserva una. Si difieren en cualquier atributo, no son idénticas y se conservan ambas.

## Personas no consideradas

Todas las personas de la población base que no entran al análisis se listan, con su motivo,
en `data/evidencias/trayectoria/personas_no_consideradas.csv`. Hay dos grupos.

### Excluidas de todo análisis: identificadas en defunción

Las personas de `data/raw/defunciones_identificadas.txt` no se consideran en **ningún**
análisis (trayectoria, evidencias, clustering, embeddings), con el motivo
`identificada en defunción` (DEC-030). Se quitan al definir la población en
`01_preprocesamiento/07_datos_personales_ultimos_5anios.ipynb`, de donde heredan todos los
notebooks posteriores, y quedan registradas en `data/processed/personas_excluidas.csv`. Como
resguardo, `fuentes.py` también las descarta si el archivo de población estuviera
desactualizado.

### Sin trayectoria

Las personas de la población sin **ninguna** evidencia de trayectoria **no se consideran en
los análisis** basados en trayectoria (perfiles, agrupamiento, búsqueda). No hay información
que describa su experiencia laboral, y un perfil vacío no aporta: las pondría a todas en un
mismo grupo artificial y, en la búsqueda, nunca podrían coincidir con ninguna consulta.

Sus motivos en `personas_no_consideradas.csv`:
- `sin registros de trayectoria en ninguna fuente`: la persona está en la población, pero no
  aparece en contratos, funciones ni experiencia externa.
- `registros descartados por reglas de calidad`: sí tiene registros, pero todos se
  descartaron (p. ej. solo contratos puntuales de un día).

Quien consuma estas evidencias en etapas posteriores debe tomar como población analizable
`persona_id ∈ evidencias_trayectoria.csv`, no la población base completa.

## Atributos por subtipo

### Cargo estructural
Fuente: `data/trayectorias/tramos_rol.csv`, consolidado por cargo + unidad con
`ec.construir_tramos_cargo_unidad_persona` (misma función que genera
`data/embeddings/tramos_cargo_unidad_persona.csv`).

- Arriba: `cargo`, `unidad`, `unidad_sigla`, `categorias_cargo`, `tipos_empleado`,
  `niveles_docencia`, `n_contratos`, `fecha_inicio`, `fecha_fin`, `vigente`, `n_periodos`,
  `duracion_total_anios`.
- Por periodo: `inicio`, `fin`, `duracion_anios`, `es_paralelo` (se solapa con otro cargo de
  la persona), `es_significativo` (dura 3 meses o más), `nivel_docencia`.
- Categoría, tipo de empleado, nivel y contratos salen de las filas de `tramos_rol` que
  forman cada periodo.

### Contrato puntual
Fuente: `data/trayectorias/eventos_puntuales_cargo.csv` (un contrato por fila). La fecha fin
es la efectiva (`pc.calcular_fecha_fin_efectiva`): la desvinculación solo se usa si cae dentro
del contrato.

- Arriba: `contrato`, `contrato_generico`, `unidad`, `unidad_sigla`, `categorias`,
  `tipos_empleado`, `niveles_docencia`, `n_contratos`, fechas, `vigente`, `n_periodos`,
  `duracion_total_anios`.
- Por periodo: `inicio`, `fin`, `duracion_anios`, `n_contratos`, `nivel_docencia`,
  `es_paralelo` (se solapa con un cargo estructural o con otro contrato puntual distinto),
  `es_significativo`.
- **Texto:**
  - Contratos de servicios (categoría de servicios profesionales, o un `CARGO` que solo nombra
    la modalidad): la descripción de la categoría más el detalle que trae el cargo después
    del guion.
  - Contratos de tipo profesor u otra actividad concreta: el texto del contrato con todos sus
    niveles.

### Función adicional / subrogación
Fuente: `data/trayectorias/funciones_adicionales_persona.csv`.

- **Excluidas:** las filas marcadas `ES_REPRESENTANTE_ESTUDIANTIL`, `ES_RUIDO_CALIDAD_DATOS`,
  `ES_DUPLICADO_EXACTO` o `ES_DESIGNACION_UN_DIA`, y las que tienen
  `ES_COINCIDENTE_CONTRATO=True`, porque ya son una evidencia de cargo estructural.
  `incluir_funciones_coincidentes=True` conserva estas últimas.
- **Coordinaciones con nivel:** se marcan `tratado_como_cargo: true` (DEC-025) y sus carreras
  o programas van en el texto.
- Arriba: `funcion`, `es_subrogacion`, `rol_subrogado`, `categoria`, `unidad`,
  `unidad_sigla`, `niveles_funcion`, `carreras_programas`, `tratado_como_cargo`, fechas,
  `vigente`, `n_periodos`, `duracion_total_dias`.
- Por periodo: `inicio`, `fin`, `duracion_dias`, `nivel_funcion`, `nivel_funcion_origen`,
  `detalle_nivel`, `coincide_con_contrato`, `tipo_empleado_durante`, `categoria_cargo_durante`.

### Experiencia externa
Fuente: `data/processed/experiencia_externa.csv`, **ya limpia en el notebook
`01_preprocesamiento/08_experiencia_externa.ipynb`** (`pc.limpiar_experiencia_externa`):
- Se eliminan los registros sin cargo, con cargo de relleno, sin fecha de inicio o que empiezan antes del nacimiento de la persona, además de los duplicados exactos.
- Las instituciones nulas, de relleno o idénticas al cargo pasan a `DESCONOCIDA`.
- Se quitan viñetas y espacios repetidos, y un mismo cargo escrito con distinta capitalización se unifica en mayúsculas.
- Los registros del mismo cargo en la misma institución con fechas solapadas se fusionan.
- Un fin anterior al inicio se deja vacío.

Una fila de la fuente es una evidencia, sin agrupar. El `evidencia_id` usa
`IDHISTORIALABORAL`, que en los registros fusionados es el menor.

- Atributos: `fecha_inicio`, `fecha_fin`, `cargo`, `institucion` (`DESCONOCIDA` → null),
  `pais`, `es_exterior`, `tipo_institucion`, `relacion_laboral`, `tiempo_dedicacion`,
  `categoria_experiencia`, `rol_academico`, `duracion_anios` (solo con fecha de fin) e
  `institucion_es_espol`.
- **Texto:** `cargo, institución`, más el país solo si es del exterior. Si la institución es
  ESPOL o una unidad suya, se le quita "ESPOL" ("CENAIM-ESPOL" → "CENAIM"; si solo era ESPOL,
  queda el cargo).
- **Sin vigencia:** `VIGENTE` no se copia.
- **Qué es ESPOL** (decisión del usuario, 2026-09-29, DEC-040): ESPOL y sus unidades, incluido
  CENAIM (también "Fundación CENAIM-ESPOL"). No son ESPOL las entidades con personería propia
  (ESPOL-TECH E.P., FUNDESPOL, ESPOLTEL, HIDROESPOL, INVENTIO, TRANSESPOL, APESPOL, CONDUESPOL,
  la empresa de radio y TV, los fondos de jubilación, la liga deportiva y las asociaciones): su
  nombre queda completo en el texto. Lista en `experiencia_externa._ENTIDAD_PROPIA`.
- **No se copian** (son códigos o duplicados): `CATEXPERIENCIA`,
  `CATEGORIAEXPERIENCIADESCRIPCION`, `ROLACADEMICO`, `ROLACADEMICOEXPERIENCIA`, `IDPAIS`.

## Pendientes / limitaciones conocidas

- `nivel_docencia` del cargo estructural siempre es `null`. `pc.construir_tramos_rol` genera
  `NIVELDOCENCIA_TRAMO`, pero `pc.resolver_roles_simultaneos` (notebook 04) devuelve una
  lista fija de columnas que no la incluye, así que se pierde antes de guardar
  `tramos_rol.csv`.
- Contratos de docencia de posgrado: la fuente no trae programa ni unidad, así que el texto
  "Contrato civil de profesor (posgrado)" es genérico. El detalle temático tendrá que venir
  de la sección Docencia.
- Contratos anulados (`AN`) y temporalmente inactivos (`TI`) todavía no tienen un
  tratamiento propio en el pipeline.
