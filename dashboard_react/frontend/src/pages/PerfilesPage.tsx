import { useCallback, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAmbitos, getMapa, getResumen, type Ambito } from "../api/client";
import MapaTSNE from "../components/MapaTSNE";
import PanelGrupo from "../components/PanelGrupo";
import FichaPersona from "../components/FichaPersona";
import BuscadorPersonas from "../components/BuscadorPersonas";
import { colorCluster } from "../lib/colores";

const AMBITOS: { id: Ambito; nombre: string }[] = [
  { id: "todos", nombre: "Todo el personal" },
  { id: "administrativos", nombre: "Administrativos" },
  { id: "docentes", nombre: "Docentes" },
];

// Mapa a la izquierda; a la derecha un panel fijo que navega: grupos → grupo → persona.
export default function PerfilesPage() {
  // estado inicial desde la URL (?ambito=docentes&cluster=3&subpatron=0) para enlazar una vista;
  // sin parametro de persona: los enlaces no llevan identificadores de personas
  const [inicial] = useState(() => new URLSearchParams(window.location.search));
  const num = (k: string) => (inicial.get(k) !== null && !isNaN(Number(inicial.get(k))) ? Number(inicial.get(k)) : null);
  const [ambito, setAmbito] = useState<Ambito>(
    AMBITOS.some((a) => a.id === inicial.get("ambito")) ? (inicial.get("ambito") as Ambito) : "todos",
  );
  const [cluster, setCluster] = useState<number | null>(num("cluster"));
  const [subpatron, setSubpatron] = useState<number | null>(num("subpatron"));
  const [persona, setPersona] = useState<number | null>(null);
  const [soloVigentes, setSoloVigentes] = useState(true);

  // Mapa y panel derecho con la MISMA altura fija (según la ventana); el panel hace scroll dentro.
  const calcularAlto = () => Math.max(560, window.innerHeight - 150);
  const [altoBloque, setAltoBloque] = useState(calcularAlto);
  useEffect(() => {
    const f = () => setAltoBloque(calcularAlto());
    window.addEventListener("resize", f);
    return () => window.removeEventListener("resize", f);
  }, []);
  // alto real del área del gráfico (bloque menos encabezado y nota, que pueden ocupar 1 o 2 líneas)
  const [altoMapa, setAltoMapa] = useState(500);
  const areaMapa = useCallback((el: HTMLDivElement | null) => {
    if (!el) return;
    const obs = new ResizeObserver(([e]) => setAltoMapa(Math.max(300, Math.floor(e.contentRect.height))));
    obs.observe(el);
  }, []);

  const ambitos = useQuery({ queryKey: ["ambitos"], queryFn: getAmbitos });
  const resumen = useQuery({ queryKey: ["resumen", ambito], queryFn: () => getResumen(ambito) });
  const mapa = useQuery({ queryKey: ["mapa", ambito, soloVigentes], queryFn: () => getMapa(ambito, soloVigentes) });

  // Esc vuelve un paso atrás en el panel
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (persona !== null) setPersona(null);
      else if (cluster !== null) elegirCluster(null);
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  });

  const cambiarAmbito = (a: Ambito) => {
    setAmbito(a);
    setCluster(null);
    setSubpatron(null);
    setPersona(null);
  };
  const elegirCluster = (c: number | null) => {
    setCluster(c);
    setSubpatron(null);
    setPersona(null);
  };

  if (ambitos.isError) {
    return (
      <p className="text-sm text-red-600">
        No hay resultados de clustering o la API no responde. Correr <code>python -m perfiles.construir</code>.
      </p>
    );
  }
  const r = resumen.data;
  const fichaSel = r?.clusters.find((c) => c.cluster === cluster) ?? null;
  const etiquetas = Object.fromEntries((r?.clusters ?? []).map((c) => [c.cluster, c.etiqueta]));

  return (
    <div className="space-y-3">
      <div className="grid lg:grid-cols-[minmax(0,1fr)_27rem] gap-4 items-center">
        <div className="inline-flex justify-self-start bg-white border rounded-lg p-1">
          {AMBITOS.map((a) => {
            const info = ambitos.data?.ambitos.find((x) => x.ambito === a.id);
            return (
              <button
                key={a.id}
                onClick={() => cambiarAmbito(a.id)}
                className={`px-3 py-1.5 text-sm rounded-md ${ambito === a.id ? "bg-espol-navy text-white" : "text-slate-600 hover:bg-slate-50"}`}
              >
                {a.nombre}
                {info && <span className="ml-1.5 text-xs opacity-70">{info.n_vigentes}</span>}
              </button>
            );
          })}
        </div>
        <div>
          <BuscadorPersonas
            ambito={ambito}
            onElegir={(res) => {
              setCluster(res.cluster);
              setSubpatron(null);
              setPersona(res.persona_id);
            }}
          />
        </div>
      </div>

      {ambitos.data && !ambitos.data.estado.actualizado && (
        <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2">
          Las evidencias cambiaron después de este cálculo (versión {ambitos.data.version}); conviene recalcularlo.
        </p>
      )}

      <div className="grid lg:grid-cols-[minmax(0,1fr)_27rem] gap-4 items-start">
        {/* mapa */}
        <div className="bg-white border rounded-lg overflow-hidden flex flex-col" style={{ height: altoBloque }}>
          <div className="px-4 py-2.5 border-b flex flex-wrap items-center gap-x-4 gap-y-1">
            <p className="text-xs text-slate-500 flex-1 min-w-[14rem]">
              Cada punto es una persona; las cercanas tienen perfiles parecidos y el color indica su grupo
              {fichaSel?.subdivision ? " (aquí, su subgrupo)" : ""}. Pasa el cursor para ver quién es y haz clic para abrir su ficha.
            </p>
            <span className="text-[11px] text-slate-400 flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full bg-slate-300 ring-2 ring-slate-800" /> representante · +/− acercar · arrastrar para moverse · doble clic: vista completa
            </span>
            <label className="text-[11px] text-slate-500 flex items-center gap-1">
              <input type="checkbox" checked={soloVigentes} onChange={(e) => setSoloVigentes(e.target.checked)} />
              solo vigentes
            </label>
          </div>
          <div ref={areaMapa} className="flex-1 min-h-0">
          {mapa.data ? (
            <MapaTSNE
              alto={altoMapa}
              mapa={mapa.data}
              clusterSeleccionado={cluster}
              subdivision={fichaSel?.subdivision ?? null}
              subpatronSeleccionado={subpatron}
              personaSeleccionada={persona}
              onPersona={setPersona}
            />
          ) : (
            <p className="text-sm text-slate-500 p-4">Cargando mapa…</p>
          )}
          </div>
          <p className="text-[11px] text-slate-400 px-4 pb-2">
            Dibujo aproximado para orientarse: los grupos se calcularon con toda la información de cada persona, no con este plano.
          </p>
        </div>

        {/* panel derecho: grupos → grupo → persona */}
        <aside className="bg-white border rounded-lg overflow-y-auto" style={{ height: altoBloque }}>
          {persona !== null ? (
            <FichaPersona
              ambito={ambito}
              personaId={persona}
              onPersona={setPersona}
              onVolver={() => setPersona(null)}
              textoVolver={fichaSel ? `Volver a «${fichaSel.etiqueta}»` : "Volver a los grupos"}
              onVerGrupo={(c) => elegirCluster(c)}
            />
          ) : cluster !== null && r ? (
            <PanelGrupo
              ambito={ambito}
              cluster={cluster}
              soloVigentes={soloVigentes}
              etiquetas={etiquetas}
              subpatron={subpatron}
              onSubpatron={setSubpatron}
              onPersona={setPersona}
              onVolver={() => elegirCluster(null)}
            />
          ) : (
            <div className="p-5">
              <h3 className="text-base font-semibold text-espol-navy">Grupos de perfiles</h3>
              <p className="text-xs text-slate-500 mt-1">
                {r ? `${r.k} grupos de personas con perfiles parecidos · ${r.n_vigentes} personas vigentes. ` : ""}
                Elige un grupo para ver quiénes lo forman y qué los caracteriza.
              </p>
              <ul className="mt-3 space-y-1.5">
                {r?.clusters.map((c) => (
                  <li key={c.cluster}>
                    <button
                      onClick={() => elegirCluster(c.cluster)}
                      className="w-full text-left rounded-md px-3 py-2 border hover:bg-slate-50 hover:border-slate-300 group"
                    >
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: colorCluster(c.cluster) }} />
                        <span className="text-sm text-slate-800 flex-1 leading-snug">
                          {c.etiqueta}
                          <span className="block text-[11px] text-slate-500 overflow-hidden" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                            {c.descripcion.replace(/^\d+ personas \([^)]*\)\. /, "")}
                          </span>
                        </span>
                        <span className="text-xs text-slate-500 shrink-0">{c.tamano_vigentes}</span>
                        <span className="text-slate-300 group-hover:text-slate-500">›</span>
                      </div>
                      <div className="mt-1.5 h-1 bg-slate-100 rounded ml-[1.15rem]">
                        <div
                          className="h-1 rounded"
                          style={{ width: `${(c.tamano_vigentes / Math.max(1, r.n_vigentes)) * 100}%`, background: colorCluster(c.cluster) }}
                        />
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
              {ambitos.data && <p className="text-[11px] text-slate-400 mt-4">Datos calculados el {ambitos.data.fecha.slice(0, 10)}</p>}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
