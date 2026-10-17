import { useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  comparar, getAmbitos, getDimensiones, getPatronesGlobales,
  type Ambito, type DimensionPatronGlobal, type PatronGlobal, type PersonaComparada,
} from "../api/client";
import BuscadorPersonas from "../components/BuscadorPersonas";
import {
  ComponentesFrentePatron, IntensidadesFrenteGrupo, ListaEvidencias, PatronEnDimension, TemasPersona,
} from "../components/DetallePersona";
import { colorPatron } from "../lib/colores";
import { textoSimilitud } from "../lib/texto";

const AMBITOS: { id: Ambito; nombre: string }[] = [
  { id: "todos", nombre: "Todo el personal" },
  { id: "administrativos", nombre: "Administrativos" },
  { id: "docentes", nombre: "Docentes" },
];
const MAX_PERSONAS = 4;

/** Contexto de la comparación: una dimensión (su clave), el perfil completo frente a su patrón
 *  global ("global") o frente a su microarquetipo ("micro"). */
type Contexto = string;

// Comparar 2–4 personas en un contexto: en una dimensión se comparan sus componentes y su patrón
// en ella; en el perfil completo, su intensidad en cada dimensión frente a su patrón global o a su
// microarquetipo. Arriba, las diferencias más grandes entre ellas.
export default function CompararPage() {
  const [params, setParams] = useSearchParams();
  const ambito: Ambito = AMBITOS.some((a) => a.id === params.get("ambito")) ? (params.get("ambito") as Ambito) : "todos";
  const contexto: Contexto = params.get("contexto") || "global";
  const ids = (params.get("ids") ?? "")
    .split(",")
    .map(Number)
    .filter((n) => Number.isInteger(n) && n > 0)
    .slice(0, MAX_PERSONAS);
  const esDimension = contexto !== "global" && contexto !== "micro";

  const actualizar = (cambios: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(cambios)) {
      if (v === null || v === "") p.delete(k);
      else p.set(k, v);
    }
    setParams(p, { replace: true });
  };
  const setIds = (nuevos: number[]) => actualizar({ ids: nuevos.join(",") });
  const agregar = (id: number) => !ids.includes(id) && ids.length < MAX_PERSONAS && setIds([...ids, id]);

  const ambitos = useQuery({ queryKey: ["ambitos"], queryFn: getAmbitos });
  const dimensiones = useQuery({ queryKey: ["dimensiones", ambito], queryFn: () => getDimensiones(ambito) });
  const globales = useQuery({ queryKey: ["patrones-globales", ambito], queryFn: () => getPatronesGlobales(ambito) });
  const datos = useQuery({
    queryKey: ["comparar", ambito, ids.join(","), esDimension ? contexto : null],
    queryFn: () => comparar(ambito, ids, esDimension ? contexto : null),
    enabled: ids.length > 0,
    placeholderData: keepPreviousData,
  });
  // el orden de las columnas sigue el de la URL
  const personas = ids.map((id) => datos.data?.find((p) => p.persona_id === id)).filter((p): p is PersonaComparada => !!p);
  const patrones = globales.data?.patrones ?? [];
  const nombreDim = dimensiones.data?.find((d) => d.dimension === contexto)?.nombre ?? contexto;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex bg-white border rounded-lg p-1">
          {AMBITOS.map((a) => {
            const info = ambitos.data?.ambitos.find((x) => x.ambito === a.id);
            return (
              <button
                key={a.id}
                onClick={() => actualizar({ ambito: a.id })}
                className={`px-3 py-1.5 text-sm rounded-md ${ambito === a.id ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
              >
                {a.nombre}
                {info && <span className="ml-1.5 text-xs opacity-70">{info.n_vigentes}</span>}
              </button>
            );
          })}
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          Comparar en
          <select
            value={contexto}
            onChange={(e) => actualizar({ contexto: e.target.value })}
            className="border rounded-md px-2 py-1.5 bg-white text-slate-800"
          >
            <optgroup label="Perfil completo (todas las dimensiones)">
              <option value="global">Frente a su patrón global</option>
              <option value="micro">Frente a su microarquetipo</option>
            </optgroup>
            <optgroup label="Una dimensión">
              {dimensiones.data?.map((d) => (
                <option key={d.dimension} value={d.dimension}>
                  {d.nombre}
                </option>
              ))}
            </optgroup>
          </select>
        </label>
        <div className="flex-1 min-w-[16rem] max-w-md">
          {ids.length < MAX_PERSONAS ? (
            <BuscadorPersonas ambito={ambito} onElegir={(r) => agregar(r.persona_id)} />
          ) : (
            <p className="text-xs text-slate-500">Máximo {MAX_PERSONAS} personas: quita una para agregar otra.</p>
          )}
        </div>
      </div>

      {ids.length === 0 ? (
        <div className="bg-white border rounded-lg p-8 text-sm text-slate-600 max-w-2xl">
          <p className="font-medium text-slate-800 mb-1">Elige entre 2 y {MAX_PERSONAS} personas para compararlas.</p>
          <p>
            Búscalas por nombre arriba, o llega aquí desde una ficha («Comparar con la persona más representativa») o desde la
            pestaña Validación. Elige el contexto: en una dimensión se comparan sus componentes y su patrón en ella; en el perfil
            completo, su intensidad en cada dimensión frente a su patrón global o a su microarquetipo.
          </p>
        </div>
      ) : (
        <>
          <Resumen personas={personas} contexto={contexto} patrones={patrones} nombreDim={nombreDim} />
          <Diferencias personas={personas} contexto={contexto} />
          <div className={`flex gap-3 overflow-x-auto pb-2 transition-opacity ${datos.isPlaceholderData ? "opacity-60" : ""}`}>
            {personas.map((p) => (
              <Columna
                key={p.persona_id}
                p={p}
                contexto={contexto}
                patrones={patrones}
                nombreDim={nombreDim}
                incluidos={ids}
                lleno={ids.length >= MAX_PERSONAS}
                onQuitar={() => setIds(ids.filter((x) => x !== p.persona_id))}
                onAgregar={agregar}
              />
            ))}
          </div>
          {datos.isLoading && <p className="text-sm text-slate-500">Cargando…</p>}
        </>
      )}
    </div>
  );
}

/** Grupo de la persona en el contexto: patrón de la dimensión, patrón global o microarquetipo. */
const grupoDe = (p: PersonaComparada, contexto: Contexto): string | null => {
  if (contexto === "global") return p.patron_global ? `G${p.patron_global.patron + 1}` : null;
  if (contexto === "micro") return p.patron_global?.micro?.codigo ?? null;
  return p.dimension?.patron ? `P${p.dimension.patron.patron + 1}` : null;
};

function Resumen({ personas, contexto, patrones, nombreDim }: {
  personas: PersonaComparada[]; contexto: Contexto; patrones: PatronGlobal[]; nombreDim: string;
}) {
  if (personas.length < 2) {
    return <p className="text-xs text-slate-500">Agrega al menos otra persona para ver las diferencias.</p>;
  }
  const grupos = personas.map((p) => grupoDe(p, contexto));
  const distintos = new Set(grupos.filter(Boolean));
  const donde =
    contexto === "global" ? "patrón global" : contexto === "micro" ? "microarquetipo" : `patrón de ${nombreDim}`;
  const etiqueta = (g: string) => {
    if (contexto === "global") return patrones[Number(g.slice(1)) - 1]?.etiqueta;
    if (contexto === "micro") {
      for (const pg of patrones) for (const m of pg.microarquetipos?.lista ?? []) if (m.codigo === g) return m.etiqueta;
    }
    return personas.find((p) => grupoDe(p, contexto) === g)?.dimension?.patron?.etiqueta;
  };
  return (
    <div className="bg-white border rounded-lg px-4 py-3 text-sm">
      {distintos.size === 1 && !grupos.includes(null) ? (
        <p>
          <strong>Todas en el mismo {donde}: {[...distintos][0]}</strong>
          <span className="text-slate-500"> · {etiqueta([...distintos][0]!)}</span>
        </p>
      ) : (
        <div>
          <p className="font-semibold">En {donde === "patrón global" ? "patrones globales" : donde === "microarquetipo" ? "microarquetipos" : `patrones de ${nombreDim}`} distintos:</p>
          <ul className="text-xs text-slate-600 mt-1 space-y-0.5">
            {[...distintos].map((g) => (
              <li key={g}>
                <strong>{g}</strong> ({personas.filter((p) => grupoDe(p, contexto) === g).map((p) => p.nombre.split(" ").slice(0, 2).join(" ")).join(", ")}) ·{" "}
                {etiqueta(g!)}
              </li>
            ))}
            {grupos.includes(null) && <li className="text-slate-500">Sin grupo en este contexto: {personas.filter((p) => !grupoDe(p, contexto)).map((p) => p.nombre).join(", ")}</li>}
          </ul>
        </div>
      )}
    </div>
  );
}

/** Filas (componentes o dimensiones) ordenadas por la diferencia entre la más alta y la más baja. */
function Diferencias({ personas, contexto }: { personas: PersonaComparada[]; contexto: Contexto }) {
  if (personas.length < 2) return null;
  const esDim = contexto !== "global" && contexto !== "micro";
  const filas = esDim
    ? (personas[0].dimension?.componentes ?? []).map((c) => ({
        clave: c.componente,
        nombre: c.descripcion.replace(" (log)", ""),
        valores: personas.map((p) => Math.round((p.dimension?.componentes.find((x) => x.componente === c.componente)?.valor ?? 0) * 100)),
      }))
    : personas[0].intensidades.map((d) => ({
        clave: d.dimension,
        nombre: d.nombre,
        valores: personas.map((p) => Math.floor(p.intensidades.find((x) => x.dimension === d.dimension)?.intensidad ?? 0)),
      }));
  const conRango = filas.map((f) => ({ ...f, rango: Math.max(...f.valores) - Math.min(...f.valores) })).sort((a, b) => b.rango - a.rango);
  return (
    <div className="bg-white border rounded-lg overflow-x-auto">
      <table className="w-full text-xs">
        <caption className="text-left px-4 pt-3 pb-1">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Diferencias</span>
          <span className="text-[11px] text-slate-500 ml-2">
            {esDim
              ? "Cada componente de 0 a 100 (100 = quien más tiene en el ámbito)."
              : "Intensidad en cada dimensión (percentil 0 a 100)."}{" "}
            Ordenadas de mayor a menor diferencia; resaltadas las de 25 puntos o más.
          </span>
        </caption>
        <thead>
          <tr className="text-slate-500 border-b">
            <th className="text-left font-normal px-4 py-1.5">{esDim ? "Componente" : "Dimensión"}</th>
            {personas.map((p) => (
              <th key={p.persona_id} className="text-right font-normal px-3 py-1.5 max-w-[10rem] truncate" title={p.nombre}>
                {p.nombre.split(" ").slice(0, 2).join(" ")}
              </th>
            ))}
            <th className="text-right font-normal px-4 py-1.5">Diferencia</th>
          </tr>
        </thead>
        <tbody>
          {conRango.map((f) => {
            const fuerte = f.rango >= 25;
            const max = Math.max(...f.valores);
            const min = Math.min(...f.valores);
            return (
              <tr key={f.clave} className={`border-b last:border-b-0 ${fuerte ? "bg-amber-50/70" : ""}`}>
                <td className="px-4 py-1.5 text-slate-700">{f.nombre}</td>
                {f.valores.map((v, i) => (
                  <td
                    key={i}
                    className={`px-3 py-1.5 text-right tabular-nums ${f.rango > 0 && v === max ? "font-semibold text-slate-900" : f.rango > 0 && v === min ? "text-slate-400" : "text-slate-700"}`}
                  >
                    {v}
                  </td>
                ))}
                <td className={`px-4 py-1.5 text-right tabular-nums ${fuerte ? "font-semibold text-amber-800" : "text-slate-500"}`}>{f.rango}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Columna({ p, contexto, patrones, nombreDim, incluidos, lleno, onQuitar, onAgregar }: {
  p: PersonaComparada; contexto: Contexto; patrones: PatronGlobal[]; nombreDim: string;
  incluidos: number[]; lleno: boolean; onQuitar: () => void; onAgregar: (id: number) => void;
}) {
  const g = p.patron_global;
  const pg = g ? patrones[g.patron] : undefined;
  let referencia: DimensionPatronGlobal[] | null = null;
  let nombreRef: string | null = null;
  let rep: { id: number | null; nombre: string | null; esRep: boolean } | null = null;
  if (contexto === "global" && g) {
    referencia = pg?.dimensiones ?? null;
    nombreRef = `su patrón global (G${g.patron + 1})`;
    rep = { id: g.representante_id, nombre: g.representante_nombre, esRep: g.es_representante };
  } else if (contexto === "micro" && g?.micro) {
    referencia = pg?.microarquetipos?.lista[g.micro.micro]?.dimensiones ?? null;
    nombreRef = `su microarquetipo (${g.micro.codigo})`;
    rep = { id: g.micro.representante_id, nombre: g.micro.representante_nombre, esRep: g.micro.es_representante };
  } else if (p.dimension?.patron) {
    const pt = p.dimension.patron;
    rep = { id: pt.representante_id, nombre: pt.representante_nombre, esRep: pt.es_representante };
  }
  const puedeAgregarRep = rep && !rep.esRep && rep.id !== null && !incluidos.includes(rep.id) && !lleno;

  return (
    <article className="bg-white border rounded-lg w-[22rem] shrink-0 flex flex-col">
      <header className="px-4 pt-3 pb-3 border-b">
        <div className="flex items-start gap-2">
          <h3 className="text-sm font-semibold text-espol-navy flex-1 leading-tight">{p.nombre}</h3>
          <button onClick={onQuitar} className="text-slate-400 hover:text-slate-700 leading-none text-lg" aria-label={`Quitar a ${p.nombre}`} title="Quitar">
            ×
          </button>
        </div>
        <p className="text-[11px] text-slate-500 mt-0.5 line-clamp-2">
          {p.cargo_actual ?? "Sin cargo actual"} · {p.tipo_empleado ?? "tipo desconocido"} · {p.vigente ? "vigente" : "no vigente"}
        </p>
      </header>

      <div className="px-4 py-3 border-b space-y-2">
        {contexto === "global" || contexto === "micro" ? (
          g ? (
            <div>
              <p className="text-sm text-slate-800 flex items-center gap-2">
                {contexto === "global" ? (
                  <>
                    <span className="w-2.5 h-2.5 rounded-full" style={{ background: colorPatron(g.patron) }} />
                    Patrón global {g.patron + 1}
                  </>
                ) : (
                  <>Microarquetipo {g.micro?.codigo ?? "—"}</>
                )}
              </p>
              <p className="text-xs text-slate-600">{contexto === "global" ? g.etiqueta : g.micro?.etiqueta ?? "Sin microarquetipo"}</p>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {contexto === "global"
                  ? textoSimilitud(g.similitud_representante, g.es_representante)
                  : g.micro
                    ? textoSimilitud(g.micro.similitud_representante, g.micro.es_representante)
                    : ""}
              </p>
              {(contexto === "global" ? g.mixto : g.micro?.mixto) && (
                <p className="text-[11px] text-amber-700">Está entre dos {contexto === "global" ? "patrones globales" : "microarquetipos"}.</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-500">Sin patrón global.</p>
          )
        ) : p.dimension ? (
          <>
            <p className="text-xs text-slate-600">
              {nombreDim}: puntaje <strong className="tabular-nums">{Math.round(p.dimension.puntaje)}</strong> de 100 · mayor o igual
              que el de {Math.round(p.dimension.posicion.menor + p.dimension.posicion.igual)} % del personal · {p.dimension.n_evidencias}{" "}
              evidencia{p.dimension.n_evidencias === 1 ? "" : "s"}
            </p>
            {p.dimension.patron ? (
              <PatronEnDimension patron={p.dimension.patron} />
            ) : (
              <p className="text-xs text-slate-500">
                {p.dimension.n_evidencias === 0 ? "Sin evidencias en esta dimensión." : "Esta dimensión no se divide en patrones."}
              </p>
            )}
          </>
        ) : null}
        {puedeAgregarRep && (
          <button onClick={() => onAgregar(rep!.id!)} className="text-[11px] text-espol-blue hover:underline text-left">
            + Agregar a la persona más representativa ({rep!.nombre})
          </button>
        )}
      </div>

      <div className="px-4 py-3 border-b">
        {contexto === "global" || contexto === "micro" ? (
          <IntensidadesFrenteGrupo intensidades={p.intensidades} referencia={referencia} nombreReferencia={nombreRef} />
        ) : p.dimension && p.dimension.n_evidencias > 0 ? (
          <ComponentesFrentePatron
            componentes={p.dimension.componentes}
            nombrePatron={p.dimension.patron ? `su Patrón ${p.dimension.patron.patron + 1}` : null}
          />
        ) : (
          <p className="text-xs text-slate-500">Sin componentes que comparar en esta dimensión.</p>
        )}
      </div>

      {p.dimension && p.dimension.temas.length > 0 && (
        <div className="px-4 py-3 border-b">
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Temas de su evidencia</p>
          <TemasPersona temas={p.dimension.temas} />
        </div>
      )}

      <div className="px-4 py-3">
        <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
          {p.dimension ? `Evidencias de ${nombreDim}` : "Evidencias"}
        </p>
        <ListaEvidencias evidencias={p.dimension?.evidencias ?? p.evidencias ?? []} />
      </div>
    </article>
  );
}
