import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import Plot from "react-plotly.js";
import { getPerfilDetalle, getResumen } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import DataTable from "../components/DataTable";
import { METRICAS_CLAVE_COLUMNS } from "../lib/columns";

export default function ResumenPage() {
  const [clusterSel, setClusterSel] = useState<number | null>(null);
  const { data, isLoading, error } = useQuery({ queryKey: ["resumen"], queryFn: getResumen });

  const detalleQuery = useQuery({
    queryKey: ["perfil", clusterSel],
    queryFn: () => getPerfilDetalle(clusterSel as number),
    enabled: clusterSel !== null,
  });

  if (isLoading) return <LoadingBlock label="Cargando resumen..." />;
  if (error || !data) return <ErrorBlock message="No se pudo cargar el resumen." />;

  const orden = [...data.perfiles].sort((a, b) => a.CLUSTER - b.CLUSTER);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <MetricCard label="Personas en el modelo" value={data.n_personas.toLocaleString()} />
        <MetricCard label="Perfiles (clusters)" value={String(data.n_perfiles)} />
        <MetricCard label="Con texto para búsqueda semántica" value={data.n_con_texto.toLocaleString()} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <p className="text-xs text-slate-500 mb-2">Haz clic en una barra para ver el detalle de ese perfil más abajo.</p>
        <Plot
          data={[
            {
              type: "bar",
              x: orden.map((p) => p.PERFIL_NOMBRE),
              y: orden.map((p) => p.N_PERSONAS),
              marker: { color: orden.map((p) => p.COLOR) },
              text: orden.map((p) => `${p.PCT_POBLACION.toFixed(1)}%`),
              textposition: "outside",
              customdata: orden.map((p) => p.CLUSTER),
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
            setClusterSel(orden[idx].CLUSTER);
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

function PerfilDetalleView({ detalle }: { detalle: NonNullable<ReturnType<typeof getPerfilDetalle>> extends Promise<infer T> ? T : never }) {
  return (
    <div className="space-y-4 bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start gap-3">
        <span className="w-2.5 h-2.5 rounded-full mt-1.5 shrink-0" style={{ backgroundColor: detalle.color }} />
        <div>
          <h3 className="text-lg font-semibold tracking-tight text-slate-800">{detalle.nombre}</h3>
          <p className="text-sm font-medium text-slate-500">
            {detalle.n_personas} personas ({detalle.pct_poblacion}% de la población)
          </p>
          <p className="text-sm text-slate-600 mt-1">{detalle.descripcion}</p>
        </div>
      </div>

      {detalle.top_features.length > 0 && (
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
