import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { buscarSemantica, type ResultadoBusqueda, type RespuestaBusqueda, type Vigencia } from "../api/client";
import FichaPersona from "../components/FichaPersona";
import { NOMBRE_TIPO } from "../lib/colores";

const EJEMPLOS = [
  "experiencia en inteligencia artificial, proyectos de investigación en aprendizaje automático y docencia en programación",
  "alguien con doctorado y al menos 5 años de experiencia docente en estadística",
  "inglés avanzado, idealmente con publicaciones sobre acuicultura",
  "quien sepa de contratación pública y haya trabajado en la GTSI",
];

const VIGENCIAS: { id: Vigencia; texto: string }[] = [
  { id: "vigentes", texto: "Vigentes" },
  { id: "no_vigentes", texto: "No vigentes" },
  { id: "todos", texto: "Todos" },
];

const colorNivel = { alta: "bg-emerald-100 text-emerald-800 border-emerald-300", media: "bg-sky-50 text-sky-800 border-sky-200", baja: "bg-slate-50 text-slate-500 border-slate-200" };

function Interpretacion({ r }: { r: RespuestaBusqueda }) {
  const i = r.interpretacion;
  const fuente = r.interpretacion_meta.fuente;
  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="flex flex-wrap items-baseline gap-x-3">
        <h3 className="text-sm font-semibold text-espol-navy">Entendí</h3>
        <span className="text-[11px] text-slate-400">
          {fuente === "respaldo"
            ? `sin LLM (${r.interpretacion_meta.motivo ?? "respaldo"}): se buscó la consulta completa en todos los tipos`
            : `interpretado por ${r.interpretacion_meta.modelo}${fuente === "cache" ? " (guardado)" : ""}`}
        </span>
      </div>
      <ul className="mt-2 space-y-1.5">
        {i.capacidades.map((c) => (
          <li key={c.id} className="text-sm">
            <span className={`text-[10px] uppercase font-semibold mr-2 px-1.5 py-0.5 rounded ${c.importancia === "obligatoria" ? "bg-espol-navy text-white" : "bg-amber-100 text-amber-800"}`}>
              {c.importancia}
            </span>
            {c.descripcion}
            <span className="text-[11px] text-slate-400"> · buscado en: {c.tipos.map((t) => NOMBRE_TIPO[t] ?? t).join(", ")}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-slate-500 mt-2">
        Personas: <strong>{r.vigencia_aplicada.replace("_", " ")}</strong>
        {i.vigencia !== "no_especificada" && " (lo pidió la consulta)"}
        {r.requisitos_aplicados.map((x) => ` · ${x}`)}
        {i.requisitos_mixtos.map((m) => ` · ${m.capacidad}: ≥ ${m.anios_minimos} años`)}
        {` · ${r.personas_con_alguna_evidencia} con evidencias relevantes de ${r.personas_en_universo} · ${r.tiempos_s.total} s`}
      </p>
    </div>
  );
}

function Tarjeta({ p, k, activa, onAbrir }: { p: ResultadoBusqueda; k: number; activa: boolean; onAbrir: () => void }) {
  return (
    <li className={`bg-white border rounded-lg p-4 ${activa ? "ring-2 ring-espol-accent" : ""}`}>
      <div className="flex items-start gap-3">
        <span className="text-lg font-semibold text-slate-300 w-6 text-right">{k}</span>
        <div className="flex-1 min-w-0">
          <button onClick={onAbrir} className="text-base font-semibold text-espol-navy hover:underline text-left">
            {p.nombre}
          </button>
          <p className="text-xs text-slate-600 truncate">
            {p.cargo_actual ?? "Sin cargo actual"}
            {p.unidad_actual ? ` · ${p.unidad_actual}` : ""}
            {!p.vigente && " · no vigente"}
          </p>
        </div>
        <span className="text-xs text-slate-500 shrink-0 text-right">
          <strong className="text-slate-800 text-sm">{p.obligatorias_cubiertas}/{p.total_obligatorias}</strong>
          <br />obligatorias
        </span>
      </div>
      <div className="mt-3 space-y-2 ml-9">
        {p.capacidades.map((c) => (
          <div key={c.id}>
            <p className="text-xs">
              <span className={c.cubierta ? "text-emerald-600" : "text-slate-400"}>{c.cubierta ? "✓" : "✗"}</span>{" "}
              <span className="font-medium text-slate-700">{c.descripcion}</span>
              {c.importancia === "deseable" && <span className="text-amber-700"> (deseable)</span>}
              <span className={`ml-2 text-[10px] px-1.5 py-0.5 rounded border ${colorNivel[c.nivel]}`}>relevancia {c.nivel}</span>
              {c.requisito_anios && (
                <span className="ml-2 text-[11px] text-slate-500">
                  {c.requisito_anios.estado === "no_verificable"
                    ? "años no verificables (sin fechas)"
                    : `${c.requisito_anios.anios} años${c.requisito_anios.aproximado ? " aprox." : ""} (mín. ${c.requisito_anios.anios_minimos})`}
                </span>
              )}
            </p>
            <ul className="mt-0.5 space-y-0.5">
              {c.evidencias.slice(0, 2).map((e, j) => (
                <li key={j} className="text-[11px] text-slate-500 truncate" title={e.texto}>
                  <span className="text-slate-400">{e.tipo} · {e.fechas} —</span> {e.texto}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </li>
  );
}

// Búsqueda abierta: una caja de texto y el filtro de vigencia; el resto lo interpreta el sistema.
export default function BusquedaPage() {
  const [texto, setTexto] = useState("");
  const [vigencia, setVigencia] = useState<Vigencia>("vigentes");
  const [persona, setPersona] = useState<number | null>(null);
  const m = useMutation({ mutationFn: (q: { consulta: string; vigencia: Vigencia }) => buscarSemantica(q.consulta, q.vigencia) });
  const ejecutar = (consulta = texto) => {
    if (consulta.trim().length < 3) return;
    setTexto(consulta);
    setPersona(null);
    m.mutate({ consulta, vigencia });
  };
  const alto = Math.max(560, window.innerHeight - 330);

  // ?q=… (y opcional &vigencia=…) ejecuta la búsqueda al abrir la página: permite compartir una búsqueda
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const q = p.get("q");
    const v = p.get("vigencia") as Vigencia | null;
    if (v && VIGENCIAS.some((x) => x.id === v)) setVigencia(v);
    if (q) {
      setTexto(q);
      m.mutate({ consulta: q, vigencia: v && VIGENCIAS.some((x) => x.id === v) ? v : "vigentes" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const f = (e: KeyboardEvent) => e.key === "Escape" && setPersona(null);
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, []);

  return (
    <div className="space-y-3">
      <div className="bg-white border rounded-lg p-4 space-y-3">
        <form
          className="flex flex-wrap gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            ejecutar();
          }}
        >
          <input
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Describe a la persona que buscas, por ejemplo: experiencia en visión artificial y docencia en programación"
            className="flex-1 min-w-[18rem] border rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue/40"
          />
          <div className="inline-flex border rounded-md p-0.5 bg-slate-50">
            {VIGENCIAS.map((v) => (
              <button
                type="button"
                key={v.id}
                onClick={() => setVigencia(v.id)}
                className={`px-3 py-1.5 text-xs rounded ${vigencia === v.id ? "bg-espol-navy text-white" : "text-slate-600"}`}
              >
                {v.texto}
              </button>
            ))}
          </div>
          <button type="submit" disabled={m.isPending} className="px-5 py-2 text-sm rounded-md bg-espol-accent text-white disabled:opacity-60">
            {m.isPending ? "Buscando…" : "Buscar"}
          </button>
        </form>
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[11px] text-slate-400">Ejemplos:</span>
          {EJEMPLOS.map((e) => (
            <button key={e} onClick={() => ejecutar(e)} className="text-[11px] text-espol-blue bg-slate-50 border rounded-full px-2 py-0.5 hover:bg-slate-100">
              {e.length > 60 ? `${e.slice(0, 58)}…` : e}
            </button>
          ))}
        </div>
      </div>

      {m.isPending && (
        <p className="text-sm text-slate-500">
          Interpretando la consulta y buscando en las evidencias… (la primera búsqueda carga los modelos y puede tardar ~30 s)
        </p>
      )}
      {m.isError && <p className="text-sm text-red-600">No se pudo completar la búsqueda: {(m.error as Error).message}</p>}

      {m.data && (
        <>
          <Interpretacion r={m.data} />
          <div className="grid lg:grid-cols-[minmax(0,1fr)_27rem] gap-4 items-start">
            <div className="overflow-y-auto pr-1" style={{ height: alto }}>
              {m.data.resultados.length === 0 ? (
                <p className="text-sm text-slate-500">No hay personas con evidencias relevantes para esta consulta.</p>
              ) : (
                <ul className="space-y-2">
                  {m.data.resultados.map((p, k) => (
                    <Tarjeta key={p.persona_id} p={p} k={k + 1} activa={persona === p.persona_id} onAbrir={() => setPersona(p.persona_id)} />
                  ))}
                </ul>
              )}
              <p className="text-[11px] text-slate-400 mt-3">
                Orden: primero cuántas capacidades obligatorias cubre cada persona y luego qué tan fuerte es su mejor evidencia en
                cada una (no cuenta cuántas evidencias tiene). Ausencia de evidencia no es ausencia de capacidad.
              </p>
            </div>
            <aside className="bg-white border rounded-lg overflow-y-auto" style={{ height: alto }}>
              {persona !== null ? (
                <FichaPersona
                  ambito="todos"
                  personaId={persona}
                  onVolver={() => setPersona(null)}
                  textoVolver="Cerrar ficha"
                />
              ) : (
                <p className="text-sm text-slate-500 p-5">Haz clic en un nombre para ver su ficha completa y su trayectoria.</p>
              )}
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
