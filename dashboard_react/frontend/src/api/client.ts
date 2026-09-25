import axios from "axios";
import type {
  EquiposResponse,
  MapaK5Response,
  MapaPorRamaResponse,
  MapaResponse,
  MapaSemanticoResponse,
  PerfilDetalle,
  PerfilDetalleK5,
  PerfilDetallePorRama,
  PerfilDetalleSemantico,
  PersonaFichaResponse,
  Rama,
  ResumenK5Response,
  ResumenPorRamaResponse,
  ResumenResponse,
  ResumenSemanticoResponse,
  SeccionesBusquedaResponse,
  TipoClusteringRama,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8001";

export const api = axios.create({ baseURL: BASE_URL });

export async function getResumen(): Promise<ResumenResponse> {
  const { data } = await api.get<ResumenResponse>("/api/resumen");
  return data;
}

export async function getPerfilDetalle(clusterId: number): Promise<PerfilDetalle> {
  const { data } = await api.get<PerfilDetalle>(`/api/perfiles/${clusterId}`);
  return data;
}

export async function getMapa(
  tipo: string,
  perfiles: number[],
  modo: "rama" | "cargo" | "cargo_real" = "rama",
): Promise<MapaResponse> {
  const { data } = await api.get<MapaResponse>("/api/mapa", {
    params: { tipo, perfiles: perfiles.join(","), modo },
  });
  return data;
}

// --- Clustering SEMANTICO (en espacio de embeddings) ---------------------------------

export async function getResumenSemantico(): Promise<ResumenSemanticoResponse> {
  const { data } = await api.get<ResumenSemanticoResponse>("/api/resumen_semantico");
  return data;
}

export async function getPerfilDetalleSemantico(clusterId: number): Promise<PerfilDetalleSemantico> {
  const { data } = await api.get<PerfilDetalleSemantico>(`/api/perfiles_semantico/${clusterId}`);
  return data;
}

export async function getMapaSemantico(
  perfiles: number[],
  modo: "rama" | "cluster_semantico" | "cargo_real" = "cluster_semantico",
  tipo: string = "Todos",
): Promise<MapaSemanticoResponse> {
  const { data } = await api.get<MapaSemanticoResponse>("/api/mapa_semantico", {
    params: { perfiles: perfiles.join(","), modo, tipo },
  });
  return data;
}

// --- Clustering GLOBAL K=5 (DEC-001/DEC-007, KMeans directo sobre X_modelado sin el paso
// de 2 niveles admin/docente) ----------------------------------------------------------

export async function getResumenK5(): Promise<ResumenK5Response> {
  const { data } = await api.get<ResumenK5Response>("/api/resumen_k5");
  return data;
}

export async function getPerfilDetalleK5(clusterId: number): Promise<PerfilDetalleK5> {
  const { data } = await api.get<PerfilDetalleK5>(`/api/perfiles_k5/${clusterId}`);
  return data;
}

export async function getMapaK5(perfiles: number[]): Promise<MapaK5Response> {
  const { data } = await api.get<MapaK5Response>("/api/mapa_k5", {
    params: { perfiles: perfiles.join(",") },
  });
  return data;
}

// --- Clustering POR RAMA (ADMINISTRATIVO o DOCENTE por separado, ver types.ts) --------

export async function getResumenPorRama(
  tipoClustering: TipoClusteringRama,
  rama: Rama,
): Promise<ResumenPorRamaResponse> {
  const { data } = await api.get<ResumenPorRamaResponse>("/api/resumen_por_rama", {
    params: { tipo_clustering: tipoClustering, rama },
  });
  return data;
}

export async function getPerfilDetallePorRama(
  clusterId: number,
  tipoClustering: TipoClusteringRama,
  rama: Rama,
): Promise<PerfilDetallePorRama> {
  const { data } = await api.get<PerfilDetallePorRama>(`/api/perfiles_por_rama/${clusterId}`, {
    params: { tipo_clustering: tipoClustering, rama },
  });
  return data;
}

export async function getMapaPorRama(
  tipoClustering: TipoClusteringRama,
  rama: Rama,
  perfiles: number[] = [],
): Promise<MapaPorRamaResponse> {
  const { data } = await api.get<MapaPorRamaResponse>("/api/mapa_por_rama", {
    params: { tipo_clustering: tipoClustering, rama, perfiles: perfiles.join(",") },
  });
  return data;
}

export interface PersonaResumen {
  IDPERSONA: number;
  NOMBRE_COMPLETO: string;
}

export async function getPersonas(): Promise<PersonaResumen[]> {
  const { data } = await api.get<{ personas: PersonaResumen[] }>("/api/personas");
  return data.personas;
}

export async function getPersonaFicha(
  idPersona: number,
  origenBusqueda?: "trayectoria",
): Promise<PersonaFichaResponse> {
  const { data } = await api.get<PersonaFichaResponse>(`/api/personas/${idPersona}`, {
    params: origenBusqueda ? { origen_busqueda: origenBusqueda } : {},
  });
  return data;
}

export interface EquiposFiltros {
  vigencia: string;
  tipo: string[];
  nivel: string[];
  minPublicaciones: number;
  minExpAdmin: number;
  maxIrregularidad: number;
  minDuracionMediana: number;
  minCargosEspol: number;
  maxCargosEspol: number;
}

export async function getEquipos(filtros: EquiposFiltros): Promise<EquiposResponse> {
  const { data } = await api.get<EquiposResponse>("/api/equipos", {
    params: {
      vigencia: filtros.vigencia,
      tipo: filtros.tipo.join(","),
      nivel: filtros.nivel.join(","),
      min_publicaciones: filtros.minPublicaciones,
      min_exp_admin: filtros.minExpAdmin,
      max_turbulencia: filtros.maxIrregularidad,
      min_duracion_mediana: filtros.minDuracionMediana,
      min_cargos_espol: filtros.minCargosEspol,
      max_cargos_espol: filtros.maxCargosEspol,
    },
  });
  return data;
}

export interface BusquedaAvanzadaParams extends EquiposFiltros {
  consulta: string;
  topN: number;
  // Ver SeccionBusqueda en types.ts: vacio/undefined busca en el embedding general (todo
  // el perfil); una o mas secciones limita la similitud a ese texto especifico (evita que
  // temas puntuales se diluyan en personas con trayectoria extensa).
  secciones?: string[];
}

export interface ResultadoAvanzado {
  rango: number;
  id_persona: number;
  nombre_completo: string;
  cluster: number | null;
  perfil_nombre: string | null;
  vigente: boolean;
  tipo_empleado: string | null;
  cargo_actual: string | null;
  n_cargos_espol: number | null;
  duracion_mediana_tramo_anios: number | null;
  evidencia: string;
}

export interface BusquedaAvanzadaResponse {
  consulta: string;
  secciones?: string[];
  n_candidatos_tras_filtros: number;
  resultados: ResultadoAvanzado[];
}

export async function buscarAvanzada(p: BusquedaAvanzadaParams): Promise<BusquedaAvanzadaResponse> {
  const { data } = await api.post<BusquedaAvanzadaResponse>("/api/buscar_avanzado", {
    consulta: p.consulta,
    top_n: p.topN,
    vigencia: p.vigencia,
    tipo: p.tipo.join(","),
    nivel: p.nivel.join(","),
    min_publicaciones: p.minPublicaciones,
    min_exp_admin: p.minExpAdmin,
    max_turbulencia: p.maxIrregularidad,
    min_duracion_mediana: p.minDuracionMediana,
    min_cargos_espol: p.minCargosEspol,
    max_cargos_espol: p.maxCargosEspol,
    secciones: p.secciones && p.secciones.length > 0 ? p.secciones : undefined,
  });
  return data;
}

export async function getSeccionesBusqueda(): Promise<SeccionesBusquedaResponse> {
  const { data } = await api.get<SeccionesBusquedaResponse>("/api/secciones_busqueda");
  return data;
}

// Igual que buscarAvanzada, pero ordena por afinidad al embedding de TRAYECTORIA (cargo/
// unidad/permanencia/estabilidad/movilidad) en vez del embedding general - capa
// exploratoria para comparar ambos rankings, ver /api/buscar_avanzado_trayectoria.
export async function buscarAvanzadaTrayectoria(p: BusquedaAvanzadaParams): Promise<BusquedaAvanzadaResponse> {
  const { data } = await api.post<BusquedaAvanzadaResponse>("/api/buscar_avanzado_trayectoria", {
    consulta: p.consulta,
    top_n: p.topN,
    vigencia: p.vigencia,
    tipo: p.tipo.join(","),
    nivel: p.nivel.join(","),
    min_publicaciones: p.minPublicaciones,
    min_exp_admin: p.minExpAdmin,
    max_turbulencia: p.maxIrregularidad,
    min_duracion_mediana: p.minDuracionMediana,
    min_cargos_espol: p.minCargosEspol,
    max_cargos_espol: p.maxCargosEspol,
  });
  return data;
}
