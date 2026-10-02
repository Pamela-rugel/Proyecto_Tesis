import Plot from "react-plotly.js";
import type { Mapa, PuntoMapa, Subdivision } from "../api/client";
import { colorCluster, colorSub } from "../lib/colores";

interface Props {
  mapa: Mapa;
  clusterSeleccionado: number | null;
  subdivision: Subdivision | null;
  subpatronSeleccionado: number | null;
  personaSeleccionada: number | null;
  /** alto en px del área del gráfico (lo fija la página para igualarlo al panel derecho) */
  alto: number;
  onPersona: (id: number) => void;
}

const corto = (t: string, n = 34) => (t.length > n ? `${t.slice(0, n - 1)}…` : t);

const hover = (p: PuntoMapa, etiquetas: Record<string, string>, sub?: Subdivision | null) =>
  [
    `<b>${p.nombre}</b>${p.es_representante ? " · representante del grupo" : ""}`,
    p.cargo_actual ?? "Sin cargo actual",
    p.unidad_actual ?? "",
    `<span style="color:#64748b">Grupo: ${etiquetas[p.cluster]}</span>`,
    sub && p.subpatron >= 0
      ? `<span style="color:#64748b">Subgrupo: ${sub.subpatrones.find((s) => s.cluster === p.subpatron)?.etiqueta}` +
        `${p.es_subrepresentante ? " · representante" : ""}</span>`
      : "",
    p.perfil_mixto ? `Está entre dos grupos: también se parece mucho a «${etiquetas[p.cluster_2]}»` : "",
    p.vigente ? "" : "<i>No vigente</i>",
    "<i style='color:#94a3b8'>Clic para ver la ficha</i>",
  ]
    .filter(Boolean)
    .join("<br>");

const mediana = (xs: number[]) => {
  const o = [...xs].sort((a, b) => a - b);
  return o[Math.floor(o.length / 2)];
};

// Etiqueta de un grupo, ubicada en la mediana de sus puntos.
const rotulo = (puntos: PuntoMapa[], texto: string, color: string, opaco: boolean): Partial<Plotly.Annotations> => ({
  x: mediana(puntos.map((p) => p.tsne_x)),
  y: mediana(puntos.map((p) => p.tsne_y)),
  text: `<b>${texto}</b>`,
  showarrow: false,
  font: { size: 12, color: "#0f172a" },
  bgcolor: "rgba(255,255,255,0.88)",
  bordercolor: color,
  borderwidth: 2,
  borderpad: 4,
  opacity: opaco ? 1 : 0.35,
});

// t-SNE solo representa visualmente la red fusionada (SNF); el clustering NO se hizo en este plano.
export default function MapaTSNE({ mapa, clusterSeleccionado, subdivision, subpatronSeleccionado, personaSeleccionada, onPersona, alto }: Props) {
  const clusters = Array.from(new Set(mapa.puntos.map((p) => p.cluster))).sort((a, b) => a - b);
  const porSubpatron = clusterSeleccionado !== null && subdivision !== null;
  const trazas: Plotly.Data[] = [];
  const rotulos: Partial<Plotly.Annotations>[] = [];

  const traza = (puntos: PuntoMapa[], color: string | string[], opacidad: number, extra: Partial<Plotly.ScatterMarker> = {}, sub?: Subdivision | null): Plotly.Data => ({
    type: "scattergl",
    mode: "markers",
    x: puntos.map((p) => p.tsne_x),
    y: puntos.map((p) => p.tsne_y),
    customdata: puntos.map((p) => p.persona_id),
    text: puntos.map((p) => hover(p, mapa.etiquetas, sub)),
    hoverinfo: "text",
    showlegend: false,
    marker: { color, size: 9, opacity: opacidad, line: { color: "#ffffff", width: 0.8 }, ...extra },
  });

  if (porSubpatron) {
    const otros = mapa.puntos.filter((p) => p.cluster !== clusterSeleccionado);
    trazas.push(traza(otros, "#cbd5e1", 0.45, { size: 7 }));
    for (const s of subdivision.subpatrones) {
      const del = mapa.puntos.filter((p) => p.cluster === clusterSeleccionado && p.subpatron === s.cluster);
      if (!del.length) continue;
      const activo = subpatronSeleccionado === null || subpatronSeleccionado === s.cluster;
      trazas.push(traza(del.filter((p) => !p.es_subrepresentante), colorSub(s.cluster), activo ? 0.9 : 0.15, {}, subdivision));
      trazas.push(
        traza(del.filter((p) => p.es_subrepresentante), colorSub(s.cluster), 1, { symbol: "circle", size: 15, line: { color: "#0f172a", width: 2.5 } }, subdivision),
      );
      rotulos.push(rotulo(del, corto(s.etiqueta, 40), colorSub(s.cluster), activo));
    }
  } else {
    for (const c of clusters) {
      const del = mapa.puntos.filter((p) => p.cluster === c);
      const activo = clusterSeleccionado === null || clusterSeleccionado === c;
      const normales = del.filter((p) => !p.es_representante);
      // todas las personas como círculo del color de su patrón; quien se parece casi igual a
      // otro patrón lo indica el texto al pasar el cursor (no un símbolo aparte)
      trazas.push(traza(normales, colorCluster(c), activo ? 0.85 : 0.12));
      trazas.push(traza(del.filter((p) => p.es_representante), colorCluster(c), 1, { symbol: "circle", size: 15, line: { color: "#0f172a", width: 2.5 } }));
      rotulos.push(rotulo(del, corto(mapa.etiquetas[c], 40), colorCluster(c), activo));
    }
  }

  const sel = mapa.puntos.find((p) => p.persona_id === personaSeleccionada);
  if (sel) {
    trazas.push({
      type: "scatter",
      mode: "markers",
      x: [sel.tsne_x],
      y: [sel.tsne_y],
      hoverinfo: "skip",
      showlegend: false,
      marker: { size: 24, color: "rgba(0,0,0,0)", line: { color: "#E63946", width: 3 } },
    });
    rotulos.push({
      x: sel.tsne_x,
      y: sel.tsne_y,
      text: sel.nombre,
      showarrow: true,
      arrowhead: 0,
      arrowcolor: "#E63946",
      ax: 0,
      ay: -38,
      font: { size: 12, color: "#fff" },
      bgcolor: "#E63946",
      borderpad: 4,
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
        hoverdistance: 8, // el tooltip aparece solo al estar encima de un punto
        hoverlabel: { bgcolor: "#fff", bordercolor: "#cbd5e1", font: { size: 12, color: "#0f172a" }, align: "left" },
        plot_bgcolor: "#fff",
        paper_bgcolor: "#fff",
        dragmode: "pan", // arrastrar desplaza el mapa (útil tras acercar); la rueda no hace zoom
      }}
      // zoom solo con los botones + / − / restablecer; la rueda del mouse desplaza la página
      config={{
        displaylogo: false,
        responsive: true,
        scrollZoom: false,
        displayModeBar: true,
        modeBarButtonsToRemove: ["zoom2d", "pan2d", "select2d", "lasso2d", "autoScale2d", "toImage"],
        doubleClick: "reset", // doble clic vuelve a la vista completa
      }}
      style={{ width: "100%" }}
      useResizeHandler
      onClick={(e) => {
        const id = e.points[0]?.customdata;
        if (typeof id === "number") onPersona(id);
      }}
    />
  );
}
