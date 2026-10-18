# Histórico (fuera del flujo actual)

Notebooks y registros del **enfoque anterior**: un dataset de features por persona y una matriz
de modelado para clustering directo. El flujo actual trabaja con evidencias individuales
(DEC-044) y no lee nada de lo que producen estos notebooks. Se conservan como referencia; no hace
falta ejecutarlos.

| Archivo | Qué hacía | Producía |
|---|---|---|
| `01_preprocesamiento_features/02_integracion_datos.ipynb` | Integraba las fuentes de `data/processed/` en una fila por persona | `data/features/dataset_personas_integrado.csv` |
| `01_preprocesamiento_features/03_construccion_features.ipynb` | Construía las features por persona | `data/features/dataset_personas_features.csv` y diagnósticos |
| `01_preprocesamiento_features/05_preparacion_modelado.ipynb` | Matriz numérica imputada y escalada para clustering | `X_modelado.csv`, `personas_modelado.csv` y diagnósticos |
| `logs_rerun/*.log` | Registros de ejecución de esos notebooks (con sus nombres y rutas de entonces) | — |

Sus nombres y rutas internas son los de entonces; no se actualizaron. El flujo vigente está en el
[README principal](../README.md#orden-de-ejecución).
