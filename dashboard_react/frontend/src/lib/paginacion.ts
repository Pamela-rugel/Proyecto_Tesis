// Opciones de tamaño de página de las listas de personas (ver components/Paginacion.tsx).
export const OPCIONES_POR_PAGINA = [10, 20, 30];
export const POR_PAGINA = 20;

// Cuántas personas por página: elección del usuario, recordada en este navegador (si se puede).
const CLAVE_POR_PAGINA = "perfiles.porPagina";
export function porPaginaGuardado(): number {
  try {
    const n = Number(window.localStorage.getItem(CLAVE_POR_PAGINA));
    return OPCIONES_POR_PAGINA.includes(n) ? n : POR_PAGINA;
  } catch {
    return POR_PAGINA;
  }
}
export function guardarPorPagina(n: number) {
  try {
    window.localStorage.setItem(CLAVE_POR_PAGINA, String(n));
  } catch {
    /* sin almacenamiento: solo dura en esta vista */
  }
}
