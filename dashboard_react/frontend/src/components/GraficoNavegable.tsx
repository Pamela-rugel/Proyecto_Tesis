import { useEffect, useMemo, useRef, useState } from "react";
import Plot from "react-plotly.js";

type Rango = [number, number];
interface Vista {
  x: Rango;
  y: Rango;
}
/** Puntos a encuadrar (p. ej. el patrón elegido). */
export interface Enfoque {
  xs: number[];
  ys: number[];
  /** p. ej. "P3" o "G2.1", para el botón */
  nombre: string;
}

interface Props {
  data: Plotly.Data[];
  annotations: Partial<Plotly.Annotations>[];
  alto: number;
  /** al cambiar (otra dimensión, otro ámbito…), se vuelve a la vista completa */
  revision: string;
  onClick: (e: Readonly<Plotly.PlotMouseEvent>) => void;
  onClickAnnotation: (e: Readonly<Plotly.ClickAnnotationEvent>) => void;
  /** grupo elegido, para "Encuadrar" */
  enfoque?: Enfoque | null;
  /** persona elegida: si queda fuera de la vista ampliada, se centra en ella */
  foco?: { id: number; x: number; y: number } | null;
  /** la rueda solo hace zoom con Ctrl (o ⌘), para no estorbar al desplazar el panel que contiene el mapa */
  ruedaConCtrl?: boolean;
}

const PASO_ZOOM = 1.6;
const PASO_MOVER = 0.15;

const ATAJOS: [string, string][] = [
  ["Rueda del mouse / pellizco", "acercar o alejar donde está el puntero"],
  ["Arrastrar", "mover el mapa"],
  ["+  /  −", "acercar / alejar"],
  ["← ↑ → ↓", "mover (con Shift, más rápido)"],
  ["F", "encuadrar el grupo elegido"],
  ["Z", "zoom por área (arrastrar un rectángulo)"],
  ["0  o  doble clic", "ver todo"],
];

// fijo: un objeto nuevo en cada render haría que Plotly redibuje (y cortaría un arrastre en curso)
const CONFIG: Partial<Plotly.Config> = {
  displaylogo: false,
  responsive: true,
  scrollZoom: true,
  displayModeBar: false,
  doubleClick: "autosize",
};

const esEditable = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));

// Mapa de dispersión (Plotly) con zoom y desplazamiento cómodos: rueda del mouse centrada en el
// puntero, arrastrar para mover, atajos de teclado (cuando el puntero está sobre el mapa o el mapa
// tiene el foco) y una barra con los mismos comandos. La vista (rango de los ejes) vive aquí, así
// que se conserva al elegir personas o grupos y se reinicia solo cuando cambia `revision`.
export default function GraficoNavegable({
  data, annotations, alto, revision, onClick, onClickAnnotation, enfoque = null, foco = null, ruedaConCtrl = false,
}: Props) {
  const contenedor = useRef<HTMLDivElement>(null);
  const grafico = useRef<HTMLElement | null>(null);
  const completa = useRef<Vista | null>(null);
  const [vista, setVistaEstado] = useState<{ revision: string; v: Vista | null }>({ revision, v: null });
  const [modoArea, setModoArea] = useState(false);
  // ref y no estado: al arrastrar, Plotly cubre la página y el puntero "sale" del mapa; un cambio de
  // estado ahí redibujaría el gráfico a mitad del arrastre (los puntos volvían a su sitio y solo se
  // movían el círculo y los rótulos)
  const encima = useRef(false);
  const [aviso, setAviso] = useState(false);
  const [ayuda, setAyuda] = useState(false);

  let v = vista.v;
  if (vista.revision !== revision) {
    v = null;
    completa.current = null;
    setVistaEstado({ revision, v: null });
  }
  const setVista = (nv: Vista | null) => setVistaEstado({ revision, v: nv });

  type Eje = { range?: Rango; autorange?: boolean | string };
  const ejes = () => (grafico.current as unknown as { _fullLayout?: { xaxis?: Eje; yaxis?: Eje } } | null)?._fullLayout;
  /** rango que Plotly está mostrando ahora (también cuando es automático) */
  const actual = (): Vista | null => {
    const fl = ejes();
    const x = fl?.xaxis?.range;
    const y = fl?.yaxis?.range;
    return x && y ? { x: [x[0], x[1]], y: [y[0], y[1]] } : null;
  };
  /** guarda la vista completa (rango automático), referencia para encuadrar y para el nivel de zoom */
  const alActualizar = (_f: unknown, div: HTMLElement) => {
    grafico.current = div;
    if (ejes()?.xaxis?.autorange === true) completa.current = actual();
  };

  const zoom = (factor: number) => {
    const a = actual();
    if (!a) return;
    const escalar = ([lo, hi]: Rango): Rango => {
      const c = (lo + hi) / 2;
      const m = ((hi - lo) / 2) * factor;
      return [c - m, c + m];
    };
    setVista({ x: escalar(a.x), y: escalar(a.y) });
  };
  const mover = (dx: number, dy: number) => {
    const a = actual();
    if (!a) return;
    const sx = (a.x[1] - a.x[0]) * dx;
    const sy = (a.y[1] - a.y[0]) * dy;
    setVista({ x: [a.x[0] + sx, a.x[1] + sx], y: [a.y[0] + sy, a.y[1] + sy] });
  };
  /** encuadra los puntos conservando la proporción de la vista completa (no deforma el mapa) */
  const encuadrar = (xs: number[], ys: number[]) => {
    const c = completa.current ?? actual();
    if (!c || !xs.length) return;
    const fx = c.x[1] - c.x[0];
    const fy = c.y[1] - c.y[0];
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    // margen del 12 % y no menos del 6 % del mapa (un grupo de una sola persona)
    const ancho = Math.max((x1 - x0) * 1.24, ((y1 - y0) * 1.24 * fx) / fy, fx * 0.06);
    const altoV = (ancho * fy) / fx;
    const cx = (x0 + x1) / 2;
    const cy = (y0 + y1) / 2;
    setVista({ x: [cx - ancho / 2, cx + ancho / 2], y: [cy - altoV / 2, cy + altoV / 2] });
  };
  const verTodo = () => setVista(null);

  // la persona elegida (p. ej. desde la lista o el buscador) siempre queda a la vista
  const focoId = foco?.id ?? null;
  useEffect(() => {
    if (!foco || !v) return;
    const dentro = (n: number, [lo, hi]: Rango) => n >= Math.min(lo, hi) && n <= Math.max(lo, hi);
    if (dentro(foco.x, v.x) && dentro(foco.y, v.y)) return;
    const mx = (v.x[1] - v.x[0]) / 2;
    const my = (v.y[1] - v.y[0]) / 2;
    setVista({ x: [foco.x - mx, foco.x + mx], y: [foco.y - my, foco.y + my] });
    // solo cuando cambia la persona, no cuando el usuario mueve el mapa
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focoId]);

  // atajos de teclado: con el puntero sobre el mapa o con el mapa enfocado
  useEffect(() => {
    const f = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || esEditable(e.target)) return;
      const enfocado = contenedor.current?.contains(document.activeElement) ?? false;
      if (!encima.current && !enfocado) return;
      const rapido = e.shiftKey ? 3 : 1;
      const acciones: Record<string, () => void> = {
        "+": () => zoom(1 / PASO_ZOOM),
        "=": () => zoom(1 / PASO_ZOOM),
        "-": () => zoom(PASO_ZOOM),
        _: () => zoom(PASO_ZOOM),
        "0": verTodo,
        ArrowLeft: () => mover(-PASO_MOVER * rapido, 0),
        ArrowRight: () => mover(PASO_MOVER * rapido, 0),
        ArrowUp: () => mover(0, PASO_MOVER * rapido),
        ArrowDown: () => mover(0, -PASO_MOVER * rapido),
        f: () => enfoque && encuadrar(enfoque.xs, enfoque.ys),
        F: () => enfoque && encuadrar(enfoque.xs, enfoque.ys),
        z: () => setModoArea((m) => !m),
        Z: () => setModoArea((m) => !m),
        "?": () => setAyuda((x) => !x),
      };
      const accion = acciones[e.key];
      if (!accion) return;
      e.preventDefault();
      accion();
    };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  });

  // rueda: sin Ctrl se deja pasar al panel (que se desplace) y se avisa cómo hacer zoom
  useEffect(() => {
    const el = contenedor.current;
    if (!el || !ruedaConCtrl) return;
    let t: ReturnType<typeof setTimeout> | undefined;
    const f = (e: WheelEvent) => {
      if (e.ctrlKey || e.metaKey) return;
      e.stopPropagation();
      setAviso(true);
      clearTimeout(t);
      t = setTimeout(() => setAviso(false), 1400);
    };
    el.addEventListener("wheel", f, { capture: true });
    return () => {
      el.removeEventListener("wheel", f, { capture: true });
      clearTimeout(t);
    };
  }, [ruedaConCtrl]);

  // solo cambia cuando cambia algo del dibujo (ver CONFIG)
  const layout = useMemo<Partial<Plotly.Layout>>(
    () => ({
      autosize: true,
      height: alto,
      margin: { l: 4, r: 4, t: 4, b: 4 },
      xaxis: { visible: false, ...(v ? { range: v.x, autorange: false } : { autorange: true }) },
      yaxis: { visible: false, ...(v ? { range: v.y, autorange: false } : { autorange: true }) },
      annotations,
      hovermode: "closest",
      hoverdistance: 8,
      hoverlabel: { bgcolor: "#fff", bordercolor: "#cbd5e1", font: { size: 12, color: "#0f172a" }, align: "left" },
      plot_bgcolor: "#fff",
      paper_bgcolor: "#fff",
      dragmode: modoArea ? "zoom" : "pan",
    }),
    [alto, v, annotations, modoArea],
  );

  const nivel = v && completa.current ? (completa.current.x[1] - completa.current.x[0]) / (v.x[1] - v.x[0]) : 1;
  const boton =
    "w-7 h-7 grid place-items-center rounded text-slate-700 hover:bg-slate-100 disabled:opacity-30 disabled:hover:bg-transparent";

  return (
    <div
      ref={contenedor}
      tabIndex={0}
      aria-label="Mapa: usa la rueda del mouse o + y − para acercar, flechas para moverte, 0 para ver todo"
      className="relative outline-none focus-visible:ring-2 focus-visible:ring-espol-blue/40 rounded"
      onMouseEnter={() => {
        encima.current = true;
      }}
      onMouseLeave={() => {
        encima.current = false;
      }}
      onPointerDownCapture={() => contenedor.current?.focus({ preventScroll: true })}
    >
      <Plot
        data={data}
        layout={layout}
        config={CONFIG}
        style={{ width: "100%" }}
        useResizeHandler
        onInitialized={alActualizar}
        onUpdate={alActualizar}
        onRelayout={(e) => {
          const r = e as Record<string, unknown>;
          if (r["xaxis.autorange"] || r["yaxis.autorange"]) {
            setVista(null);
            return;
          }
          const x0 = r["xaxis.range[0]"] ?? (r["xaxis.range"] as Rango | undefined)?.[0];
          const y0 = r["yaxis.range[0]"] ?? (r["yaxis.range"] as Rango | undefined)?.[0];
          if (typeof x0 !== "number" && typeof y0 !== "number") return;
          // tras arrastrar o usar la rueda: guardar la vista que dejó Plotly
          const a = actual();
          if (a) setVista(a);
        }}
        onClick={onClick}
        onClickAnnotation={onClickAnnotation}
      />

      {/* barra de navegación */}
      <div className="absolute top-2 right-2 flex flex-col items-end gap-1.5">
        <div className="flex flex-col bg-white/95 border rounded-md shadow-sm p-0.5" role="toolbar" aria-label="Navegar el mapa">
          <button className={boton} onClick={() => zoom(1 / PASO_ZOOM)} title="Acercar (+)" aria-label="Acercar">
            <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M8 3v10M3 8h10" strokeLinecap="round" />
            </svg>
          </button>
          <button className={boton} onClick={() => zoom(PASO_ZOOM)} title="Alejar (−)" aria-label="Alejar">
            <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M3 8h10" strokeLinecap="round" />
            </svg>
          </button>
          <button className={boton} onClick={verTodo} disabled={v === null} title="Ver todo (0 o doble clic)" aria-label="Ver todo">
            <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
              <path d="M2 6V2h4M10 2h4v4M14 10v4h-4M6 14H2v-4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <span className="h-px bg-slate-200 mx-1 my-0.5" />
          <button
            className={`${boton} ${modoArea ? "bg-slate-100 text-espol-navy ring-1 ring-espol-blue/50" : ""}`}
            onClick={() => setModoArea((m) => !m)}
            aria-pressed={modoArea}
            title={modoArea ? "Zoom por área activo: arrastra un rectángulo (Z para volver a mover)" : "Zoom por área (Z)"}
            aria-label="Zoom por área"
          >
            <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
              <rect x="2" y="2" width="9" height="9" strokeDasharray="2 1.6" />
              <path d="M10 10l4 4" strokeLinecap="round" />
            </svg>
          </button>
          {enfoque && (
            <button
              className={boton}
              onClick={() => encuadrar(enfoque.xs, enfoque.ys)}
              title={`Encuadrar ${enfoque.nombre} (F)`}
              aria-label={`Encuadrar ${enfoque.nombre}`}
            >
              <svg viewBox="0 0 16 16" className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
                <circle cx="8" cy="8" r="2.2" />
                <path d="M8 1.5v2.5M8 12v2.5M1.5 8H4M12 8h2.5" strokeLinecap="round" />
              </svg>
            </button>
          )}
          <button
            className={`${boton} text-xs font-semibold`}
            onClick={() => setAyuda((x) => !x)}
            aria-expanded={ayuda}
            title="Cómo navegar el mapa (?)"
            aria-label="Cómo navegar el mapa"
          >
            ?
          </button>
        </div>
        {nivel > 1.05 && (
          <span className="text-[10px] tabular-nums text-slate-500 bg-white/90 border rounded px-1.5 py-0.5" title="Ampliación respecto a la vista completa">
            ×{nivel.toLocaleString("es", { maximumFractionDigits: 1 })}
          </span>
        )}
      </div>

      {ayuda && (
        <div className="absolute top-2 right-12 w-72 bg-white border rounded-md shadow-lg p-3 text-xs z-10">
          <div className="flex items-center mb-1.5">
            <p className="font-semibold text-slate-700 flex-1">Cómo navegar el mapa</p>
            <button onClick={() => setAyuda(false)} className="text-slate-400 hover:text-slate-700" aria-label="Cerrar ayuda">
              ×
            </button>
          </div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {ATAJOS.map(([k, t]) => (
              <div key={k} className="contents">
                <dt className="text-slate-800 font-medium whitespace-nowrap">
                  {ruedaConCtrl && k.startsWith("Rueda") ? "Ctrl + rueda / pellizco" : k}
                </dt>
                <dd className="text-slate-500">{t}</dd>
              </div>
            ))}
          </dl>
          <p className="text-[11px] text-slate-400 mt-2">Los atajos funcionan con el puntero sobre el mapa.</p>
        </div>
      )}

      {aviso && (
        <div className="absolute inset-0 grid place-items-center pointer-events-none bg-slate-900/10 rounded transition-opacity">
          <p className="bg-slate-900/80 text-white text-sm rounded-md px-3 py-2">
            Usa <kbd className="font-semibold">Ctrl</kbd> + rueda para acercar o alejar el mapa
          </p>
        </div>
      )}
    </div>
  );
}
