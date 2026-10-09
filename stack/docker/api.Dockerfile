# API del dashboard: perfiles (clustering multivista) + búsqueda semántica de personas.
# Contexto de build: la raíz del repositorio (ver docker-compose.yml).

# === BASE ===
FROM python:3.11-slim AS base
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# === DEPENDENCIAS ===
FROM base AS deps
# Variante de PyTorch: CPU por defecto (servidor). La laptop con GPU usa docker-compose.gpu.yml,
# que pasa el índice cu124 y construye otra imagen (perfiles-espol-api-gpu).
ARG TORCH_INDEX=https://download.pytorch.org/whl/cpu
ARG TORCH_VERSION=2.6.0
COPY dashboard_react/backend/requirements.txt .
ENV PYTHONPATH=/install/lib/python3.11/site-packages
# torch se instala aparte, desde el índice de PyTorch elegido (el build normal de PyPI trae CUDA,
# ~3 GB extra sin GPU). PYTHONPATH al mismo --prefix en ambos comandos para que pip vea ese torch y
# no vuelva a descargar otra variante al instalar sentence-transformers.
RUN python -m pip install --upgrade pip "setuptools>=64" \
    && python -m pip install --prefix=/install --index-url ${TORCH_INDEX} torch==${TORCH_VERSION} \
    && python -m pip install --prefix=/install -r requirements.txt

# === NOMBRES: del historial laboral crudo se conservan SOLO 3 columnas ===
# (el archivo completo tiene identificación y otros datos personales; queda solo en esta etapa
# intermedia, que no forma parte de la imagen final)
FROM base AS nombres
COPY --from=deps /install /usr/local
COPY data/raw/historialaboralpersonas.csv /tmp/historial.csv
RUN python -c "import pandas as pd; pd.read_csv('/tmp/historial.csv', usecols=['IDPERSONA','APELLIDOS','NOMBRES'], dtype=str).to_csv('/tmp/nombres.csv', index=False)"

# === RUNTIME ===
FROM base AS runtime
COPY --from=deps /install /usr/local
RUN python -m pip install --upgrade "setuptools>=64"

ENV HF_HOME=/app/.cache/huggingface

# Modelos descargados en el build (el contenedor no necesita internet para ellos):
# embedding de consultas (bge-m3) y reranker de la búsqueda (bge-reranker-v2-m3).
# bge-m3 se descarga DOS veces (pytorch_model.bin + una conversión model.safetensors en otra
# revisión, 2,27 GB cada una); sin conexión se usa el .bin, así que la copia .safetensors se borra
# en el mismo paso (si se borrara en un paso posterior la imagen no se achicaría). Verificado:
# vectores idénticos (diferencia 0,0). La comprobación final hace fallar el build si algún modelo
# no carga sin internet.
RUN python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('BAAI/bge-m3'); CrossEncoder('BAAI/bge-reranker-v2-m3')" \
    && H=$HF_HOME/hub/models--BAAI--bge-m3 \
    && for f in $H/snapshots/*/model.safetensors; do [ -e "$f" ] && rm -f "$(readlink -f "$f")" "$f"; done \
    && HF_HUB_OFFLINE=1 python -c "from sentence_transformers import SentenceTransformer, CrossEncoder; SentenceTransformer('BAAI/bge-m3'); CrossEncoder('BAAI/bge-reranker-v2-m3'); print('modelos OK sin internet')"

# Los modelos ya están dentro: no intentar descargarlos al arrancar (evita bajar otra vez la copia
# borrada). No afecta a Groq, que es otra API.
ENV HF_HUB_OFFLINE=1

# Paquetes del proyecto (instalación editable: los módulos ubican data/ relativo a /app)
COPY pyproject.toml ./
COPY 02_evidencias/ ./02_evidencias/
COPY 03_perfiles/ ./03_perfiles/
COPY 04_busqueda_semantica/ ./04_busqueda_semantica/
RUN python -m pip install --no-deps --no-build-isolation -e .

# Backend (misma profundidad que localmente: repositorio.py usa parents[2] para ubicar /app)
COPY dashboard_react/backend/main.py dashboard_react/backend/repositorio.py \
     ./dashboard_react/backend/

# Datos que lee la API (todo derivado; nada del crudo salvo los nombres reducidos)
COPY data/evidencias/ ./data/evidencias/
COPY data/perfiles/embeddings/ ./data/perfiles/embeddings/
COPY data/perfiles/clustering/ ./data/perfiles/clustering/
COPY data/processed/historial_laboral_features.csv ./data/processed/historial_laboral_features.csv
COPY --from=nombres /tmp/nombres.csv ./data/raw/historialaboralpersonas.csv

# Índice BM25 de la búsqueda precalculado (sin datos de personas: vocabulario y pesos por texto)
RUN python -c "from busqueda.indice import cargar_indice; cargar_indice()"

WORKDIR /app/dashboard_react/backend

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:80/api/health', timeout=3).read()"

# GROQ_API_KEY llega como variable de entorno desde docker-compose (nunca dentro de la imagen)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
