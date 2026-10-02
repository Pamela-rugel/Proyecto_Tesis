# Guion de exposición — Resultados (diapositivas 10 a 19)

Cubre la segunda mitad de la presentación completa (Propuesta de proyecto v2):
desde el EDA real de la población hasta la viabilidad. Pensado para leerlo casi
literal mientras se muestra cada diapositiva. Las diapositivas 1-9 (portada,
contexto, justificación, ámbito, objetivos, metodología, fuente de datos,
variables) se asumen ya presentadas antes de este bloque.

---

## DIAPOSITIVA 10 — EDA: ¿Quién compone la población?

**Objetivo:** dejar claro que ya no se trabaja con "candidatos a seleccionar"
sino con el personal real, y mostrar su composición básica.

**Contenido:** dona Docente (68,5%) vs. Administrativo (31,3%) sobre 2.213
personas; roles mixtos 39,6%; vigencia actual solo 30,9%.

**Qué decir:**
> "Empiezo por mostrar quién compone realmente la población de estudio: 2.213
> personas, de las cuales el 68,5% tiene un rol docente y el 31,3% administrativo.
> Dos datos importantes para interpretar todo lo que sigue: primero, el 39,6% del
> personal tiene actividad docente y administrativa registrada al mismo tiempo, es
> decir, los roles no son compartimentos estancos. Segundo, solo el 30,9% está
> vigente actualmente; el resto son trayectorias históricas dentro de la ventana de
> los últimos cinco años que definimos como población de estudio."

**Tiempo:** ~35 s

---

## DIAPOSITIVA 11 — EDA: Hallazgos en Personal (nivel académico y dedicación)

**Objetivo:** mostrar el perfil formativo y de dedicación típico del personal.

**Contenido:** nivel académico máximo (1.540 personas con cuarto nivel, 599 con
tercer nivel, 72 con bachillerato); dedicación docente actual (1.315 tiempo
completo, 234 tiempo parcial, 103 medio tiempo, 10 no aplica).

**Qué decir:**
> "En cuanto a formación, la mayoría del personal tiene título de cuarto nivel:
> 1.540 personas, frente a 599 con tercer nivel. Y en dedicación, el tiempo
> completo es claramente el estándar entre los docentes: 1.315 personas, muy por
> encima del tiempo parcial o medio tiempo. Esto ya empieza a anticipar algo que
> vamos a ver en los perfiles: la institución tiene una base docente
> mayoritariamente de cuarto nivel y tiempo completo."

**Tiempo:** ~30 s

---

## DIAPOSITIVA 12 — EDA: Hallazgos en Personal (cobertura por fuente)

**Objetivo:** mostrar qué tan completa es la información según el dominio, y
justificar por qué el modelo tolera datos faltantes en vez de descartar personas.

**Contenido:** % de personas con al menos un registro por fuente: formación y
historial laboral 100%, capacitaciones 91%, experiencia externa 82%, idiomas 75%,
carga politécnica 68%, certificaciones 51%, investigación 47%, docencia 46%,
heteroevaluación 45%, reconocimientos 43%, publicaciones 37%, vinculación 19%,
dirección de tesis 18%, ponencias 17%.

**Qué decir:**
> "No toda la información está igual de completa para todas las personas. Formación
> e historial laboral cubren al 100%, porque son datos base de cualquier contrato.
> Pero en el otro extremo, dirigir una tesis, ser ponente o participar en proyectos
> de vinculación son actividades que solo entre el 17% y el 19% del personal tiene
> registradas. Esto no es un error de los datos: refleja que son actividades menos
> frecuentes por naturaleza. Por eso el modelo no descarta a quien no las tiene,
> sino que las trata como cero o como dato ausente de forma explícita."

**Tiempo:** ~40 s

---

## DIAPOSITIVA 13 — EDA: Hallazgos en Personal (tipos de capacitación)

**Objetivo:** caracterizar cómo se capacita el personal.

**Contenido:** top 10 tipos de evento de capacitación; curso domina ampliamente
(~31.000 registros), seguido de taller (~9.000) y seminario (~8.500); congreso,
conferencia y otros formatos con volumen mucho menor.

**Qué decir:**
> "Cuando miramos cómo se capacita el personal, el curso es, por lejos, el formato
> más común, con más de 31 mil registros. Le siguen los talleres y seminarios. Hay
> personal que también asiste a congresos y conferencias, pero en un volumen mucho
> menor. Esta variable la usamos más adelante como parte de la trayectoria de
> capacitación de cada persona, no solo como conteo total."

**Tiempo:** ~25 s

---

## DIAPOSITIVA 14 — Relaciones Clave (correlaciones)

**Objetivo:** mostrar qué variables se mueven juntas, como insumo para entender
por qué ciertas variables terminan agrupadas en los mismos perfiles.

**Contenido:** matriz de correlación de indicadores representativos; investigación
y publicaciones correlacionan positivamente; carga politécnica correlaciona
positivamente con proyectos de investigación; reconocimientos y capacitaciones
tienen una correlación positiva débil.

**Qué decir:**
> "Antes de modelar, revisamos cómo correlacionan las variables entre sí. Encontramos
> una relación positiva clara entre proyectos de investigación y publicaciones —algo
> esperable—, y también entre la carga politécnica y el número de proyectos de
> investigación, lo que sugiere que quienes participan en gestión institucional
> también suelen estar en proyectos formales. La relación entre reconocimientos y
> capacitaciones es positiva pero débil. Ninguna correlación es tan alta como para
> considerar variables redundantes entre sí; las únicas que sí eliminamos por
> redundancia fueron duplicados casi exactos, documentados aparte."

**Tiempo:** ~35 s

---

## DIAPOSITIVA 15 — Preparación y transformación de datos

**Objetivo:** explicar el paso de datos limpios a una matriz numérica lista para
clustering.

**Contenido:** limpieza y tratamiento de faltantes (imputación por mediana/moda o
marcador "sin dato"); 15 columnas descartadas (demográficas o redundantes);
agregación de trayectoria en conteos, sumas y proporciones; flujo 85 FEATURES →
TRANSFORMACIÓN (log1p en 46 variables) → ENCODING (one-hot/binaria/ordinal) →
ESCALAMIENTO (StandardScaler) → 100 FEATURES FINALES; resultado 2.213 × 100.

**Qué decir:**
> "Con esa base de datos limpiamos y tratamos los faltantes de forma explícita,
> descartamos 15 columnas por ser demográficas —como sexo, edad u origen— o
> redundantes con otra variable ya incluida, y agregamos toda la trayectoria
> histórica en conteos, sumas y proporciones por persona. De ahí salen 85
> características. Pero un algoritmo de clustering no puede trabajar directo con
> eso: aplicamos log1p a 46 variables muy sesgadas, codificamos las categóricas y
> escalamos todo con StandardScaler. El resultado final es una matriz de 2.213
> personas por 100 variables, sin nulos ni valores infinitos."

**Tiempo:** ~40 s

---

## DIAPOSITIVA 16 — Modelado: algoritmos evaluados

**Objetivo:** justificar la elección de K-Means frente a las alternativas.

**Contenido:** cuatro tarjetas — Jerárquico (Ward): evaluado K=3-7, usado como
contraste de estabilidad (ARI=0,66); DBSCAN/HDBSCAN: descartados por dejar más de
90% de los registros como ruido, o colapsar en un solo cluster; K-Means (K=5):
elegido, mejor estabilidad entre semillas (ARI=0,99), mejor acuerdo con
jerárquico, tamaños balanceados; K-Means sobre embeddings: complementario, no
fusionado (ARI=0,116 frente al clustering estructural).

**Qué decir:**
> "Sobre esa matriz probamos varios algoritmos. El jerárquico con Ward lo usamos
> como punto de contraste, no como modelo final. DBSCAN y HDBSCAN los descartamos
> porque, en 100 variables dispersas, con parámetros exigentes dejan más del 90% de
> los registros como ruido, y con parámetros laxos colapsan todo en un solo grupo:
> ninguno de los dos extremos es útil. El modelo elegido es K-Means con K igual a
> 5, por tener la mayor estabilidad entre semillas y buen acuerdo con el jerárquico.
> Además exploramos K-Means sobre los embeddings del texto profesional, pero es una
> representación complementaria: no la fusionamos con el clustering estructural
> porque miden cosas distintas."

**Tiempo:** ~45 s

---

## DIAPOSITIVA 17 — Cluster: los cinco perfiles

**Objetivo:** presentar el resultado final del modelo con sus tamaños y nombres.

**Contenido:** barras con el tamaño de cada perfil (483, 588, 262, 326, 554
personas); nombres: Perfil 0 docente de trayectoria histórica moderada (21,8%),
Perfil 1 administrativo (26,6%), Perfil 2 alta producción académica e
investigativa / liderazgo integral (11,8%), Perfil 3 alta carga docente (14,7%),
Perfil 4 ingreso reciente / trayectoria corta (25,0%); criterio de selección de K.

**Qué decir:**
> "Este es el resultado: cinco perfiles, con tamaños que van de 262 a 588 personas,
> es decir, entre el 12% y el 27% de la población, sin grupos extremadamente
> pequeños. El perfil 1 es administrativo; el perfil 3 concentra la mayor carga
> docente; el perfil 2 es el de mayor producción académica e investigativa; el
> perfil 0 tuvo actividad docente relevante en el pasado pero ya no está vigente; y
> el perfil 4 son personas de ingreso reciente. Elegimos K igual a 5 porque, aunque
> K igual a 2 tenía mejor Silhouette, era un corte demasiado grueso y no
> interpretable. K igual a 5 combina estabilidad, acuerdo con el jerárquico y
> tamaños balanceados. Es importante remarcar: estos nombres son una síntesis
> interpretativa nuestra, no categorías institucionales oficiales."

**Tiempo:** ~45 s

---

## DIAPOSITIVA 18 — Herramienta de exploración (dashboard)

**Objetivo:** mostrar que el análisis se tradujo en un prototipo usable.

**Contenido:** captura real de la ficha de una persona con gráfico de radar
(percentiles frente a la institución); cinco funcionalidades: resumen general,
explorar perfiles, buscar persona, formar equipos/comisiones, búsqueda semántica.

**Qué decir:**
> "Todo este análisis no se queda en el notebook: lo llevamos a un dashboard en
> Streamlit. Esta captura es real, no un mockup: es la ficha de una persona con su
> perfil asignado y un gráfico de radar que la compara por percentil contra el resto
> de la institución en variables como horas de docencia, publicaciones o proyectos.
> El dashboard tiene cinco funciones: un resumen general de los perfiles, la
> exploración de qué variables distinguen a cada uno, la búsqueda de una persona
> específica, un filtro para formar equipos o comisiones —sin usar sexo ni edad—, y
> una búsqueda semántica en lenguaje natural sobre los embeddings de texto."

**Tiempo:** ~40 s

---

## DIAPOSITIVA 19 — Viabilidad (cierre)

**Objetivo:** cerrar la exposición confirmando que el proyecto ya es un pipeline
funcional, no solo un plan.

**Contenido:** disponibilidad de datos confirmada; viabilidad técnica: pipeline de
ETL, feature engineering, embeddings y clustering ya implementados y
ejecutándose sobre datos reales; viabilidad operativa: validación con expertos
institucionales como siguiente paso.

**Qué decir:**
> "Para cerrar: la viabilidad de este proyecto ya no es una promesa, es un hecho.
> Los datos están disponibles y ya integrados. La parte técnica —ETL, feature
> engineering, embeddings de texto y clustering— está implementada y corriendo
> sobre datos reales, no sobre una simulación. Lo que queda pendiente, y es el
> siguiente paso, es la validación cualitativa formal con expertos institucionales
> de Talento Humano, para contrastar estos cinco perfiles con su criterio y ajustar
> lo que haga falta. Con esto termino esta sección de resultados. Gracias."

**Tiempo:** ~35 s

---

## TIEMPO TOTAL ESTIMADO (diapositivas 10-19): ~6 min 10 s

(35 + 30 + 40 + 25 + 35 + 40 + 45 + 45 + 40 + 35 = 370 segundos, con margen
natural de pausas y transiciones.)

---

## Notas de trazabilidad (para la estudiante, no para leer en la presentación)

- Todas las cifras de este bloque provienen de los mismos archivos ya usados en
  el resto del proyecto: `data/features/dataset_personas_features.csv`,
  `data/features/features_excluded.csv`, `data/modeling/preprocessing_summary.csv`,
  `data/modeling/X_modelado.csv`, `data/clustering/clustering_metrics.csv`,
  `data/clustering/evaluacion_k.csv`, `data/clustering/cluster_sizes.csv`,
  `data/clustering/cluster_characterization.csv`, `data/embeddings/embeddings_metadata.csv`
  y `context/DECISION_LOG.md` (DEC-001, DEC-002, DEC-003).
- La diapositiva 12 (cobertura por fuente) y la 13 (tipos de evento de
  capacitación) y la 14 (correlaciones) no estaban en el guion anterior de 7
  diapositivas: son hallazgos adicionales de esta versión más extensa de la
  presentación. Si te preguntan de dónde salen, son del EDA sobre
  `dataset_personas_features.csv` y `capacitaciones_todas.csv`.
- La diapositiva 18 muestra las 5 pestañas reales del dashboard (no 6): ya no
  incluye una pestaña separada de "Metodología y límites", que no existe en
  `notebooks/07_dashboard/app.py`.
- Si un evaluador pregunta por qué no se fusionaron los embeddings con el
  clustering (diapositiva 16), la respuesta corta es: se midió la
  complementariedad con ARI y dio 0,116 — son representaciones que capturan
  cosas distintas, y fusionarlas sin más análisis (reducción de dimensionalidad,
  ponderación) podría diluir la señal estructural que ya funciona.
