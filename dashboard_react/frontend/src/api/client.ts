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

/** porcentaje: proporciones y marcas sí/no; nivel: escala ordinal; numero: conteos y razones */
export type FormatoComponente = "porcentaje" | "nivel" | "numero";
/** cuánto se aleja el grupo del promedio de la dimensión */
export type Comparacion = "mucho_mas" | "mas" | "similar" | "menos" | "mucho_menos";
export interface ComponentePatron {
  componente: string;
  descripcion: string;
  /** centroide estandarizado: cuántas desviaciones se aleja el grupo del promedio de la dimensión */
  z: number;
  /** promedio del grupo y de la dimensión, en unidades reales (en las variables en log, media en log) */
  media_grupo: number;
  media_dimension: number;
  formato: FormatoComponente;
  comparacion: Comparacion;
}

export interface Patron {
  id: number;
  /** p. ej. "Más que el promedio de Formación en …; menos en …" */
  etiqueta: string;
  /** la calculada al construir ("Alto: …") */
  etiqueta_tecnica?: string;
  tamano: number;
  tamano_vigentes: number;
  proporcion: number;
  representante_id: number | null;
  representante_nombre: string | null;
  componentes: ComponentePatron[];
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

export type Evidencias = { tipo_id: string; n: number; textos: string[] }[];

/** La persona vista desde una dimensión (ficha abierta desde esa dimensión, comparar, validar). */
export interface PersonaEnDimension {
  dimension: string;
  nombre: string;
  /** percentil del puntaje en el ámbito (= posicion.menor + posicion.igual) */
  intensidad: number;
  n_evidencias: number;
  /** índice de DEC-053 en 0–100: suma de los aportes de los componentes */
  puntaje: number;
  suma_pesos: number;
  /** % del personal del ámbito con un puntaje menor, igual o mayor que el suyo */
  posicion: { n: number; ambito: string; menor: number; igual: number; mayor: number };
  patron: {
    patron: number; etiqueta: string; tamano: number; afinidad: number; mixto: boolean; segundo: number; segundo_etiqueta: string;
    /** 1 = es la persona representativa; 0 = la más distinta a ella dentro del patrón */
    similitud_representante: number | null; es_representante: boolean;
    representante_id: number | null; representante_nombre: string | null;
  } | null;
  /** valor 0–1 (1 = el máximo del ámbito), promedios de su patrón y de la dimensión, y su peso y
   *  aporte (en puntos) al puntaje */
  componentes: {
    componente: string; descripcion: string; valor: number; media_dimension: number; media_patron: number | null;
    peso: number; aporte: number;
  }[];
  temas: { tema: number; etiqueta: string; proporcion: number }[];
  /** sus datos reales en las variables con que se forman los patrones, junto al valor típico de su
   *  patrón y de la dimensión (vacío si no se pudieron calcular) */
  datos: DatoPersona[];
  /** solo las evidencias de esta dimensión */
  evidencias: Evidencias;
}
export interface DatoPersona {
  componente: string;
  descripcion: string;
  /** en sus unidades: conteo, nivel, proporción 0–1 o marca 0/1 */
  valor: number;
  formato: FormatoComponente;
  /** marca sí/no: para la persona se muestra "Sí"/"No" */
  marca: boolean;
  media_patron: number | null;
  media_dimension: number | null;
  /** cómo es su patrón frente a la dimensión en este dato (null si no tiene patrón) */
  comparacion: Comparacion | null;
  z: number | null;
}
export interface ParecidoDimension {
  persona_id: number;
  nombre: string;
  rango: number;
  cargo_actual: string | null;
  mismo_patron: boolean;
  patron: number | null;
  /** mismo valor en todos los componentes de la dimensión */
  mismos_valores: boolean;
  temas_comunes: string[];
}
export const getPersonaEnDimension = async (id: number, d: string, a: Ambito) =>
  (
    await api.get<PersonaEnDimension & { persona_id: number; parecidos: ParecidoDimension[] }>(
      `/api/personas/${id}/dimension/${d}`, { params: { ambito: a } },
    )
  ).data;

export interface PersonaComparada {
  persona_id: number;
  nombre: string;
  vigente: boolean;
  cargo_actual: string | null;
  unidad_actual: string | null;
  tipo_empleado: string | null;
  patron_global: Persona["patron_global"];
  intensidades: { dimension: string; nombre: string; intensidad: number; n_evidencias: number; patron: number | null }[];
  /** con `dimension` */
  dimension?: PersonaEnDimension;
  /** sin `dimension`: todas sus evidencias, resumidas */
  evidencias?: Evidencias;
}
export const comparar = async (a: Ambito, ids: number[], dimension: string | null) =>
  (
    await api.get<{ personas: PersonaComparada[] }>("/api/comparar", {
      params: { ambito: a, ids: ids.join(","), ...(dimension ? { dimension } : {}) },
    })
  ).data.personas;

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
/** Patrón de una dimensión mucho más frecuente en un grupo global que en su referencia. */
export interface PatronDistintivo {
  dimension: string;
  nombre: string;
  patron: number;
  etiqueta_patron: string | null;
  /** entre las personas del grupo con evidencias en la dimensión, y en su referencia */
  proporcion: number;
  proporcion_referencia: number;
  lift: number | null;
}
export interface MicroGlobal {
  id: number;
  codigo: string;
  /** p. ej. "Por debajo del promedio de su Patrón global 1 en Formación" */
  etiqueta: string;
  etiqueta_tecnica?: string;
  patrones_distintivos: PatronDistintivo[];
  tamano: number;
  tamano_vigentes: number;
  proporcion: number;
  representante_id: number | null;
  representante_nombre: string | null;
  dimensiones: DimensionPatronGlobal[];
}
export interface PatronGlobal {
  id: number;
  /** p. ej. "Por encima del promedio de todo el personal en Investigación y Docencia" */
  etiqueta: string;
  etiqueta_tecnica?: string;
  patrones_distintivos: PatronDistintivo[];
  tamano: number;
  tamano_vigentes: number;
  proporcion: number;
  representante_id: number | null;
  representante_nombre: string | null;
  dimensiones: DimensionPatronGlobal[];
  microarquetipos: { k: number; estabilidad_ari: number; lista: MicroGlobal[] } | null;
}
/** Cómo se reparten las personas de un patrón global (o microarquetipo) entre los patrones de una
 *  dimensión, frente a su referencia (el ámbito, o su patrón global). */
export interface RepartoEnDimension {
  n_grupo: number;
  con_evidencia: number;
  n_referencia_con_evidencia: number;
  patrones: { patron: number; n: number; proporcion: number; proporcion_referencia: number }[];
}
export const getRepartoEnDimension = async (a: Ambito, patron: number, micro: number | null, dimension: string) =>
  (
    await api.get<RepartoEnDimension>(`/api/perfil/${a}/patrones/${patron}/dimension/${dimension}`, {
      params: micro !== null ? { micro } : {},
    })
  ).data;
export const getPatronesGlobales = async (a: Ambito) =>
  (await api.get<{ k?: number; estabilidad_ari?: number; patrones?: PatronGlobal[] }>(`/api/perfil/${a}/patrones`)).data;
/** Una página de las personas de un grupo (patrón, tema, microarquetipo…), ya ordenadas. */
export interface PaginaPersonas<T> {
  /** personas del grupo, sin el filtro por nombre */
  total: number;
  /** personas que coinciden con `q` (= total si no hay filtro) */
  total_filtrado: number;
  q: string | null;
  pagina: number;
  por_pagina: number;
  paginas: number;
  /** cada una con su `posicion` (1 = primera) en el orden del grupo, que se conserva al filtrar */
  personas: (T & { posicion: number })[];
}
/** grupo: el orden del grupo (p. ej. de más a menos parecida a la representante); inverso: al revés;
 *  azar: una muestra al azar reproducible con `semilla` */
export type OrdenLista = "grupo" | "inverso" | "azar";
export interface ConsultaPagina {
  q?: string;
  pagina: number;
  porPagina: number;
  orden?: OrdenLista;
  semilla?: number;
}
const paramsPagina = ({ q, pagina, porPagina, orden, semilla }: ConsultaPagina) => ({
  pagina,
  por_pagina: porPagina,
  ...(q && q.trim() ? { q: q.trim() } : {}),
  ...(orden && orden !== "grupo" ? { orden } : {}),
  ...(orden === "azar" ? { semilla: semilla ?? 0 } : {}),
});

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
export const getPersonasPatronGlobal = async (
  a: Ambito, patron: number, micro: number | null, soloVigentes: boolean, pag: ConsultaPagina,
) =>
  (
    await api.get<PaginaPersonas<PersonaPatronGlobal>>(`/api/perfil/${a}/personas`, {
      params: { patron, solo_vigentes: soloVigentes, ...(micro !== null ? { micro } : {}), ...paramsPagina(pag) },
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
export const getPersonasDimension = async (
  a: Ambito, d: string, filtro: { patron?: number; tema?: number }, soloVigentes: boolean, pag: ConsultaPagina,
) =>
  (
    await api.get<PaginaPersonas<PersonaDimension>>(`/api/dimensiones/${a}/${d}/personas`, {
      params: { ...filtro, solo_vigentes: soloVigentes, ...paramsPagina(pag) },
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
