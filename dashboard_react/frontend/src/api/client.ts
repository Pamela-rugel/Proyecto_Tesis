import axios from "axios";
import type {
  BusquedaResponse,
  EquiposResponse,
  MapaResponse,
  PerfilDetalle,
  PersonaFichaResponse,
  ResumenResponse,
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

export interface PersonaResumen {
  IDPERSONA: number;
  NOMBRE_COMPLETO: string;
}

export async function getPersonas(): Promise<PersonaResumen[]> {
  const { data } = await api.get<{ personas: PersonaResumen[] }>("/api/personas");
  return data.personas;
}

export async function getPersonaFicha(idPersona: number): Promise<PersonaFichaResponse> {
  const { data } = await api.get<PersonaFichaResponse>(`/api/personas/${idPersona}`);
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

export async function buscarSemantica(
  consulta: string,
  topN: number,
  vigencia: string = "Cualquiera",
): Promise<BusquedaResponse> {
  const { data } = await api.post<BusquedaResponse>("/api/buscar", { consulta, top_n: topN, vigencia });
  return data;
}

export interface BusquedaAvanzadaParams extends EquiposFiltros {
  consulta: string;
  topN: number;
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
  });
  return data;
}
