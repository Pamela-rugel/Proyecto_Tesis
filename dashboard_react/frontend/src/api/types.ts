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

export interface PeriodoParaleloRef {
  cargo: string | null;
  unidad: string | null;
  inicio: string | null;
  fin: string | null;
}

export interface PeriodoTrayectoria {
  cargo: string | null;
  unidad: string | null;
  inicio: string | null;
  fin: string | null;
  vigente: boolean;
  duracion_anios: number | null;
  es_significativo: boolean;
  es_paralelo: boolean;
  paralelo_con: PeriodoParaleloRef[];
}

export interface CambioSecuencia {
  fecha: string | null;
  de: string | null;
  a: string | null;
}

export interface EvidenciaTrayectoria {
  disponible: boolean;
  motivo?: string;
  documento_texto?: string;
  variables?: {
    n_cargos_total: number;
    n_cargos_significativos: number;
    n_cambios_cargo: number;
    n_cambios_unidad: number;
    duracion_media_cargo_anios: number | null;
    duracion_mediana_cargo_anios: number | null;
    duracion_max_cargo_anios: number | null;
    n_unidades_total: number;
    n_unidades_significativas: number;
    proporcion_cargos_significativos: number | null;
  };
  periodos?: PeriodoTrayectoria[];
  secuencia_cambios_cargo?: CambioSecuencia[];
  secuencia_cambios_unidad?: CambioSecuencia[];
  tiene_cargos_paralelos?: boolean;
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
  evidencia_trayectoria: EvidenciaTrayectoria | null;
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


// --- Clustering SEMANTICO (en espacio de embeddings) ---------------------------------
// Estructuras paralelas a PerfilResumen/PerfilDetalle/MapaPunto de arriba, pero para el
// clustering de notebooks/07b_clustering_semantico (espacio distinto, K propio, sin
// relacion 1:1 de IDs de cluster con el clustering estructural — nunca mezclar CLUSTER con
// CLUSTER_SEMANTICO).

export interface PerfilResumenSemantico {
  CLUSTER_SEMANTICO: number;
  PERFIL_NOMBRE_SEMANTICO: string;
  N_PERSONAS: number;
  PCT_POBLACION: number;
  DESCRIPCION: string;
  TIPOEMPLEADO_PREDOMINANTE: string | null;
  CARGO_MAS_FRECUENTE: string | null;
  NIVEL_ACADEMICO_PREDOMINANTE: string | null;
  PCT_VIGENTE: number | null;
  COLOR: string;
}

export interface ResumenSemanticoResponse {
  n_personas: number;
  n_perfiles: number;
  perfiles: PerfilResumenSemantico[];
}

export interface PerfilDetalleSemantico {
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
  cargo_textual_predominante: string | null;
  unidad_textual_predominante: string | null;
  desglose_cargo_textual: string | null;
  desglose_unidad_textual: string | null;
  pct_con_trayectoria: number | null;
  pct_formacion_titulo_top1: number | null;
  ejemplos_texto: string[];
}

export interface MapaPuntoSemantico {
  IDPERSONA: number;
  NOMBRE_COMPLETO: string;
  PC1: number;
  PC2: number;
  CLUSTER_SEMANTICO: number;
  PERFIL_NOMBRE_SEMANTICO: string | null;
  TIPOEMPLEADO_ACTUAL_DESC: string;
  VIGENTE_MOSTRAR: boolean;
  CARGO_ACTUAL: string | null;
  ES_MIXTO: boolean;
  CARGOS_ACTUALES_MIXTO: string | null;
  COLOR: string;
  GRUPO_COLOR: string;
}

export interface MapaSemanticoResponse {
  total_modelo: number;
  n_mostrados: number;
  modo: "rama" | "cluster_semantico" | "cargo_real";
  puntos: MapaPuntoSemantico[];
}

// --- Clustering GLOBAL K=5 (DEC-001/DEC-007) -------------------------------------------
// KMeans directo sobre X_modelado, SIN el paso de 2 niveles admin/docente de DEC-008. IDs
// de cluster no comparables con los 13 grupos de "Categoría".

export interface PerfilResumenK5 {
  CLUSTER_K5: number;
  PERFIL_NOMBRE_K5: string;
  N_PERSONAS: number;
  PCT_POBLACION: number;
  DESCRIPCION: string;
  TIPOEMPLEADO_PREDOMINANTE: string | null;
  CARGO_MAS_FRECUENTE: string | null;
  NIVEL_ACADEMICO_PREDOMINANTE: string | null;
  PCT_VIGENTE: number | null;
  COLOR: string;
}

export interface ResumenK5Response {
  n_personas: number;
  n_perfiles: number;
  perfiles: PerfilResumenK5[];
}

export interface PerfilDetalleK5 {
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

export interface MapaPuntoK5 {
  IDPERSONA: number;
  NOMBRE_COMPLETO: string;
  PC1: number;
  PC2: number;
  CLUSTER_K5: number;
  PERFIL_NOMBRE_K5: string | null;
  TIPOEMPLEADO_ACTUAL_DESC: string;
  VIGENTE_MOSTRAR: boolean;
  CARGO_ACTUAL: string | null;
  COLOR: string;
  GRUPO_COLOR: string;
}

export interface MapaK5Response {
  total_modelo: number;
  n_mostrados: number;
  puntos: MapaPuntoK5[];
}

// --- Clustering POR RAMA (ADMINISTRATIVO o DOCENTE por separado) ----------------------
// El clustering estructural y el semantico de arriba agrupan a TODA la poblacion junta
// antes de separar por rama, asi que en la practica el eje que domina la separacion de
// clusters es simplemente "administrativo vs docente". Estas estructuras son para un
// SEGUNDO corte de clustering propio de cada rama (mismo espacio de
// features/embeddings, pero solo dentro de esa rama), con su propio K y PCA no
// comparable entre ramas ni con las vistas globales.

export type TipoClusteringRama = "estructurado" | "semantico";
export type Rama = "ADMINISTRATIVO" | "DOCENTE";

// Seccion del documento semantico con embedding propio (ver ARCHIVO_EMBEDDING_SECCION en
// main.py) - usado como chip seleccionable en la busqueda semantica: elegir una o mas
// limita la similitud a ese texto especifico, evitando que temas puntuales (ej.
// "investigacion en IA") se diluyan en personas con trayectoria extensa y variada.
export interface SeccionBusqueda {
  clave: string;
  etiqueta: string;
  n_personas: number;
}

export interface SeccionesBusquedaResponse {
  secciones: SeccionBusqueda[];
}

export interface PerfilResumenPorRama {
  CLUSTER_RAMA: number;
  PERFIL_NOMBRE: string;
  DESCRIPCION: string;
  N_PERSONAS: number;
  PCT_POBLACION: number;
  COLOR: string;
}

export interface ResumenPorRamaResponse {
  n_personas: number;
  n_perfiles: number;
  perfiles: PerfilResumenPorRama[];
}

export interface PerfilDetallePorRama {
  cluster: number;
  rama: Rama;
  tipo_clustering: TipoClusteringRama;
  nombre: string;
  n_personas: number;
  pct_poblacion: number;
  descripcion: string;
  color: string;
  cargos: CargoConteo[];
  n_cargos_distintos: number;
  n_con_cargo: number;
  muestra_personas: Record<string, unknown>[];
}

export interface MapaPuntoPorRama {
  IDPERSONA: number;
  RAMA: Rama;
  NOMBRE_COMPLETO: string;
  PC1: number;
  PC2: number;
  CLUSTER_RAMA: number;
  PERFIL_NOMBRE: string | null;
  TIPOEMPLEADO_ACTUAL_DESC: string;
  VIGENTE_MOSTRAR: boolean;
  CARGO_ACTUAL: string | null;
  COLOR: string;
  GRUPO_COLOR: string;
}

export interface MapaPorRamaResponse {
  total_modelo: number;
  n_mostrados: number;
  puntos: MapaPuntoPorRama[];
  tipo_clustering: TipoClusteringRama;
  rama: Rama;
}
