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
  /** nombre corto que se cumple para todas las personas del patrón (DEC-063) */
  nombre?: string;
  /** parte del resto de la dimensión que no cumple el nombre (qué tan propio es) */
  nombre_distingue?: number;
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
  /** percentil entre quienes tienen registros (null con menos de 40 personas con registros) */
  nivel: number | null;
  n_evidencias: number;
  vigente: boolean;
  cargo_actual: string | null;
  unidad_actual: string | null;
  tipo_empleado: string | null;
  patron: number | null;
  afinidad_1: number | null;
  mixto: boolean | null;
  es_representante?: boolean | null;
  similitud_representante?: number | null;
  proporcion?: number;
}

/** con_registros · sin_registros; solo en Idiomas: solo_espanol · sin_validos · sin_informacion */
export type EstadoRegistros = "con_registros" | "sin_registros" | "solo_espanol" | "sin_validos" | "sin_informacion";

export interface TemaPersona {
  tema: number;
  etiqueta: string;
  terminos: string[];
  /** personas del ámbito con al menos una evidencia en el tema */
  n_personas_tema: number;
  /** parte de sus evidencias de la dimensión en el tema */
  proporcion: number;
  dominante: boolean;
  /** parte de sus evidencias de este tema que se asignaron por parecido (no encajaban en ninguno); null si no hay dato */
  parte_por_cercania: number | null;
}

export interface ParecidoDimension {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  /** mismos valores de actividad (lista actividad) o mismo contenido/idiomas (lista tema) */
  identico: boolean;
  /** aparece también en la otra lista */
  en_ambos: boolean;
  /** temas (o idiomas) que comparten */
  comparte: string[];
  /** par de evidencias más parecido (títulos) en la lista de temas */
  texto_persona: string | null;
  texto_vecino: string | null;
  misma_evidencia: boolean;
}

export interface IdiomaPersona {
  idioma: string;
  conversacion: string | null;
  lectura: string | null;
  escritura: string | null;
  mcer: string | null;
  /** personas del ámbito que registran este idioma */
  n_personas: number;
}

export interface DimensionPersona {
  dimension: string;
  nombre: string;
  estado: EstadoRegistros;
  /** percentil 0-100 frente a TODAS las personas del ámbito; 0 sin evidencias */
  intensidad: number;
  /** percentil SOLO entre quienes tienen registros en la dimensión (rango medio en empates);
   *  null sin registros o con menos de 40 personas con registros */
  nivel: number | null;
  n_evidencias: number;
  /** personas del ámbito (población de referencia del percentil) */
  n_ambito: number;
  /** personas del ámbito con un valor medible en la dimensión */
  n_con_registros: number;
  /** % del ámbito sin registros: el percentil de quien tiene registros nunca baja de aquí */
  pct_sin_registros: number;
  componentes: { componente: string; descripcion: string; valor: number }[];
  /** todos sus temas en la dimensión, de mayor a menor proporción */
  temas: TemaPersona[];
  /** más de un tema con la misma proporción máxima */
  dominante_empatado: boolean;
  /** temas descubiertos en la dimensión y % de textos asignados al tema más cercano (no encajaban en ninguno) */
  temas_dimension: { k: number; proporcion_por_cercania: number | null } | null;
  /** por qué la dimensión no tiene temas (null si los tiene) */
  sin_temas: string | null;
  /** solo en Idiomas: sus idiomas (hacen de temas) con los niveles tal como se registraron */
  idiomas: IdiomaPersona[] | null;
  /** fecha de su evidencia más reciente en la dimensión (ISO); null si no tiene fechas */
  ultima_evidencia?: string | null;
  /** personas vigentes parecidas dentro de la dimensión; null si no se compara */
  parecidos?: {
    n_identicos: number;
    actividad: ParecidoDimension[] | null;
    tema: ParecidoDimension[] | null;
  } | null;
  /** patrón de actividad descubierto (null si la dimensión no se subdivide) */
  patron: {
    patron: number; etiqueta: string; afinidad: number; mixto: boolean; segundo: string; segundo_id: number; tamano: number; n_personas: number;
    nombre?: string | null; segundo_nombre?: string | null;
    representante_id: number | null; representante_nombre: string | null;
  } | null;
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
    /** temas mucho más frecuentes en el perfil amplio que en el ámbito (DEC-062) */
    temas?: TemaDistintivo[];
    /** número de perfiles amplios del ámbito y estabilidad (ARI) del agrupamiento */
    k?: number | null;
    estabilidad?: number | null;
    micro: {
      micro: number; codigo: string; etiqueta: string; tamano: number; mixto: boolean;
      similitud_representante: number | null; es_representante: boolean;
      representante_id: number | null; representante_nombre: string | null;
      /** temas distintivos frente a su perfil amplio, y estabilidad de la subdivisión */
      temas?: TemaDistintivo[]; k?: number | null; estabilidad?: number | null; estable?: boolean | null;
    } | null;
  } | null;
  /** personas vigentes con el perfil completo más parecido (DEC-056), en orden */
  parecidos: Parecido[];
}

/** desde dónde se abre la ficha: decide la pestaña inicial */
export type OrigenFicha = "dimension" | "perfil" | "otra";

/** patrón o tema elegido dentro de una dimensión */
export type FiltroDimension = { tipo: "patron" | "tema"; id: number } | null;

/** enlaces de la ficha hacia el resto del dashboard (cada página decide cómo navegar) */
export interface NavegacionFicha {
  /** abrir la ficha de otra persona, con el contexto del lugar donde se hizo clic */
  persona?: (id: number, origen: OrigenFicha, dimension?: string) => void;
  /** ir a un patrón global (y opcionalmente a uno de sus microarquetipos) en la vista Perfil completo */
  patronGlobal?: (patron: number, micro: number | null) => void;
  /** ir a una dimensión en la vista Por dimensión, opcionalmente filtrada por un patrón o un tema */
  dimension?: (dimension: string, filtro: FiltroDimension) => void;
}

export type ValorAtributo = string | number | boolean | null | ValorAtributo[] | { [k: string]: ValorAtributo };
export interface EvidenciaDetalle {
  texto: string | null;
  /** fechas tal como vienen en la evidencia; null si no tiene ninguna */
  fechas: string | null;
  /** false = la fuente de este tipo no tiene fechas (no se muestra nada) */
  con_fecha: boolean;
  /** valor null = la fuente lo trae vacío */
  campos: { campo: string; valor: ValorAtributo }[];
}
export interface GrupoEvidencias {
  /** clave de la dimensión, u "otras" si no cuenta en ninguna */
  dimension: string;
  nombre: string;
  n: number;
  tipos: { tipo_id: string; n: number; evidencias: EvidenciaDetalle[] }[];
}
export const getEvidencias = async (id: number) =>
  (await api.get<{ grupos: GrupoEvidencias[] }>(`/api/personas/${id}/evidencias`)).data.grupos;

export interface Parecido {
  persona_id: number;
  nombre: string;
  rango: number;
  cargo_actual: string | null;
  /** dimensiones donde ambas tienen nivel >= 50; `mismo_patron` si participan igual */
  comparte: { dimension: string; nombre: string; mismo_patron: boolean; patron: number | null; patron_nombre?: string | null }[];
  /** vistas del perfil multivista en que son vecinas (DEC-062): en qué se parecen.
   *  `rango`: puesto de esta persona en esa vista entre las vigentes (null en versiones anteriores) */
  vistas?: { vista: string; nombre: string; rango?: number | null }[];
}

export interface TemaDistintivo {
  dimension: string;
  nombre_dimension?: string;
  tema: number;
  etiqueta: string;
  /** parte del grupo con evidencias en el tema */
  proporcion: number;
  lift: number;
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
  /** nivel en la dimensión elegida; null/ausente = sin registros (o muy pocas personas para comparar) */
  nivel?: number | null;
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
  /** % del grupo con registros en la dimensión y el de su referencia */
  pct_con_registros: number;
  pct_con_registros_referencia: number;
  /** nivel mediano de quienes tienen registros (grupo y referencia); null si nadie tiene nivel */
  nivel_mediano: number | null;
  nivel_mediano_referencia: number | null;
  patron_frecuente: { patron: number; proporcion: number; proporcion_referencia: number; lift: number | null; nombre?: string | null } | null;
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
  microarquetipos: { k: number; estabilidad_ari: number; estable?: boolean; lista: MicroGlobal[] } | null;
  temas?: TemaDistintivo[];
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
/** Una página de una lista de personas. `total`: las que coinciden con la búsqueda (lo que se
 *  pagina); `total_grupo`: todas las del grupo. `posicion`: lugar de cada una en el orden del grupo. */
export interface PaginaPersonas<T> {
  total: number;
  total_grupo: number;
  q: string | null;
  personas: (T & { posicion: number })[];
}
/** búsqueda por nombre o apellidos (`q`) en una lista paginada; vacía = sin filtro */
const paramBusqueda = (q?: string) => (q && q.trim() ? { q: q.trim() } : {});

export const getPersonasPatronGlobal = async (a: Ambito, patron: number, micro: number | null, soloVigentes: boolean,
  pagina = 0, porPagina = 20, q?: string) =>
  (
    await api.get<PaginaPersonas<PersonaPatronGlobal>>(`/api/perfil/${a}/personas`, {
      params: {
        patron, solo_vigentes: soloVigentes, offset: pagina * porPagina, limite: porPagina,
        ...(micro !== null ? { micro } : {}), ...paramBusqueda(q),
      },
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
export const getPersonasDimension = async (a: Ambito, d: string, filtro: { patron?: number; tema?: number }, soloVigentes: boolean,
  pagina = 0, porPagina = 20, q?: string) =>
  (
    await api.get<PaginaPersonas<PersonaDimension>>(`/api/dimensiones/${a}/${d}/personas`, {
      params: { ...filtro, solo_vigentes: soloVigentes, offset: pagina * porPagina, limite: porPagina, ...paramBusqueda(q) },
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
  nivel?: number | null;
  patron?: number | null;
  tema?: number | null;
  proporcion_tema?: number | null;
  /** todos sus temas en la dimensión: [tema, parte de sus evidencias] */
  temas?: [number, number][] | null;
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
  /** cerrado · actual (periodo de ESPOL abierto y la persona está vigente) · sin_fin (sin fecha de fin registrada) */
  estado: "cerrado" | "actual" | "sin_fin";
}
export const getTrayectoria = async (id: number) =>
  (await api.get<{ vigente: boolean; tramos: TramoTrayectoria[]; sin_inicio: number }>(`/api/personas/${id}/trayectoria`)).data;

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
