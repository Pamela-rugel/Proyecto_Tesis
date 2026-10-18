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
  /** nombre de cada patrón (hover) */
  nombresPatrones?: Record<number, string>;
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

type PuntoDibujo = PuntoMapaDimension & { apilados: number };

// Quienes tienen exactamente los mismos valores quedan en la MISMA coordenada t-SNE (en Ponencias
// de docentes, 223 personas en 61 posiciones) y se tapan entre sí. Cada grupo apilado se reparte
// en una espiral (girasol) alrededor de su posición, para que cada persona tenga su punto.
const ANGULO_AUREO = Math.PI * (3 - Math.sqrt(5));
function desapilar(puntos: PuntoMapaDimension[]): PuntoDibujo[] {
  if (!puntos.length) return [];
  const xs = puntos.map((p) => p.x), ys = puntos.map((p) => p.y);
  const paso = 0.005 * Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 1e-6);
  const pilas = new Map<string, PuntoMapaDimension[]>();
  for (const p of puntos) {
    const clave = `${p.x.toFixed(2)}|${p.y.toFixed(2)}`;
    pilas.set(clave, [...(pilas.get(clave) ?? []), p]);
  }
  const salida: PuntoDibujo[] = [];
  for (const pila of pilas.values()) {
    pila.sort((a, b) => a.nombre.localeCompare(b.nombre));
    pila.forEach((p, k) => {
      const r = paso * Math.sqrt(k);
      salida.push({ ...p, x: p.x + r * Math.cos(k * ANGULO_AUREO), y: p.y + r * Math.sin(k * ANGULO_AUREO), apilados: pila.length });
    });
  }
  return salida;
}

// Mapa t-SNE de las personas con evidencias en la dimensión (solo para orientarse).
export default function MapaDimension({ puntos: originales, tipo, seleccion, personaSeleccionada, alto, onPersona, onGrupo, nombresPatrones = {} }: Props) {
  const puntos = desapilar(originales);
  const grupo = (p: PuntoDibujo) => (tipo === "patrones" ? p.patron : p.tema) ?? null;
  const prefijo = tipo === "patrones" ? "P" : "T";
  const nombreGrupo = tipo === "patrones" ? "Patrón" : "Tema principal";

  // parte de las evidencias de la persona en el tema elegido (0 si no tiene evidencias en él)
  const enTema = (p: PuntoDibujo) =>
    tipo === "temas" && seleccion !== null ? (p.temas ?? []).find(([t]) => t === seleccion)?.[1] ?? 0 : 0;

  const hover = (p: PuntoDibujo) =>
    [
      `<b>${p.nombre}</b>`,
      enTema(p) > 0 ? `Tema ${seleccion! + 1}: ${Math.round(enTema(p) * 100)} % de sus evidencias` : "",
      p.apilados > 1 ? `<i>${p.apilados} personas con valores idénticos (agrupadas aquí)</i>` : "",
      p.cargo_actual ?? "Sin cargo actual",
      p.patron !== null && p.patron !== undefined ? `Patrón ${p.patron + 1}${nombresPatrones[p.patron] ? `: ${nombresPatrones[p.patron]}` : ""}` : "",
      p.tema !== null && p.tema !== undefined
        ? `Tema principal: ${p.tema + 1} (${Math.round((p.proporcion_tema ?? 0) * 100)} % de sus evidencias)`
        : "",
      p.nivel != null ? `Nivel: ${Math.round(p.nivel)}` : "",
      p.vigente ? "" : "<i>No vigente</i>",
      "<i style='color:#94a3b8'>Clic para ver la ficha</i>",
    ]
      .filter(Boolean)
      .join("<br>");

  const traza = (ps: PuntoDibujo[], color: string, opacidad: number, tam: number | number[]): Plotly.Data => ({
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
    // tema elegido: TODAS las personas con evidencias en él (no solo las que lo tienen como
    // principal); el tamaño crece con la parte de sus evidencias en el tema
    const elegidos = puntos.filter((p) => enTema(p) > 0).sort((a, b) => enTema(a) - enTema(b));
    const resto = seleccion === null ? puntos : puntos.filter((p) => enTema(p) === 0);
    trazas.push(traza(resto, BASE, seleccion === null ? 0.7 : 0.2, seleccion === null ? 8 : 6));
    if (elegidos.length) trazas.push(traza(elegidos, RESALTE, 0.85, elegidos.map((p) => 6 + 12 * Math.sqrt(enTema(p)))));
  }

  // rótulos: todos los patrones; en temas, los MAX_ROTULOS_TEMA con más personas (y el elegido)
  const porGrupo = new Map<number, PuntoDibujo[]>();
  for (const p of puntos) {
    const g = grupo(p);
    if (g === null) continue;
    porGrupo.set(g, [...(porGrupo.get(g) ?? []), p]);
  }
  let ids = [...porGrupo.keys()].sort((a, b) => porGrupo.get(b)!.length - porGrupo.get(a)!.length);
  if (tipo === "temas") ids = ids.slice(0, MAX_ROTULOS_TEMA);
  if (seleccion !== null && porGrupo.has(seleccion) && !ids.includes(seleccion)) ids.push(seleccion);
  const rotulos: Partial<Plotly.Annotations>[] = ids.map((g) => {
    const conTema = tipo === "temas" && g === seleccion ? puntos.filter((p) => enTema(p) > 0) : [];
    const ps = conTema.length ? conTema : porGrupo.get(g)!;
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
      hovertext: conTema.length
        ? `Tema ${g + 1}: ${ps.length} personas con evidencias en él · clic para quitar`
        : `${nombreGrupo} ${g + 1}: ${ps.length} personas · clic para resaltar`,
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
        // conserva el acercamiento del usuario entre re-renderizados; se reinicia al cambiar los datos
        uirevision: `dimension-${tipo}-${originales.length}`,
      }}
      config={{
        displaylogo: false,
        responsive: true,
        scrollZoom: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ["zoom2d", "select2d", "lasso2d", "autoScale2d", "toImage"],
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
