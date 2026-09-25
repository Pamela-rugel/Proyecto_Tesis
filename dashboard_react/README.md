# Dashboard React — Perfiles de Personal ESPOL

Versión alternativa del dashboard (`notebooks/08_dashboard/app.py`, Streamlit) construida con
React + FastAPI, pensada como interfaz más profesional para presentación/demo. **No reemplaza
el dashboard Streamlit** — ambos leen los mismos datos generados en `data/dashboard/`,
`data/clustering/` y `data/embeddings/` y pueden mantenerse en paralelo.

## Arquitectura

- `backend/` — API FastAPI que reutiliza `notebooks/08_dashboard/lib.py` (misma lógica de carga
  de datos que ya usa Streamlit) y expone los datos como JSON. También corre el modelo de
  embeddings (`BAAI/bge-m3`) para la búsqueda semántica en lenguaje libre.
- `frontend/` — SPA en React + TypeScript + Vite + Tailwind + Plotly, con las mismas 5 vistas del
  dashboard original: Resumen general, Mapa de perfiles, Buscar persona, Formar equipos/comisiones,
  Búsqueda semántica.

## Cómo correrlo

**1. Backend** (desde la raíz del proyecto, usando el `.venv` que ya tiene pandas/sentence-transformers):

```
cd dashboard_react/backend
d:\Proyecto_Tesis\.venv\Scripts\python -m uvicorn main:app --reload --port 8001
```

**2. Frontend** (en otra terminal):

```
cd dashboard_react/frontend
npm install   # solo la primera vez
npm run dev
```

Abrir la URL que imprima Vite (usualmente http://localhost:5173, o 5174 si el 5173 está
ocupado). El frontend apunta a `http://127.0.0.1:8001` por defecto (ver `frontend/.env`,
variable `VITE_API_URL`).

**Si el puerto 8001 (o 5173) ya está en uso:** cambia el puerto al arrancar
(`--port 8002`, o Vite elegirá otro automáticamente) y actualiza `frontend/.env` y la lista
`allow_origins` en `backend/main.py` para que coincidan.

## Notas

- Requiere que los notebooks `06_clustering`, `07_embeddings` y `08_dashboard` ya se hayan
  ejecutado (mismos insumos que usa la app Streamlit).
- El primer request a `/api/buscar` carga el modelo de embeddings en memoria (puede tardar unos
  segundos); las siguientes búsquedas son rápidas.
- Requiere Node.js 20+ para herramientas de testing con navegador (Playwright); Node 18 alcanza
  para desarrollo y build normal.
