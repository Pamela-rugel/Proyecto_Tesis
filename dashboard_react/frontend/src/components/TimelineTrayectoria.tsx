import Plot from "react-plotly.js";
import { useQuery } from "@tanstack/react-query";
import { getTrayectoria, type TramoTrayectoria } from "../api/client";

const ORDEN_CARRIL = [
  "Cargo de planta en ESPOL",
  "Contrato ocasional en ESPOL",
  "Función adicional",
  "Subrogación",
  "Experiencia externa (Ecuador)",
  "Experiencia externa (exterior)",
];
const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const DIA = 86400000;
const fecha = (d: Date) => `${MESES[d.getMonth()]} ${d.getFullYear()}`;

// Un color por cargo de la persona (tonos equiespaciados): el mismo cargo siempre con el mismo
// color, para ver de un vistazo si volvió a un cargo que ya tuvo.
function paleta(textos: string[]): Map<string, string> {
  const unicos = Array.from(new Set(textos));
  return new Map(unicos.map((t, i) => [t, `hsl(${Math.round((i * 360) / Math.max(unicos.length, 1)) % 360}, 62%, ${i % 2 ? 42 : 52}%)`]));
}

interface Preparado {
  t: TramoTrayectoria;
  inicio: Date;
  fin: Date;
  fila: number;
}

// Tramos de un mismo carril que se solapan van en sub-filas distintas (algoritmo voraz).
function ubicar(tramos: TramoTrayectoria[], hoy: Date) {
  const carriles = ORDEN_CARRIL.filter((c) => tramos.some((t) => t.carril === c));
  const preparados: Preparado[] = [];
  const ticks: { y: number; texto: string; desde: number; hasta: number }[] = [];
  let base = 0;
  for (const carril of carriles) {
    const finPorSubfila: number[] = [];
    const del = tramos.filter((t) => t.carril === carril).sort((a, b) => a.inicio.localeCompare(b.inicio));
    for (const t of del) {
      const inicio = new Date(t.inicio);
      let fin = t.fin ? new Date(t.fin) : t.estado === "actual" ? hoy : new Date(inicio.getTime() + 60 * DIA);
      if (fin.getTime() - inicio.getTime() < 20 * DIA) fin = new Date(inicio.getTime() + 20 * DIA);
      let sub = finPorSubfila.findIndex((f) => inicio.getTime() >= f);
      if (sub === -1) {
        sub = finPorSubfila.length;
        finPorSubfila.push(0);
      }
      finPorSubfila[sub] = fin.getTime();
      preparados.push({ t, inicio, fin, fila: base + sub });
    }
    const alto = Math.max(1, finPorSubfila.length);
    ticks.push({ y: base + (alto - 1) / 2, texto: carril, desde: base - 0.5, hasta: base + alto - 0.5 });
    base += alto;
  }
  return { preparados, ticks, filas: base };
}

export default function TimelineTrayectoria({ personaId }: { personaId: number }) {
  const { data, isLoading } = useQuery({ queryKey: ["trayectoria", personaId], queryFn: () => getTrayectoria(personaId) });
  if (isLoading) return <p className="text-xs text-slate-500">Cargando trayectoria…</p>;
  if (!data || data.tramos.length === 0) return <p className="text-xs text-slate-400">No hay trayectoria laboral registrada.</p>;

  const hoy = new Date();
  const { preparados, ticks, filas } = ubicar(data.tramos, hoy);
  const colores = paleta(preparados.map((p) => p.t.titulo));
  const texto = (p: Preparado) =>
    `<b>${p.t.titulo}</b>${p.t.lugar ? `<br>${p.t.lugar}` : ""}<br>${fecha(p.inicio)} – ` +
    (p.t.estado === "actual" ? "actualidad" : p.t.estado === "sin_fin" ? "sin fecha de fin registrada" : fecha(new Date(p.t.fin!)));

  // `base` es un atributo válido de las barras de Plotly que sus tipos de TypeScript no declaran
  const traza = (lista: Preparado[], extra: Partial<Plotly.PlotData>): Plotly.Data => ({
    type: "bar",
    orientation: "h",
    // con eje de fechas, la longitud de la barra va en milisegundos
    base: lista.map((p) => p.inicio.toISOString().slice(0, 10)) as unknown as number[],
    x: lista.map((p) => p.fin.getTime() - p.inicio.getTime()),
    y: lista.map((p) => p.fila),
    width: 0.7,
    text: lista.map(texto),
    hovertemplate: "%{text}<extra></extra>",
    textposition: "none",
    showlegend: false,
    ...extra,
  }) as Plotly.Data;
  const normales = preparados.filter((p) => p.t.estado !== "sin_fin");
  const sinFin = preparados.filter((p) => p.t.estado === "sin_fin");
  const hoyIso = hoy.toISOString().slice(0, 10);
  // rango: desde el primer tramo hasta hoy (o el ultimo fin), con un pequeño margen
  const minimo = Math.min(...preparados.map((p) => p.inicio.getTime()));
  const maximo = Math.max(hoy.getTime(), ...preparados.map((p) => p.fin.getTime()));
  const margen = (maximo - minimo) * 0.03 + 90 * DIA;
  const rango = [new Date(minimo - margen).toISOString().slice(0, 10), new Date(maximo + margen).toISOString().slice(0, 10)];
  // franjas alternas para separar visualmente cada tipo (carril)
  const franjas: Partial<Plotly.Shape>[] = ticks.map((t, i) => ({
    type: "rect", xref: "paper", x0: 0, x1: 1, y0: t.desde, y1: t.hasta, layer: "below", line: { width: 0 },
    fillcolor: i % 2 ? "#ffffff" : "#f1f5f9",
  }));

  return (
    <div>
      <Plot
        data={[
          traza(normales, { marker: { color: normales.map((p) => colores.get(p.t.titulo)!) } }),
          traza(sinFin, {
            marker: {
              color: sinFin.map((p) => colores.get(p.t.titulo)!),
              opacity: 0.35,
              line: { color: "#64748b", width: 1 },
              pattern: { shape: "/", fgcolor: "#64748b", size: 5 },
            },
          }),
        ]}
        layout={{
          height: 70 + 30 * filas,
          barmode: "overlay",
          margin: { l: 10, r: 10, t: 18, b: 30 },
          font: { size: 11, color: "#334155" },
          plot_bgcolor: "#fff",
          paper_bgcolor: "#fff",
          // grafico fijo: sin zoom ni arrastre, solo tooltip al pasar sobre una barra
          dragmode: false,
          hovermode: "closest",
          hoverdistance: 4,
          xaxis: { type: "date", range: rango, fixedrange: true, showgrid: true, gridcolor: "#e2e8f0", tickfont: { size: 10 }, zeroline: false },
          yaxis: {
            range: [filas - 0.5, -0.5],
            fixedrange: true,
            tickmode: "array",
            tickvals: ticks.map((t) => t.y),
            ticktext: ticks.map((t) => t.texto.replace(" en ESPOL", "").replace("Experiencia externa", "Exp. externa")),
            tickfont: { size: 11, color: "#1E293B" },
            automargin: true,
            showgrid: false,
            zeroline: false,
          },
          shapes: [...franjas, { type: "line", x0: hoyIso, x1: hoyIso, y0: 0, y1: 1, yref: "paper", line: { color: "#E63946", width: 1.5, dash: "dot" } }],
          annotations: [{ x: hoyIso, y: 1, yref: "paper", text: "Hoy", showarrow: false, yanchor: "bottom", font: { color: "#E63946", size: 10 } }],
          hoverlabel: { bgcolor: "#fff", bordercolor: "#cbd5e1", font: { size: 12, color: "#0f172a" }, align: "left" },
        }}
        config={{ displayModeBar: false, responsive: true, scrollZoom: false, doubleClick: false }}
        style={{ width: "100%" }}
        useResizeHandler
      />
      <p className="text-[11px] text-slate-400">
        Cada barra es un periodo; el mismo cargo conserva su color. Pasa el cursor para ver el detalle.
        {sinFin.length > 0 && " Las barras rayadas no tienen fecha de fin registrada y la persona ya no está vigente."}
      </p>
    </div>
  );
}
