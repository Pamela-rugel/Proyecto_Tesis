# Búsqueda semántica de personas: diseño

> Estado: **implementado** el 1 de octubre de 2026 — ver [IMPLEMENTACION.md](IMPLEMENTACION.md) (cambios respecto a este diseño en su §4). Etiquetas usadas:
> **[Decidido]** ya establecido en el proyecto · **[Recomendado]** propuesta de diseño ·
> **[Alternativa]** opción razonable no elegida por ahora · **[Validar]** debe probarse
> experimentalmente antes de afirmarlo en la tesis.

## 1. Problema

Dada una consulta en lenguaje natural ("necesito a alguien con experiencia en IA, proyectos de
investigación en aprendizaje automático y docencia en programación"), devolver **personas**
ordenadas y **explicadas con sus evidencias**. La unidad de representación es la **evidencia
individual** (126 070 evidencias, 17 tipos, 3 164 personas); hay que pasar de evidencias
relevantes a personas completas sin perder granularidad.

## 2. Punto de partida

| Elemento | Estado |
|---|---|
| Evidencia como unidad; embedding `BAAI/bge-m3` (1 024 dim., norma L2 = 1) de cada texto único (87 166) | [Decidido] |
| Fechas **dentro de `atributos`**, con formato distinto por tipo (ver §4.4) | Hecho del dato |
| No mostrar coseno crudo (anisotropía, DEC-020) | [Decidido] |
| Solo vigentes en los resultados; sin filtros por sexo/edad; nombres leídos en vivo | [Decidido] |
| Se puede usar un LLM para interpretar la consulta (proveedor: ver §9) | [Decidido] (usuaria, 01/10) |
| **Búsqueda abierta**: una sola caja de texto; el usuario no elige tipos de evidencia ni otros filtros, todo se interpreta de la consulta | [Decidido] (usuaria, 01/10) |
| **Único filtro visible: vigentes / no vigentes** (por defecto, solo vigentes). Si la consulta lo menciona ("que ya no trabaje en ESPOL", "solo personal vigente"), prevalece la consulta | [Decidido] (usuaria, 01/10) |
| 1 363 vigentes con perfil; ~374 vigentes fuera de la población de evidencias | Hecho; declararlo en resultados |

## 3. Diagnóstico previo (datos reales)

Script de diagnóstico de solo lectura sobre los embeddings existentes. Hallazgos que condicionan
el diseño:

1. **Similitudes concentradas.** Mediana del coseno 0,32–0,43 y máximo 0,62–0,78 según la
   capacidad. Un umbral fijo de coseno no significa lo mismo para dos consultas.
2. **Un corte global calibrado tampoco basta.** Con z ≥ 3 sobre todos los textos quedan 54
   textos para "docencia en cursos de programación" y 1 255 (2 034 personas) para "contratación
   pública": ruido semántico en la cola. Aparecen falsos positivos léxicos ("AUDITOR
   EXPERIMENTADO…" en el puesto 3 de "experiencia en inteligencia artificial").
3. **El volumen sesga hacia tipos débiles.** En el top-200 de "experiencia en IA", 113 son
   capacitaciones (charlas, cursos cortos).
4. **La búsqueda global esconde tipos relevantes.** Materias como *FUNDAMENTOS DE PROGRAMACIÓN*
   quedan en los puestos 126–267 del ranking global de "docencia en programación", detrás de
   experiencia externa y actividades de carga; buscando **solo dentro de materias dictadas**
   salen primeras. Reformular la consulta con un formato que no es el del tipo ("Materia dictada:
   Programación") **empeora** el resultado.
5. **Términos exactos.** Recall de la búsqueda densa sola sobre textos que contienen el término:
   CIBE 42 %, Python 62 %, SENESCYT 82 %, FIEC 88 %, ISO 9001 92 %, GTSI 95 %.
6. **Fechas por tipo.** Trayectoria, proyectos y docencia tienen inicio/fin o periodos;
   publicaciones y actividades de carga solo años; títulos y tesis solo fecha de fin; idiomas y
   formación en curso, nada.

## 4. Arquitectura

```
CONSULTA
  │
  ▼ A. INTERPRETACIÓN AUTOMÁTICA (LLM, salida JSON validada) ─ se muestra "Entendí: …"
  │    capacidades semánticas (+ tipos pertinentes, elegidos por el LLM) · requisitos de persona
  │    · requisitos mixtos · importancia · vigencia (si la consulta la menciona)
  │
  ▼ B. RECUPERACIÓN (retrieval: maximizar recall)
  │    B1 vigencia (filtro de la vista, salvo que la consulta diga otra cosa) + requisitos de
  │       persona extraídos de la consulta → universo de candidatos
  │    B2 por capacidad × tipo de evidencia:
  │         denso exacto + léxico (BM25) → fusión por rangos (RRF)
  │         calibración DENTRO del tipo → evidencias candidatas
  │
  ▼ C. RANKING (ordenar personas con reglas explicables)
  │    C1 puntaje persona × capacidad = mejor evidencia
  │    C2 requisitos mixtos sobre las evidencias relevantes (unión de intervalos)
  │    C3 cobertura de obligatorias → combinación → deseables
  │
  ▼ D. RERANKING (precisión en el top) — cross-encoder local sobre (capacidad, evidencia)
  │
  ▼ E. EXPLICACIÓN — evidencias por capacidad, requisitos verificados, lo que falta
```

### 4.1 Interpretación de la consulta (A)

- **Búsqueda abierta [Decidido]**: el usuario solo escribe la consulta (y, si quiere, cambia el
  filtro vigentes / no vigentes). Todo lo demás lo infiere el sistema.
- **[Recomendado]** LLM con salida estructurada validada contra un esquema (`pydantic`):
  - `capacidades[]`: texto normalizado, importancia (`obligatoria` / `deseable`, inferida del
    lenguaje: "además", "idealmente", "de preferencia"…), **tipos de evidencia pertinentes
    elegidos por el LLM** a partir de un catálogo con la descripción de los 17 tipos y un ejemplo
    real del formato de texto de cada uno, y una **reformulación por tipo en ese formato** (el
    diagnóstico §3.4 muestra que el formato importa).
  - `requisitos_persona`: lo que la consulta pida explícitamente (nivel de formación, idioma y
    nivel). No hay filtros de este tipo en la pantalla.
  - `requisitos_mixtos`: condición estructurada ligada a una capacidad (p. ej. años ≥ 5 de C3).
  - `vigencia`: `vigentes` / `no_vigentes` / `todos` **solo si la consulta lo dice**; si no, se
    usa el filtro de la vista (por defecto, vigentes).
- Al LLM solo se envía **la consulta** y el catálogo de tipos, nunca datos de personas.
- **Transparencia**: la interpretación se muestra como "Entendí: …" (capacidades, tipos en los que
  se buscó cada una, requisitos y vigencia aplicada). No hace falta editarla para buscar.
  **[Alternativa]** permitir corregirla si el usuario lo pide.
- **Respaldo**: si el LLM falla o no responde, la consulta completa se usa como una sola
  capacidad buscada en todos los tipos (calibrada por tipo), sin requisitos estructurados.
- **[Alternativa / línea base]** Sin LLM: la consulta completa como una única capacidad y reglas
  (regex) para años y niveles.
- **Uno vs varios embeddings.** Varios cuando la consulta pide capacidades independientes en
  conjunción; uno cuando es un solo concepto. **[Recomendado]** conservar además la consulta
  completa como canal global. **[Validar]** completa vs descompuesta vs ambas.

### 4.2 Recuperación (B)

- **B1 · Universo de candidatos** (exacto): vigencia (filtro de la vista o lo que diga la
  consulta) y los requisitos de persona que la consulta haya pedido explícitamente.
- **B2 · Por capacidad y por tipo de evidencia** (cambio motivado por §3.3–3.4):
  - **Denso exacto**: producto `V_tipo · q` (sin índice aproximado: 87 166 × 1 024 se resuelve en
    milisegundos; resultado exacto y reproducible).
  - **Léxico**: BM25 sobre los textos (o el modo *sparse* de bge-m3) para siglas y nombres propios
    (§3.5).
  - **Fusión**: Reciprocal Rank Fusion, `Σ 1/(60 + rango)`; combina rangos, no escalas
    incomparables, y no requiere pesos.
  - **Calibración dentro del tipo**: el puntaje de una evidencia se expresa como percentil (o z)
    respecto a todos los textos **de su mismo tipo** para esa capacidad. Así una materia y una
    capacitación compiten cada una en su escala.
  - **[Validar]** el corte de relevancia (p. ej. percentil 99 / 99,5) con el conjunto de
    evaluación, no a ojo; global vs por tipo; denso vs híbrido.

### 4.3 De evidencias a personas (C1)

- **[Recomendado]** puntaje de la persona en la capacidad = **su mejor evidencia** (máximo). No
  premia el volumen (40 capacitaciones parecidas no suman).
- **[Alternativa]** *noisy-OR* sobre puntajes calibrados, `1 − Π(1 − pᵢ)`, contando una sola vez
  los textos repetidos: premio decreciente por evidencias fuertes distintas.
- **[Validar]** máximo vs noisy-OR.

### 4.4 Requisitos mixtos (C2)

- Se evalúan **solo sobre las evidencias relevantes para su capacidad**: se unen sus intervalos
  (sin contar dos veces periodos simultáneos) y se suma la duración.
- **Capa temporal normalizada** (requisito previo a implementar): `inicio`, `fin`, `precision`
  (`dia` / `anio` / `solo_fin` / `sin_fecha`) por evidencia, a partir de `fecha_inicio`,
  `fecha_fin`, `periodos`, `anios` y `fechas` según el tipo (§3.6).
- Sin fechas suficientes → **"no verificable"**, no "no cumple".

### 4.5 Combinación entre capacidades (C3)

- **[Recomendado]** orden lexicográfico:
  1. número de capacidades **obligatorias** cubiertas (cobertura);
  2. a igual cobertura, **media geométrica** de los puntajes calibrados de las obligatorias ("AND
     suave": una capacidad débil arrastra el total, a diferencia de una suma);
  3. las deseables desempatan.
- **[Alternativa]** suma ponderada; RRF entre los rankings por capacidad. **[Validar]** las tres.

### 4.6 Reranking (D)

- **[Recomendado]** cross-encoder local `BAAI/bge-reranker-v2-m3` (multilingüe, sin
  entrenamiento) sobre pares (capacidad, texto) de las mejores evidencias de los N primeros
  (p. ej. 50 personas × 3 evidencias por capacidad). Ataca los falsos positivos léxicos de §3.2.
  Se ejecuta a nivel de evidencia para que reranking y explicación sean coherentes.
- **[Alternativa, no recomendada por ahora]** reranking con LLM: implicaría enviar datos de
  personas (privacidad, normativa ecuatoriana), es caro y menos reproducible.
- **[Validar]** nDCG@10 con y sin reranker.

### 4.7 Explicación (E)

- Por capacidad: 1–3 evidencias que la sustentan (tipo, fecha, unidad) y su posición relativa
  ("entre el 1 % más relevante de las materias dictadas"), nunca el coseno.
- Requisitos verificados (años calculados) y no verificables.
- Capacidades **no** cubiertas.
- Advertencia fija: *ausencia de evidencia ≠ ausencia de capacidad*.
- **[Alternativa]** resumen redactado por un LLM local **solo** a partir de esas evidencias.

## 5. Pesos: qué se pondera y cómo se justifica

Regla general: todo parámetro es **declarado por el usuario**, **calibrado con los datos** o
**elegido con un conjunto de validación**; ninguno se fija a mano.

| Componente | Qué representa | Tratamiento | Justificación / alternativa objetiva | Evaluación |
|---|---|---|---|---|
| Similitud semántica | Ajuste evidencia–capacidad | Percentil dentro del tipo | La escala cruda no es comparable entre consultas ni tipos (§3.1–3.4) | Crudo vs calibrado global vs calibrado por tipo |
| Importancia de la capacidad | Obligatoria / deseable | Lexicográfica, sin números | La infiere el LLM del lenguaje de la consulta ("además", "idealmente") y se muestra en "Entendí: …" | Vs suma con importancias numéricas |
| Cantidad de capacidades cubiertas | Cobertura | Primer criterio del orden | Lexicográfico, sin pesos | Con y sin cobertura primero |
| Tipo de evidencia | Fuerza con que un tipo acredita una capacidad | Tipos pertinentes por capacidad (elegidos automáticamente por el LLM) + calibración por tipo | Evita el sesgo por volumen (§3.3). Alternativa: aprender un peso por tipo con juicios (learning to rank) si hay etiquetas suficientes | Con y sin preferencia de tipo |
| Rareza | Cuán compartido es un texto | **No** en el puntaje | En la búsqueda, todos los que tienen el texto pedido son igual de relevantes; útil solo como matiz en la explicación | Con y sin |
| Evidencia estructurada | Años, niveles, fechas | Restricción, no peso | Es verificable; un peso la volvería negociable | Exactitud sobre muestra revisada |
| Recencia | Actualidad | Solo si la consulta lo pide, como ventana temporal | Por defecto penalizaría trayectorias largas | Consultas con y sin componente temporal |
| Duración | Tiempo sostenido | Dentro de requisitos mixtos (unión de intervalos) | Idem evidencia estructurada | Idem |

## 6. Relación con el clustering

**[Recomendado] Recuperación y ranking independientes del clustering.**

1. Como filtro ("buscar primero el grupo más cercano") perdería a las personas entre dos grupos
   (194 en todo el personal) y propagaría el error de un método no supervisado con k elegido por
   eigengap.
2. El grupo no está condicionado a la consulta: la red fusionada incluye la vista estructurada y
   toda la trayectoria.
3. Componentes independientes se validan por separado.

Usos posteriores al ranking: mostrar el grupo como **contexto**; **"ver personas parecidas"** a
partir de un resultado elegido (30 vecinos en la red fusionada). **[Alternativa a validar]**
diversificar el top por subgrupo (tipo MMR) si resulta útil para conformar comisiones.

## 7. Implementación prevista por etapa

| Etapa | Entrada | Salida | Algoritmo | Librería | Costo aprox. | ¿Entrenamiento? |
|---|---|---|---|---|---|---|
| Interpretación | Consulta | JSON de capacidades y requisitos | LLM con salida estructurada | SDK del proveedor + `pydantic` | 1 llamada, ~1–3 s | No |
| Capa temporal | Atributos | inicio, fin, precisión por evidencia | Reglas por tipo | `pandas` | O(n) una vez | No |
| Embedding de capacidades | Textos de capacidad | Vectores 1 024 | bge-m3 | `sentence-transformers` | ms (GPU) | No |
| Recuperación densa | Vectores | Similitud por texto | Producto matriz-vector exacto | `numpy` | O(87k·1024) por capacidad, ms | No |
| Recuperación léxica | Capacidad | Puntaje BM25 | BM25 | `rank_bm25` (o sparse de bge-m3) | ms | No |
| Fusión y calibración | Rangos por tipo | Percentiles por evidencia | RRF + percentil dentro del tipo | `numpy` | O(n) | No |
| Filtros de persona | Requisitos | Universo de candidatos | Filtro exacto | `pandas` | O(personas) | No |
| Agregación por persona | Evidencias relevantes | Puntaje persona × capacidad | Máximo (alt. noisy-OR) | `pandas` | O(evidencias relevantes) | No |
| Requisitos mixtos | Evidencias relevantes + fechas | Cumple / no / no verificable | Unión de intervalos | `pandas` | O(k log k) por persona | No |
| Ranking | Puntajes | Orden de personas | Lexicográfico + media geométrica | `numpy` | O(p log p) | No |
| Reranking | Top N | Orden refinado | Cross-encoder | `sentence-transformers` (`CrossEncoder`) | ~N·3·caps pares, ~1–2 s GPU | No |
| Explicación | Top final | Texto y evidencias | Plantillas | — | despreciable | No |

Retrieval = A–B; ranking = C; reranking = D.

## 8. Evaluación

1. **Consultas**: 30–50 reales con responsables de talento humano (simples, compuestas, con
   requisitos mixtos y con siglas).
2. **Juicios por *pooling***: unión del top-20 de todas las variantes, calificada 0–2 por
   expertos; acuerdo entre evaluadores (kappa de Cohen).
3. **Métricas**: nDCG@10, P@5, MRR (personas); precisión de las evidencias citadas
   (explicación); recall@K (recuperación).
4. **Known-item automático**: una evidencia real, parafraseada por el LLM, como consulta; se
   mide la posición de su persona. Barato y masivo; mide sobre todo recall.
5. **Ablaciones**: cada [Validar] de este documento.
6. **Sesgos**: distribución de resultados por tipo de empleado y unidad; cuántas personas con
   pocas evidencias aparecen en algún top.

## 9. LLM

**Qué hace el LLM** (y qué no): solo interpreta la consulta (capacidades, tipos pertinentes,
importancia, requisitos, vigencia) y, en la evaluación, parafrasea consultas de prueba. No
puntúa ni ordena personas ni recibe sus datos. Es una tarea corta (≈1–2 mil tokens por
consulta) que exige sobre todo **salida estructurada confiable en español**.

| Opción | Ventajas | Desventajas |
|---|---|---|
| **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`, API de Anthropic) **[Recomendado]** | Rápido y barato (fracciones de centavo por consulta); salida estructurada confiable (JSON por *tool use*); buen español | Requiere cuenta, clave y conexión; servicio externo |
| Claude Sonnet 5 (`claude-sonnet-5`) | Mejor en consultas ambiguas o largas | Más caro y lento; probablemente innecesario para esta tarea |
| GPT de OpenAI | Equivalente en calidad y costo para esta tarea | Mismas consideraciones que Claude |
| Local (Ollama + Qwen 2.5 7B o Llama 3.1 8B, en la RTX 3060) | Gratis, sin enviar nada fuera de la máquina | Salida estructurada menos confiable en español; ocupa la GPU que también usan bge-m3 y el reranker; más trabajo de configuración |

**Criterios para la tesis**: fijar la versión exacta del modelo y `temperature = 0`; guardar
cada consulta con su interpretación (trazabilidad y reproducibilidad); validar la salida contra
el esquema y caer al respaldo sin LLM si falla; código con una interfaz independiente del
proveedor para poder cambiarlo. **[Validar]** en el conjunto de evaluación: calidad de la
interpretación (capacidades y tipos correctos) del modelo elegido frente a la línea base sin LLM.

**Privacidad**: a la API solo va la consulta y el catálogo de tipos. Para parafrasear evidencias
en la evaluación *known-item* se envía el texto de evidencias (sin nombres de personas, pero con
proyectos, unidades, etc.); si eso no es aceptable institucionalmente, esa parte se hace con el
modelo local.

**[Decidido] (usuaria, 01/10): Groq**, plan gratuito (sin costo ni tarjeta), API compatible con
OpenAI, SDK `groq`, clave en la variable de entorno `GROQ_API_KEY` (nunca en el código ni en el
repositorio). Modelo a elegir con una prueba de interpretación sobre consultas de ejemplo entre
los disponibles en la cuenta (candidatos: `llama-3.3-70b-versatile`, `openai/gpt-oss-120b`,
`qwen/qwen3-32b`). Límites de tasa del plan gratuito: respuestas en caché para la evaluación.
Las alternativas de la tabla quedan como respaldo (la interfaz es independiente del proveedor).

**Prueba de interpretación (01/10, 7 consultas variadas, catálogo con ejemplos sintéticos,
esquema JSON estricto, `temperature = 0`, `reasoning_effort = "low"`):**

| Modelo (Groq) | JSON válido | Observaciones |
|---|---|---|
| `openai/gpt-oss-120b` **[Recomendado]** | 7/7 | Separa bien las capacidades de la consulta de ejemplo; detecta "idealmente" → deseable; tipos pertinentes. Junta "contratación pública" + "trabajó en la GTSI" en una sola capacidad |
| `openai/gpt-oss-20b` | 7/7 | Similar, pero marca como obligatoria una capacidad "idealmente"; a veces elige más de 5 tipos; pierde la capacidad "trabajó en la GTSI" |
| `qwen/qwen3.8-27b` | — | Bloqueado a nivel de organización en la cuenta |

Lecciones: sin `reasoning_effort = "low"` la latencia era de 10–35 s y el modelo dejó un campo
obligatorio en `null`; con él, 2–20 s (variabilidad probablemente de la cola del plan gratuito).
Pendiente del prompt: regla explícita para "trabajó en la unidad X" como capacidad separada, y
criterio único para idiomas (requisito estructurado vs capacidad). **[Validar]** con un conjunto
más amplio de consultas de prueba de interpretación.

## 10. Pendiente de definir

- Confirmar `openai/gpt-oss-120b` como modelo de interpretación (clave `GROQ_API_KEY` ya configurada).
- Quién juzga la relevancia y cuántas consultas son realistas.
