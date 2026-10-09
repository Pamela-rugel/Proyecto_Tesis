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
}

export interface Ambitos {
  version: string;
  fecha: string;
  estado: { actualizado: boolean; evidencias_cambiadas: string[] };
  ambitos: AmbitoResumen[];
}

// ---- Dimensiones de evidencia (DEC-053) y sus temas y patrones descubiertos (DEC-055) ----
export interface ResumenDimension {
  dimension: string;
  nombre: string;
  n_personas: number;
  n_vigentes: number;
  n_personas_ambito: number;
  n_vigentes_ambito: number;
  k_temas: number;
  k_patrones: number;
  nota: string | null;
}

export interface Tema {
  id: number;
  etiqueta: string;
  terminos_distintivos: string[];
  n_textos: number;
  n_evidencias: number;
  n_personas: number;
  n_personas_vigentes: number;
  personas_dominante: number;
  ejemplos: { texto: string; personas: number }[];
}

export interface Patron {
  id: number;
  etiqueta: string;
  tamano: number;
  tamano_vigentes: number;
  proporcion: number;
  representante_id: number | null;
  representante_nombre: string | null;
  componentes: { componente: string; descripcion: string; z: number; media_grupo: number }[];
}

export interface DetalleDimension {
  ambito: Ambito;
  dimension: string;
  nombre: string;
  n_personas: number;
  nota?: string;
  definicion: { nombre: string; tipos_evidencia: string[]; componentes: Record<string, { peso: number; descripcion: string }> };
  temas: { n_textos: number; k: number; proporcion_asignada_por_cercania: number; temas: Tema[] } | null;
  patrones: { k: number; estabilidad_ari: number; perfiles_mixtos: number; patrones: Patron[] } | null;
}

export interface PersonaDimension {
  persona_id: number;
  nombre: string;
  intensidad: number;
  n_evidencias: number;
  vigente: boolean;
  cargo_actual: string | null;
  unidad_actual: string | null;
  tipo_empleado: string | null;
  patron: number | null;
  afinidad_1: number | null;
  mixto: boolean | null;
  similitud_representante?: number | null;
  proporcion?: number;
}

export interface DimensionPersona {
  dimension: string;
  nombre: string;
  /** percentil 0-100 dentro del ámbito; 0 sin evidencias */
  intensidad: number;
  n_evidencias: number;
  componentes: { componente: string; descripcion: string; valor: number }[];
  /** temas descubiertos con más evidencias de la persona en la dimensión (máx. 3) */
  temas: { tema: number; etiqueta: string; proporcion: number }[];
  /** patrón de actividad descubierto (null si la dimensión no se subdivide) */
  patron: { patron: number; etiqueta: string; afinidad: number; mixto: boolean; segundo: string; tamano: number; n_personas: number } | null;
}

export interface Persona {
  persona_id: number;
  nombre: string;
  ambito: Ambito;
  estado: { tipo_empleado: string | null; vigente: boolean; cargo_actual: string | null; unidad_actual: string | null };
  dimensiones: DimensionPersona[];
  /** patrón global descubierto sobre el perfil completo (DEC-057) */
  patron_global: {
    patron: number; etiqueta: string; afinidad: number; mixto: boolean; segundo: number; segundo_etiqueta: string; tamano: number;
    /** 1 = es la persona representativa; 0 = la más distinta a ella dentro del grupo */
    similitud_representante: number | null; es_representante: boolean;
    representante_id: number | null; representante_nombre: string | null;
    micro: {
      micro: number; codigo: string; etiqueta: string; tamano: number; mixto: boolean;
      similitud_representante: number | null; es_representante: boolean;
      representante_id: number | null; representante_nombre: string | null;
    } | null;
  } | null;
  /** personas vigentes con el perfil completo más parecido (DEC-056), en orden */
  parecidos: Parecido[];
  evidencias: { tipo_id: string; n: number; textos: string[] }[];
}

export interface Parecido {
  persona_id: number;
  nombre: string;
  rango: number;
  cargo_actual: string | null;
  /** dimensiones donde ambas tienen intensidad >= 50; `mismo_patron` si participan igual */
  comparte: { dimension: string; nombre: string; mismo_patron: boolean; patron: number | null }[];
}

export interface PuntoPerfil {
  persona_id: number;
  nombre: string;
  x: number;
  y: number;
  vigente: boolean;
  cargo_actual: string | null;
  unidad_actual: string | null;
  intensidad?: number | null;
  patron?: number | null;
  patron_global?: number | null;
  micro_global?: number | null;
}

export interface DimensionPatronGlobal {
  dimension: string;
  nombre: string;
  intensidad_media: number;
  /** media del grupo de referencia: todo el ámbito (patrón global) o su patrón global (microarquetipo) */
  intensidad_media_referencia: number;
  diferencia: number;
  con_evidencia: number;
  patron_frecuente: { patron: number; proporcion: number; proporcion_referencia: number; lift: number | null } | null;
}
export interface MicroGlobal {
  id: number;
  codigo: string;
  etiqueta: string;
  tamano: number;
  tamano_vigentes: number;
  proporcion: number;
  representante_id: number | null;
  representante_nombre: string | null;
  dimensiones: DimensionPatronGlobal[];
}
export interface PatronGlobal {
  id: number;
  etiqueta: string;
  tamano: number;
  tamano_vigentes: number;
  proporcion: number;
  representante_id: number | null;
  representante_nombre: string | null;
  dimensiones: DimensionPatronGlobal[];
  microarquetipos: { k: number; estabilidad_ari: number; lista: MicroGlobal[] } | null;
}
export const getPatronesGlobales = async (a: Ambito) =>
  (await api.get<{ k?: number; estabilidad_ari?: number; patrones?: PatronGlobal[] }>(`/api/perfil/${a}/patrones`)).data;
export interface PersonaPatronGlobal {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  vigente: boolean;
  /** con su persona representativa: 1 = ella misma; 0 = la más distinta del grupo */
  similitud: number | null;
  es_rep: boolean;
  entre_dos: boolean;
  micro: number;
}
export const getPersonasPatronGlobal = async (a: Ambito, patron: number, micro: number | null, soloVigentes: boolean) =>
  (
    await api.get<{ total: number; personas: PersonaPatronGlobal[] }>(`/api/perfil/${a}/personas`, {
      params: { patron, solo_vigentes: soloVigentes, ...(micro !== null ? { micro } : {}) },
    })
  ).data;
export const getMapaPerfil = async (a: Ambito, dimension: string | null, soloVigentes: boolean) =>
  (
    await api.get<{ puntos: PuntoPerfil[] }>(`/api/perfil/${a}/mapa`, {
      params: { solo_vigentes: soloVigentes, ...(dimension ? { dimension } : {}) },
    })
  ).data.puntos;

export const getHealth = async () => (await api.get<Health>("/api/health")).data;
export const getAmbitos = async () => (await api.get<Ambitos>("/api/ambitos")).data;
export const getDimensiones = async (a: Ambito) =>
  (await api.get<{ ambito: Ambito; dimensiones: ResumenDimension[] }>(`/api/dimensiones/${a}`)).data.dimensiones;
export const getDimension = async (a: Ambito, d: string) => (await api.get<DetalleDimension>(`/api/dimensiones/${a}/${d}`)).data;
export const getPersonasDimension = async (a: Ambito, d: string, filtro: { patron?: number; tema?: number }, soloVigentes: boolean) =>
  (
    await api.get<{ total: number; personas: PersonaDimension[] }>(`/api/dimensiones/${a}/${d}/personas`, {
      params: { ...filtro, solo_vigentes: soloVigentes },
    })
  ).data;
export interface PuntoMapaDimension {
  persona_id: number;
  nombre: string;
  x: number;
  y: number;
  vigente: boolean;
  cargo_actual: string | null;
  unidad_actual: string | null;
  intensidad: number | null;
  patron?: number | null;
  tema?: number | null;
  proporcion_tema?: number | null;
}
export type TipoMapa = "patrones" | "temas";
export const getMapaDimension = async (a: Ambito, d: string, tipo: TipoMapa, soloVigentes: boolean) =>
  (
    await api.get<{ puntos: PuntoMapaDimension[] }>(`/api/dimensiones/${a}/${d}/mapa`, {
      params: { tipo, solo_vigentes: soloVigentes },
    })
  ).data.puntos;
export const getPersona = async (id: number, a: Ambito) =>
  (await api.get<Persona>(`/api/personas/${id}`, { params: { ambito: a } })).data;

export interface PersonaEncontrada {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  unidad_actual: string | null;
}
export const buscarPersonas = async (a: Ambito, q: string) =>
  (await api.get<{ resultados: PersonaEncontrada[] }>("/api/personas/buscar", { params: { ambito: a, q } })).data.resultados;

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
