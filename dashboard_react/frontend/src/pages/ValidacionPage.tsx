import { useEffect, useState, type ReactNode } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import {
  comparar, getAmbitos, getDimension, getDimensiones, getPatronesGlobales, getPersonaEnDimension, getPersonasDimension,
  getPersonasPatronGlobal,
  type Ambito, type ConsultaPagina, type DimensionPatronGlobal, type OrdenLista, type PaginaPersonas, type Patron,
} from "../api/client";
import { BloqueDimension, ComponentesPatron, IntensidadesFrenteGrupo, ListaEvidencias } from "../components/DetallePersona";
import { BuscadorEnGrupo, FiltroAplicado, Paginacion, Resaltado, ResumenPagina } from "../components/ListaPaginada";
import { ListaDimensiones } from "../components/PanelPatronGlobal";
import { ProveedorPatronesDimension } from "../components/PatronesDimension";
import { colorPatron } from "../lib/colores";
import { enlaceComparar } from "../lib/enlaces";
import { useListaPersonas } from "../lib/listaPersonas";
import { de } from "../lib/texto";

const AMBITOS: { id: Ambito; nombre: string }[] = [
  { id: "todos", nombre: "Todo el personal" },
  { id: "administrativos", nombre: "Administrativos" },
  { id: "docentes", nombre: "Docentes" },
];
const NOMBRE_AMBITO: Record<Ambito, string> = {
  todos: "todo el personal",
  administrativos: "el personal administrativo",
  docentes: "el personal docente",
};
type Tipo = "dimension" | "global";

/** Persona de un grupo, igual para patrones por dimensión y globales. */
interface Miembro {
  persona_id: number;
  nombre: string;
  cargo_actual: string | null;
  vigente: boolean;
  /** con la persona más representativa: 1 = ella misma; 0 = la más distinta del grupo */
  similitud: number | null;
  es_rep: boolean;
  entre_dos: boolean;
}

const ORDENES: { id: OrdenLista; nombre: string; ayuda: string }[] = [
  { id: "grupo", nombre: "Más parecidas", ayuda: "De más a menos parecida a la persona más representativa" },
  { id: "inverso", nombre: "Menos parecidas", ayuda: "Empieza por las más distintas a la persona más representativa: los bordes del grupo" },
  { id: "azar", nombre: "Al azar", ayuda: "Una muestra al azar del grupo, sin quedarse con los extremos" },
];

// Revisión de los grupos descubiertos, para uso del equipo (solo visual, no cambia nada): qué dice
// el patrón, quién lo representa y sus evidencias, y cuánto se le parece cada persona del grupo,
// con sus evidencias a la vista para juzgar si el grupo tiene sentido.
export default function ValidacionPage() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const ambito: Ambito = AMBITOS.some((a) => a.id === params.get("ambito")) ? (params.get("ambito") as Ambito) : "todos";
  const tipo: Tipo = params.get("tipo") === "global" ? "global" : "dimension";
  const dimension = params.get("dimension") ?? "investigacion";
  const patron = Number(params.get("patron") ?? 0) || 0;
  const micro = params.get("micro") !== null && params.get("micro") !== "" ? Number(params.get("micro")) : null;
  const [soloVigentes, setSoloVigentes] = useState(true);
  const [orden, setOrden] = useState<OrdenLista>("grupo");
  const [semilla, setSemilla] = useState(0);
  const [abierta, setAbierta] = useState<number | null>(null);

  const actualizar = (cambios: Record<string, string | null>) => {
    const p = new URLSearchParams(params);
    for (const [k, v] of Object.entries(cambios)) {
      if (v === null) p.delete(k);
      else p.set(k, v);
    }
    setParams(p, { replace: true });
    setAbierta(null);
  };

  const calcularAlto = () => Math.max(560, window.innerHeight - 150);
  const [alto, setAlto] = useState(calcularAlto);
  useEffect(() => {
    const f = () => setAlto(calcularAlto());
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);

  const ambitos = useQuery({ queryKey: ["ambitos"], queryFn: getAmbitos });
  const dimensiones = useQuery({ queryKey: ["dimensiones", ambito], queryFn: () => getDimensiones(ambito) });
  const detalle = useQuery({
    queryKey: ["dimension", ambito, dimension],
    queryFn: () => getDimension(ambito, dimension),
    enabled: tipo === "dimension",
  });
  const globales = useQuery({ queryKey: ["patrones-globales", ambito], queryFn: () => getPatronesGlobales(ambito) });

  const patronDim: Patron | undefined = tipo === "dimension" ? detalle.data?.patrones?.patrones[patron] : undefined;
  const pg = tipo === "global" ? globales.data?.patrones?.[patron] : undefined;
  const mg = pg && micro !== null ? pg.microarquetipos?.lista[micro] : undefined;
  const grupo = patronDim ?? mg ?? pg;
  const nombreGrupo =
    tipo === "dimension" ? `Patrón ${patron + 1} de ${detalle.data?.nombre ?? ""}` : mg ? mg.codigo : `Patrón global ${patron + 1}`;
  /** contexto para Comparar: la dimensión, "micro" o "global" */
  const contextoComparar = tipo === "dimension" ? dimension : mg ? "micro" : "global";
  const repId = grupo?.representante_id ?? null;

  const lista = useListaPersonas(`${ambito}|${tipo}|${dimension}|${patron}|${micro}|${soloVigentes}|${orden}|${semilla}`);
  const consulta = { pagina: lista.pagina, porPagina: lista.porPagina, q: lista.q, orden, semilla };
  const claveGrupo = ["validar", ambito, tipo, tipo === "dimension" ? dimension : null, patron, micro, soloVigentes];
  const buscar = async (pag: ConsultaPagina): Promise<PaginaPersonas<Miembro>> => {
    if (tipo === "dimension") {
      const r = await getPersonasDimension(ambito, dimension, { patron }, soloVigentes, pag);
      return {
        ...r,
        personas: r.personas.map((x) => ({
          persona_id: x.persona_id, nombre: x.nombre, cargo_actual: x.cargo_actual, vigente: x.vigente, posicion: x.posicion,
          similitud: x.similitud_representante ?? null, es_rep: false, entre_dos: !!x.mixto,
        })),
      };
    }
    const r = await getPersonasPatronGlobal(ambito, patron, micro, soloVigentes, pag);
    return {
      ...r,
      personas: r.personas.map((x) => ({
        persona_id: x.persona_id, nombre: x.nombre, cargo_actual: x.cargo_actual, vigente: x.vigente, posicion: x.posicion,
        similitud: x.similitud, es_rep: x.es_rep, entre_dos: x.entre_dos,
      })),
    };
  };
  const miembros = useQuery({
    queryKey: [...claveGrupo, lista.pagina, lista.porPagina, lista.q, orden, semilla],
    queryFn: () => buscar(consulta),
    enabled: !!grupo,
    placeholderData: keepPreviousData,
  });

  const referenciaGlobal: { dims: DimensionPatronGlobal[]; nombre: string } | null = mg
    ? { dims: mg.dimensiones, nombre: mg.codigo }
    : pg
      ? { dims: pg.dimensiones, nombre: `Patrón global ${pg.id + 1}` }
      : null;

  // desde aquí, "ir a la dimensión" abre la pestaña Perfiles en esa dimensión y patrón
  const irADimension = (d: string, p: number | null) =>
    navigate(`/?ambito=${ambito}&vista=dimension&dimension=${d}${p !== null ? `&patron=${p}` : ""}`);

  return (
    <ProveedorPatronesDimension ambito={ambito} onIr={irADimension}>
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="inline-flex bg-white border rounded-lg p-1">
          {AMBITOS.map((a) => {
            const info = ambitos.data?.ambitos.find((x) => x.ambito === a.id);
            return (
              <button
                key={a.id}
                onClick={() => actualizar({ ambito: a.id, patron: "0", micro: null })}
                className={`px-3 py-1.5 text-sm rounded-md ${ambito === a.id ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
              >
                {a.nombre}
                {info && <span className="ml-1.5 text-xs opacity-70">{info.n_vigentes}</span>}
              </button>
            );
          })}
        </div>
        <div className="inline-flex bg-white border rounded-lg p-1" role="group" aria-label="Qué grupos revisar">
          {([["dimension", "Patrones por dimensión"], ["global", "Patrones globales y microarquetipos"]] as const).map(([t, n]) => (
            <button
              key={t}
              onClick={() => actualizar({ tipo: t, patron: "0", micro: null })}
              aria-pressed={tipo === t}
              className={`px-3 py-1.5 text-sm rounded-md ${tipo === t ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
            >
              {n}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-500 flex-1 min-w-[16rem]">
          Para revisar si los grupos tienen sentido: qué dice el patrón, quién lo representa y cuánto se le parece cada persona.
          Solo se consulta; no cambia nada.
        </p>
      </div>

      <div className="grid lg:grid-cols-[17rem_minmax(0,1fr)_30rem] gap-4 items-start">
        {/* elegir el grupo */}
        <nav className="bg-white border rounded-lg overflow-y-auto p-2" style={{ height: alto }} aria-label="Grupos">
          {tipo === "dimension" ? (
            <>
              <p className="text-[11px] uppercase tracking-wide text-slate-500 px-2 pt-1 pb-2">Dimensión</p>
              <select
                value={dimension}
                onChange={(e) => actualizar({ dimension: e.target.value, patron: "0" })}
                className="w-full border rounded-md px-2 py-1.5 text-sm bg-white mb-3"
              >
                {dimensiones.data?.map((d) => (
                  <option key={d.dimension} value={d.dimension} disabled={d.k_patrones === 0}>
                    {d.nombre}
                    {d.k_patrones === 0 ? " (sin patrones)" : ` (${d.k_patrones})`}
                  </option>
                ))}
              </select>
              <p className="text-[11px] uppercase tracking-wide text-slate-500 px-2 pb-1">Patrones</p>
              {detalle.data?.patrones?.patrones.map((p) => (
                <BotonGrupo
                  key={p.id}
                  activo={patron === p.id}
                  color={colorPatron(p.id)}
                  titulo={`Patrón ${p.id + 1}`}
                  n={soloVigentes ? p.tamano_vigentes : p.tamano}
                  etiqueta={p.etiqueta}
                  onClick={() => actualizar({ patron: String(p.id) })}
                />
              ))}
              {detalle.data && !detalle.data.patrones && <p className="text-xs text-slate-500 px-2">Esta dimensión no tiene patrones.</p>}
            </>
          ) : (
            <>
              <p className="text-[11px] uppercase tracking-wide text-slate-500 px-2 pt-1 pb-2">Patrones globales</p>
              {globales.data?.patrones?.map((g) => (
                <div key={g.id}>
                  <BotonGrupo
                    activo={patron === g.id && micro === null}
                    color={colorPatron(g.id)}
                    titulo={`Patrón global ${g.id + 1}`}
                    n={soloVigentes ? g.tamano_vigentes : g.tamano}
                    etiqueta={g.etiqueta}
                    onClick={() => actualizar({ patron: String(g.id), micro: null })}
                  />
                  {(g.microarquetipos?.lista.length ?? 0) > 0 && (
                    <ul className="ml-4 mb-2 border-l pl-2">
                      {g.microarquetipos!.lista.map((m) => (
                        <li key={m.id}>
                          <button
                            onClick={() => actualizar({ patron: String(g.id), micro: String(m.id) })}
                            aria-pressed={patron === g.id && micro === m.id}
                            title={m.etiqueta}
                            className={`w-full text-left rounded px-1.5 py-1 flex items-center gap-1.5 ${patron === g.id && micro === m.id ? "bg-slate-100" : "hover:bg-slate-50"}`}
                          >
                            <span className={`text-xs ${patron === g.id && micro === m.id ? "font-semibold text-espol-navy" : "text-slate-700"}`}>{m.codigo}</span>
                            <span className="text-[11px] text-slate-500 truncate flex-1">{m.etiqueta}</span>
                            <span className="text-[11px] text-slate-500 tabular-nums">{soloVigentes ? m.tamano_vigentes : m.tamano}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </>
          )}
          <label className="text-[11px] text-slate-500 flex items-center gap-1 px-2 pt-3 mt-2 border-t">
            <input type="checkbox" checked={soloVigentes} onChange={(e) => setSoloVigentes(e.target.checked)} />
            solo personas vigentes
          </label>
        </nav>

        {/* qué dice el grupo y quién lo representa */}
        <section className="bg-white border rounded-lg overflow-y-auto" style={{ height: alto }}>
          {!grupo ? (
            <p className="text-sm text-slate-500 p-5">{detalle.isLoading || globales.isLoading ? "Cargando…" : "Elige un grupo."}</p>
          ) : (
            <>
              <header className="px-5 pt-4 pb-3 border-b">
                <h2 className="text-lg font-semibold text-espol-navy flex items-center gap-2">
                  {!mg && <span className="w-3 h-3 rounded-full" style={{ background: colorPatron(patron) }} />}
                  {nombreGrupo}
                </h2>
                <p className="text-sm text-slate-700 mt-1">
                  <span className="text-[11px] uppercase tracking-wide text-slate-500 mr-1">Lo que dice el patrón:</span>
                  {grupo.etiqueta}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {grupo.tamano_vigentes} personas vigentes · {grupo.tamano} en total · {Math.round(grupo.proporcion * 100)} %{" "}
                  {mg ? `del Patrón global ${patron + 1}` : tipo === "dimension" ? "de quienes tienen evidencias en la dimensión" : de(NOMBRE_AMBITO[ambito])}
                </p>
                <Calidad
                  tipo={tipo}
                  k={tipo === "dimension" ? detalle.data?.patrones?.k : mg ? pg?.microarquetipos?.k : globales.data?.k}
                  ari={tipo === "dimension" ? detalle.data?.patrones?.estabilidad_ari : mg ? pg?.microarquetipos?.estabilidad_ari : globales.data?.estabilidad_ari}
                  mixtos={tipo === "dimension" ? detalle.data?.patrones?.perfiles_mixtos : undefined}
                />
              </header>

              <Bloque titulo={tipo === "dimension" ? "En qué se distingue" : `En qué se distingue (frente a ${mg ? `el Patrón global ${patron + 1}` : NOMBRE_AMBITO[ambito]})`}>
                {patronDim ? (
                  <ComponentesPatron
                    componentes={patronDim.componentes}
                    nombreDimension={detalle.data?.nombre ?? ""}
                  />
                ) : referenciaGlobal ? (
                  <ListaDimensiones
                    dims={referenciaGlobal.dims}
                    referencia={mg ? `el Patrón global ${patron + 1}` : NOMBRE_AMBITO[ambito]}
                    ambito={ambito}
                    grupo={{ patron, micro, nombre: nombreGrupo }}
                  />
                ) : null}
              </Bloque>

              <Bloque titulo="Persona más representativa">
                {repId === null ? (
                  <p className="text-xs text-slate-500">El grupo no tiene personas vigentes que lo representen.</p>
                ) : (
                  <>
                    <p className="text-[11px] text-slate-500 mb-2">
                      La persona vigente más cercana al centro del grupo. Sus evidencias permiten comprobar si la etiqueta del patrón
                      describe bien a quien mejor lo representa.
                    </p>
                    <p className="text-sm font-semibold text-slate-800 mb-2">{grupo.representante_nombre}</p>
                    <DetalleMiembro
                      ambito={ambito}
                      tipo={tipo}
                      dimension={dimension}
                      personaId={repId}
                      referencia={referenciaGlobal}
                      evidenciasAbiertas
                    />
                  </>
                )}
              </Bloque>
            </>
          )}
        </section>

        {/* personas del grupo */}
        <aside className="bg-white border rounded-lg overflow-y-auto" style={{ height: alto }}>
          {grupo && (
            <>
              <div className="px-5 pt-4 pb-3 border-b space-y-2">
                <h3 className="text-base font-semibold text-espol-navy">Personas de {nombreGrupo}</h3>
                <p className="text-[11px] text-slate-500">
                  El porcentaje es cuánto se parece cada una a la persona más representativa (100 % = ella misma; 0 % = la más
                  distinta del grupo). Abre una para ver sus evidencias o compararla.
                </p>
                <div className="inline-flex bg-slate-100 rounded-md p-0.5" role="group" aria-label="Orden">
                  {ORDENES.map((o) => (
                    <button
                      key={o.id}
                      onClick={() => setOrden(o.id)}
                      aria-pressed={orden === o.id}
                      title={o.ayuda}
                      className={`px-2.5 py-1 text-xs rounded ${orden === o.id ? "bg-white shadow-sm text-espol-navy font-medium" : "text-slate-600"}`}
                    >
                      {o.nombre}
                    </button>
                  ))}
                </div>
                {orden === "azar" && (
                  <button onClick={() => setSemilla((s) => s + 1)} className="ml-2 text-xs text-espol-blue hover:underline">
                    Otra muestra
                  </button>
                )}
                <BuscadorEnGrupo
                  key={lista.contexto}
                  claveGrupo={claveGrupo}
                  nombreGrupo={nombreGrupo}
                  totalGrupo={miembros.data?.total ?? null}
                  sugerir={(q) => buscar({ q, pagina: 1, porPagina: 8, orden: "grupo" })}
                  aplicado={lista.q}
                  onAplicar={lista.setQ}
                  onPersona={(id, nombre) => {
                    // puede no estar en esta página: se filtra por su nombre y se abre
                    lista.setQ(nombre);
                    setAbierta(id);
                  }}
                />
                <FiltroAplicado lista={lista} />
                <ResumenPagina datos={miembros.data} lista={lista} />
              </div>
              <ul className={`divide-y transition-opacity ${miembros.isPlaceholderData ? "opacity-60" : ""}`}>
                {miembros.data?.personas.map((r) => {
                  const sim = r.similitud;
                  const esRep = r.es_rep || r.persona_id === repId;
                  const abiertaEsta = abierta === r.persona_id;
                  return (
                    <li key={r.persona_id}>
                      <button
                        onClick={() => setAbierta(abiertaEsta ? null : r.persona_id)}
                        aria-expanded={abiertaEsta}
                        className={`w-full text-left px-5 py-2 hover:bg-slate-50 ${abiertaEsta ? "bg-slate-50" : ""}`}
                      >
                        <span className="flex items-center gap-2">
                          <span className={`text-slate-400 text-xs transition-transform ${abiertaEsta ? "rotate-90" : ""}`}>▸</span>
                          <span className="text-sm text-slate-800 flex-1 truncate">
                            <Resaltado texto={r.nombre} q={lista.q} />
                          </span>
                          <span className="text-[10px] text-slate-400 tabular-nums" title="Lugar en el orden del grupo">
                            n.º {r.posicion}
                          </span>
                          <span className="w-16 h-1.5 bg-slate-100 rounded-sm" title="Similitud con la persona más representativa">
                            <span className="block h-1.5 bg-espol-blue rounded-sm" style={{ width: `${(sim ?? 0) * 100}%` }} />
                          </span>
                          <span className="text-xs tabular-nums text-slate-700 w-10 text-right">
                            {esRep ? "rep." : sim !== null ? `${Math.round(sim * 100)} %` : "—"}
                          </span>
                        </span>
                        <span className="block text-[11px] text-slate-500 truncate ml-5">
                          {r.cargo_actual ?? "Sin cargo actual"}
                          {!r.vigente && " · no vigente"}
                          {r.entre_dos && <span className="text-amber-700"> · entre dos grupos</span>}
                        </span>
                      </button>
                      {abiertaEsta && (
                        <div className="px-5 pb-4 pt-1 bg-slate-50 border-t">
                          {!esRep && repId !== null && (
                            <Link
                              to={enlaceComparar(ambito, contextoComparar, [repId, r.persona_id])}
                              className="inline-block mb-2 text-xs text-espol-blue hover:underline"
                            >
                              Comparar con la persona más representativa →
                            </Link>
                          )}
                          <DetalleMiembro
                            ambito={ambito}
                            tipo={tipo}
                            dimension={dimension}
                            personaId={r.persona_id}
                            referencia={referenciaGlobal}
                          />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
              {miembros.data?.total_filtrado === 0 && (
                <p className="text-xs text-slate-500 px-5 py-4">{lista.q ? `Nadie coincide con «${lista.q}».` : "El grupo no tiene personas."}</p>
              )}
              <Paginacion datos={miembros.data} lista={lista} />
            </>
          )}
        </aside>
      </div>
    </div>
    </ProveedorPatronesDimension>
  );
}

function BotonGrupo({ activo, color, titulo, n, etiqueta, onClick }: {
  activo: boolean; color: string; titulo: string; n: number; etiqueta: string; onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      aria-pressed={activo}
      className={`w-full text-left rounded-md px-2 py-2 mb-0.5 ${activo ? "bg-slate-100" : "hover:bg-slate-50"}`}
    >
      <span className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: color }} />
        <span className={`text-sm flex-1 ${activo ? "font-semibold text-espol-navy" : "text-slate-800"}`}>{titulo}</span>
        <span className="text-[11px] text-slate-500 tabular-nums">{n}</span>
      </span>
      <span className="block text-[11px] text-slate-500 mt-0.5">{etiqueta}</span>
    </button>
  );
}

const Bloque = ({ titulo, children }: { titulo: string; children: ReactNode }) => (
  <div className="px-5 py-4 border-b">
    <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{titulo}</h4>
    {children}
  </div>
);

/** Datos del agrupamiento que formó el grupo, para tenerlos a mano al juzgarlo. */
function Calidad({ tipo, k, ari, mixtos }: { tipo: Tipo; k?: number; ari?: number; mixtos?: number }) {
  if (k === undefined && ari === undefined) return null;
  return (
    <p className="text-[11px] text-slate-500 mt-1">
      {k !== undefined && `${k} grupos en total`}
      {ari !== undefined && (
        <span title="Cuánto se repiten los grupos al recalcularlos con variaciones (1 = idénticos)">
          {" · "}estabilidad {ari.toLocaleString("es", { maximumFractionDigits: 2 })}
          {ari >= 0.9 ? " (alta)" : ari >= 0.75 ? " (media)" : " (baja)"}
        </span>
      )}
      {mixtos !== undefined && tipo === "dimension" && ` · ${mixtos} personas entre dos patrones en la dimensión`}
    </p>
  );
}

/** Detalle de una persona del grupo: en una dimensión, su patrón, componentes, temas y evidencias
 *  de la dimensión; en lo global, su intensidad por dimensión frente al grupo y sus evidencias. */
function DetalleMiembro({ ambito, tipo, dimension, personaId, referencia, evidenciasAbiertas = false }: {
  ambito: Ambito; tipo: Tipo; dimension: string; personaId: number;
  referencia: { dims: DimensionPatronGlobal[]; nombre: string } | null; evidenciasAbiertas?: boolean;
}) {
  const enDim = useQuery({
    queryKey: ["persona-dimension", ambito, personaId, dimension],
    queryFn: () => getPersonaEnDimension(personaId, dimension, ambito),
    enabled: tipo === "dimension",
  });
  const global = useQuery({
    queryKey: ["comparar", ambito, String(personaId), null],
    queryFn: () => comparar(ambito, [personaId], null),
    enabled: tipo === "global",
  });
  if (tipo === "dimension") {
    if (!enDim.data) return <p className="text-xs text-slate-500">Cargando…</p>;
    return <BloqueDimension datos={enDim.data} evidenciasAbiertas={evidenciasAbiertas} />;
  }
  const p = global.data?.[0];
  if (!p) return <p className="text-xs text-slate-500">Cargando…</p>;
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-slate-500">{p.cargo_actual ?? "Sin cargo actual"}</p>
      <IntensidadesFrenteGrupo intensidades={p.intensidades} referencia={referencia?.dims ?? null} nombreReferencia={referencia?.nombre ?? null} />
      <div>
        <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">Evidencias</p>
        <ListaEvidencias evidencias={p.evidencias ?? []} abiertas={evidenciasAbiertas} />
      </div>
    </div>
  );
}
