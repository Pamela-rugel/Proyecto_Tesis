# === BASE ===
FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# === DEPENDENCIAS ===
FROM base AS deps
COPY dashboard_react/backend/requirements.txt .
ENV PYTHONPATH=/install/lib/python3.11/site-packages
# torch se instala aparte, desde el indice CPU-only de PyTorch (el build normal de PyPI
# trae CUDA/drivers nvidia, ~3GB extra innecesarios sin GPU). PYTHONPATH apuntando al mismo
# --prefix en ambos comandos es necesario para que pip vea ese torch ya instalado y no lo
# vuelva a resolver contra el PyPI normal al instalar sentence-transformers (que lo pide
# como dependencia transitiva sin version fija) - bug real: sin esto, el segundo pip
# install no detectaba el torch ya instalado y redescargaba la variante CUDA completa.
RUN python -m pip install --upgrade pip \
    && python -m pip install --prefix=/install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 \
    && python -m pip install --prefix=/install -r requirements.txt

# === RUNTIME ===
FROM base AS runtime
COPY --from=deps /install /usr/local

ENV HF_HOME=/app/.cache/huggingface

# Pre-descarga el modelo de embeddings durante el build (no en el primer request) - evita
# que el contenedor necesite salida a internet en el servidor de despliegue y que el
# modelo se re-descargue cada vez que se recrea el contenedor (sin esto viviria solo en
# el filesystem efimero del contenedor, ver get_text_model() en main.py)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"

# Codigo del backend (misma profundidad que localmente: main.py usa
# Path(__file__).resolve().parents[2] para ubicar la raiz del repo)
COPY dashboard_react/backend/main.py ./dashboard_react/backend/main.py

# Modulos reutilizados del pipeline de notebooks (lib.py + _preprocesamiento_comun.py),
# igual patron que localmente (main.py hace sys.path.insert hacia estas rutas)
COPY notebooks/08_dashboard/lib.py ./notebooks/08_dashboard/lib.py
COPY notebooks/01_preprocesamiento/_preprocesamiento_comun.py ./notebooks/01_preprocesamiento/_preprocesamiento_comun.py

# Datos necesarios para que lib.py/main.py funcionen (generados localmente, ver
# CLAUDE.md / pipeline de notebooks - no se regeneran dentro del contenedor)
COPY data/dashboard/ ./data/dashboard/
COPY data/clustering/ ./data/clustering/
COPY data/embeddings/ ./data/embeddings/
COPY data/trayectorias/ ./data/trayectorias/
COPY data/features/feature_dictionary.csv ./data/features/feature_dictionary.csv
COPY data/processed/reporte_titulaciones_educacion.csv ./data/processed/reporte_titulaciones_educacion.csv
COPY data/processed/carga_academica_disponible.csv ./data/processed/carga_academica_disponible.csv
COPY data/processed/proyectos_investigacion_disponible.csv ./data/processed/proyectos_investigacion_disponible.csv
COPY data/processed/publicaciones.csv ./data/processed/publicaciones.csv
COPY data/processed/proyecto_grado.csv ./data/processed/proyecto_grado.csv
COPY data/processed/ponentes_todos.csv ./data/processed/ponentes_todos.csv
COPY data/processed/proyectos_vinculacion_disponible.csv ./data/processed/proyectos_vinculacion_disponible.csv
COPY data/processed/capacitaciones_todas.csv ./data/processed/capacitaciones_todas.csv
COPY data/processed/certificados_todos.csv ./data/processed/certificados_todos.csv
COPY data/processed/idiomas_personas.csv ./data/processed/idiomas_personas.csv
COPY data/processed/mencion_honor.csv ./data/processed/mencion_honor.csv
COPY data/raw/historialaboralpersonas.csv ./data/raw/historialaboralpersonas.csv

WORKDIR /app/dashboard_react/backend

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:80/api/health', timeout=3).read()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
