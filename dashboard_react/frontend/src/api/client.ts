import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8001";

export const api = axios.create({ baseURL: BASE_URL });

export type Ambito = "todos" | "administrativos" | "docentes";

export interface Health {
  estado: string;
  carpetas_de_evidencias: string[];
  clustering: { version: string | null; actualizado?: boolean; evidencias_cambiadas?: string[]; mensaje?: string };
}

export interface AmbitoResumen {
  ambito: Ambito;
  nombre: string;
  n_personas: number;
  n_vigentes: number;
  k: number;
  perfiles_mixtos: number;
  estabilidad_ari: number;
}

export interface Ambitos {
  version: string;
  fecha: string;
  metodo: string;
  vistas: Record<string, string>;
  estado: { actualizado: boolean; evidencias_cambiadas: string[] };
  ambitos: AmbitoResumen[];
}

export interface Rasgo {
  variable: string;
  descripcion: string;
  z: number;
  media_cluster: number;
  media_ambito: number;
}

/** Rasgo en unidades reales (años, cantidades, %, sí/no) para mostrar; ver backend/legible.py. */
export interface RasgoLegible {
  variable: string;
  texto: string;
  direccion: "más" | "menos";
  valor_grupo: string;
  valor_referencia: string;
  valor_persona?: string;
  comparte?: boolean;
}

export interface SeleccionK {
  k_elegido: number;
  criterio: string;
  tabla: { k: number; eigengap: number; silueta: number; tamano_minimo: number }[];
}

/** Subpatron (segundo nivel): misma ficha que un cluster, pero descrita frente a su patron padre. */
export interface FichaSubpatron extends Omit<FichaCluster, "subdivision"> {
  subpatron_id: string;
}

export interface Subdivision {
  k: number;
  seleccion_k: SeleccionK;
  estabilidad_ari: number;
  nota: string;
  subpatrones: FichaSubpatron[];
}

export interface FichaCluster {
  cluster: number;
  etiqueta: string;
  descripcion: string;
  tamano: number;
  tamano_vigentes: number;
  perfiles_mixtos: number;
  cohesion: number;
  tipo_empleado: Record<string, number>;
  tipos_evidencia: { tipo_id: string; tipo: string; prop_integrantes: number; prop_ambito: number; lift: number | null }[];
  rasgos_estructurados: Rasgo[];
  rasgos_legibles: RasgoLegible[];
  evidencias_compartidas: { tipo: string; texto: string; integrantes: number; prop: number }[];
  terminos_distintivos: string[];
  unidades: { unidad: string; prop: number }[];
  /** medoide elegido solo entre personas vigentes; null si el grupo no tiene vigentes */
  representante: { persona_id: number; nombre: string; cargo_actual: string | null; unidad_actual: string | null; vigente: boolean } | null;
  microarquetipos?: number[];
  microarquetipo?: number;
  subdivision: Subdivision | null;
}

export interface ResumenClustering {
  ambito: Ambito;
  nombre: string;
  n_personas: number;
  n_vigentes: number;
  k: number;
  seleccion_k: SeleccionK;
  estabilidad_ari: number;
  perfiles_mixtos: number;
  variables_estructuradas_usadas: string[];
  vistas: string[];
  clusters: FichaCluster[];
}

export interface PuntoMapa {
  persona_id: number;
  nombre: string;
  tsne_x: number;
  tsne_y: number;
  cluster: number;
  cluster_2: number;
  pertenencia_1: number;
  pertenencia_2: number;
  perfil_mixto: boolean;
  vigente: boolean;
  es_representante: boolean;
  cargo_actual: string | null;
  unidad_actual: string | null;
  tipo_empleado: string | null;
  subpatron: number;
  es_subrepresentante: boolean;
}

export interface Mapa {
  ambito: Ambito;
  solo_vigentes: boolean;
  etiquetas: Record<string, string>;
  puntos: PuntoMapa[];
}

export interface Integrante {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  unidad_actual: string | null;
  tipo_empleado: string | null;
  similitud_representante: number;
  coseno_v1_representante: number;
  coseno_v2_representante: number;
  pertenencia_1: number;
  cluster_2: number;
  pertenencia_2: number;
  perfil_mixto: boolean;
  es_representante: boolean;
  subpatron: number;
  sub_pertenencia_1: number | null;
  sub_perfil_mixto: boolean;
  es_subrepresentante: boolean;
  similitud_subrepresentante: number | null;
  vigente: boolean;
}

export interface DetalleCluster {
  ambito: Ambito;
  solo_vigentes: boolean;
  ficha: FichaCluster;
  integrantes: Integrante[];
  mixtos_desde_otros_clusters: { persona_id: number; nombre: string; cargo_actual: string | null; unidad_actual: string | null; cluster: number; pertenencia_1: number; pertenencia_2: number }[];
}

export interface Persona {
  persona_id: number;
  nombre: string;
  ambito: Ambito;
  estado: { tipo_empleado: string | null; vigente: boolean; cargo_actual: string | null; unidad_actual: string | null };
  cluster: {
    cluster: number;
    etiqueta: string;
    pertenencia: number;
    perfil_mixto: boolean;
    es_representante: boolean;
    representante_id: number | null;
    representante_nombre: string | null;
    similitud_representante: number;
    coseno_v1_representante: number;
    coseno_v2_representante: number;
    coseno_v1_centroide: number;
    coseno_v2_centroide: number;
  };
  subpatron: {
    subpatron: number;
    subpatron_id: string;
    etiqueta: string;
    descripcion: string;
    pertenencia: number;
    perfil_mixto: boolean;
    segundo_subpatron: string;
    pertenencia_2: number;
    es_representante: boolean;
    representante_id: number | null;
    representante_nombre: string | null;
    similitud_representante: number;
    estabilidad_ari: number;
  } | null;
  /** microarquetipo EXCLUSIVO (referencia estructural) */
  microarquetipo: {
    id: number; nombre: string; grupo: number; descripcion: string; afinidad: number; perfil_mixto: boolean;
    segundo: string | null; afinidad_2: number; representante_id: number | null; representante_nombre: string | null;
    similitud_representante: number | null;
  } | null;
  /** afinidades DERIVADAS (soft, no probabilidades) con todos los microarquetipos del ámbito, de mayor a menor */
  afinidades_microarquetipos: { id: number; nombre: string; grupo: number; afinidad: number }[];
  pertenencias: { cluster: number; etiqueta: string; pertenencia: number }[];
  cluster_por_vista: { vista: string; nombre: string; cluster: number; etiqueta: string; coincide: boolean }[];
  rasgos: (Rasgo & { z_persona: number; comparte: boolean })[];
  rasgos_legibles: RasgoLegible[];
  vistas_faltantes: string[];
  evidencias: { tipo_id: string; n: number; textos: string[]; compartidas_con_cluster: string[] }[];
}

export const getHealth = async () => (await api.get<Health>("/api/health")).data;
export const getAmbitos = async () => (await api.get<Ambitos>("/api/clustering/ambitos")).data;
export const getResumen = async (a: Ambito) => (await api.get<ResumenClustering>(`/api/clustering/${a}`)).data;
export const getMapa = async (a: Ambito, soloVigentes: boolean) =>
  (await api.get<Mapa>(`/api/clustering/${a}/mapa`, { params: { solo_vigentes: soloVigentes } })).data;
export const getDetalleCluster = async (a: Ambito, c: number, soloVigentes: boolean) =>
  (await api.get<DetalleCluster>(`/api/clustering/${a}/clusters/${c}`, { params: { solo_vigentes: soloVigentes } })).data;
export const getPersona = async (id: number, a: Ambito) =>
  (await api.get<Persona>(`/api/personas/${id}`, { params: { ambito: a } })).data;

export interface ResultadoBusqueda {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  unidad_actual: string | null;
  cluster: number;
  etiqueta: string;
}
export const buscarPersonas = async (a: Ambito, q: string) =>
  (await api.get<{ resultados: ResultadoBusqueda[] }>(`/api/clustering/${a}/buscar`, { params: { q } })).data.resultados;

export interface TramoTrayectoria {
  carril: string;
  titulo: string;
  lugar: string;
  inicio: string;
  fin: string | null;
  /** cerrado · actual (abierto y la persona está vigente) · sin_fin (abierto, persona no vigente) */
  estado: "cerrado" | "actual" | "sin_fin";
}
export const getTrayectoria = async (id: number) =>
  (await api.get<{ vigente: boolean; tramos: TramoTrayectoria[] }>(`/api/personas/${id}/trayectoria`)).data;

// ---- Búsqueda semántica (POST /api/busqueda) ----
export type Vigencia = "vigentes" | "no_vigentes" | "todos";

export interface EvidenciaBusqueda {
  tipo: string;
  texto: string;
  fechas: string;
  relevancia: number;
  nivel: "alta" | "media" | "baja";
}

export interface CapacidadResultado {
  id: string;
  descripcion: string;
  importancia: "obligatoria" | "deseable";
  cubierta: boolean;
  relevancia: number;
  nivel: "alta" | "media" | "baja";
  requisito_anios: { anios_minimos: number; anios: number; estado: "cumple" | "no_cumple" | "no_verificable"; aproximado: boolean } | null;
  evidencias: EvidenciaBusqueda[];
}

export interface ResultadoBusqueda {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  unidad_actual: string | null;
  tipo_empleado: string | null;
  vigente: boolean;
  obligatorias_cubiertas: number;
  total_obligatorias: number;
  deseables_cubiertas: number;
  puntaje: number;
  capacidades: CapacidadResultado[];
  grupo?: { cluster: number; etiqueta: string };
}

export interface RespuestaBusqueda {
  consulta: string;
  interpretacion: {
    capacidades: { id: string; descripcion: string; tema: string; importancia: "obligatoria" | "deseable"; tipos: string[] }[];
    requisitos_persona: { nivel_formacion_minimo: string | null; idiomas: { idioma: string; nivel_minimo: string | null }[] };
    requisitos_mixtos: { capacidad: string; anios_minimos: number }[];
    vigencia: string;
  };
  interpretacion_meta: { fuente: "llm" | "cache" | "respaldo"; modelo?: string; segundos?: number; motivo?: string };
  vigencia_aplicada: Vigencia;
  requisitos_aplicados: string[];
  personas_en_universo: number;
  personas_con_alguna_evidencia: number;
  tiempos_s: { total: number };
  resultados: ResultadoBusqueda[];
}

export const buscarSemantica = async (consulta: string, vigencia: Vigencia) =>
  (await api.post<RespuestaBusqueda>("/api/busqueda", { consulta, vigencia }, { timeout: 180000 })).data;
