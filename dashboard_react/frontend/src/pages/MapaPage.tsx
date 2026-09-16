import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import { getMapa, getResumen } from "../api/client";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";
import { colorPorTexto } from "../lib/color";

const TIPOS = ["Todos", "Solo Administrativo", "Solo Docente", "Solo Mixto"];

type Modo = "rama" | "cargo" | "cargo_real";

const MODOS: { value: Modo; label: string }[] = [
  { value: "rama", label: "Rama" },
  { value: "cargo", label: "Categoría (13 grupos)" },
  { value: "cargo_real", label: "Cargo real (todos)" },
];

// Sin acentos y en minúsculas, para que "tecnico" encuentre "TÉCNICO" — la búsqueda de
// cargo real no debe ser sensible a tildes.
function normalizar(texto: string): string {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

export default function MapaPage() {
  const [tipoFiltro, setTipoFiltro] = useState("Todos");
  const [perfilesFiltro, setPerfilesFiltro] = useState<number[]>([]);
  const [modo, setModo] = useState<Modo>("rama");
  const [terminosCargo, setTerminosCargo] = useState<string[]>([]);
  const [terminoCargoActual, setTerminoCargoActual] = useState("");
  const [idSel, setIdSel] = useState<number | null>(null);
  const [nombreBuscado, setNombreBuscado] = useState("");
  const [idResaltado, setIdResaltado] = useState<number | null>(null);
  const [nombreResaltado, setNombreResaltado] = useState("");

  const resumenQuery = useQuery({ queryKey: ["resumen"], queryFn: getResumen });
  const mapaQuery = useQuery({
    queryKey: ["mapa", tipoFiltro, perfilesFiltro, modo],
    queryFn: () => getMapa(tipoFiltro, perfilesFiltro, modo),
  });

  const perfiles = resumenQuery.data?.perfiles ?? [];

  const puntoResaltado = useMemo(() => {
    if (idResaltado === null || !mapaQuery.data) return null;
    return mapaQuery.data.puntos.find((p) => p.IDPERSONA === idResaltado) ?? null;
  }, [idResaltado, mapaQuery.data]);

  const hayBusquedaCargo = modo === "cargo_real" && terminosCargo.length > 0;

  // Lista de cargos reales que existen en los datos, para el desplegable de sugerencias
  // (evita adivinar a ciegas qué tipos de "técnico" existen, por ejemplo) — y el color que
  // el backend ya calculó para cada uno (color_por_texto), reutilizado tal cual en los
  // chips para que el color del chip sea idéntico al color de esos puntos en el mapa.
  const { cargosDisponibles, colorPorCargo } = useMemo(() => {
    if (!mapaQuery.data || modo !== "cargo_real") return { cargosDisponibles: [] as string[], colorPorCargo: new Map<string, string>() };
    const set = new Set<string>();
    const colores = new Map<string, string>();
    for (const p of mapaQuery.data.puntos) {
      if (p.GRUPO_COLOR !== "MIXTO") {
        set.add(p.GRUPO_COLOR);
        colores.set(p.GRUPO_COLOR, p.COLOR);
      }
    }
    return { cargosDisponibles: Array.from(set).sort(), colorPorCargo: colores };
  }, [mapaQuery.data, modo]);

  const sugerenciasCargo = useMemo(() => {
    const q = normalizar(terminoCargoActual.trim());
    if (!q) return [];
    // Sin límite de cantidad — la lista ya tiene scroll interno (max-h-56 overflow-y-auto
    // en el <ul>), así que una búsqueda genérica ("profesor") simplemente se desplaza en
    // vez de ocultar coincidencias reales.
    return cargosDisponibles.filter((c) => normalizar(c).includes(q));
  }, [cargosDisponibles, terminoCargoActual]);

  const sugerenciasNombre = useMemo(() => {
    const q = normalizar(nombreBuscado.trim());
    if (!q || !mapaQuery.data) return [];
    const vistos = new Set<number>();
    const resultado: { idPersona: number; nombre: string }[] = [];
    for (const p of mapaQuery.data.puntos) {
      if (vistos.has(p.IDPERSONA) || !normalizar(p.NOMBRE_COMPLETO).includes(q)) continue;
      vistos.add(p.IDPERSONA);
      resultado.push({ idPersona: p.IDPERSONA, nombre: p.NOMBRE_COMPLETO });
    }
    return resultado.slice(0, 20);
  }, [mapaQuery.data, nombreBuscado]);

  // Combinaciones "Mixto (A + B)" reales: para cada par de cargos seleccionados, busca si
  // existe al menos una persona Mixto cuyos cargos concurrentes sean EXACTAMENTE esos dos
  // (usando CARGOS_ACTUALES_MIXTO, "cargo1; cargo2") — si no existe nadie con esa
  // combinación exacta, no se genera ninguna etiqueta (pedido explícito del usuario).
  const combinacionesMixtoDetectadas = useMemo(() => {
    if (!mapaQuery.data || terminosCargo.length < 2) return [];
    const mixtos = mapaQuery.data.puntos.filter((p) => p.ES_MIXTO && p.CARGOS_ACTUALES_MIXTO);
    const combinaciones: { cargos: [string, string]; label: string; color: string }[] = [];
    for (let i = 0; i < terminosCargo.length; i++) {
      for (let j = i + 1; j < terminosCargo.length; j++) {
        const [a, b] = [terminosCargo[i], terminosCargo[j]];
        const existe = mixtos.some((p) => {
          const cargosPersona = (p.CARGOS_ACTUALES_MIXTO ?? "").split(";").map((c) => c.trim());
          return cargosPersona.includes(a) && cargosPersona.includes(b);
        });
        if (existe) {
          const label = `Mixto (${a} + ${b})`;
          combinaciones.push({ cargos: [a, b], label, color: colorPorTexto(label) });
        }
      }
    }
    return combinaciones;
  }, [mapaQuery.data, terminosCargo]);

  // Solo se puede agregar un cargo eligiéndolo del desplegable de sugerencias (clic ->
  // se agrega al instante) — no existe una vía de texto libre, para no dejar "buscar" algo
  // que no corresponda a ningún cargo real de los datos.
  function agregarTerminoCargo(texto: string) {
    setTerminosCargo((prev) => (prev.includes(texto) ? prev : [...prev, texto]));
    setTerminoCargoActual("");
  }

  function quitarTerminoCargo(texto: string) {
    setTerminosCargo((prev) => prev.filter((x) => x !== texto));
  }

  const traces = useMemo(() => {
    if (!mapaQuery.data) return [];

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let base: any[];

    if (hayBusquedaCargo) {
      // Con búsqueda activa en modo Cargo real, el agrupamiento no es por GRUPO_COLOR del
      // backend (que pondría a todo Mixto bajo un único "MIXTO" violeta genérico) — cada
      // combinación real detectada (combinacionesMixtoDetectadas) tiene su propia
      // etiqueta/color, cada término suelto (cargo puro, sin combinación) usa el color que
      // el backend ya le asignó, y el resto queda atenuado en un solo grupo.
      const grupos = new Map<string, { pts: typeof mapaQuery.data.puntos; color: string }>();
      const resto: typeof mapaQuery.data.puntos = [];

      for (const p of mapaQuery.data.puntos) {
        // cargosPersona: TODOS los cargos reales de la persona (2 si es Mixto, 1 si no) -
        // así un Mixto que solo tenga UNO de sus cargos entre los términos buscados ya se
        // colorea con el color de ese cargo puro, en vez de quedar atenuado hasta que se
        // busquen ambos a la vez (caso reportado: 3519 no se marcaba buscando solo
        // "PROFESOR TITULAR AUXILIAR 2 (TP)", solo aparecía al agregar el segundo término
        // — debía cambiar de color, no aparecer recién ahí).
        const cargosPersona = p.ES_MIXTO ? (p.CARGOS_ACTUALES_MIXTO ?? "").split(";").map((c) => c.trim()) : [p.CARGO_ACTUAL ?? ""];
        const combinacion = combinacionesMixtoDetectadas.find((c) => c.cargos.every((cg) => cargosPersona.includes(cg)));
        const cargoCoincidente = terminosCargo.find((t) => cargosPersona.includes(t));
        if (combinacion) {
          if (!grupos.has(combinacion.label)) grupos.set(combinacion.label, { pts: [], color: combinacion.color });
          grupos.get(combinacion.label)!.pts.push(p);
        } else if (cargoCoincidente) {
          const color = colorPorCargo.get(cargoCoincidente) ?? p.COLOR;
          if (!grupos.has(cargoCoincidente)) grupos.set(cargoCoincidente, { pts: [], color });
          grupos.get(cargoCoincidente)!.pts.push(p);
        } else {
          resto.push(p);
        }
      }

      base = Array.from(grupos.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([nombre, { pts, color }]) => ({
          type: "scattergl" as const,
          mode: "markers" as const,
          name: nombre,
          x: pts.map((p) => p.PC1),
          y: pts.map((p) => p.PC2),
          marker: { color, size: 6, opacity: idResaltado !== null ? 0.25 : 0.9, line: { width: 0 } },
          customdata: pts.map((p) => [
            p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC,
            p.VIGENTE_MOSTRAR ? "Si" : "No", p.CARGOS_ACTUALES_MIXTO ?? "", p.NOMBRE_COMPLETO,
          ]),
          hovertemplate:
            "%{customdata[5]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}" +
            (nombre.startsWith("Mixto") ? "<br>Cargos concurrentes: %{customdata[4]}" : "") +
            "<extra></extra>",
        }));

      if (resto.length > 0) {
        base.push({
          type: "scattergl" as const,
          mode: "markers" as const,
          name: "Otros",
          x: resto.map((p) => p.PC1),
          y: resto.map((p) => p.PC2),
          marker: { color: "#94A3B8", size: 6, opacity: idResaltado !== null ? 0.1 : 0.12, line: { width: 0 } },
          customdata: resto.map((p) => [p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC, p.VIGENTE_MOSTRAR ? "Si" : "No", "", p.NOMBRE_COMPLETO]),
          hovertemplate: "%{customdata[5]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
        });
      }
    } else {
      const porGrupo = new Map<string, typeof mapaQuery.data.puntos>();
      for (const p of mapaQuery.data.puntos) {
        if (!porGrupo.has(p.GRUPO_COLOR)) porGrupo.set(p.GRUPO_COLOR, []);
        porGrupo.get(p.GRUPO_COLOR)!.push(p);
      }
      base = Array.from(porGrupo.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([grupo, pts]) => {
          const esMixto = grupo === "MIXTO";
          const nombre = esMixto ? "Mixto" : modo === "rama" ? grupo : modo === "cargo_real" ? grupo : pts[0].PERFIL_NOMBRE;
          return {
            type: "scattergl" as const,
            mode: "markers" as const,
            name: nombre,
            x: pts.map((p) => p.PC1),
            y: pts.map((p) => p.PC2),
            marker: { color: pts[0].COLOR, size: 6, opacity: idResaltado === null ? 0.7 : 0.25, line: { width: 0 } },
            customdata: pts.map((p) => [
              p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC,
              p.VIGENTE_MOSTRAR ? "Si" : "No", p.CARGOS_ACTUALES_MIXTO ?? "", p.NOMBRE_COMPLETO,
            ]),
            hovertemplate:
              "%{customdata[5]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}" +
              (esMixto ? "<br>Cargos concurrentes: %{customdata[4]}" : "") +
              "<extra></extra>",
          };
        });
    }

    if (puntoResaltado) {
      base.push({
        type: "scattergl" as const,
        mode: "markers" as const,
        name: puntoResaltado.NOMBRE_COMPLETO,
        x: [puntoResaltado.PC1],
        y: [puntoResaltado.PC2],
        marker: {
          color: "#E63946",
          size: 16,
          opacity: 1,
          line: { width: 2, color: "#FFFFFF" },
        },
        customdata: [[
          puntoResaltado.IDPERSONA, puntoResaltado.CARGO_ACTUAL ?? "-", puntoResaltado.TIPOEMPLEADO_ACTUAL_DESC,
          puntoResaltado.VIGENTE_MOSTRAR ? "Si" : "No", puntoResaltado.CARGOS_ACTUALES_MIXTO ?? "", puntoResaltado.NOMBRE_COMPLETO,
        ]],
        hovertemplate:
          "%{customdata[5]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}" +
          (puntoResaltado.ES_MIXTO ? "<br>Cargos concurrentes: %{customdata[4]}" : "") +
          "<extra></extra>",
      });
    }

    return base;
  }, [mapaQuery.data, puntoResaltado, idResaltado, modo, hayBusquedaCargo, terminosCargo, combinacionesMixtoDetectadas, colorPorCargo]);

  function togglePerfil(c: number) {
    setPerfilesFiltro((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  // perfilesFiltro es un filtro exclusivo del modo "Categoría" (los 13 botones) — si queda
  // seleccionado al cambiar a otro modo, se sigue enviando al backend y excluye
  // silenciosamente personas del mapa/sugerencias en el modo nuevo sin que se vea ningún
  // control activo en pantalla (bug real: "RECTOR(A)" no aparecía en las sugerencias de
  // Cargo real porque un filtro de categoría de una sesión anterior en modo Categoría
  // seguía aplicado). Cambiar de modo limpia ese filtro.
  function cambiarModo(m: Modo) {
    setModo(m);
    setPerfilesFiltro([]);
  }

  function resaltarPersona(idPersona: number, nombre: string) {
    setIdResaltado(idPersona);
    setNombreResaltado(nombre);
    setNombreBuscado("");
  }

  function limpiarResaltado() {
    setNombreBuscado("");
    setIdResaltado(null);
    setNombreResaltado("");
  }

  const hayFiltrosActivos =
    tipoFiltro !== "Todos" || perfilesFiltro.length > 0 || idResaltado !== null || terminosCargo.length > 0;

  function limpiarTodosLosFiltros() {
    setTipoFiltro("Todos");
    setPerfilesFiltro([]);
    setTerminosCargo([]);
    setTerminoCargoActual("");
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

        {/* "Ver por" es el control principal: decide qué otros controles aparecen debajo. */}
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Ver el mapa coloreado por
          </p>
          <div className="flex gap-2">
            {MODOS.map((m) => (
              <button
                key={m.value}
                onClick={() => cambiarModo(m.value)}
                className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
                  modo === m.value
                    ? "bg-espol-blue text-white border-espol-blue"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-1">
            {modo === "rama" && "Administrativo / Docente / Mixto (3 colores)."}
            {modo === "cargo" && "Las 13 categorías de cargo agrupadas + Mixto (14 colores)."}
            {modo === "cargo_real" && "Cada cargo real tiene su propio color (238 cargos distintos). Usa el buscador para ubicar uno."}
          </p>
        </div>

        {/* Solo en modo Rama: filtro de tipo de empleado. */}
        {modo === "rama" && (
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
        )}

        {/* Solo en modo Categoría: los 13 botones de cluster + indicador de Mixto. */}
        {modo === "cargo" && (
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
              <span
                className="px-2.5 py-1 text-xs rounded-md text-white"
                style={{ backgroundColor: "#7B2CBF" }}
                title="Personas con 2+ cargos estructurales vigentes en paralelo — siempre visibles con este color, incluso al filtrar por uno de sus cargos"
              >
                Mixto
              </span>
            </div>
          </div>
        )}

        {/* Solo en modo Cargo real: buscador con autocompletado (no hay botones, son
            demasiados cargos) — el desplegable evita tener que adivinar el texto exacto
            (ej. qué tipos de "técnico" existen). */}
        {modo === "cargo_real" && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
              Buscar cargos (resalta los puntos que coincidan; puedes agregar varios)
            </p>
            <div className="relative max-w-sm">
              <input
                type="text"
                value={terminoCargoActual}
                onChange={(e) => setTerminoCargoActual(e.target.value)}
                placeholder="Ej. rector, decano, técnico..."
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
              />
              {sugerenciasCargo.length > 0 && (
                <ul className="absolute z-10 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
                  {sugerenciasCargo.map((c) => (
                    <li key={c}>
                      <button
                        onClick={() => agregarTerminoCargo(c)}
                        className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-espol-blue hover:text-white transition-colors"
                      >
                        {c}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Escribe para ver sugerencias y haz clic en una para agregarla — solo se pueden
              agregar cargos que existen exactamente en los datos. No hay leyenda en este modo
              (238 cargos no caben en una lista) — pasa el mouse sobre un punto para ver su
              cargo exacto.
            </p>
            {terminosCargo.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {terminosCargo.map((t) => (
                  <button
                    key={t}
                    onClick={() => quitarTerminoCargo(t)}
                    className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors"
                    title="Quitar este término"
                  >
                    <span
                      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
                      style={{ backgroundColor: colorPorCargo.get(t) ?? "#94A3B8" }}
                    />
                    {t} ✕
                  </button>
                ))}
              </div>
            )}
            {combinacionesMixtoDetectadas.length > 0 && (
              <div className="mt-2">
                <p className="text-xs text-slate-500 mb-1">
                  Combinaciones Mixto detectadas (existe al menos una persona con ambos cargos):
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {combinacionesMixtoDetectadas.map((c) => (
                    <span
                      key={c.label}
                      className="flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md text-white"
                      style={{ backgroundColor: c.color }}
                    >
                      {c.label}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="border-t border-slate-100 pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Ubicar una persona en el mapa
          </p>
          <div className="flex items-center gap-2">
            <div className="relative w-64">
              <input
                type="text"
                value={nombreBuscado}
                onChange={(e) => setNombreBuscado(e.target.value)}
                placeholder="Escribe un nombre..."
                className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-espol-blue"
              />
              {sugerenciasNombre.length > 0 && (
                <ul className="absolute z-10 left-0 right-0 mt-1 max-h-56 overflow-y-auto rounded-md border border-slate-200 bg-white shadow-lg">
                  {sugerenciasNombre.map((s) => (
                    <li key={s.idPersona}>
                      <button
                        onClick={() => resaltarPersona(s.idPersona, s.nombre)}
                        className="w-full text-left px-3 py-1.5 text-xs text-slate-700 hover:bg-espol-blue hover:text-white transition-colors"
                      >
                        {s.nombre}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            {idResaltado !== null && (
              <button
                onClick={limpiarResaltado}
                className="px-3 py-1.5 text-sm rounded-md border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
              >
                Quitar marca
              </button>
            )}
          </div>
          {idResaltado !== null && (
            <p className="text-xs text-slate-500 mt-1.5">
              {nombreResaltado} resaltada en rojo — el resto de puntos se mantiene visible.
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
                // Plotly no soporta scroll en su leyenda: con 238 cargos distintos se
                // corta y solo se ven los primeros, dando la falsa impresion de que
                // faltan cargos en el mapa. Se oculta en este modo; identificar un cargo
                // se hace con el buscador de texto (resalta puntos) o el hover (el
                // tooltip siempre muestra el cargo real exacto de cada punto).
                showlegend: modo !== "cargo_real",
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
