# 07 — Dashboard

Herramienta de exploración de perfiles del personal docente y administrativo de ESPOL. Ver
`07_dashboard.ipynb` para el detalle de la preparación de datos y las decisiones de diseño (DEC-003
en `context/DECISION_LOG.md`).

## Archivos

- `lib.py` — utilidades compartidas (rutas, nombres/descripciones de perfil, carga de datos).
  Usado tanto por el notebook como por la app.
- `07_dashboard.ipynb` — prepara y valida los datasets consolidados en `data/dashboard/`, y
  documenta la búsqueda semántica y el chequeo de equidad demográfica.
- `app.py` — aplicación Streamlit (la herramienta final).

## Entorno

Este notebook/app usa un entorno virtual **aislado** en `d:\Proyecto_Tesis\.venv` (no el intérprete
global usado por los notebooks 01-06), para poder instalar `streamlit`/`plotly` sin conflictos de
dependencias con otras herramientas del sistema (ver DEC-003). Si no existe, créalo con:

```
cd d:\Proyecto_Tesis
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install pandas numpy scikit-learn matplotlib seaborn joblib sentence-transformers streamlit plotly ipykernel nbconvert nbclient
.\.venv\Scripts\python.exe -m ipykernel install --user --name=proyecto-tesis-dashboard --display-name="Proyecto Tesis - Dashboard (.venv)"
```

## Ejecutar la app

```
d:\Proyecto_Tesis\.venv\Scripts\streamlit run notebooks\07_dashboard\app.py
```

Por defecto Streamlit escucha en todas las interfaces de red, no solo en `localhost`. Los datos son
institucionales (aunque las personas solo se identifican por `IDPERSONA`, sin nombres) — si vas a
dejar la app corriendo en una red compartida, arráncala restringida a localhost:

```
d:\Proyecto_Tesis\.venv\Scripts\streamlit run notebooks\07_dashboard\app.py --server.address localhost
```

Un despliegue institucional real (fuera del alcance de este prototipo) requeriría además
autenticación/autorización acorde a los roles de RRHH/decanatos.

## Regenerar los datos del dashboard

Si cambian los resultados de `05_clustering` o `06_embeddings`, vuelve a ejecutar
`07_dashboard.ipynb` completo (con el kernel "Proyecto Tesis - Dashboard (.venv)") para regenerar
`data/dashboard/personas_dashboard.csv`, `cluster_perfiles_resumen.csv` y `cluster_top_features.csv`.
