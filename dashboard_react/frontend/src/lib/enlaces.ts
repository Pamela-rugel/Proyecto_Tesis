import type { Ambito } from "../api/client";

/** Enlace a la pestaña Comparar con estas personas en un contexto: una dimensión, "global" o "micro". */
export const enlaceComparar = (ambito: Ambito, contexto: string, ids: number[]) =>
  `/comparar?ambito=${ambito}&contexto=${encodeURIComponent(contexto)}&ids=${ids.join(",")}`;
