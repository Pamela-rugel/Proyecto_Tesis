import Plot from "react-plotly.js";
import type { PuntoPerfil } from "../api/client";
import { colorPatron } from "../lib/colores";

export type ColorPerfil = "ninguno" | "intensidad" | "patron" | "global";

interface Props {
  puntos: PuntoPerfil[];
  color: ColorPerfil;
  nombreDimension: string | null;
  personaSeleccionada: number | null;
  alto: number;
  onPersona: (id: number) => void;
  /** patrón global resaltado (modo "global") */
  globalSeleccionado?: number | null;
  onGlobal?: (id: number) => void;
  /** microarquetipo resaltado dentro del patrón global elegido */
  microSeleccionado?: number | null;
  onMicro?: (id: number) => void;
}

const RESALTE = "#2a78d6";

// Rampa secuencial de un solo tono (azul) de la paleta de referencia: claro = poca intensidad.
const RAMPA: [number, string][] = [
  [0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"], [0.75, "#1c5cab"], [1, "#0d366b"],
];
const BASE = "#94a3b8";

const mediana = (xs: number[]) => {
  const o = [...xs].sort((a, b) => a - b);
  return o[Math.floor(o.length / 2)];
};

// Mapa t-SNE del perfil completo (todas las dimensiones, DEC-056): las personas cercanas se parecen
// en el conjunto. Se colorea por la intensidad o el patrón de UNA dimensión para leerlo.
export default function MapaPerfil({
  puntos, color, nombreDimension, personaSeleccionada, alto, onPersona, globalSeleccionado = null, onGlobal,
  microSeleccionado = null, onMicro,
}: Props) {
  const hover = (p: PuntoPerfil) =>
    [
      `<b>${p.nombre}</b>`,
      p.cargo_actual ?? "Sin cargo actual",
      p.patron_global !== null && p.patron_global !== undefined ? `Patrón global ${p.patron_global + 1}` : "",
      nombreDimension && p.intensidad !== undefined && p.intensidad !== null
        ? `${nombreDimension}: intensidad ${Math.floor(p.intensidad)}${p.patron !== null && p.patron !== undefined ? ` · Patrón ${p.patron + 1}` : ""}`
        : "",
      p.vigente ? "" : "<i>No vigente</i>",
      "<i style='color:#94a3b8'>Clic para ver la ficha</i>",
    ]
      .filter(Boolean)
      .join("<br>");

  const base = (ps: PuntoPerfil[], marker: Partial<Plotly.ScatterMarker>): Plotly.Data => ({
    type: "scattergl",
    mode: "markers",
    x: ps.map((p) => p.x),
    y: ps.map((p) => p.y),
    customdata: ps.map((p) => p.persona_id),
    text: ps.map(hover),
    hoverinfo: "text",
    showlegend: false,
    marker: { size: 7, line: { color: "#ffffff", width: 0.6 }, ...marker },
  });

  const trazas: Plotly.Data[] = [];
  const rotulos: Partial<Plotly.Annotations>[] = [];
  if (color === "intensidad") {
    // primero los de menor intensidad, para que los intensos queden encima
    const ps = [...puntos].sort((a, b) => (a.intensidad ?? 0) - (b.intensidad ?? 0));
    trazas.push(base(ps, {
      color: ps.map((p) => p.intensidad ?? 0), colorscale: RAMPA, cmin: 0, cmax: 100, opacity: 0.9,
      colorbar: { title: { text: "Intensidad", side: "right" }, thickness: 10, len: 0.6, outlinewidth: 0, tickfont: { size: 10 } },
    }));
  } else if (color === "patron") {
    const sin = puntos.filter((p) => p.patron === null || p.patron === undefined);
    trazas.push(base(sin, { color: "#e2e8f0", opacity: 0.6 }));
    const ids = Array.from(new Set(puntos.map((p) => p.patron).filter((x): x is number => x !== null && x !== undefined))).sort((a, b) => a - b);
    for (const g of ids) {
      const ps = puntos.filter((p) => p.patron === g);
      trazas.push(base(ps, { color: colorPatron(g), opacity: 0.85 }));
      rotulos.push({
        x: mediana(ps.map((p) => p.x)), y: mediana(ps.map((p) => p.y)), text: `<b>P${g + 1}</b>`, showarrow: false,
        font: { size: 12, color: "#0f172a" }, bgcolor: "rgba(255,255,255,0.9)", bordercolor: colorPatron(g), borderwidth: 2, borderpad: 3,
      });
    }
  } else if (color === "global") {
    // hasta 6 patrones: un color cada uno (paleta validada) + rótulo; con más, gris + rótulo y el
    // elegido resaltado (no hay paleta que distinga más de 6 en un scatter)
    const ids = Array.from(new Set(puntos.map((p) => p.patron_global).filter((x): x is number => x !== null && x !== undefined))).sort((a, b) => a - b);
    const conColor = ids.length <= 6;
    const conMicros =
      globalSeleccionado !== null && puntos.some((p) => p.patron_global === globalSeleccionado && (p.micro_global ?? -1) >= 0);
    if (conMicros) {
      // patrón elegido: un color por microarquetipo (máx. 5) y rótulo G{n}.{m}; el resto en gris
      trazas.push(base(puntos.filter((p) => p.patron_global !== globalSeleccionado), { color: BASE, opacity: 0.12 }));
      const del = puntos.filter((p) => p.patron_global === globalSeleccionado);
      const micros = Array.from(new Set(del.map((p) => p.micro_global ?? -1))).sort((a, b) => a - b);
      for (const m of micros) {
        const ps = del.filter((p) => (p.micro_global ?? -1) === m);
        const activo = microSeleccionado === null || microSeleccionado === m;
        trazas.push(base(ps, { color: m >= 0 ? colorPatron(m) : BASE, opacity: activo ? 0.9 : 0.15 }));
        if (m < 0) continue;
        rotulos.push({
          x: mediana(ps.map((p) => p.x)), y: mediana(ps.map((p) => p.y)), text: `<b>G${globalSeleccionado + 1}.${m + 1}</b>`,
          showarrow: false, font: { size: 12, color: "#0f172a" }, bgcolor: "rgba(255,255,255,0.9)", bordercolor: colorPatron(m),
          borderwidth: 2, borderpad: 3, opacity: activo ? 1 : 0.45, captureevents: true,
          hovertext: `Microarquetipo G${globalSeleccionado + 1}.${m + 1}: ${ps.length} personas · clic para resaltar`,
        });
      }
    }
    for (const g of conMicros ? [] : ids) {
      const ps = puntos.filter((p) => p.patron_global === g);
      const activo = globalSeleccionado === null || globalSeleccionado === g;
      const c = conColor ? colorPatron(g) : globalSeleccionado === g ? RESALTE : BASE;
      trazas.push(base(ps, { color: c, opacity: activo ? 0.85 : 0.12 }));
      rotulos.push({
        x: mediana(ps.map((p) => p.x)), y: mediana(ps.map((p) => p.y)), text: `<b>G${g + 1}</b>`, showarrow: false,
        font: { size: 12, color: "#0f172a" }, bgcolor: "rgba(255,255,255,0.9)", bordercolor: conColor ? colorPatron(g) : "#64748b",
        borderwidth: 2, borderpad: 3, opacity: activo ? 1 : 0.45, captureevents: true,
        hovertext: `Patrón global ${g + 1}: ${ps.length} personas · clic para resaltar`,
      });
    }
  } else {
    trazas.push(base(puntos, { color: BASE, opacity: 0.7 }));
  }

  const sel = puntos.find((p) => p.persona_id === personaSeleccionada);
  if (sel) {
    trazas.push({
      type: "scatter", mode: "markers", x: [sel.x], y: [sel.y], hoverinfo: "skip", showlegend: false,
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
        const texto = String(e.annotation.text ?? "");
        const g = /^<b>G(\d+)<\/b>$/.exec(texto);
        if (g && onGlobal) onGlobal(Number(g[1]) - 1);
        const mi = /^<b>G\d+\.(\d+)<\/b>$/.exec(texto);
        if (mi && onMicro) onMicro(Number(mi[1]) - 1);
      }}
    />
  );
}
