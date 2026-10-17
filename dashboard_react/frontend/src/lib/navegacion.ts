import { createContext, useContext } from "react";

/** Patrón global (o microarquetipo) desde el que se mira una dimensión. */
export interface GrupoGlobal {
  patron: number;
  micro: number | null;
  /** p. ej. "Patrón global 3" o "G3.1" */
  nombre: string;
}

export interface NavegacionPatrones {
  /** Abre la ventana con todos los patrones de la dimensión, resaltando `patron`; con `grupo`,
   *  cómo se reparten sus personas entre ellos. */
  verPatrones: (dimension: string, opciones?: { patron?: number | null; grupo?: GrupoGlobal | null }) => void;
  /** Ir a la dimensión en la vista "Por dimensión", con el patrón elegido y, si se da, la ficha de
   *  la persona abierta (con regreso). No existe donde no se puede ir. */
  irADimension?: (dimension: string, patron: number | null, persona?: number | null) => void;
}

/** La da `ProveedorPatronesDimension`; sin proveedor, los chips de patrón no se pueden abrir. */
export const ContextoPatrones = createContext<NavegacionPatrones | null>(null);
export const usePatronesDimension = () => useContext(ContextoPatrones);
