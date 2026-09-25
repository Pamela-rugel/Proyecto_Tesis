import sys, warnings, time
warnings.filterwarnings("ignore")
sys.path.insert(0, 'notebooks/01_preprocesamiento')
sys.path.insert(0, 'notebooks/07_embeddings')
import pandas as pd
import numpy as np
import torch
from pathlib import Path
import _preprocesamiento_comun as pc
import _embeddings_comun as ec
from sentence_transformers import SentenceTransformer

ROOT = Path('.')
DATA_MODELING = ROOT / "data" / "modeling"
DATA_EMBEDDINGS = ROOT / "data" / "embeddings"

personas = pd.read_csv(DATA_MODELING / "personas_modelado.csv")
POBLACION = set(personas["IDPERSONA"])

items = ec.construir_items_investigacion(POBLACION)
print(f"Total items: {len(items)}", flush=True)
print(items["TIPO_ITEM"].value_counts(), flush=True)

model = SentenceTransformer("BAAI/bge-m3", device="cuda", model_kwargs={"torch_dtype": torch.float16})
print("modelo cargado", flush=True)

t0 = time.time()
emb = model.encode(items["TEXTO_ITEM"].tolist(), batch_size=32, show_progress_bar=True, normalize_embeddings=True)
print(f"tiempo: {time.time()-t0:.1f}s, shape={emb.shape}", flush=True)

emb_df = pd.DataFrame(emb, columns=[f"E_{i:03d}" for i in range(emb.shape[1])])
emb_df.insert(0, "ITEM_IDX", range(len(items)))
emb_df.to_csv(DATA_EMBEDDINGS / "embeddings_items_investigacion.csv", index=False)
print("guardado embeddings_items_investigacion.csv", flush=True)

items_out = items.copy()
items_out.insert(0, "ITEM_IDX", range(len(items)))
items_out.to_csv(DATA_EMBEDDINGS / "items_investigacion.csv", index=False, encoding="utf-8-sig")
print("guardado items_investigacion.csv", flush=True)
