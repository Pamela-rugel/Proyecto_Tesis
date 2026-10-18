import type { ReactNode } from "react";
import { OPCIONES_POR_PAGINA } from "../lib/paginacion";

// Paginación de las listas de personas: "‹ · 21–40 de 223 · ›" y cuántas por página. Las páginas
// las sirve la API (offset/limite), así que no hay tope de personas por lista. Va fija al pie del
// panel mientras su lista está a la vista (quien la usa la pone junto a la lista en un mismo
// contenedor) y puede llevar una nota corta que también queda siempre visible.

interface Props {
  pagina: number;
  total: number;
  porPagina: number;
  onCambiar: (pagina: number) => void;
  onPorPagina: (n: number) => void;
  cargando?: boolean;
  nota?: ReactNode;
}

export default function Paginacion({ pagina, total, porPagina, onCambiar, onPorPagina, cargando = false, nota }: Props) {
  const paginas = Math.max(1, Math.ceil(total / porPagina));
  const conControles = total > OPCIONES_POR_PAGINA[0];
  if (!conControles && !nota) return null;
  const desde = total ? pagina * porPagina + 1 : 0;
  const hasta = Math.min(total, (pagina + 1) * porPagina);
  const boton = "px-2 py-0.5 text-xs rounded border bg-white text-slate-700 hover:bg-slate-50 disabled:opacity-40 disabled:hover:bg-white";
  // destacado (azul) cuando se puede avanzar o retroceder
  const activo = "px-2.5 py-0.5 text-xs rounded border border-espol-blue bg-espol-blue text-white font-semibold hover:opacity-90 disabled:opacity-50";
  return (
    <div className="sticky bottom-0 z-10 border-t bg-white/95 backdrop-blur-sm px-4 py-1.5 space-y-0.5">
      {conControles && (
        <nav className="flex items-center gap-2" aria-label="Paginación">
          <button className={pagina > 0 ? activo : boton} disabled={pagina === 0 || cargando} onClick={() => onCambiar(pagina - 1)} aria-label="Página anterior">
            ‹
          </button>
          <span className={`text-[11px] tabular-nums ${cargando ? "text-slate-400" : "text-slate-500"}`}>
            {desde}–{hasta} de {total}
          </span>
          <button className={pagina < paginas - 1 ? activo : boton} disabled={pagina >= paginas - 1 || cargando}
            onClick={() => onCambiar(pagina + 1)} aria-label="Página siguiente">
            ›
          </button>
          <span className="flex-1" />
          <label className="text-[11px] text-slate-500 flex items-center gap-1">
            <select
              value={porPagina}
              onChange={(e) => onPorPagina(Number(e.target.value))}
              className="border rounded px-1 py-0.5 text-[11px] bg-white text-slate-700"
            >
              {OPCIONES_POR_PAGINA.map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
            por página
          </label>
        </nav>
      )}
      {nota && <p className="text-[10px] leading-tight text-slate-400">{nota}</p>}
    </div>
  );
}
