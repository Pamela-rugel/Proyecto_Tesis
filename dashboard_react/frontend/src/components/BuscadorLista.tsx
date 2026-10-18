import { useEffect, useState, type ReactNode } from "react";

// Buscador por nombre y apellidos de una lista paginada: filtra la lista del grupo en el que se está
// (patrón, tema, perfil…) mientras se escribe; la API filtra antes de paginar, así que busca en todas
// las páginas. Esc borra la búsqueda (sin cerrar el panel).

interface Props {
  /** búsqueda aplicada a la lista ("" = ninguna) */
  valor: string;
  onCambiar: (q: string) => void;
  /** p. ej. "Patrón 2": dónde se busca */
  contexto: string;
  /** coincidencias y total del grupo, para el texto de ayuda */
  coincidencias?: number;
  totalGrupo?: number;
}

export default function BuscadorLista({ valor, onCambiar, contexto, coincidencias, totalGrupo }: Props) {
  const [texto, setTexto] = useState(valor);
  // si la búsqueda aplicada cambia desde fuera (p. ej. al cambiar de grupo se vacía), el campo la sigue
  const [valorAntes, setValorAntes] = useState(valor);
  if (valor !== valorAntes) {
    setValorAntes(valor);
    if (valor !== texto.trim()) setTexto(valor);
  }

  useEffect(() => {
    const t = setTimeout(() => {
      const q = texto.trim();
      if (q !== valor && (q.length >= 2 || q === "")) onCambiar(q);
    }, 250);
    return () => clearTimeout(t);
  }, [texto, valor, onCambiar]);

  return (
    <div>
      <div className="flex items-center gap-1.5 border rounded-md bg-white px-2 focus-within:ring-2 focus-within:ring-espol-blue/40">
        <svg aria-hidden viewBox="0 0 20 20" className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="M13 13l4.5 4.5" strokeLinecap="round" />
        </svg>
        <input
          type="search"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape" && texto) {
              e.stopPropagation();
              setTexto("");
              onCambiar("");
            }
          }}
          placeholder={`Buscar por nombre o apellido en ${contexto}…`}
          aria-label={`Buscar por nombre o apellido en ${contexto}`}
          className="flex-1 min-w-0 py-1.5 text-sm bg-transparent focus:outline-none [&::-webkit-search-cancel-button]:hidden"
        />
        {texto && (
          <button
            type="button"
            onClick={() => {
              setTexto("");
              onCambiar("");
            }}
            className="text-slate-400 hover:text-slate-700 text-base leading-none px-0.5"
            aria-label="Borrar búsqueda"
          >
            ×
          </button>
        )}
      </div>
      {valor && coincidencias !== undefined && (
        <p className="text-[11px] text-slate-500 mt-1" aria-live="polite">
          {coincidencias === 0
            ? `Nadie en ${contexto} coincide con «${valor}».`
            : `${coincidencias} de ${totalGrupo ?? "?"} coinciden con «${valor}».`}
        </p>
      )}
    </div>
  );
}

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Resalta en `texto` los términos de `q` (sin distinguir tildes ni mayúsculas). */
export function Resaltado({ texto, q }: { texto: string; q: string }) {
  const terminos = norm(q).split(/\s+/).filter(Boolean);
  const letras = [...texto];
  const base = letras.map(norm);
  // solo si cada letra se normaliza a una sola (casi siempre); si no, sin resaltar
  if (!terminos.length || base.some((c) => c.length !== 1)) return <>{texto}</>;
  const plano = base.join("");
  const marca = new Array<boolean>(plano.length).fill(false);
  for (const t of terminos) {
    for (let i = plano.indexOf(t); i >= 0; i = plano.indexOf(t, i + 1)) marca.fill(true, i, i + t.length);
  }
  const trozos: ReactNode[] = [];
  for (let i = 0; i < letras.length; ) {
    let j = i;
    while (j < letras.length && marca[j] === marca[i]) j++;
    const s = letras.slice(i, j).join("");
    trozos.push(marca[i] ? <mark key={i} className="bg-amber-100 text-inherit rounded-sm">{s}</mark> : s);
    i = j;
  }
  return <>{trozos}</>;
}
