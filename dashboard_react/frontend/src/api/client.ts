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

export async function getMapa(tipo: string, perfiles: number[]): Promise<MapaResponse> {
  const { data } = await api.get<MapaResponse>("/api/mapa", {
    params: { tipo, perfiles: perfiles.join(",") },
  });
  return data;
}

export async function getPersonasIds(): Promise<number[]> {
  const { data } = await api.get<{ ids: number[] }>("/api/personas");
  return data.ids;
}

export async function getPersonaFicha(idPersona: number): Promise<PersonaFichaResponse> {
  const { data } = await api.get<PersonaFichaResponse>(`/api/personas/${idPersona}`);
  return data;
}

export interface EquiposFiltros {
  perfiles: number[];
  vigencia: string;
  tipo: string[];
  nivel: string[];
  minPublicaciones: number;
  minExpAdmin: number;
}

export async function getEquipos(filtros: EquiposFiltros): Promise<EquiposResponse> {
  const { data } = await api.get<EquiposResponse>("/api/equipos", {
    params: {
      perfiles: filtros.perfiles.join(","),
      vigencia: filtros.vigencia,
      tipo: filtros.tipo.join(","),
      nivel: filtros.nivel.join(","),
      min_publicaciones: filtros.minPublicaciones,
      min_exp_admin: filtros.minExpAdmin,
    },
  });
  return data;
}

export async function buscarSemantica(consulta: string, topN: number): Promise<BusquedaResponse> {
  const { data } = await api.post<BusquedaResponse>("/api/buscar", { consulta, top_n: topN });
  return data;
}
