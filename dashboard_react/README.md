# Dashboard React — Perfiles de Personal ESPOL

**Estado (2026-09-30): esqueleto.** La versión anterior (clustering por persona, embeddings de un
documento por persona y el dashboard Streamlit `notebooks/08_dashboard`) se eliminó: el
clustering y la búsqueda semántica se rehacen sobre las evidencias individuales
(`data/evidencias/`, ver `evidencias/ATRIBUTOS.md`). La versión anterior, con sus páginas y
componentes (línea de tiempo, ficha de persona, mapa), sigue en el historial de git por si se
quieren reutilizar.

## Arquitectura

- `backend/` — API FastAPI. Por ahora solo `/api/health`, que lista las carpetas de evidencias
  disponibles. Los endpoints de clustering y búsqueda se agregarán aquí.
- `frontend/` — SPA en React + TypeScript + Vite + Tailwind (React Query y React Router ya
  configurados). Por ahora una sola página de inicio.

## Cómo correrlo

**1. Backend** (usando el `.venv` del dashboard):

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

El frontend apunta a `http://127.0.0.1:8001` por defecto (`frontend/.env`, `VITE_API_URL`). Si
cambias de puerto, actualiza también `allow_origins` en `backend/main.py`.
