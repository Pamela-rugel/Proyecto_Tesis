import { useState } from "react";

export const OPCIONES_POR_PAGINA = [10, 25, 50, 100] as const;
const CLAVE_POR_PAGINA = "personas-por-pagina";

const leerPorPagina = (): number => {
  try {
    const n = Number(localStorage.getItem(CLAVE_POR_PAGINA));
    return (OPCIONES_POR_PAGINA as readonly number[]).includes(n) ? n : 25;
  } catch {
    return 25;
  }
};

/** Página y búsqueda de la lista de un grupo. `contexto` identifica el grupo (ámbito, dimensión,
 *  patrón…): al cambiar, se vuelve a la primera página y se quita la búsqueda. Vive en la página
 *  (no en la lista) para que abrir una ficha y volver no pierda el lugar. La cantidad por página
 *  se recuerda en el navegador. */
export function useListaPersonas(contexto: string) {
  const [porPagina, setPorPaginaEstado] = useState(leerPorPagina);
  const [estado, setEstado] = useState({ contexto, pagina: 1, q: "" });
  let actual = estado;
  if (estado.contexto !== contexto) {
    actual = { contexto, pagina: 1, q: "" };
    setEstado(actual);
  }
  return {
    contexto,
    pagina: actual.pagina,
    q: actual.q,
    porPagina,
    setPagina: (pagina: number) => setEstado((e) => ({ ...e, pagina })),
    setQ: (q: string) => setEstado((e) => ({ ...e, q, pagina: 1 })),
    /** conserva a la vista la primera persona de la página actual */
    setPorPagina: (n: number) => {
      setEstado((e) => ({ ...e, pagina: Math.floor(((e.pagina - 1) * porPagina) / n) + 1 }));
      setPorPaginaEstado(n);
      try {
        localStorage.setItem(CLAVE_POR_PAGINA, String(n));
      } catch {
        /* sin almacenamiento: solo no se recuerda */
      }
    },
  };
}
export type ListaPersonas = ReturnType<typeof useListaPersonas>;
