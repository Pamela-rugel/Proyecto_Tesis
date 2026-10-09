# Perfiles del personal: clustering multivista (DEC-045)

Agrupa al personal integrando **tres vistas del mismo perfil** con *Similarity Network Fusion*
(SNF), en tres ámbitos independientes: todo el personal, administrativos y docentes. Los
resultados se calculan fuera de línea, se guardan versionados en `data/perfiles/` y la API del
dashboard (`dashboard_react/backend`) solo los lee.

> Explicación completa del proceso, con fórmulas, umbrales, parámetros y el diagrama
> (`img/proceso_multivista.png`): **[METODOLOGIA.md](METODOLOGIA.md)**.

## Ejecución

```
python -m perfiles.embeddings    # embeddings de evidencias con BAAI/bge-m3 (GPU; incremental)
python -m perfiles.construir     # vistas + SNF + clustering + interpretación + t-SNE
```
O el notebook `perfiles/clustering_perfiles.ipynb`. Requiere las evidencias de `data/evidencias/`
y `data/processed/historial_laboral_features.csv` (vigencia y tipo de empleado, DEC-023).

## Datos que usa

| Vista | Contenido | Por persona |
|---|---|---|
| **V1 semántica: trayectoria y gestión** | Embeddings de cargos estructurales, contratos puntuales, funciones adicionales, experiencia externa y actividades de carga | Promedio ponderado por tipo de evidencia y luego entre tipos (L2) |
| **V2 semántica: académico-temática** | Embeddings de títulos, formación en curso, proyectos de investigación y vinculación, publicaciones, tesis, ponencias, materias, capacitaciones, certificaciones y menciones | Igual |
| **V3 estructurada** | ~40 variables agregadas de los `atributos` de las evidencias (`vistas.VARIABLES_ESTRUCTURADAS`): años y categorías de cargo, funciones y autoridad, experiencia externa, nivel de formación, producción académica, docencia, carga por actividad, capacitación, inglés, menciones | Conteos en log1p; estandarizadas dentro de cada ámbito |

- **Embeddings:** cada texto único se embebe una vez (126 070 evidencias → ~87 000 textos). Peso de
  cada evidencia en el promedio: `1 / log2(1 + personas que comparten ese texto)`.
- **Fuera del clustering:** identificadores, campos administrativos, sexo, edad y el tipo
  docente/administrativo (solo define los ámbitos). Los idiomas y los tipos sin tema (IDIOMA)
  entran como variables estructuradas, no como texto.
- **Vigencia y tipo de empleado:** `VIGENTE_ACTUALMENTE` y `TIPOS_EMPLEADO_ACTUALES` (DEC-054: puede ser "ADMINISTRATIVO / DOCENTE" y la persona entra en ambos ámbitos) de
  `historial_laboral_features.csv` (corregidos en DEC-023). El atributo `vigente` de las
  evidencias de trayectoria está inflado y no se usa.

## Método

1. **SNF** (`snf.py`, Wang et al. 2014): una red de afinidad por vista (kernel gaussiano con escala
   local, K = 20 vecinos, μ = 0.5) y difusión cruzada (20 iteraciones) hasta una red fusionada.
   Cada vista conserva su propia métrica y escala; no se concatenan variables.
2. **Clustering espectral** sobre la red fusionada. Número de patrones por *eigengap* (entre 4 y
   12); se reportan silueta y estabilidad por submuestreo (ARI, 10 submuestras del 90 %).
3. **Pertenencia derivada**: afinidad fusionada media de cada persona con los integrantes de cada
   cluster, normalizada. La asignación sigue siendo **exclusiva** (limitación del método);
   la pertenencia solo mide la conexión con los demás grupos. **Perfil mixto**: el segundo
   cluster tiene al menos 0.8 veces la pertenencia del primero.
4. **Por vista**: el cluster con mayor afinidad media en la red de cada vista, para explicar
   si la persona se parece al grupo por su trayectoria, su perfil académico o sus datos.
5. **Representante**: medoide (integrante con mayor afinidad media al resto). Además, centroide
   semántico de V1 y V2 (para la búsqueda).
6. **Interpretación** (`interpretacion.py`): tipos de evidencia sobrerrepresentados, rasgos
   estructurados más alejados del ámbito (σ), evidencias más compartidas, términos distintivos
   (c-TF-IDF) y unidades. La etiqueta se arma solo con esos hechos.
7. **t-SNE** sobre la distancia de la red fusionada: **solo para visualizar**.
8. **Subpatrones (segundo nivel, DEC-046)**: cada patrón con ≥ 150 personas se subdivide
   recalculando SNF **solo con sus integrantes** (mismas tres vistas; escalas de afinidad y
   estandarización de V3 locales al patrón) + clustering espectral, k por eigengap entre 2 y 8
   (tope n/10), con estabilidad ARI propia. Se calculan pertenencia, perfil mixto entre
   subpatrones, medoide y similitud al subrepresentante. Los subpatrones se describen **frente
   a su patrón padre** (los campos `*_ambito` de su ficha contienen los valores del padre).
   En `personas.parquet`: `subpatron` (-1 si el patrón no se subdividió), `subpatron_id`
   ("3.4"), `sub_pertenencia_1/2`, `sub_cluster_2`, `sub_perfil_mixto`, `subrepresentante_id`,
   `es_subrepresentante`, `similitud_subrepresentante`; en `clusters.json`, cada ficha trae
   `subdivision` (k, selección de k, ARI, fichas de subpatrones) o `null`.

## Salidas (`data/perfiles/`)

```
embeddings/            textos.parquet, vectores.npy (float16), manifest.json
clustering/actual.json versión vigente
clustering/<versión>/  manifest.json (huellas de evidencias y embeddings, parámetros)
                       personas_vistas.npz (embeddings de persona V1 y V2)
                       vista_estructurada.parquet
                       <ámbito>/personas.parquet, clusters.json, centroides_v1.npy,
                                centroides_v2.npy, vecinos.parquet (30 vecinos en la red)
```
La versión se nombra con la fecha y la huella de las entradas. **Se recalcula** cuando cambian
las evidencias o los embeddings: `/api/health` compara las huellas y avisa si quedó
desactualizada.

## Preparado para la búsqueda semántica

`consulta → embedding → cluster más cercano (centroides V1/V2) → representante → clusters
vecinos (pertenencias) → candidatos (integrantes y vecinos en la red) → similitud / reranking`.
Los centroides, las pertenencias, los vecinos y los embeddings de persona ya quedan persistidos.
