import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { getMapa, getResumen } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";

const TIPOS = ["Todos", "Solo Administrativo", "Solo Docente"];

export default function MapaPage() {
  const [tipoFiltro, setTipoFiltro] = useState("Todos");
  const [perfilesFiltro, setPerfilesFiltro] = useState<number[]>([]);
  const [idSel, setIdSel] = useState<number | null>(null);
  const [idBuscado, setIdBuscado] = useState("");
  const [idResaltado, setIdResaltado] = useState<number | null>(null);
  const [avisoNoEncontrado, setAvisoNoEncontrado] = useState(false);

  const resumenQuery = useQuery({ queryKey: ["resumen"], queryFn: getResumen });
  const mapaQuery = useQuery({
    queryKey: ["mapa", tipoFiltro, perfilesFiltro],
    queryFn: () => getMapa(tipoFiltro, perfilesFiltro),
  });

  const perfiles = resumenQuery.data?.perfiles ?? [];

  const puntoResaltado = useMemo(() => {
    if (idResaltado === null || !mapaQuery.data) return null;
    return mapaQuery.data.puntos.find((p) => p.IDPERSONA === idResaltado) ?? null;
  }, [idResaltado, mapaQuery.data]);

  const traces = useMemo(() => {
    if (!mapaQuery.data) return [];
    const porCluster = new Map<number, typeof mapaQuery.data.puntos>();
    for (const p of mapaQuery.data.puntos) {
      if (!porCluster.has(p.CLUSTER)) porCluster.set(p.CLUSTER, []);
      porCluster.get(p.CLUSTER)!.push(p);
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const base: any[] = Array.from(porCluster.entries())
      .sort(([a], [b]) => a - b)
      .map(([, pts]) => ({
        type: "scattergl" as const,
        mode: "markers" as const,
        name: pts[0].PERFIL_NOMBRE,
        x: pts.map((p) => p.PC1),
        y: pts.map((p) => p.PC2),
        marker: {
          color: pts[0].COLOR,
          size: 6,
          opacity: idResaltado === null ? 0.7 : 0.25,
          line: { width: 0 },
        },
        customdata: pts.map((p) => [p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC, p.VIGENTE_MOSTRAR ? "Si" : "No"]),
        hovertemplate:
          "ID %{customdata[0]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
      }));

    if (puntoResaltado) {
      base.push({
        type: "scattergl" as const,
        mode: "markers" as const,
        name: `Persona ${puntoResaltado.IDPERSONA}`,
        x: [puntoResaltado.PC1],
        y: [puntoResaltado.PC2],
        marker: {
          color: "#E63946",
          size: 16,
          opacity: 1,
          line: { width: 2, color: "#FFFFFF" },
        },
        customdata: [[puntoResaltado.IDPERSONA, puntoResaltado.CARGO_ACTUAL ?? "-", puntoResaltado.TIPOEMPLEADO_ACTUAL_DESC, puntoResaltado.VIGENTE_MOSTRAR ? "Si" : "No"]],
        hovertemplate:
          "ID %{customdata[0]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
      });
    }

    return base;
  }, [mapaQuery.data, puntoResaltado, idResaltado]);

  function togglePerfil(c: number) {
    setPerfilesFiltro((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  function buscarPersonaEnMapa() {
    const id = Number(idBuscado.trim());
    if (!idBuscado.trim() || Number.isNaN(id)) {
      setAvisoNoEncontrado(false);
      return;
    }
    const existe = mapaQuery.data?.puntos.some((p) => p.IDPERSONA === id);
    if (existe) {
      setIdResaltado(id);
      setAvisoNoEncontrado(false);
    } else {
      setIdResaltado(null);
      setAvisoNoEncontrado(true);
    }
  }

  function limpiarResaltado() {
    setIdBuscado("");
    setIdResaltado(null);
    setAvisoNoEncontrado(false);
  }

  const hayFiltrosActivos = tipoFiltro !== "Todos" || perfilesFiltro.length > 0 || idResaltado !== null;

  function limpiarTodosLosFiltros() {
    setTipoFiltro("Todos");
    setPerfilesFiltro([]);
    limpiarResaltado();
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Filtros</h3>
          <button
            onClick={limpiarTodosLosFiltros}
            disabled={!hayFiltrosActivos}
            className="text-xs font-medium text-espol-blue hover:text-espol-navy disabled:text-slate-300 disabled:cursor-not-allowed transition-colors"
          >
            Limpiar todos los filtros
          </button>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Tipo de empleado</p>
          <div className="flex gap-2">
            {TIPOS.map((t) => (
              <button
                key={t}
                onClick={() => setTipoFiltro(t)}
                className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                  tipoFiltro === t
                    ? "bg-espol-blue text-white border-espol-blue"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Categorías de cargo a mostrar (opcional)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {perfiles.map((p) => (
              <button
                key={p.CLUSTER}
                onClick={() => togglePerfil(p.CLUSTER)}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  perfilesFiltro.includes(p.CLUSTER)
                    ? "text-white border-transparent"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
                style={perfilesFiltro.includes(p.CLUSTER) ? { backgroundColor: p.COLOR } : undefined}
              >
                {p.CLUSTER} — {p.PERFIL_NOMBRE}
              </button>
            ))}
          </div>
        </div>
        <div className="border-t border-slate-100 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Ubicar una persona en el mapa
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={idBuscado}
              onChange={(e) => setIdBuscado(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && buscarPersonaEnMapa()}
              placeholder="IDPERSONA"
              className="w-40 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
            />
            <button
              onClick={buscarPersonaEnMapa}
              className="px-3 py-1.5 text-sm rounded-md bg-espol-navy text-white hover:bg-espol-blue transition-colors"
            >
              Ubicar
            </button>
            {idResaltado !== null && (
              <button
                onClick={limpiarResaltado}
                className="px-3 py-1.5 text-sm rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Quitar marca
              </button>
            )}
          </div>
          {avisoNoEncontrado && (
            <p className="text-xs text-amber-600 mt-1.5">
              Esa persona no aparece en el mapa (puede estar fuera de los filtros activos, o sin
              perfil/cluster asignado).
            </p>
          )}
          {idResaltado !== null && !avisoNoEncontrado && (
            <p className="text-xs text-slate-500 mt-1.5">
              Persona {idResaltado} resaltada en rojo — el resto de puntos se mantiene visible.
            </p>
          )}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        {mapaQuery.isLoading ? (
          <LoadingBlock label="Cargando mapa..." />
        ) : mapaQuery.error || !mapaQuery.data ? (
          <ErrorBlock message="No se pudo cargar el mapa." />
        ) : (
          <>
            <Plot
              data={traces}
              layout={{
                height: 560,
                legend: { title: { text: "" }, font: { size: 11 } },
                margin: { l: 50, r: 20, t: 20, b: 50 },
                font: { size: 12, color: "#334155" },
                plot_bgcolor: "#FFFFFF",
                paper_bgcolor: "#FFFFFF",
                xaxis: {
                  title: { text: "PC1" },
                  showgrid: true,
                  gridcolor: "#EEF1F5",
                  zeroline: false,
                  showline: true,
                  linecolor: "#CBD5E1",
                },
                yaxis: {
                  title: { text: "PC2" },
                  showgrid: true,
                  gridcolor: "#EEF1F5",
                  zeroline: false,
                  showline: true,
                  linecolor: "#CBD5E1",
                },
                dragmode: "pan",
              }}
              config={{
                displayModeBar: true,
                displaylogo: false,
                scrollZoom: true,
                responsive: true,
                modeBarButtonsToRemove: ["lasso2d", "select2d"],
              }}
              style={{ width: "100%" }}
              useResizeHandler
              onClick={(e) => {
                const point = e.points[0];
                const idp = (point.customdata as [number, ...unknown[]])[0];
                setIdSel(Number(idp));
              }}
            />
            <p className="text-xs text-slate-500 mt-1">
              {mapaQuery.data.n_mostrados.toLocaleString()} personas mostradas de{" "}
              {mapaQuery.data.total_modelo.toLocaleString()} en el modelo. Usa la rueda del mouse o el
              pad para hacer zoom; arrastra para desplazarte.
            </p>
          </>
        )}
      </div>

      {idSel === null ? (
        <div className="rounded-lg bg-slate-50 border border-slate-200 text-slate-600 text-sm px-4 py-3">
          Haz clic en un punto del gráfico para ver la ficha de esa persona.
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <PersonaFicha idPersona={idSel} mostrarClusterPerfil={false} />
        </div>
      )}
    </div>
  );
}
