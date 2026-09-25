import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Plot from "react-plotly.js";
import {
  getPerfilDetalleK5,
  getPerfilDetallePorRama,
  getPerfilDetalleSemantico,
  getResumenK5,
  getResumenPorRama,
  getResumenSemantico,
} from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import DataTable from "../components/DataTable";
import { METRICAS_CLAVE_COLUMNS } from "../lib/columns";
import type { PerfilDetalleK5, PerfilDetallePorRama, PerfilDetalleSemantico, Rama } from "../api/types";

type Vista = "estructural" | "semantico";

const VISTAS: { value: Vista; label: string; descripcion: string }[] = [
  {
    value: "estructural",
    label: "Clustering estructurado",
    descripcion:
      "Perfiles calculados sobre variables estructuradas (cargo, antigüedad, nivel académico, trayectoria...). Interpretable variable por variable — es la base de perfiles del dashboard.",
  },
  {
    value: "semantico",
    label: "Clustering en embeddings",
    descripcion:
      "Clustering independiente sobre el espacio de embeddings (texto narrativo de trayectoria/formación/docencia/investigación de cada persona). Capa de comparación/validación: valida si los perfiles estructurales también emergen del texto, no los reemplaza. Los clusters aquí no tienen nombre interpretado a mano todavía — se describen automáticamente con las mismas variables estructuradas.",
  },
];

export default function ResumenPage() {
  const [vista, setVista] = useState<Vista>("estructural");
  const [perfilesSeparados, setPerfilesSeparados] = useState(false);
  const vistaActual = VISTAS.find((v) => v.value === vista)!;

  return (
    <div className="space-y-4">
      <div>
        <div className="flex gap-1 border-b border-slate-200">
          {VISTAS.map((v) => (
            <button
              key={v.value}
              onClick={() => setVista(v.value)}
              className={`px-4 py-2.5 text-sm font-medium rounded-t-md border-b-2 -mb-px transition-colors ${
                vista === v.value
                  ? "bg-white text-espol-navy border-espol-blue"
                  : "text-slate-500 border-transparent hover:text-espol-navy hover:bg-slate-50"
              }`}
            >
              {v.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-slate-400 mt-2">{vistaActual.descripcion}</p>
      </div>

      <div className="bg-espol-blue/5 rounded-xl border border-espol-blue/20 p-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-espol-navy">Perfiles separados por tipo de empleado</p>
          <p className="text-xs text-slate-500 mt-0.5">
            El clustering normal agrupa Administrativo y Docente juntos antes de buscar perfiles, así
            que el rasgo que más pesa es esa misma división. Activa esto para ver perfiles calculados
            por separado dentro de cada tipo.
          </p>
        </div>
        <button
          onClick={() => setPerfilesSeparados((v) => !v)}
          className={`shrink-0 px-3 py-1.5 text-sm rounded-md border transition-colors whitespace-nowrap ${
            perfilesSeparados
              ? "bg-espol-blue text-white border-espol-blue"
              : "border-slate-300 text-slate-600 hover:bg-slate-50"
          }`}
        >
          {perfilesSeparados ? "Ver tipo de empleados separados: ON" : "Ver tipo de empleados separados: OFF"}
        </button>
      </div>

      {perfilesSeparados ? (
        <ResumenPorRama tipoClustering={vista === "estructural" ? "estructurado" : "semantico"} />
      ) : vista === "estructural" ? (
        <ResumenK5 />
      ) : (
        <ResumenSemantico />
      )}
    </div>
  );
}

function ResumenPorRama({ tipoClustering }: { tipoClustering: "estructurado" | "semantico" }) {
  const [rama, setRama] = useState<Rama>("ADMINISTRATIVO");
  const [clusterSel, setClusterSel] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["resumen_por_rama", tipoClustering, rama],
    queryFn: () => getResumenPorRama(tipoClustering, rama),
  });

  const detalleQuery = useQuery({
    queryKey: ["perfil_por_rama", tipoClustering, rama, clusterSel],
    queryFn: () => getPerfilDetallePorRama(clusterSel as number, tipoClustering, rama),
    enabled: clusterSel !== null,
  });

  function cambiarRama(r: Rama) {
    setRama(r);
    setClusterSel(null);
  }

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        {(["ADMINISTRATIVO", "DOCENTE"] as Rama[]).map((r) => (
          <button
            key={r}
            onClick={() => cambiarRama(r)}
            className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
              rama === r
                ? "bg-espol-blue text-white border-espol-blue"
                : "border-slate-300 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {r === "ADMINISTRATIVO" ? "Administrativo" : "Docente"}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingBlock label="Cargando resumen por rama..." />
      ) : error || !data ? (
        <ErrorBlock message="No se pudo cargar el resumen por rama." />
      ) : (
        (() => {
          const orden = [...data.perfiles].sort((a, b) => a.CLUSTER_RAMA - b.CLUSTER_RAMA);
          return (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <MetricCard label={`Personas (${rama === "ADMINISTRATIVO" ? "Administrativo" : "Docente"})`} value={data.n_personas.toLocaleString()} />
                <MetricCard label="Perfiles (clusters de esta rama)" value={String(data.n_perfiles)} />
              </div>

              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <p className="text-xs text-slate-500 mb-2">
                  Haz clic en una barra para ver el detalle de ese perfil más abajo. Estos clusters son
                  propios de la rama {rama === "ADMINISTRATIVO" ? "Administrativo" : "Docente"} — no
                  comparables con los IDs de otra rama ni con la vista combinada.
                </p>
                <Plot
                  data={[
                    {
                      type: "bar",
                      x: orden.map((p) => p.PERFIL_NOMBRE),
                      y: orden.map((p) => p.N_PERSONAS),
                      marker: { color: orden.map((p) => p.COLOR) },
                      text: orden.map((p) => `${p.PCT_POBLACION.toFixed(1)}%`),
                      textposition: "outside",
                      customdata: orden.map((p) => p.CLUSTER_RAMA),
                    } as never,
                  ]}
                  layout={{
                    height: 480,
                    showlegend: false,
                    margin: { l: 60, r: 20, t: 20, b: 160 },
                    font: { size: 12, color: "#334155" },
                    plot_bgcolor: "#FFFFFF",
                    paper_bgcolor: "#FFFFFF",
                    xaxis: {
                      title: { text: "" },
                      tickangle: -35,
                      automargin: true,
                      tickfont: { size: 11 },
                      showgrid: false,
                      showline: true,
                      linecolor: "#CBD5E1",
                    },
                    yaxis: {
                      title: { text: "N personas" },
                      showgrid: true,
                      gridcolor: "#EEF1F5",
                      zeroline: false,
                      automargin: true,
                    },
                  }}
                  config={{ displayModeBar: false, responsive: true }}
                  style={{ width: "100%" }}
                  useResizeHandler
                  onClick={(e) => {
                    const point = e.points[0];
                    const idx = point.pointIndex as number;
                    setClusterSel(orden[idx].CLUSTER_RAMA);
                  }}
                />
              </div>

              {clusterSel === null ? (
                <div className="rounded-lg bg-slate-50 border border-slate-200 text-slate-600 text-sm px-4 py-3">
                  Haz clic en una barra del gráfico de arriba para ver el detalle de ese perfil.
                </div>
              ) : detalleQuery.isLoading ? (
                <LoadingBlock label="Cargando detalle del perfil..." />
              ) : detalleQuery.data ? (
                <PerfilDetalleView detalle={detalleQuery.data} />
              ) : null}
            </>
          );
        })()
      )}
    </div>
  );
}

function ResumenK5() {
  const [clusterSel, setClusterSel] = useState<number | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["resumen_k5"], queryFn: getResumenK5 });

  const detalleQuery = useQuery({
    queryKey: ["perfil_k5", clusterSel],
    queryFn: () => getPerfilDetalleK5(clusterSel as number),
    enabled: clusterSel !== null,
  });

  if (isLoading) return <LoadingBlock label="Cargando resumen..." />;
  if (error || !data) return <ErrorBlock message="No se pudo cargar el resumen." />;

  const orden = [...data.perfiles].sort((a, b) => a.CLUSTER_K5 - b.CLUSTER_K5);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <MetricCard label="Personas en el modelo" value={data.n_personas.toLocaleString()} />
        <MetricCard label="Perfiles (clusters)" value={String(data.n_perfiles)} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <p className="text-xs text-slate-500 mb-2">Haz clic en una barra para ver el detalle de ese perfil más abajo.</p>
        <Plot
          data={[
            {
              type: "bar",
              x: orden.map((p) => p.PERFIL_NOMBRE_K5),
              y: orden.map((p) => p.N_PERSONAS),
              marker: { color: orden.map((p) => p.COLOR) },
              text: orden.map((p) => `${p.PCT_POBLACION.toFixed(1)}%`),
              textposition: "outside",
              customdata: orden.map((p) => p.CLUSTER_K5),
            } as never,
          ]}
          layout={{
            height: 480,
            showlegend: false,
            margin: { l: 60, r: 20, t: 20, b: 160 },
            font: { size: 12, color: "#334155" },
            plot_bgcolor: "#FFFFFF",
            paper_bgcolor: "#FFFFFF",
            xaxis: {
              title: { text: "" },
              tickangle: -35,
              automargin: true,
              tickfont: { size: 11 },
              showgrid: false,
              showline: true,
              linecolor: "#CBD5E1",
            },
            yaxis: {
              title: { text: "N personas" },
              showgrid: true,
              gridcolor: "#EEF1F5",
              zeroline: false,
              automargin: true,
            },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
          useResizeHandler
          onClick={(e) => {
            const point = e.points[0];
            const idx = point.pointIndex as number;
            setClusterSel(orden[idx].CLUSTER_K5);
          }}
        />
      </div>

      {clusterSel === null ? (
        <div className="rounded-lg bg-slate-50 border border-slate-200 text-slate-600 text-sm px-4 py-3">
          Haz clic en una barra del gráfico de arriba para ver el detalle de ese perfil.
        </div>
      ) : detalleQuery.isLoading ? (
        <LoadingBlock label="Cargando detalle del perfil..." />
      ) : detalleQuery.data ? (
        <PerfilDetalleView detalle={detalleQuery.data} />
      ) : null}
    </div>
  );
}

function ResumenSemantico() {
  const [clusterSel, setClusterSel] = useState<number | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["resumen_semantico"],
    queryFn: getResumenSemantico,
  });

  const detalleQuery = useQuery({
    queryKey: ["perfil_semantico", clusterSel],
    queryFn: () => getPerfilDetalleSemantico(clusterSel as number),
    enabled: clusterSel !== null,
  });

  if (isLoading) return <LoadingBlock label="Cargando resumen semántico..." />;
  if (error || !data) return <ErrorBlock message="No se pudo cargar el resumen semántico." />;

  const orden = [...data.perfiles].sort((a, b) => a.CLUSTER_SEMANTICO - b.CLUSTER_SEMANTICO);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <MetricCard label="Personas con embedding" value={data.n_personas.toLocaleString()} />
        <MetricCard label="Perfiles semánticos (clusters)" value={String(data.n_perfiles)} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <p className="text-xs text-slate-500 mb-2">
          Haz clic en una barra para ver el detalle de ese perfil semántico más abajo. Los IDs de
          cluster aquí no corresponden a los del clustering estructural — son dos particiones
          independientes.
        </p>
        <Plot
          data={[
            {
              type: "bar",
              orientation: "h",
              y: orden.map((p) => p.PERFIL_NOMBRE_SEMANTICO),
              x: orden.map((p) => p.N_PERSONAS),
              marker: { color: orden.map((p) => p.COLOR) },
              text: orden.map((p) => `${p.PCT_POBLACION.toFixed(1)}%`),
              textposition: "outside",
              customdata: orden.map((p) => p.CLUSTER_SEMANTICO),
            } as never,
          ]}
          layout={{
            height: Math.max(420, orden.length * 70),
            showlegend: false,
            margin: { l: 20, r: 60, t: 20, b: 40 },
            font: { size: 12, color: "#334155" },
            plot_bgcolor: "#FFFFFF",
            paper_bgcolor: "#FFFFFF",
            yaxis: {
              title: { text: "" },
              autorange: "reversed",
              automargin: true,
              tickfont: { size: 11 },
              showgrid: false,
              showline: true,
              linecolor: "#CBD5E1",
            },
            xaxis: {
              title: { text: "N personas" },
              showgrid: true,
              gridcolor: "#EEF1F5",
              zeroline: false,
              automargin: true,
            },
          }}
          config={{ displayModeBar: false, responsive: true }}
          style={{ width: "100%" }}
          useResizeHandler
          onClick={(e) => {
            const point = e.points[0];
            const idx = point.pointIndex as number;
            setClusterSel(orden[idx].CLUSTER_SEMANTICO);
          }}
        />
      </div>

      {clusterSel === null ? (
        <div className="rounded-lg bg-slate-50 border border-slate-200 text-slate-600 text-sm px-4 py-3">
          Haz clic en una barra del gráfico de arriba para ver el detalle de ese perfil.
        </div>
      ) : detalleQuery.isLoading ? (
        <LoadingBlock label="Cargando detalle del perfil..." />
      ) : detalleQuery.data ? (
        <PerfilDetalleView detalle={detalleQuery.data} />
      ) : null}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-2xl font-semibold mt-1 text-slate-800">{value}</p>
    </div>
  );
}

function PerfilDetalleView({ detalle }: { detalle: PerfilDetalleSemantico | PerfilDetalleK5 | PerfilDetallePorRama }) {
  return (
    <div className="space-y-4 bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start gap-3">
        <span className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: detalle.color }} />
        <div>
          <h3 className="text-lg font-semibold tracking-tight text-slate-800">{detalle.nombre}</h3>
          <p className="text-sm font-medium text-slate-500">
            {detalle.n_personas} personas ({detalle.pct_poblacion.toFixed(1)}% de la población)
          </p>
          <p className="text-sm text-slate-600 mt-1">{detalle.descripcion}</p>
        </div>
      </div>

      {"pct_con_trayectoria" in detalle &&
        detalle.pct_con_trayectoria !== null &&
        detalle.pct_formacion_titulo_top1 !== null && (
          <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-slate-700 mb-2">¿En qué se basa este nombre?</h4>
            <p className="text-xs text-slate-600 mb-3">
              El nombre se construye a partir de la sección del texto que resultó más consistente entre
              las personas más cercanas al centro de este grupo — no es una elección arbitraria: se compara
              qué tan repetido es el patrón de Trayectoria (cargo/unidad) frente al de Formación académica
              (título de carrera), y gana la sección con mayor coincidencia real.
            </p>
            <div className="space-y-2">
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-slate-600">Trayectoria (cargo/unidad)</span>
                  <span className="text-slate-500">{detalle.pct_con_trayectoria.toFixed(0)}% de coincidencia</span>
                </div>
                <div className="h-2 bg-slate-200 rounded overflow-hidden">
                  <div
                    className="h-full bg-indigo-500 rounded"
                    style={{ width: `${detalle.pct_con_trayectoria}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-slate-600">Formación académica (título)</span>
                  <span className="text-slate-500">
                    {detalle.pct_formacion_titulo_top1.toFixed(0)}% de coincidencia
                  </span>
                </div>
                <div className="h-2 bg-slate-200 rounded overflow-hidden">
                  <div
                    className="h-full bg-slate-400 rounded"
                    style={{ width: `${detalle.pct_formacion_titulo_top1}%` }}
                  />
                </div>
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-2">
              {detalle.pct_con_trayectoria > detalle.pct_formacion_titulo_top1
                ? "En este perfil, la trayectoria (cargo y unidad institucional) es la señal más fuerte y consistente, por eso domina el nombre."
                : "En este perfil, la trayectoria no es la señal dominante (por eso el nombre no se basa en cargo/unidad)."}
            </p>
          </div>
        )}

      {"desglose_cargo_textual" in detalle && (detalle.desglose_cargo_textual || detalle.desglose_unidad_textual) && (
        <div>
          <h4 className="text-sm font-semibold text-slate-700 mb-2">
            Desglose real de cargo/unidad (documentos más cercanos al centro del grupo)
          </h4>
          <p className="text-xs text-slate-500 mb-2">
            Cuando ningún cargo o unidad supera el 40% de los casos, el nombre del perfil no fuerza uno solo
            como si fuera dominante — este desglose muestra la distribución real.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            {detalle.desglose_cargo_textual && (
              <div className="bg-slate-50 rounded px-3 py-2">
                <div className="font-medium text-slate-600 mb-1">Cargo (evento más reciente)</div>
                <div className="text-slate-600">{detalle.desglose_cargo_textual}</div>
              </div>
            )}
            {detalle.desglose_unidad_textual && (
              <div className="bg-slate-50 rounded px-3 py-2">
                <div className="font-medium text-slate-600 mb-1">Unidad institucional</div>
                <div className="text-slate-600">{detalle.desglose_unidad_textual}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {"ejemplos_texto" in detalle && detalle.ejemplos_texto.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-slate-700 mb-2">
            Evidencia textual ({detalle.ejemplos_texto.length} documentos más representativos del perfil)
          </h4>
          <p className="text-xs text-slate-500 mb-2">
            El nombre de este perfil se construyó a partir del cargo/unidad predominante en el texto de las
            personas más cercanas al centro de este grupo en el espacio de embeddings — estos son ejemplos
            reales de ese texto.
          </p>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {detalle.ejemplos_texto.map((texto, i) => (
              <blockquote
                key={i}
                className="text-xs text-slate-600 bg-slate-50 border-l-2 border-slate-300 rounded px-3 py-2 whitespace-pre-wrap"
              >
                {texto}
              </blockquote>
            ))}
          </div>
        </div>
      )}

      {"top_features" in detalle && detalle.top_features.length > 0 && (
        <div>
          <Plot
            data={[
              {
                type: "bar",
                orientation: "h",
                y: detalle.top_features.map((f) => f.FEATURE_LABEL),
                x: detalle.top_features.map((f) => f.VALUE_CLUSTER),
                name: "Este perfil",
                marker: { color: detalle.color },
              },
              {
                type: "bar",
                orientation: "h",
                y: detalle.top_features.map((f) => f.FEATURE_LABEL),
                x: detalle.top_features.map((f) => f.VALUE_GLOBAL),
                name: "Institución (global)",
                marker: { color: "#CBD5E1" },
              },
            ]}
            layout={{
              barmode: "group",
              height: 440,
              title: { text: "Variables más distintivas de este perfil", font: { size: 13 } },
              font: { size: 12, color: "#334155" },
              plot_bgcolor: "#FFFFFF",
              paper_bgcolor: "#FFFFFF",
              legend: { orientation: "h", yanchor: "bottom", y: 1.02, xanchor: "left", x: 0, font: { size: 11 } },
              yaxis: { autorange: "reversed", automargin: true, showgrid: false, showline: true, linecolor: "#CBD5E1" },
              xaxis: { showgrid: true, gridcolor: "#EEF1F5", zeroline: false, automargin: true },
              margin: { l: 10, r: 20, t: 60, b: 10 },
            }}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
          <p className="text-xs text-slate-500">
            Comparación de mediana (o proporción) del perfil vs. la mediana institucional global.
          </p>
        </div>
      )}

      <div>
        <h4 className="font-semibold text-sm mb-2 text-slate-700">Cargos reales que componen este perfil</h4>
        {detalle.cargos.length > 0 ? (
          <>
            <DataTable
              columns={[
                { key: "CARGO_ACTUAL", label: "Cargo actual" },
                { key: "N_PERSONAS", label: "N personas" },
              ]}
              rows={detalle.cargos as unknown as Record<string, unknown>[]}
              maxHeight={250}
            />
            <p className="text-xs text-slate-500 mt-1">
              {detalle.n_cargos_distintos} cargos distintos entre las {detalle.n_con_cargo} personas de
              este perfil con cargo actual registrado.
            </p>
          </>
        ) : (
          <p className="text-sm text-slate-400">Ninguna persona de este perfil tiene cargo actual registrado.</p>
        )}
      </div>

      <div>
        <h4 className="font-semibold text-sm mb-2 text-slate-700">Personas de este perfil (muestra)</h4>
        <DataTable columns={METRICAS_CLAVE_COLUMNS} rows={detalle.muestra_personas} maxHeight={400} />
      </div>
    </div>
  );
}
