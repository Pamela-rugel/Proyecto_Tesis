# Guion de presentación — Avance de tesis (~5 minutos)

Sistema de Generación de Perfiles del Personal Docente y Administrativo en ESPOL.
Construido exclusivamente a partir de los resultados reales disponibles en
`notebooks/` y `data/` del proyecto (ver fuentes citadas en cada diapositiva).

---

## DIAPOSITIVA 1 — Portada

**Objetivo:** presentarse y ubicar al profesor en el tema en menos de 20 segundos.

**Contenido:** título de la tesis, subtítulo, nombre de la estudiante, ESPOL —
Maestría en Ciencia de Datos e Inteligencia Artificial.

**Qué decir:**
> "Buenas tardes. Esta es una presentación del avance de mi tesis: un sistema para
> generar perfiles del personal docente y administrativo de ESPOL, apoyado en
> clustering y en el procesamiento de su información académica y profesional, con
> el objetivo de apoyar la asignación de tareas y otros procesos de gestión del
> talento."

**Tiempo:** ~15 s

---

## DIAPOSITIVA 2 — El problema y los datos

**Objetivo:** mostrar por qué el problema es real (información dispersa) y de qué
tamaño es el conjunto de datos con el que se trabajó.

**Contenido:** fragmentación de la información en sistemas separados; población de
2.213 personas; 19 fuentes de datos institucionales originales agrupadas en 8
dominios (formación, docencia, investigación, experiencia, capacitación,
vinculación, reconocimientos, carga politécnica); dato destacado sobre volumen de
heteroevaluación (76.645 registros).

**Qué decir:**
> "El punto de partida es un problema concreto: la información de cada persona en
> ESPOL no vive en un solo lugar. Docencia, investigación, capacitación,
> experiencia laboral... cada dominio tiene su propio sistema. Para este proyecto
> integramos 19 fuentes de datos institucionales distintas, correspondientes a una
> población de 2.213 personas que han estado contratadas o vigentes en los
> últimos cinco años. Como referencia de la escala de estos datos: solo la
> heteroevaluación docente aporta más de 76 mil registros individuales para esas
> 2.213 personas."

**Tiempo:** ~40 s

---

## DIAPOSITIVA 3 — De múltiples fuentes a una persona

**Objetivo:** explicar cómo se pasó de 19 tablas sueltas a una tabla integrada por
persona.

**Contenido:** flujo MÚLTIPLES FUENTES → IDPERSONA → INTEGRACIÓN → 1 FILA = 1
PERSONA → CARACTERÍSTICAS; limpieza y tratamiento de faltantes; 11 columnas
descartadas explícitamente (demográficas o redundantes); resultado: 2.213
personas × 85 características.

**Qué decir:**
> "El primer paso técnico es pasar de 19 tablas independientes a una sola fila
> por persona. Usamos IDPERSONA como llave de integración, tratamos los valores
> faltantes de forma explícita, y descartamos 11 columnas que eran demográficas
> —como sexo o edad— o redundantes con otra variable ya incluida, precisamente
> para no introducir sesgos en el perfilamiento. El resultado de esta etapa son
> 2.213 personas caracterizadas con 85 variables que resumen su trayectoria."

**Tiempo:** ~40 s

---

## DIAPOSITIVA 4 — Representación para el modelado

**Objetivo:** explicar por qué las 85 características no son directamente
utilizables por un algoritmo de clustering y qué se hizo al respecto.

**Contenido:** flujo 85 FEATURES → TRANSFORMACIÓN (log1p en 46) → ENCODING
(one-hot/binaria/ordinal) → ESCALAMIENTO (StandardScaler) → 100 FEATURES;
composición de las 85 variables (72 numéricas, 6 categóricas, 4 binarias, 3
excluidas); resultado: 2.213 × 100, 0 nulos, 0 infinitos.

**Qué decir:**
> "Esas 85 variables no se pueden usar directamente en un algoritmo de
> clustering: son de distinto tipo y escala. Por eso las transformamos —log1p en
> 46 variables muy sesgadas—, codificamos las categóricas y estandarizamos todo
> con StandardScaler. El resultado es una matriz de 100 variables para las mismas
> 2.213 personas, sin nulos ni infinitos, lista para calcular distancias entre
> personas de forma consistente."

**Tiempo:** ~35 s

---

## DIAPOSITIVA 5 — Clustering y perfiles

**Objetivo:** justificar la elección de K-Means con K=5 frente a las alternativas
evaluadas, y presentar los cinco perfiles resultantes.

**Contenido:** algoritmos evaluados (K-Means K=2-12, jerárquico Ward K=3-7,
DBSCAN, HDBSCAN); modelo final K-Means K=5; métricas (Silhouette 0.117,
Calinski-Harabasz 326.5, Davies-Bouldin 2.33, ARI entre semillas ≈0.99, ARI vs.
jerárquico ≈0.66); criterio de selección; gráfico de tamaños de cluster (483,
588, 262, 326, 554 personas); los 5 nombres de perfil (síntesis interpretativa
del propio proyecto, no categorías oficiales).

**Qué decir:**
> "Con esa matriz evaluamos varios algoritmos: K-Means de 2 a 12 clusters,
> jerárquico con Ward, DBSCAN y HDBSCAN. Nos quedamos con K-Means, K igual a 5.
> No elegimos el mejor Silhouette —que correspondía a K igual a 2— porque ese
> corte era demasiado grueso y no separaba nada interpretable. K igual a 5, en
> cambio, tiene la mayor estabilidad entre semillas —casi 0.99 de ARI—, buen
> acuerdo con el clustering jerárquico, y grupos balanceados que van del 12% al
> 27% de la población. Estos cinco grupos son los perfiles que se muestran
> aquí."

**Tiempo:** ~45 s

---

## DIAPOSITIVA 6 — Perfiles + tareas/actividades (incluye embeddings)

**Objetivo:** conectar cada perfil con las actividades reales que lo distinguen,
y aclarar qué significa "tarea/actividad" en este proyecto; cerrar con el rol de
los embeddings de texto.

**Contenido:** aclaración de que no se creó una taxonomía de tareas nueva, sino
que se usan las categorías ya registradas (docencia, carga politécnica,
investigación, vinculación, capacitación); las variables distintivas de cada uno
de los 5 perfiles (tomadas de `cluster_top_features.csv` /
`cluster_characterization.csv`); bloque final sobre embeddings: 9 fuentes de
texto, modelo local `paraphrase-multilingual-MiniLM-L12-v2`, cobertura 99,2%, no
fusionado con el clustering estructural (ARI=0,116), carácter exploratorio y
complementario.

**Qué decir:**
> "Aquí es donde el clustering se vuelve útil: no basta con decir 'grupo 2', hay
> que explicar qué caracteriza a cada uno. Para eso usamos las variables de
> actividad que ya trae cada fuente: horas y cursos de docencia, proyectos de
> investigación y vinculación, capacitaciones, carga politécnica institucional.
> No inventamos una taxonomía de tareas nueva. Así, el perfil 1 es claramente
> administrativo, con más de 11 años de experiencia en esa función; el perfil 2
> concentra la mayor producción de investigación y publicaciones; el perfil 3
> tiene la mayor carga docente pura; el perfil 0 tuvo actividad docente relevante
> en el pasado pero ya no está vigente; y el perfil 4 corresponde a personas de
> ingreso reciente. Además, exploramos embeddings de texto sobre publicaciones,
> proyectos y otras fuentes con un modelo local, por privacidad. Cubren al 99%
> de las personas, pero los mantenemos como una representación complementaria:
> no se fusionaron con el clustering estructural, porque el análisis de
> similitud entre ambos agrupamientos mostró que capturan cosas distintas."

**Tiempo:** ~50 s

---

## DIAPOSITIVA 7 — Dashboard y resultado final

**Objetivo:** mostrar el prototipo funcional y cerrar con la conclusión general
del avance.

**Contenido:** captura real de la pestaña "Resumen general" del dashboard
Streamlit; las 6 pestañas realmente implementadas (Resumen general, Explorar
perfiles, Buscar persona, Formar equipos/comisiones, Búsqueda semántica,
Metodología y límites); flujo DATOS → FEATURES → CLUSTERS → PERFILES +
ACTIVIDADES → DASHBOARD; cita de cierre.

**Qué decir:**
> "Todo este análisis se traduce en un prototipo funcional: un dashboard en
> Streamlit con seis pestañas, donde se puede ver la distribución de perfiles,
> explorar qué distingue a cada uno, consultar la ficha de una persona, filtrar
> candidatos para un equipo o comisión sin usar sexo ni edad, y hasta hacer
> búsqueda semántica en lenguaje natural. En resumen: partimos de información
> institucional dispersa en 19 fuentes, y llegamos a una representación
> integrada que permite descubrir perfiles y entender qué actividades
> caracterizan al personal de ESPOL. Muchas gracias."

**Tiempo:** ~40 s

---

## TIEMPO TOTAL ESTIMADO: ~5 MINUTOS

(15 + 40 + 40 + 35 + 45 + 50 + 40 = 265 segundos ≈ 4 min 25 s de discurso, con
margen natural de pausas y transiciones hasta ~5 minutos.)

---

## Notas de trazabilidad (para la estudiante, no para leer en la presentación)

- Todas las cifras provienen de archivos reales del repositorio: `data/raw/`,
  `data/features/dataset_personas_features.csv`, `data/features/feature_dictionary.csv`,
  `data/features/features_excluded.csv`, `data/modeling/preprocessing_summary.csv`,
  `data/modeling/X_modelado.csv`, `data/clustering/clustering_metrics.csv`,
  `data/clustering/evaluacion_k.csv`, `data/clustering/cluster_sizes.csv`,
  `data/clustering/cluster_characterization.csv`,
  `data/dashboard/cluster_perfiles_resumen.csv`,
  `data/dashboard/cluster_top_features.csv`, `data/embeddings/embeddings_metadata.csv`,
  y `context/DECISION_LOG.md` (DEC-001, DEC-002, DEC-003).
- Los nombres de los 5 perfiles (diapositiva 5 y 6) son los que ya definió el
  propio proyecto en `notebooks/07_dashboard/lib.py` (`PERFIL_NOMBRES`,
  `PERFIL_DESCRIPCIONES`) — no se inventaron nombres nuevos para esta
  presentación.
- La captura del dashboard (diapositiva 7) es una captura real, tomada
  ejecutando `notebooks/07_dashboard/app.py` con Streamlit y fotografiando la
  pestaña "Resumen general" — no es un mockup.
- El proyecto no tiene una taxonomía explícita de "tareas": lo que existe son
  variables de actividad agregadas por persona a partir de las categorías ya
  registradas en las fuentes institucionales (por ejemplo, el catálogo interno
  de ~110 tipos de actividad politécnica en
  `data/raw/catalogoactividadescarga.csv`). Esto se explicita en la diapositiva
  6 para no sugerir una clasificación de tareas que el proyecto no construyó.
- Los embeddings de texto se presentan explícitamente como una representación
  **complementaria y exploratoria**, no como una mejora validada del
  clustering, siguiendo la evidencia de DEC-002 (ARI=0,116 entre clusters
  estructurales y clusters de embeddings).
