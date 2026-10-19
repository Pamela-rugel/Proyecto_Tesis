import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getComparacionPerfiles, type Ambito, type ComparacionPerfiles, type ContenidoVista, type TemaComparado, type VistaComparada,
} from "../api/client";
import { colorPatron, NOMBRE_TIPO } from "../lib/colores";
import Enlace from "./Enlace";

interface Props {
  ambito: Ambito;
  a: number;
  b: number;
  /** abrir la ficha de una de las dos personas */
  onPersona?: (id: number) => void;
}

// qué compara cada vista de la red del perfil completo (DEC-062)
const QUE_COMPARA: Record<string, string> = {
  actividad: "Cuánto y cómo participan en cada una de las 12 dimensiones: su nivel (percentil entre quienes tienen registros) y su patrón de actividad.",
  academico: "El significado de los títulos de sus publicaciones, proyectos de investigación, ponencias, tesis dirigidas, proyectos de vinculación y menciones de honor.",
  docencia: "El significado de las materias que dictan y de sus actividades de carga docente.",
  formacion: "El significado de sus títulos académicos, capacitaciones y certificaciones.",
  trayectoria: "El significado de los cargos que han ocupado en ESPOL (planta, contratos, funciones adicionales) y fuera.",
};

/** "A" o "B" en una pastilla oscura, junto al nombre de la persona */
function Persona({ letra, nombre, clase = "" }: { letra: "A" | "B"; nombre: string; clase?: string }) {
  return (
    <span className={`inline-flex items-center gap-1 min-w-0 ${clase}`} title={nombre}>
      <span className="text-[9px] font-semibold text-white bg-espol-navy rounded w-4 h-4 grid place-items-center shrink-0">{letra}</span>
      <span className="truncate">{nombre}</span>
    </span>
  );
}

// vistas de la más parecida (N.º menor) a la menos; las que no son vecinas, al final
const ordenVistas = (v: VistaComparada) => (v.vecinas ? (v.rango ?? 999) : 10_000);

// Dos personas lado a lado en las vistas del perfil completo, para comprobar si de verdad se
// parecen: qué forma cada vista, y en ella sus datos (actividad) o una tabla de temas con sus
// evidencias (contenido).
export default function CompararPerfiles({ ambito, a, b, onPersona }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["comparar-perfiles", ambito, a, b],
    queryFn: () => getComparacionPerfiles(ambito, a, b),
  });
  const [elegida, setElegida] = useState<string | null>(null);

  if (isLoading) return <p className="text-sm text-slate-500 p-5">Cargando comparación…</p>;
  if (isError || !data) return <p className="text-sm text-red-600 p-5">No se pudo cargar la comparación.</p>;

  const vistas = [...data.vistas].sort((x, y) => ordenVistas(x) - ordenVistas(y));
  const vista = vistas.find((v) => v.vista === elegida) ?? vistas[0];

  return (
    <section className="bg-white border rounded-lg">
      <header className="px-5 pt-3 pb-3 border-b">
        <div className="grid md:grid-cols-2 gap-3">
          {(["a", "b"] as const).map((k) => {
            const p = data[k];
            return (
              <div key={k} className="rounded-md border border-slate-200 px-3 py-2 flex gap-2">
                <span className="text-[10px] font-semibold text-white bg-espol-navy rounded w-5 h-5 grid place-items-center shrink-0">
                  {k.toUpperCase()}
                </span>
                <div className="min-w-0">
                  <Enlace className="text-sm font-semibold" onClick={onPersona ? () => onPersona(p.persona_id) : undefined}>{p.nombre}</Enlace>
                  <p className="text-[11px] text-slate-500 truncate">
                    {p.cargo_actual ?? "Sin cargo actual"}
                    {!p.vigente && " · no vigente"}
                  </p>
                  {p.perfil && (
                    <p className="text-[11px] text-slate-600">
                      Perfil {p.perfil.patron + 1}
                      {p.perfil.micro ? ` · ${p.perfil.micro}` : ""}
                    </p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </header>

      <div role="tablist" aria-label="Vistas" className="flex flex-wrap gap-1 px-4 border-b bg-slate-50/60">
        {vistas.map((v) => {
          const sinDatos = v.vista !== "actividad" && (v.a!.n === 0 || v.b!.n === 0);
          return (
            <button
              key={v.vista}
              role="tab"
              aria-selected={v.vista === vista.vista}
              onClick={() => setElegida(v.vista)}
              className={`px-3 py-2 text-xs border-b-2 -mb-px flex items-center gap-1.5 ${
                v.vista === vista.vista ? "border-espol-blue text-espol-navy font-semibold" : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
              title={v.vecinas ? "En esta vista son vecinas" : sinDatos ? "Una de las dos no tiene evidencias en esta vista" : "En esta vista no están entre las más parecidas"}
            >
              {v.nombre}
              {v.vecinas ? (
                <span className="tabular-nums rounded bg-blue-50 border border-blue-100 px-1 text-[10px] text-espol-navy">
                  {v.rango != null ? `N.º ${v.rango}` : "vecinas"}
                </span>
              ) : (
                <span className="text-[10px] text-slate-400">{sinDatos ? "sin datos" : "—"}</span>
              )}
            </button>
          );
        })}
      </div>
      <p className="px-5 pt-2 text-[10px] text-slate-400">
        Vistas de la más parecida a la menos. <strong className="font-semibold">N.º</strong>: puesto de {data.b.nombre} entre las
        personas más parecidas a {data.a.nombre} en esa vista (N.º 1 = la más parecida). «—»: en esa vista no está entre sus más parecidas.
      </p>

      <div className="px-5 py-4">
        {/* key: al cambiar de vista, la subpestaña de dimensión vuelve a «Todas» */}
        <VistaDetalle key={vista.vista} vista={vista} data={data} />
      </div>
    </section>
  );
}

function VistaDetalle({ vista, data }: { vista: VistaComparada; data: ComparacionPerfiles }) {
  // dimensión elegida en la tabla de temas (null = todas)
  const [dimension, setDimension] = useState<string | null>(null);
  return (
    <div className="space-y-4">
      <Contenido vista={vista} data={data} dimension={dimension} onDimension={setDimension} />
      {vista.vista === "actividad" ? (
        <Actividad vista={vista} data={data} />
      ) : (
        <Temas vista={vista} data={data} dimension={dimension} onDimension={setDimension} />
      )}
    </div>
  );
}

/** Qué forma la vista: sus dimensiones, sus tipos de evidencia y cuántas tiene cada persona. Clic
 *  en una dimensión: sus temas abajo. */
function Contenido({ vista, data, dimension, onDimension }: {
  vista: VistaComparada; data: ComparacionPerfiles; dimension: string | null; onDimension: (d: string | null) => void;
}) {
  const filas: ContenidoVista[] = vista.contenido ?? [];
  const conTemas = new Set((vista.temas ?? []).map((t) => t.dimension));
  return (
    <div>
      <p className="text-xs text-slate-700 mb-1.5">
        <strong>Qué compara:</strong> {QUE_COMPARA[vista.vista] ?? ""}
      </p>
      {vista.vista !== "actividad" && (
        <table className="w-full text-xs border rounded-md overflow-hidden">
          <thead className="bg-slate-50 text-[11px] text-slate-500">
            <tr>
              <th className="text-left font-normal px-2 py-1">Dimensión</th>
              <th className="text-left font-normal px-2 py-1">Evidencias que la forman</th>
              <th className="text-right font-normal px-2 py-1 w-44"><Persona letra="A" nombre={data.a.nombre} clase="justify-end max-w-full" /></th>
              <th className="text-right font-normal px-2 py-1 w-44"><Persona letra="B" nombre={data.b.nombre} clase="justify-end max-w-full" /></th>
            </tr>
          </thead>
          <tbody>
            {filas.map((f) => {
              const clic = conTemas.has(f.dimension);
              return (
                <tr
                  key={f.dimension}
                  className={`border-t ${clic ? "cursor-pointer hover:bg-slate-50" : ""} ${dimension === f.dimension ? "bg-blue-50/60" : ""}`}
                  onClick={clic ? () => onDimension(dimension === f.dimension ? null : f.dimension) : undefined}
                  title={clic ? `Ver los temas de ${f.nombre}` : undefined}
                >
                  <td className="px-2 py-1 text-slate-800">{f.nombre}</td>
                  <td className="px-2 py-1 text-[11px] text-slate-500">{f.tipos.map((t) => NOMBRE_TIPO[t] ?? t).join(", ")}</td>
                  <td className={`px-2 py-1 text-right tabular-nums ${f.n_a ? "text-slate-800" : "text-slate-300"}`}>{f.n_a}</td>
                  <td className={`px-2 py-1 text-right tabular-nums ${f.n_b ? "text-slate-800" : "text-slate-300"}`}>{f.n_b}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Actividad({ vista, data }: { vista: VistaComparada; data: ComparacionPerfiles }) {
  const filas = vista.dimensiones_actividad ?? [];
  const evid = new Map((vista.contenido ?? []).map((c) => [c.dimension, c]));
  const celda = (x: NonNullable<VistaComparada["dimensiones_actividad"]>[number]["a"]) =>
    x.n_evidencias === 0 ? (
      <span className="text-[11px] italic text-slate-400">sin registros</span>
    ) : (
      <span className="flex items-center gap-2">
        <span className="relative w-16 h-1.5 rounded-sm bg-slate-100 shrink-0" aria-hidden>
          {x.nivel != null && (
            <span className="absolute top-1/2 w-2 h-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-espol-blue" style={{ left: `${x.nivel}%` }} />
          )}
        </span>
        <span className="text-[11px] tabular-nums text-slate-700 w-6 text-right">{x.nivel != null ? Math.round(x.nivel) : "—"}</span>
        <span className="text-[10px] tabular-nums text-slate-400 w-10">{x.n_evidencias} ev.</span>
        {x.patron != null && (
          <span className="text-[11px] text-slate-600 truncate flex items-center gap-1" title={x.patron_nombre ?? undefined}>
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: colorPatron(x.patron) }} />
            {x.patron_nombre ?? `Patrón ${x.patron + 1}`}
          </span>
        )}
      </span>
    );
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-[11px] text-slate-500 border-b">
            <th className="text-left font-normal py-1.5 pr-3 w-40">Dimensión</th>
            <th className="text-left font-normal py-1.5 pr-3"><Persona letra="A" nombre={data.a.nombre} /></th>
            <th className="text-left font-normal py-1.5 pr-3"><Persona letra="B" nombre={data.b.nombre} /></th>
            <th className="text-left font-normal py-1.5 w-28">Coinciden</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.dimension} className={`border-b last:border-b-0 ${f.mismo_patron ? "bg-blue-50/40" : ""}`}>
              <td className="py-1.5 pr-3 text-slate-700" title={(evid.get(f.dimension)?.tipos ?? []).map((t) => NOMBRE_TIPO[t] ?? t).join(", ")}>
                {f.nombre}
              </td>
              <td className="py-1.5 pr-3">{celda(f.a)}</td>
              <td className="py-1.5 pr-3">{celda(f.b)}</td>
              <td className="py-1.5 text-[11px] text-espol-navy">{f.mismo_patron ? "✓ mismo patrón" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-[10px] text-slate-400 mt-2">
        Número: nivel (percentil entre quienes tienen registros en la dimensión). Color: patrón de actividad. Pasa el cursor por una dimensión
        para ver qué evidencias la forman.
      </p>
    </div>
  );
}

/** Tabla de temas de una vista de contenido, por dimensión (subpestañas) o todas juntas: cuántas
 *  evidencias tiene cada una en cada tema, con sus textos al desplegar la fila. Primero los temas
 *  en común; luego los de solo una de las dos. */
function Temas({ vista, data, dimension, onDimension }: {
  vista: VistaComparada; data: ComparacionPerfiles; dimension: string | null; onDimension: (d: string | null) => void;
}) {
  const todos = vista.temas ?? [];
  const [abierta, setAbierta] = useState<string | null>(null);
  if (!todos.length) return <p className="text-[11px] text-slate-500">Ninguna de las dos tiene evidencias en esta vista.</p>;

  // subpestañas: «Todas» y una por dimensión con temas, en el orden de la vista
  const dims = (vista.contenido ?? [])
    .map((c) => ({ dimension: c.dimension, nombre: c.nombre, n: todos.filter((t) => t.dimension === c.dimension).length }))
    .filter((d) => d.n > 0);
  const temas = dimension ? todos.filter((t) => t.dimension === dimension) : todos;
  const maximo = Math.max(1, ...temas.map((t) => Math.max(t.n_a, t.n_b)));
  const comunes = temas.filter((t) => t.comun).length;
  const conTema = temas.filter((t) => t.tema !== null).length;
  const secciones: { id: string; titulo: string; filtro: (t: TemaComparado) => boolean }[] = [
    { id: "comun", titulo: "En común", filtro: (t) => t.comun },
    { id: "a", titulo: `Solo de ${data.a.nombre}`, filtro: (t) => !t.comun && t.tema !== null && t.n_a > 0 },
    { id: "b", titulo: `Solo de ${data.b.nombre}`, filtro: (t) => !t.comun && t.tema !== null && t.n_a === 0 },
    { id: "sin", titulo: "Sin tema asignado", filtro: (t) => t.tema === null },
  ];
  const barra = (n: number) => (
    <span className="flex items-center gap-1.5 justify-end">
      <span className={`tabular-nums w-6 text-right ${n ? "text-slate-800" : "text-slate-300"}`}>{n}</span>
      <span className="w-16 h-1.5 bg-slate-100 rounded-sm overflow-hidden" aria-hidden>
        <span className="block h-full bg-espol-blue/70" style={{ width: `${(n / maximo) * 100}%` }} />
      </span>
    </span>
  );

  return (
    <div>
      <p className="text-xs text-slate-700 mb-1.5">
        <strong>Temas de sus evidencias</strong>
        {dimension ? ` en ${dims.find((d) => d.dimension === dimension)?.nombre ?? dimension}` : ""}: comparten <strong>{comunes}</strong> de{" "}
        {conTema} temas. Clic en una fila para ver los textos.
      </p>
      {dims.length > 1 && (
        <div role="tablist" aria-label="Dimensiones" className="flex flex-wrap gap-1 mb-2">
          {[{ dimension: null as string | null, nombre: "Todas", n: todos.length }, ...dims].map((d) => (
            <button
              key={d.dimension ?? "todas"}
              role="tab"
              aria-selected={dimension === d.dimension}
              onClick={() => {
                onDimension(d.dimension);
                setAbierta(null);
              }}
              className={`px-2.5 py-1 text-[11px] rounded-full border ${
                dimension === d.dimension ? "bg-espol-navy text-white border-espol-navy" : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {d.nombre} <span className="opacity-70 tabular-nums">({d.n})</span>
            </button>
          ))}
        </div>
      )}
      <table className="w-full text-xs border rounded-md overflow-hidden">
        <thead className="bg-slate-50 text-[11px] text-slate-500">
          <tr>
            <th className="text-left font-normal px-2 py-1">Tema</th>
            {!dimension && <th className="text-left font-normal px-2 py-1 w-36">Dimensión</th>}
            <th className="text-right font-normal px-2 py-1 w-44"><Persona letra="A" nombre={data.a.nombre} clase="justify-end max-w-full" /></th>
            <th className="text-right font-normal px-2 py-1 w-44"><Persona letra="B" nombre={data.b.nombre} clase="justify-end max-w-full" /></th>
          </tr>
        </thead>
        <tbody>
          {secciones.map((sec) => {
            const filas = temas.filter(sec.filtro);
            if (!filas.length) return null;
            const columnas = dimension ? 3 : 4;
            return (
              <Fragment key={sec.id}>
                <tr className="border-t bg-slate-50/70">
                  <td colSpan={columnas} className={`px-2 py-1 text-[10px] uppercase tracking-wide ${sec.id === "comun" ? "text-espol-navy font-semibold" : "text-slate-500"}`}>
                    {sec.titulo} ({filas.length})
                  </td>
                </tr>
                {filas.map((t) => {
                  const clave = `${t.dimension}-${t.tema ?? "x"}`;
                  const desplegada = abierta === clave;
                  return (
                    <Fragment key={clave}>
                      <tr
                        className={`border-t cursor-pointer ${desplegada ? "bg-blue-50/50" : "hover:bg-slate-50"}`}
                        onClick={() => setAbierta(desplegada ? null : clave)}
                        aria-expanded={desplegada}
                      >
                        <td className="px-2 py-1 text-slate-800">
                          <span className="text-slate-400 mr-1">{desplegada ? "▾" : "▸"}</span>
                          {t.etiqueta ? t.etiqueta.split(",").slice(0, 4).join(",") : <span className="italic text-slate-500">sin tema</span>}
                        </td>
                        {!dimension && <td className="px-2 py-1 text-[11px] text-slate-500">{t.nombre_dimension}</td>}
                        <td className="px-2 py-1">{barra(t.n_a)}</td>
                        <td className="px-2 py-1">{barra(t.n_b)}</td>
                      </tr>
                      {desplegada && (
                        <tr className="bg-blue-50/30">
                          <td colSpan={columnas} className="px-3 py-2">
                            <div className="grid md:grid-cols-2 gap-3">
                              {(["a", "b"] as const).map((k) => {
                                const textos = k === "a" ? t.textos_a : t.textos_b;
                                const n = k === "a" ? t.n_a : t.n_b;
                                return (
                                  <div key={k} className="min-w-0">
                                    <p className="text-[11px] font-semibold text-slate-600 mb-0.5 flex items-center gap-1">
                                      <Persona letra={k === "a" ? "A" : "B"} nombre={data[k].nombre} />
                                      <span className="font-normal text-slate-500 shrink-0">· {n} evidencia{n === 1 ? "" : "s"}</span>
                                    </p>
                                    {textos.length === 0 ? (
                                      <p className="text-[11px] italic text-slate-400">Sin evidencias en este tema.</p>
                                    ) : (
                                      <ul className="space-y-0.5">
                                        {textos.map((x, i) => (
                                          <li key={i} className="text-[11px] text-slate-700 leading-snug">· {x}</li>
                                        ))}
                                        {n > textos.length && <li className="text-[10px] text-slate-400">… y {n - textos.length} más</li>}
                                      </ul>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <p className="text-[10px] text-slate-400 mt-1.5">
        Los temas se descubrieron agrupando los títulos por su significado. La red compara el significado de todas sus evidencias de la vista,
        así que pueden ser cercanas aunque compartan pocos temas.
      </p>
    </div>
  );
}
