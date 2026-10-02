# 04 · Búsqueda semántica

Siguiente etapa del proyecto: encontrar **personas** a partir de una consulta en lenguaje
natural, usando como unidad de búsqueda la **evidencia individual** y explicando cada resultado
con las evidencias que lo sustentan.

Estado: **implementado** (paquete `busqueda`, vista React `/busqueda`). Ver
**[IMPLEMENTACION.md](IMPLEMENTACION.md)** (qué se hizo, parámetros, evaluación y ejemplos, con el
diagrama `img/proceso_busqueda.png`) y **[DISENO.md](DISENO.md)** (justificación metodológica).

Resumen del flujo:

    consulta (búsqueda abierta; único filtro: vigentes / no vigentes)
             → interpretación automática (LLM) → capacidades, tipos y requisitos
             → recuperación por capacidad y tipo de evidencia (denso + BM25, calibrado por tipo)
             → relevancia de cada evidencia (cross-encoder sobre el tema)
             → mejor evidencia por persona → requisitos con fechas
             → cobertura y ranking → explicación

La búsqueda es **independiente del clustering** de `03_perfiles`; el grupo de cada persona se
muestra solo como contexto y sus vecinos sirven para "ver personas parecidas" (DISENO.md §6).
Apoyo a la decisión: resultados explicados, sin decisiones automáticas sobre personas.
