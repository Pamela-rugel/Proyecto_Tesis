export interface PerfilResumen {
  CLUSTER: number;
  GRUPO_PRINCIPAL: string;
  SUBGRUPO: string;
  N_PERSONAS: number;
  PCT_POBLACION: number;
  PERFIL_NOMBRE: string;
  DESCRIPCION: string;
  COLOR: string;
}

export interface ResumenResponse {
  n_personas: number;
  n_perfiles: number;
  n_con_texto: number;
  perfiles: PerfilResumen[];
}

export interface TopFeature {
  FEATURE: string;
  FEATURE_LABEL: string;
  VALUE_CLUSTER: number;
  VALUE_GLOBAL: number;
}

export interface CargoConteo {
  CARGO_ACTUAL: string;
  N_PERSONAS: number;
}

export interface PerfilDetalle {
  cluster: number;
  nombre: string;
  n_personas: number;
  pct_poblacion: number;
  descripcion: string;
  color: string;
  top_features: TopFeature[];
  cargos: CargoConteo[];
  n_cargos_distintos: number;
  n_con_cargo: number;
  muestra_personas: Record<string, unknown>[];
}

export interface MapaPunto {
  IDPERSONA: number;
  NOMBRE_COMPLETO: string;
  PC1: number;
  PC2: number;
  CLUSTER: number;
  PERFIL_NOMBRE: string;
  TIPOEMPLEADO_ACTUAL_DESC: string;
  VIGENTE_MOSTRAR: boolean;
  CARGO_ACTUAL: string | null;
  COLOR: string;
  GRUPO_COLOR: string;
  ES_MIXTO: boolean;
  CARGOS_ACTUALES_MIXTO: string | null;
}

export interface MapaResponse {
  total_modelo: number;
  n_mostrados: number;
  puntos: MapaPunto[];
  modo: "rama" | "cargo" | "cargo_real";
}

export interface EventoTrayectoria {
  IDPERSONA: number;
  TIPO_EVENTO: string;
  DESCRIPCION: string;
  UNIDAD: string | null;
  FECHA_INICIO: string | null;
  FECHA_FIN: string | null;
  ES_VIGENTE: boolean;
}

export interface RadarData {
  features: string[];
  valores: number[];
}

export interface ResumenCargosEspol {
  total: number;
  administrativo: number;
  docente: number;
  otras_categorias: { etiqueta: string; cantidad: number }[];
}

export interface PersonaFichaResponse {
  persona: Record<string, unknown>;
  tiene_perfil: boolean;
  motivo_sin_perfil: string | null;
  eventos_trayectoria: EventoTrayectoria[];
  resumen_cargos_espol: ResumenCargosEspol;
  secciones: Record<string, unknown>;
  radar: RadarData | null;
  cluster_descripcion: string | null;
  corpus_muestra: { FUENTE: string; TEXTO: string }[];
  n_textos: number;
  color_tipo_evento: Record<string, string>;
  etiqueta_tipo_evento: Record<string, string>;
}

export interface EquiposResponse {
  n_resultados: number;
  candidatos: Record<string, unknown>[];
  opciones: {
    tipo_empleado: string[];
    nivel_academico: string[];
  };
}

export interface BusquedaResultado {
  rango: number;
  id_persona: number;
  nombre_completo: string;
  cluster: number | null;
  perfil_nombre: string | null;
  vigente: boolean;
  tipo_empleado: string | null;
  cargo_actual: string | null;
  evidencia: string;
}

export interface BusquedaResponse {
  consulta: string;
  resultados: BusquedaResultado[];
}
