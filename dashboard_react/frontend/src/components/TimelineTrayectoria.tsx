import Plot from "react-plotly.js";
import type { EventoTrayectoria } from "../api/types";

interface Props {
  eventos: EventoTrayectoria[];
  colorTipoEvento: Record<string, string>;
  etiquetaTipoEvento: Record<string, string>;
}

const MESES = [
  "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic",
];

function formatMesAnio(iso: string): string {
  const d = new Date(iso);
  return `${MESES[d.getMonth()]} ${d.getFullYear()}`;
}

interface EventoPreparado {
  evento: EventoTrayectoria;
  lane: string;
  inicio: Date;
  finEfectiva: Date;
  detalle: string;
  rango: string;
}

/** Empaqueta eventos que se solapan en fecha dentro de la MISMA lane en sub-filas
 * distintas (0, 1, 2...), para que dos contratos simultaneos (ej. dos cargos de grado a
 * la vez) se dibujen en barras separadas verticalmente en vez de superpuestas - pedido
 * explicito del usuario 2026-09-10 ("siento que ahora se mezcla todo"). Algoritmo greedy
 * de intervalos: dentro de cada lane, ordenado por fecha de inicio, cada evento se asigna
 * a la primera sub-fila cuyo ultimo evento ya haya terminado antes de que este empiece;
 * si ninguna esta libre, abre una sub-fila nueva. Misma logica que
 * `_asignar_subfilas` en notebooks/08_dashboard/app.py (Streamlit) - mantener ambas en
 * sync si se ajusta el criterio. */
function asignarSubfilas(porLane: Map<string, EventoPreparado[]>): Map<EventoPreparado, number> {
  const subfila = new Map<EventoPreparado, number>();
  for (const grupo of porLane.values()) {
    const ordenado = [...grupo].sort((a, b) => a.inicio.getTime() - b.inicio.getTime());
    const finPorSubfila: Date[] = [];
    for (const item of ordenado) {
      let asignada = -1;
      for (let i = 0; i < finPorSubfila.length; i++) {
        if (item.inicio.getTime() >= finPorSubfila[i].getTime()) {
          asignada = i;
          break;
        }
      }
      if (asignada === -1) {
        asignada = finPorSubfila.length;
        finPorSubfila.push(item.finEfectiva);
      } else {
        finPorSubfila[asignada] = item.finEfectiva;
      }
      subfila.set(item, asignada);
    }
  }
  return subfila;
}

export default function TimelineTrayectoria({ eventos, colorTipoEvento, etiquetaTipoEvento }: Props) {
  if (eventos.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No hay eventos de trayectoria (cargos, funciones, experiencia externa) registrados para
        esta persona.
      </p>
    );
  }

  const hoy = new Date();
  const hoyIso = hoy.toISOString().slice(0, 10);

  const sorted = [...eventos].sort(
    (a, b) => new Date(a.FECHA_INICIO ?? 0).getTime() - new Date(b.FECHA_INICIO ?? 0).getTime()
  );

  const preparados: EventoPreparado[] = sorted.map((e) => {
    const inicio = e.FECHA_INICIO ? new Date(e.FECHA_INICIO) : hoy;
    let finEfectiva = e.FECHA_FIN ? new Date(e.FECHA_FIN) : hoy;
    if (finEfectiva <= inicio) {
      finEfectiva = new Date(inicio.getTime() + 30 * 86400000);
    }
    const detalle = e.DESCRIPCION + (e.UNIDAD ? ` — ${e.UNIDAD}` : "");
    const rango = e.FECHA_INICIO
      ? `${formatMesAnio(e.FECHA_INICIO)} - ${e.ES_VIGENTE ? "actualidad" : e.FECHA_FIN ? formatMesAnio(e.FECHA_FIN) : ""}`
      : "";
    return {
      evento: e,
      lane: etiquetaTipoEvento[e.TIPO_EVENTO] ?? e.TIPO_EVENTO,
      inicio,
      finEfectiva,
      detalle,
      rango,
    };
  });

  // Orden de lanes: primera aparicion por fecha de inicio (igual que Streamlit).
  const ordenLanes = Array.from(new Set(preparados.map((p) => p.lane)));

  const porLane = new Map<string, EventoPreparado[]>();
  for (const p of preparados) {
    if (!porLane.has(p.lane)) porLane.set(p.lane, []);
    porLane.get(p.lane)!.push(p);
  }
  const subfilaPorEvento = asignarSubfilas(porLane);

  // Cada lane ocupa tantas filas visuales como su maximo de sub-filas simultaneas (1 si
  // nunca hay solape); las lanes se apilan de arriba a abajo en `ordenLanes`.
  const altoPorLane = new Map<string, number>();
  for (const [lane, grupo] of porLane) {
    const maxSubfila = Math.max(...grupo.map((p) => subfilaPorEvento.get(p) ?? 0));
    altoPorLane.set(lane, maxSubfila + 1);
  }
  const offsetPorLane = new Map<string, number>();
  let acumulado = 0;
  for (const lane of ordenLanes) {
    offsetPorLane.set(lane, acumulado);
    acumulado += altoPorLane.get(lane) ?? 1;
  }
  const totalFilas = acumulado;

  const filaYPorEvento = new Map<EventoPreparado, number>();
  for (const p of preparados) {
    filaYPorEvento.set(p, (offsetPorLane.get(p.lane) ?? 0) + (subfilaPorEvento.get(p) ?? 0));
  }

  // Etiquetas del eje Y: una por lane, centrada en sus sub-filas (si tiene 2 sub-filas en
  // las posiciones 3 y 4, la etiqueta se centra en 3.5) - las sub-filas no llevan
  // etiqueta propia, siguen leyendose como "la misma categoria".
  const tickvals = ordenLanes.map(
    (lane) => (offsetPorLane.get(lane) ?? 0) + ((altoPorLane.get(lane) ?? 1) - 1) / 2
  );

  const tiposPresentes = Array.from(new Set(preparados.map((p) => p.evento.TIPO_EVENTO)));

  const traces = tiposPresentes.map((tipo) => {
    const itemsTipo = preparados.filter((p) => p.evento.TIPO_EVENTO === tipo);
    return {
      type: "bar" as const,
      orientation: "h" as const,
      base: itemsTipo.map((p) => p.inicio.toISOString().slice(0, 10)),
      x: itemsTipo.map((p) => p.finEfectiva.getTime() - p.inicio.getTime()),
      y: itemsTipo.map((p) => filaYPorEvento.get(p) ?? 0),
      name: etiquetaTipoEvento[tipo] ?? tipo,
      marker: { color: colorTipoEvento[tipo] ?? "#94A3B8", line: { width: 0 } },
      customdata: itemsTipo.map((p) => [p.detalle, p.rango]),
      hovertemplate: "<b>%{customdata[0]}</b><br>%{customdata[1]}<extra></extra>",
      width: 0.7,
    };
  });

  const hayVigentes = preparados.some((p) => p.evento.ES_VIGENTE);
  const lanesVigentes = Array.from(new Set(preparados.filter((p) => p.evento.ES_VIGENTE).map((p) => p.lane)));

  return (
    <div>
      <Plot
        data={traces}
        layout={{
          height: 190 + 42 * totalFilas,
          barmode: "overlay",
          showlegend: true,
          legend: {
            orientation: "h",
            yanchor: "bottom",
            y: 1.02,
            xanchor: "left",
            x: 0,
            font: { size: 11 },
          },
          margin: { l: 160, r: 30, t: 44, b: 44 },
          font: { size: 12, color: "#334155" },
          plot_bgcolor: "#FFFFFF",
          paper_bgcolor: "#FFFFFF",
          xaxis: {
            type: "date",
            title: { text: "" },
            showgrid: true,
            gridcolor: "#EEF1F5",
            showline: true,
            linecolor: "#CBD5E1",
            tickfont: { size: 11, color: "#475569" },
            automargin: true,
            zeroline: false,
          },
          yaxis: {
            autorange: "reversed",
            title: { text: "" },
            showgrid: false,
            showline: true,
            linecolor: "#CBD5E1",
            tickfont: { size: 12, color: "#1E293B" },
            automargin: true,
            tickmode: "array",
            tickvals,
            ticktext: ordenLanes,
          },
          shapes: [
            {
              type: "line",
              x0: hoyIso,
              x1: hoyIso,
              y0: 0,
              y1: 1,
              yref: "paper",
              line: { color: "#E63946", width: 1.5, dash: "dot" },
            },
          ],
          annotations: [
            {
              x: hoyIso,
              y: 1,
              yref: "paper",
              text: "Hoy",
              showarrow: false,
              font: { color: "#E63946", size: 11 },
              yanchor: "bottom",
            },
          ],
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%" }}
        useResizeHandler
      />
      {hayVigentes && (
        <p className="text-xs text-slate-500 mt-1">
          Vigente hasta la actualidad: {lanesVigentes.join(", ")} (línea punteada roja = hoy).
        </p>
      )}
    </div>
  );
}
