import { useEffect, useId, useState, type ReactNode } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { PaginaPersonas } from "../api/client";
import { OPCIONES_POR_PAGINA, type ListaPersonas } from "../lib/listaPersonas";

// Piezas para recorrer las personas de un grupo (patrón, tema, microarquetipo…) sin listas
// inmensas: el buscador por nombre dentro del grupo y los controles de paginación (el estado vive
// en `useListaPersonas`). La paginación y el filtro se hacen en la API (ver `_pagina_personas`).

const norm = (s: string) => s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

/** Resalta en `texto` los términos de `q` (sin distinguir tildes ni mayúsculas). */
export function Resaltado({ texto, q }: { texto: string; q: string }) {
  const terminos = norm(q).split(/\s+/).filter((t) => t.length > 0);
  const base = [...texto].map(norm);
  // solo si cada letra se normaliza a una sola (casi siempre); si no, sin resaltar
  if (!terminos.length || base.some((c) => c.length !== 1)) return <>{texto}</>;
  const plano = base.join("");
  const marca = new Array<boolean>(plano.length).fill(false);
  for (const t of terminos) {
    for (let i = plano.indexOf(t); i >= 0; i = plano.indexOf(t, i + 1)) marca.fill(true, i, i + t.length);
  }
  const letras = [...texto];
  const trozos: ReactNode[] = [];
  let i = 0;
  while (i < letras.length) {
    let j = i;
    while (j < letras.length && marca[j] === marca[i]) j++;
    const s = letras.slice(i, j).join("");
    trozos.push(marca[i] ? <mark key={i} className="bg-amber-100 text-inherit rounded-sm">{s}</mark> : s);
    i = j;
  }
  return <>{trozos}</>;
}

interface PersonaSugerida {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
}

interface PropsBuscador<T extends PersonaSugerida> {
  /** identifica el grupo, para la caché de las sugerencias */
  claveGrupo: unknown[];
  /** p. ej. "Patrón 3": dónde se busca */
  nombreGrupo: string;
  /** personas del grupo (sin filtro), para el texto de ayuda */
  totalGrupo: number | null;
  /** primeras coincidencias de `q` en el grupo */
  sugerir: (q: string) => Promise<PaginaPersonas<T>>;
  /** búsqueda aplicada a la lista ("" = ninguna) */
  aplicado: string;
  onAplicar: (q: string) => void;
  onPersona: (id: number, nombre: string) => void;
}

const N_SUGERENCIAS = 8;

/** Buscador por nombre dentro del grupo, con sugerencias mientras se escribe. Elegir una
 *  sugerencia abre su ficha; Enter (o "ver todas") filtra la lista con lo escrito. */
export function BuscadorEnGrupo<T extends PersonaSugerida>({
  claveGrupo, nombreGrupo, totalGrupo, sugerir, aplicado, onAplicar, onPersona,
}: PropsBuscador<T>) {
  const [texto, setTexto] = useState(aplicado);
  // si la búsqueda aplicada cambia desde fuera (p. ej. "Quitar"), el campo la refleja
  const [aplicadoAntes, setAplicadoAntes] = useState(aplicado);
  if (aplicado !== aplicadoAntes) {
    setAplicadoAntes(aplicado);
    if (aplicado !== texto.trim()) setTexto(aplicado);
  }
  const [consulta, setConsulta] = useState(aplicado.trim());
  const [abierto, setAbierto] = useState(false);
  const [activo, setActivo] = useState(-1);
  const id = useId();

  useEffect(() => {
    const t = setTimeout(() => setConsulta(texto.trim()), 200);
    return () => clearTimeout(t);
  }, [texto]);

  const { data, isFetching } = useQuery({
    queryKey: [...claveGrupo, "sugerencias", consulta],
    queryFn: () => sugerir(consulta),
    enabled: consulta.length >= 2,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
  const sugerencias = consulta.length >= 2 ? data?.personas.slice(0, N_SUGERENCIAS) ?? [] : [];
  const visible = abierto && consulta.length >= 2;

  const aplicar = (q: string) => {
    onAplicar(q.trim());
    setAbierto(false);
    setActivo(-1);
  };
  const elegir = (p: T) => {
    setAbierto(false);
    setActivo(-1);
    onPersona(p.persona_id, p.nombre);
  };

  return (
    <div className="relative">
      <div className="flex items-center gap-1.5 border rounded-md bg-white px-2 focus-within:ring-2 focus-within:ring-espol-blue/40">
        <svg aria-hidden viewBox="0 0 20 20" className="w-3.5 h-3.5 text-slate-400 shrink-0" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="8.5" cy="8.5" r="5.5" />
          <path d="M13 13l4.5 4.5" strokeLinecap="round" />
        </svg>
        <input
          role="combobox"
          aria-expanded={visible}
          aria-controls={`${id}-lista`}
          aria-autocomplete="list"
          aria-activedescendant={visible && activo >= 0 ? `${id}-op-${activo}` : undefined}
          value={texto}
          onChange={(e) => {
            setTexto(e.target.value);
            setAbierto(true);
            setActivo(-1);
            if (!e.target.value.trim() && aplicado) onAplicar("");
          }}
          onFocus={() => setAbierto(true)}
          onBlur={() => setTimeout(() => setAbierto(false), 150)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown" && sugerencias.length) {
              e.preventDefault();
              setAbierto(true);
              setActivo((i) => (i + 1) % sugerencias.length);
            } else if (e.key === "ArrowUp" && sugerencias.length) {
              e.preventDefault();
              setActivo((i) => (i <= 0 ? sugerencias.length - 1 : i - 1));
            } else if (e.key === "Enter") {
              e.preventDefault();
              if (visible && activo >= 0 && sugerencias[activo]) elegir(sugerencias[activo]);
              else aplicar(texto);
            } else if (e.key === "Escape") {
              // no cerrar el patrón (Esc de la página) mientras se usa el buscador
              e.stopPropagation();
              if (visible) setAbierto(false);
              else if (texto) {
                setTexto("");
                if (aplicado) onAplicar("");
              } else (e.target as HTMLInputElement).blur();
            }
          }}
          placeholder={`Buscar por nombre entre ${totalGrupo !== null ? `las ${totalGrupo} personas de ` : ""}${nombreGrupo}…`}
          className="flex-1 min-w-0 py-1.5 text-sm bg-transparent focus:outline-none"
        />
        {texto && (
          <button
            type="button"
            aria-label="Borrar búsqueda"
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => {
              setTexto("");
              setConsulta("");
              if (aplicado) onAplicar("");
            }}
            className="text-slate-400 hover:text-slate-700 text-base leading-none px-0.5"
          >
            ×
          </button>
        )}
      </div>
      {visible && (
        <div className="absolute z-40 mt-1 w-full bg-white border rounded-md shadow-lg overflow-hidden">
          {isFetching && !data && <p className="text-xs text-slate-500 p-3">Buscando…</p>}
          {data && sugerencias.length === 0 && (
            <p className="text-xs text-slate-500 p-3">Nadie en {nombreGrupo} coincide con «{consulta}».</p>
          )}
          <ul id={`${id}-lista`} role="listbox" aria-label={`Sugerencias en ${nombreGrupo}`} className="max-h-72 overflow-y-auto">
            {sugerencias.map((p, i) => (
              <li
                key={p.persona_id}
                id={`${id}-op-${i}`}
                role="option"
                aria-selected={activo === i}
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActivo(i)}
                onClick={() => elegir(p)}
                className={`px-3 py-1.5 cursor-pointer border-b last:border-b-0 ${activo === i ? "bg-slate-100" : ""}`}
              >
                <span className="flex items-baseline gap-2">
                  <span className="text-sm text-slate-800 flex-1 truncate">
                    <Resaltado texto={p.nombre} q={consulta} />
                  </span>
                  <span className="text-[11px] text-slate-400 tabular-nums" title={`Lugar en el orden de ${nombreGrupo}`}>
                    n.º {p.posicion}
                  </span>
                </span>
                <span className="block text-[11px] text-slate-500 truncate">{p.cargo_actual ?? "Sin cargo actual"}</span>
              </li>
            ))}
          </ul>
          {data && data.total_filtrado > 0 && (
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => aplicar(texto)}
              className="w-full text-left px-3 py-2 text-xs text-espol-blue bg-slate-50 hover:bg-slate-100 border-t"
            >
              {data.total_filtrado > sugerencias.length
                ? `Ver las ${data.total_filtrado} coincidencias en la lista`
                : "Mostrar solo estas en la lista"}{" "}
              <kbd className="ml-1 text-[10px] text-slate-500 border rounded px-1 bg-white">Enter</kbd>
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** "26–50 de 312" y el selector de cuántas mostrar por página. */
export function ResumenPagina({ datos, lista }: { datos: PaginaPersonas<unknown> | undefined; lista: ListaPersonas }) {
  const desde = datos && datos.total_filtrado ? (datos.pagina - 1) * datos.por_pagina + 1 : 0;
  const hasta = datos ? desde + datos.personas.length - (datos.personas.length ? 1 : 0) : 0;
  return (
    <div className="flex items-center gap-2 text-[11px] text-slate-500">
      <span className="flex-1 tabular-nums" aria-live="polite">
        {datos
          ? datos.total_filtrado === 0
            ? "Ninguna persona"
            : `${desde}–${hasta} de ${datos.total_filtrado}${datos.q ? ` coincidencias (de ${datos.total})` : ""}`
          : "…"}
      </span>
      <label className="flex items-center gap-1">
        Mostrar
        <select
          value={lista.porPagina}
          onChange={(e) => lista.setPorPagina(Number(e.target.value))}
          className="border rounded px-1 py-0.5 bg-white text-slate-700"
        >
          {OPCIONES_POR_PAGINA.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        por página
      </label>
    </div>
  );
}

/** Números de página a mostrar: siempre la primera, la última y dos alrededor de la actual. */
const numeros = (actual: number, total: number): (number | "…")[] => {
  const s = new Set([1, total, actual - 1, actual, actual + 1].filter((n) => n >= 1 && n <= total));
  if (actual <= 3) [2, 3, 4].forEach((n) => n <= total && s.add(n));
  if (actual >= total - 2) [total - 3, total - 2, total - 1].forEach((n) => n >= 1 && s.add(n));
  const orden = [...s].sort((a, b) => a - b);
  const salida: (number | "…")[] = [];
  orden.forEach((n, i) => {
    if (i > 0 && n - orden[i - 1] > 1) salida.push(n - orden[i - 1] === 2 ? n - 1 : "…");
    salida.push(n);
  });
  return salida;
};

/** Controles de página, fijos al pie del panel que se desplaza. */
export function Paginacion({ datos, lista, onCambio }: {
  datos: PaginaPersonas<unknown> | undefined; lista: ListaPersonas; onCambio?: () => void;
}) {
  if (!datos || datos.paginas <= 1) return null;
  const ir = (p: number) => {
    lista.setPagina(Math.min(Math.max(1, p), datos.paginas));
    onCambio?.();
  };
  const boton = "min-w-[1.75rem] h-7 px-1.5 rounded text-xs tabular-nums disabled:opacity-30 disabled:cursor-default";
  return (
    <nav
      aria-label="Páginas"
      className="sticky bottom-0 bg-white/95 backdrop-blur border-t px-3 py-2 flex items-center justify-center gap-0.5"
    >
      <button className={`${boton} text-slate-600 hover:bg-slate-100`} disabled={datos.pagina === 1} onClick={() => ir(datos.pagina - 1)}
        aria-label="Página anterior" title="Página anterior">
        ‹
      </button>
      {numeros(datos.pagina, datos.paginas).map((n, i) =>
        n === "…" ? (
          <span key={`s${i}`} className="text-xs text-slate-400 px-1">…</span>
        ) : (
          <button
            key={n}
            onClick={() => ir(n)}
            aria-current={n === datos.pagina ? "page" : undefined}
            className={`${boton} ${n === datos.pagina ? "bg-espol-navy text-white font-medium" : "text-slate-700 hover:bg-slate-100"}`}
          >
            {n}
          </button>
        ),
      )}
      <button className={`${boton} text-slate-600 hover:bg-slate-100`} disabled={datos.pagina === datos.paginas}
        onClick={() => ir(datos.pagina + 1)} aria-label="Página siguiente" title="Página siguiente">
        ›
      </button>
    </nav>
  );
}

/** Aviso de búsqueda aplicada a la lista, con la opción de quitarla. */
export function FiltroAplicado({ lista }: { lista: ListaPersonas }) {
  if (!lista.q) return null;
  return (
    <p className="text-[11px] text-slate-600 flex items-center gap-1.5">
      <span className="bg-amber-50 border border-amber-200 rounded px-1.5 py-0.5">
        Nombre contiene «{lista.q}»
      </span>
      <button onClick={() => lista.setQ("")} className="text-espol-blue hover:underline">
        Quitar
      </button>
    </p>
  );
}
