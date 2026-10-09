import Plot from "react-plotly.js";
import type { PuntoMapaDimension, TipoMapa } from "../api/client";
import { colorPatron } from "../lib/colores";

interface Props {
  puntos: PuntoMapaDimension[];
  tipo: TipoMapa;
  /** patrón o tema resaltado (según `tipo`); null = ninguno */
  seleccion: number | null;
  personaSeleccionada: number | null;
  alto: number;
  onPersona: (id: number) => void;
  onGrupo: (id: number) => void;
}

// Patrones (máx. 6): un color por patrón (paleta validada para scatter) + rótulo P1…P6 sobre su
// zona. Temas (decenas): ninguna paleta los distingue, así que van en gris con rótulo T1… para los
// más grandes y el tema elegido se resalta en azul.
const RESALTE = "#2a78d6";
const BASE = "#94a3b8";
const MAX_ROTULOS_TEMA = 10;

const mediana = (xs: number[]) => {
  const o = [...xs].sort((a, b) => a - b);
  return o[Math.floor(o.length / 2)];
};

// Mapa t-SNE de las personas con evidencias en la dimensión (solo para orientarse).
export default function MapaDimension({ puntos, tipo, seleccion, personaSeleccionada, alto, onPersona, onGrupo }: Props) {
  const grupo = (p: PuntoMapaDimension) => (tipo === "patrones" ? p.patron : p.tema) ?? null;
  const prefijo = tipo === "patrones" ? "P" : "T";
  const nombreGrupo = tipo === "patrones" ? "Patrón" : "Tema principal";

  const hover = (p: PuntoMapaDimension) =>
    [
      `<b>${p.nombre}</b>`,
      p.cargo_actual ?? "Sin cargo actual",
      p.patron !== null && p.patron !== undefined ? `Patrón ${p.patron + 1}` : "",
      p.tema !== null && p.tema !== undefined
        ? `Tema principal: ${p.tema + 1} (${Math.round((p.proporcion_tema ?? 0) * 100)} % de sus evidencias)`
        : "",
      p.intensidad !== null ? `Intensidad: ${Math.floor(p.intensidad)}` : "",
      p.vigente ? "" : "<i>No vigente</i>",
      "<i style='color:#94a3b8'>Clic para ver la ficha</i>",
    ]
      .filter(Boolean)
      .join("<br>");

  const traza = (ps: PuntoMapaDimension[], color: string, opacidad: number, tam: number): Plotly.Data => ({
    type: "scattergl",
    mode: "markers",
    x: ps.map((p) => p.x),
    y: ps.map((p) => p.y),
    customdata: ps.map((p) => p.persona_id),
    text: ps.map(hover),
    hoverinfo: "text",
    showlegend: false,
    marker: { color, size: tam, opacity: opacidad, line: { color: "#ffffff", width: 0.8 } },
  });

  const trazas: Plotly.Data[] = [];
  if (tipo === "patrones") {
    const patrones = Array.from(new Set(puntos.map((p) => p.patron ?? -1))).sort((a, b) => a - b);
    for (const g of patrones) {
      const ps = puntos.filter((p) => (p.patron ?? -1) === g);
      const activo = seleccion === null || seleccion === g;
      trazas.push(traza(ps, g >= 0 ? colorPatron(g) : BASE, activo ? 0.85 : 0.12, 8));
    }
  } else {
    const elegidos = seleccion === null ? [] : puntos.filter((p) => grupo(p) === seleccion);
    const resto = seleccion === null ? puntos : puntos.filter((p) => grupo(p) !== seleccion);
    trazas.push(traza(resto, BASE, seleccion === null ? 0.7 : 0.25, 8));
    if (elegidos.length) trazas.push(traza(elegidos, RESALTE, 0.95, 9));
  }

  // rótulos: todos los patrones; en temas, los MAX_ROTULOS_TEMA con más personas (y el elegido)
  const porGrupo = new Map<number, PuntoMapaDimension[]>();
  for (const p of puntos) {
    const g = grupo(p);
    if (g === null) continue;
    porGrupo.set(g, [...(porGrupo.get(g) ?? []), p]);
  }
  let ids = [...porGrupo.keys()].sort((a, b) => porGrupo.get(b)!.length - porGrupo.get(a)!.length);
  if (tipo === "temas") ids = ids.slice(0, MAX_ROTULOS_TEMA);
  if (seleccion !== null && porGrupo.has(seleccion) && !ids.includes(seleccion)) ids.push(seleccion);
  const rotulos: Partial<Plotly.Annotations>[] = ids.map((g) => {
    const ps = porGrupo.get(g)!;
    const activo = seleccion === null || seleccion === g;
    return {
      x: mediana(ps.map((p) => p.x)),
      y: mediana(ps.map((p) => p.y)),
      text: `<b>${prefijo}${g + 1}</b>`,
      showarrow: false,
      font: { size: 12, color: "#0f172a" },
      bgcolor: "rgba(255,255,255,0.9)",
      bordercolor: tipo === "patrones" ? colorPatron(g) : seleccion === g ? RESALTE : "#64748b",
      borderwidth: tipo === "patrones" || seleccion === g ? 2 : 1,
      borderpad: 3,
      opacity: activo ? 1 : 0.45,
      captureevents: true,
      hovertext: `${nombreGrupo} ${g + 1}: ${ps.length} personas · clic para resaltar`,
    };
  });

  const sel = puntos.find((p) => p.persona_id === personaSeleccionada);
  if (sel) {
    trazas.push({
      type: "scatter",
      mode: "markers",
      x: [sel.x],
      y: [sel.y],
      hoverinfo: "skip",
      showlegend: false,
      marker: { size: 22, color: "rgba(0,0,0,0)", line: { color: "#E63946", width: 3 } },
    });
    rotulos.push({
      x: sel.x, y: sel.y, text: sel.nombre, showarrow: true, arrowhead: 0, arrowcolor: "#E63946", ax: 0, ay: -36,
      font: { size: 12, color: "#fff" }, bgcolor: "#E63946", borderpad: 4,
    });
  }

  return (
    <Plot
      data={trazas}
      layout={{
        autosize: true,
        height: alto,
        margin: { l: 4, r: 4, t: 4, b: 4 },
        xaxis: { visible: false },
        yaxis: { visible: false },
        annotations: rotulos,
        hovermode: "closest",
        hoverdistance: 8,
        hoverlabel: { bgcolor: "#fff", bordercolor: "#cbd5e1", font: { size: 12, color: "#0f172a" }, align: "left" },
        plot_bgcolor: "#fff",
        paper_bgcolor: "#fff",
        dragmode: "pan",
      }}
      config={{
        displaylogo: false,
        responsive: true,
        scrollZoom: false,
        displayModeBar: true,
        modeBarButtonsToRemove: ["zoom2d", "pan2d", "select2d", "lasso2d", "autoScale2d", "toImage"],
        doubleClick: "reset",
      }}
      style={{ width: "100%" }}
      useResizeHandler
      onClick={(e) => {
        const id = e.points[0]?.customdata;
        if (typeof id === "number") onPersona(id);
      }}
      onClickAnnotation={(e) => {
        const m = /^<b>[PT](\d+)<\/b>$/.exec(String(e.annotation.text ?? ""));
        if (m) onGrupo(Number(m[1]) - 1);
      }}
    />
  );
}
