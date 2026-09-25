import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import Plot from "react-plotly.js";
import {
  getMapa, getMapaK5, getMapaPorRama, getMapaSemantico,
  getResumen, getResumenK5, getResumenPorRama, getResumenSemantico,
} from "../api/client";
import type { Rama } from "../api/types";
import { LoadingBlock, ErrorBlock } from "../components/LoadingBlock";
import PersonaFicha from "../components/PersonaFicha";
import { colorPorTexto } from "../lib/color";
import { normalizar, coincideNombre } from "../lib/busqueda";

const TIPOS = ["Todos", "Solo Administrativo", "Solo Docente", "Solo Mixto"];

type Modo = "rama" | "k5" | "cargo" | "cargo_real";
type Pestana = "estatico" | "semantico";

const PESTANAS: { value: Pestana; label: string }[] = [
  { value: "estatico", label: "Clustering estructurado" },
  { value: "semantico", label: "Clustering en embeddings" },
];

const MODOS: { value: Modo; label: string }[] = [
  { value: "rama", label: "Tipo Cargo" },
  { value: "k5", label: "Cluster estructurado" },
  { value: "cargo", label: "Cargos agrupados" },
  { value: "cargo_real", label: "Todos los cargos" },
];

// Leyenda propia en HTML (no la leyenda nativa de Plotly) debajo del mapa: Plotly con
// orientation:"h" NO hace wrap real a varias filas cuando hay muchas entradas (13-14
// categorías, 9 clusters semánticos) — todo se aprieta en una sola fila y las etiquetas
// terminan superpuestas. Con flex-wrap de CSS cada chip pasa a la siguiente fila
// naturalmente, y el nombre se trunca con elipsis via CSS (no via entrywidth de Plotly,
// que solo trunca el texto pero no evita el solape entre chips). Pedido explícito del
// usuario: nombre real completo (accesible via title on hover), nunca "Cluster N".
function LeyendaMapa({ items }: { items: { nombre: string; color: string }[] }) {
  if (items.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1.5 mt-3 pt-3 border-t border-slate-100">
      {items.map((it) => (
        <div key={it.nombre} className="flex items-center gap-1.5 max-w-[180px]" title={it.nombre}>
          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: it.color }} />
          <span className="text-xs text-slate-600 truncate">{it.nombre}</span>
        </div>
      ))}
    </div>
  );
}

export default function MapaPage() {
  const [pestana, setPestana] = useState<Pestana>("estatico");
  const [perfilesSeparados, setPerfilesSeparados] = useState(false);

  return (
    <div className="space-y-4">
      <div className="flex gap-1 border-b border-slate-200">
        {PESTANAS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPestana(p.value)}
            className={`px-4 py-2.5 text-sm font-medium rounded-t-md border-b-2 -mb-px transition-colors ${
              pestana === p.value
                ? "bg-white text-espol-navy border-espol-blue"
                : "text-slate-500 border-transparent hover:text-espol-navy hover:bg-slate-50"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div className="bg-espol-blue/5 rounded-xl border border-espol-blue/20 p-4 flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-espol-navy">Perfiles separados por tipo de empleado</p>
          <p className="text-xs text-slate-500 mt-0.5">
            El clustering normal agrupa Administrativo y Docente juntos antes de buscar perfiles, así
            que en la práctica el rasgo que más pesa es esa misma división. Activa esto para ver un
            clustering nuevo, calculado por separado dentro de cada rama (su propio número de grupos y
            su propio mapa), y así encontrar matices que quedan ocultos al mezclarlas.
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
        <MapaPorRama tipoClustering={pestana === "estatico" ? "estructurado" : "semantico"} />
      ) : pestana === "estatico" ? (
        <MapaEstatico />
      ) : (
        <MapaSemantico />
      )}
    </div>
  );
}

function MapaPorRama({ tipoClustering }: { tipoClustering: "estructurado" | "semantico" }) {
  const [rama, setRama] = useState<Rama>("ADMINISTRATIVO");
  const [perfilesFiltro, setPerfilesFiltro] = useState<number[]>([]);
  const [idSel, setIdSel] = useState<number | null>(null);
  const [nombreBuscado, setNombreBuscado] = useState("");
  const [idResaltado, setIdResaltado] = useState<number | null>(null);
  const [nombreResaltado, setNombreResaltado] = useState("");

  const resumenQuery = useQuery({
    queryKey: ["resumen_por_rama", tipoClustering, rama],
    queryFn: () => getResumenPorRama(tipoClustering, rama),
  });
  const mapaQuery = useQuery({
    queryKey: ["mapa_por_rama", tipoClustering, rama, perfilesFiltro],
    queryFn: () => getMapaPorRama(tipoClustering, rama, perfilesFiltro),
  });

  const perfiles = resumenQuery.data?.perfiles ?? [];

  const puntoResaltado = useMemo(() => {
    if (idResaltado === null) return null;
    return mapaQuery.data?.puntos.find((p) => p.IDPERSONA === idResaltado) ?? null;
  }, [idResaltado, mapaQuery.data]);

  const sugerenciasNombre = useMemo(() => {
    if (!nombreBuscado.trim() || !mapaQuery.data) return [];
    const vistos = new Set<number>();
    const resultado: { idPersona: number; nombre: string }[] = [];
    for (const p of mapaQuery.data.puntos) {
      if (vistos.has(p.IDPERSONA) || !coincideNombre(p.NOMBRE_COMPLETO, nombreBuscado)) continue;
      vistos.add(p.IDPERSONA);
      resultado.push({ idPersona: p.IDPERSONA, nombre: p.NOMBRE_COMPLETO });
    }
    return resultado.slice(0, 20);
  }, [mapaQuery.data, nombreBuscado]);

  function togglePerfil(c: number) {
    setPerfilesFiltro((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  function cambiarRama(r: Rama) {
    setRama(r);
    setPerfilesFiltro([]);
    limpiarResaltado();
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

  const traces = useMemo(() => {
    if (!mapaQuery.data) return [];
    const porGrupo = new Map<string, typeof mapaQuery.data.puntos>();
    for (const p of mapaQuery.data.puntos) {
      if (!porGrupo.has(p.GRUPO_COLOR)) porGrupo.set(p.GRUPO_COLOR, []);
      porGrupo.get(p.GRUPO_COLOR)!.push(p);
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const base: any[] = Array.from(porGrupo.entries())
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([, pts]) => ({
        type: "scattergl" as const,
        mode: "markers" as const,
        name: pts[0].PERFIL_NOMBRE ?? `Cluster ${pts[0].CLUSTER_RAMA}`,
        x: pts.map((p) => p.PC1),
        y: pts.map((p) => p.PC2),
        marker: { color: pts[0].COLOR, size: 6, opacity: idResaltado === null ? 0.7 : 0.25, line: { width: 0 } },
        customdata: pts.map((p) => [p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.VIGENTE_MOSTRAR ? "Si" : "No", p.NOMBRE_COMPLETO]),
        hovertemplate: "%{customdata[3]}<br>%{customdata[1]}<br>Vigente: %{customdata[2]}<extra></extra>",
      }));
    if (puntoResaltado) {
      base.push({
        type: "scattergl" as const,
        mode: "markers" as const,
        name: puntoResaltado.NOMBRE_COMPLETO,
        x: [puntoResaltado.PC1],
        y: [puntoResaltado.PC2],
        marker: { color: "#E63946", size: 16, opacity: 1, line: { width: 2, color: "#FFFFFF" } },
        customdata: [[puntoResaltado.IDPERSONA, puntoResaltado.CARGO_ACTUAL ?? "-", puntoResaltado.VIGENTE_MOSTRAR ? "Si" : "No", puntoResaltado.NOMBRE_COMPLETO]],
        hovertemplate: "%{customdata[3]}<br>%{customdata[1]}<br>Vigente: %{customdata[2]}<extra></extra>",
      });
    }
    return base;
  }, [mapaQuery.data, puntoResaltado, idResaltado]);

  const leyendaItems = useMemo(() => {
    const relevantes = puntoResaltado ? traces.slice(0, -1) : traces;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return relevantes.map((t: any) => ({ nombre: t.name as string, color: t.marker.color as string }));
  }, [traces, puntoResaltado]);

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-4">
        <p className="text-xs text-slate-400">
          Clustering calculado por separado dentro de cada rama, en el mismo espacio (
          {tipoClustering === "estructurado" ? "variables estructuradas" : "embeddings de texto"}) que
          su versión combinada, pero sin mezclar Administrativo con Docente. Los IDs de cluster y el
          mapa PCA aquí no son comparables entre ramas ni con la vista combinada.
        </p>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">Rama</p>
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
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Perfiles a mostrar (opcional)
          </p>
          <div className="flex flex-wrap gap-1.5">
            {perfiles.map((p) => (
              <button
                key={p.CLUSTER_RAMA}
                onClick={() => togglePerfil(p.CLUSTER_RAMA)}
                title={p.DESCRIPCION}
                className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                  perfilesFiltro.includes(p.CLUSTER_RAMA)
                    ? "text-white border-transparent"
                    : "border-slate-300 text-slate-600 hover:bg-slate-50"
                }`}
                style={perfilesFiltro.includes(p.CLUSTER_RAMA) ? { backgroundColor: p.COLOR } : undefined}
              >
                {p.PERFIL_NOMBRE}
              </button>
            ))}
          </div>
        </div>

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
                height: 640,
                showlegend: false,
                margin: { l: 50, r: 20, t: 20, b: 50 },
                font: { size: 12, color: "#334155" },
                plot_bgcolor: "#FFFFFF",
                paper_bgcolor: "#FFFFFF",
                xaxis: { title: { text: "PC1" }, showgrid: true, gridcolor: "#EEF1F5", zeroline: false, showline: true, linecolor: "#CBD5E1" },
                yaxis: { title: { text: "PC2" }, showgrid: true, gridcolor: "#EEF1F5", zeroline: false, showline: true, linecolor: "#CBD5E1" },
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
            <LeyendaMapa items={leyendaItems} />
            <p className="text-xs text-slate-500 mt-1">
              {mapaQuery.data.n_mostrados.toLocaleString()} personas de la rama{" "}
              {rama === "ADMINISTRATIVO" ? "Administrativo" : "Docente"} mostradas de{" "}
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

function MapaEstatico() {
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
  const resumenK5Query = useQuery({ queryKey: ["resumen_k5"], queryFn: getResumenK5, enabled: modo === "k5" });
  const mapaQuery = useQuery({
    queryKey: ["mapa", tipoFiltro, perfilesFiltro, modo],
    queryFn: () => getMapa(tipoFiltro, perfilesFiltro, modo === "k5" ? "rama" : modo),
    enabled: modo !== "k5",
  });
  const mapaK5Query = useQuery({
    queryKey: ["mapa_k5", perfilesFiltro],
    queryFn: () => getMapaK5(perfilesFiltro),
    enabled: modo === "k5",
  });

  const perfiles = resumenQuery.data?.perfiles ?? [];
  const perfilesK5 = resumenK5Query.data?.perfiles ?? [];

  const puntoResaltado = useMemo(() => {
    if (idResaltado === null) return null;
    if (modo === "k5") return mapaK5Query.data?.puntos.find((p) => p.IDPERSONA === idResaltado) ?? null;
    return mapaQuery.data?.puntos.find((p) => p.IDPERSONA === idResaltado) ?? null;
  }, [idResaltado, mapaQuery.data, mapaK5Query.data, modo]);

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
    const puntosFuente = modo === "k5" ? mapaK5Query.data?.puntos : mapaQuery.data?.puntos;
    if (!nombreBuscado.trim() || !puntosFuente) return [];
    const vistos = new Set<number>();
    const resultado: { idPersona: number; nombre: string }[] = [];
    for (const p of puntosFuente) {
      if (vistos.has(p.IDPERSONA) || !coincideNombre(p.NOMBRE_COMPLETO, nombreBuscado)) continue;
      vistos.add(p.IDPERSONA);
      resultado.push({ idPersona: p.IDPERSONA, nombre: p.NOMBRE_COMPLETO });
    }
    return resultado.slice(0, 20);
  }, [mapaQuery.data, mapaK5Query.data, modo, nombreBuscado]);

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
    if (modo === "k5") {
      if (!mapaK5Query.data) return [];
      const porGrupo = new Map<string, typeof mapaK5Query.data.puntos>();
      for (const p of mapaK5Query.data.puntos) {
        if (!porGrupo.has(p.GRUPO_COLOR)) porGrupo.set(p.GRUPO_COLOR, []);
        porGrupo.get(p.GRUPO_COLOR)!.push(p);
      }
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const baseK5: any[] = Array.from(porGrupo.entries())
        .sort(([a], [b]) => Number(a) - Number(b))
        .map(([, pts]) => ({
          type: "scattergl" as const,
          mode: "markers" as const,
          name: pts[0].PERFIL_NOMBRE_K5 ?? `Cluster ${pts[0].CLUSTER_K5}`,
          x: pts.map((p) => p.PC1),
          y: pts.map((p) => p.PC2),
          marker: { color: pts[0].COLOR, size: 6, opacity: idResaltado === null ? 0.7 : 0.25, line: { width: 0 } },
          customdata: pts.map((p) => [p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC, p.VIGENTE_MOSTRAR ? "Si" : "No", p.NOMBRE_COMPLETO]),
          hovertemplate: "%{customdata[4]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
        }));
      if (puntoResaltado && "CLUSTER_K5" in puntoResaltado) {
        baseK5.push({
          type: "scattergl" as const,
          mode: "markers" as const,
          name: puntoResaltado.NOMBRE_COMPLETO,
          x: [puntoResaltado.PC1],
          y: [puntoResaltado.PC2],
          marker: { color: "#E63946", size: 16, opacity: 1, line: { width: 2, color: "#FFFFFF" } },
          customdata: [[puntoResaltado.IDPERSONA, puntoResaltado.CARGO_ACTUAL ?? "-", puntoResaltado.TIPOEMPLEADO_ACTUAL_DESC, puntoResaltado.VIGENTE_MOSTRAR ? "Si" : "No", puntoResaltado.NOMBRE_COMPLETO]],
          hovertemplate: "%{customdata[4]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
        });
      }
      return baseK5;
    }

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

    if (puntoResaltado && "ES_MIXTO" in puntoResaltado) {
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
  }, [
    mapaQuery.data, mapaK5Query.data, puntoResaltado, idResaltado, modo,
    hayBusquedaCargo, terminosCargo, combinacionesMixtoDetectadas, colorPorCargo,
  ]);

  // Items para la leyenda propia en HTML (ver LeyendaMapa) - se derivan de `traces` pero
  // excluyendo el trace del punto resaltado (siempre el ultimo cuando existe, con el nombre
  // de la persona en vez de un grupo).
  const leyendaItems = useMemo(() => {
    const relevantes = puntoResaltado ? traces.slice(0, -1) : traces;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return relevantes.map((t: any) => ({ nombre: t.name as string, color: t.marker.color as string }));
  }, [traces, puntoResaltado]);

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
            {modo === "k5" && "K-Means directo sobre las 102 variables, sin separar antes por Administrativo/Docente — un corte más grueso que Cargos agrupados."}
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

        {/* Solo en modo "5 grupos": botones de los 5 clusters del K global. */}
        {modo === "k5" && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
              Grupos a mostrar (opcional)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {perfilesK5.map((p) => (
                <button
                  key={p.CLUSTER_K5}
                  onClick={() => togglePerfil(p.CLUSTER_K5)}
                  title={p.PERFIL_NOMBRE_K5}
                  className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                    perfilesFiltro.includes(p.CLUSTER_K5)
                      ? "text-white border-transparent"
                      : "border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}
                  style={perfilesFiltro.includes(p.CLUSTER_K5) ? { backgroundColor: p.COLOR } : undefined}
                >
                  {p.PERFIL_NOMBRE_K5}
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
        {(() => {
          const activa = modo === "k5" ? mapaK5Query : mapaQuery;
          if (activa.isLoading) return <LoadingBlock label="Cargando mapa..." />;
          if (activa.error || !activa.data) return <ErrorBlock message="No se pudo cargar el mapa." />;
          return (
            <>
              <Plot
                data={traces}
                layout={{
                  height: 640,
                  // Leyenda nativa de Plotly desactivada: con muchas entradas (13-14
                  // categorías) no hace wrap real a varias filas ni siquiera con
                  // orientation:"h", y las etiquetas terminan superpuestas. Se reemplaza por
                  // <LeyendaMapa> (HTML + flex-wrap) debajo del gráfico — mismo criterio en
                  // "cargo_real" (238 cargos): ahí ya no se mostraba leyenda, se usa el
                  // buscador de texto y el hover para identificar un cargo.
                  showlegend: false,
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
              {modo !== "cargo_real" && <LeyendaMapa items={leyendaItems} />}
              <p className="text-xs text-slate-500 mt-1">
                {activa.data.n_mostrados.toLocaleString()} personas mostradas de{" "}
                {activa.data.total_modelo.toLocaleString()} en el modelo. Usa la rueda del mouse o el
                pad para hacer zoom; arrastra para desplazarte.
              </p>
            </>
          );
        })()}
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

type ModoSemantico = "rama" | "cluster_semantico" | "cargo_real";

const MODOS_SEMANTICO: { value: ModoSemantico; label: string }[] = [
  { value: "rama", label: "Tipo Cargo" },
  { value: "cluster_semantico", label: "Cluster semántico" },
  { value: "cargo_real", label: "Todos los cargos" },
];

function MapaSemantico() {
  const [tipoFiltro, setTipoFiltro] = useState("Todos");
  const [perfilesFiltro, setPerfilesFiltro] = useState<number[]>([]);
  const [modo, setModo] = useState<ModoSemantico>("cluster_semantico");
  const [terminoCargoActual, setTerminoCargoActual] = useState("");
  const [terminosCargo, setTerminosCargo] = useState<string[]>([]);
  const [idSel, setIdSel] = useState<number | null>(null);
  const [nombreBuscado, setNombreBuscado] = useState("");
  const [idResaltado, setIdResaltado] = useState<number | null>(null);
  const [nombreResaltado, setNombreResaltado] = useState("");

  const resumenSemanticoQuery = useQuery({ queryKey: ["resumen_semantico"], queryFn: getResumenSemantico });
  const mapaSemanticoQuery = useQuery({
    queryKey: ["mapa_semantico", tipoFiltro, perfilesFiltro, modo],
    queryFn: () => getMapaSemantico(perfilesFiltro, modo, tipoFiltro),
  });

  const perfilesSemanticos = resumenSemanticoQuery.data?.perfiles ?? [];

  const puntoResaltado = useMemo(() => {
    if (idResaltado === null) return null;
    return mapaSemanticoQuery.data?.puntos.find((p) => p.IDPERSONA === idResaltado) ?? null;
  }, [idResaltado, mapaSemanticoQuery.data]);

  // Igual criterio que MapaEstatico: lista de cargos reales presentes en los datos, para el
  // desplegable de sugerencias del modo "Cargo real".
  const { cargosDisponibles, colorPorCargo } = useMemo(() => {
    if (!mapaSemanticoQuery.data || modo !== "cargo_real") return { cargosDisponibles: [] as string[], colorPorCargo: new Map<string, string>() };
    const set = new Set<string>();
    const colores = new Map<string, string>();
    for (const p of mapaSemanticoQuery.data.puntos) {
      if (p.GRUPO_COLOR !== "MIXTO") {
        set.add(p.GRUPO_COLOR);
        colores.set(p.GRUPO_COLOR, p.COLOR);
      }
    }
    return { cargosDisponibles: Array.from(set).sort(), colorPorCargo: colores };
  }, [mapaSemanticoQuery.data, modo]);

  const sugerenciasCargo = useMemo(() => {
    const q = normalizar(terminoCargoActual.trim());
    if (!q) return [];
    return cargosDisponibles.filter((c) => normalizar(c).includes(q));
  }, [cargosDisponibles, terminoCargoActual]);

  const sugerenciasNombre = useMemo(() => {
    if (!nombreBuscado.trim() || !mapaSemanticoQuery.data) return [];
    const vistos = new Set<number>();
    const resultado: { idPersona: number; nombre: string }[] = [];
    for (const p of mapaSemanticoQuery.data.puntos) {
      if (vistos.has(p.IDPERSONA) || !coincideNombre(p.NOMBRE_COMPLETO, nombreBuscado)) continue;
      vistos.add(p.IDPERSONA);
      resultado.push({ idPersona: p.IDPERSONA, nombre: p.NOMBRE_COMPLETO });
    }
    return resultado.slice(0, 20);
  }, [mapaSemanticoQuery.data, nombreBuscado]);

  function agregarTerminoCargo(texto: string) {
    setTerminosCargo((prev) => (prev.includes(texto) ? prev : [...prev, texto]));
    setTerminoCargoActual("");
  }

  function quitarTerminoCargo(texto: string) {
    setTerminosCargo((prev) => prev.filter((x) => x !== texto));
  }

  const hayBusquedaCargo = modo === "cargo_real" && terminosCargo.length > 0;

  const traces = useMemo(() => {
    if (!mapaSemanticoQuery.data) return [];

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let base: any[];

    if (hayBusquedaCargo) {
      const grupos = new Map<string, { pts: typeof mapaSemanticoQuery.data.puntos; color: string }>();
      const resto: typeof mapaSemanticoQuery.data.puntos = [];
      for (const p of mapaSemanticoQuery.data.puntos) {
        const cargoCoincidente = terminosCargo.find((t) => p.CARGO_ACTUAL === t);
        if (cargoCoincidente) {
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
          customdata: pts.map((p) => [p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC, p.VIGENTE_MOSTRAR ? "Si" : "No", p.NOMBRE_COMPLETO]),
          hovertemplate: "%{customdata[4]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
        }));
      if (resto.length > 0) {
        base.push({
          type: "scattergl" as const,
          mode: "markers" as const,
          name: "Otros",
          x: resto.map((p) => p.PC1),
          y: resto.map((p) => p.PC2),
          marker: { color: "#94A3B8", size: 6, opacity: idResaltado !== null ? 0.1 : 0.12, line: { width: 0 } },
          customdata: resto.map((p) => [p.IDPERSONA, p.CARGO_ACTUAL ?? "-", p.TIPOEMPLEADO_ACTUAL_DESC, p.VIGENTE_MOSTRAR ? "Si" : "No", p.NOMBRE_COMPLETO]),
          hovertemplate: "%{customdata[4]}<br>%{customdata[2]} - %{customdata[1]}<br>Vigente: %{customdata[3]}<extra></extra>",
        });
      }
    } else {
      const porGrupo = new Map<string, typeof mapaSemanticoQuery.data.puntos>();
      for (const p of mapaSemanticoQuery.data.puntos) {
        if (!porGrupo.has(p.GRUPO_COLOR)) porGrupo.set(p.GRUPO_COLOR, []);
        porGrupo.get(p.GRUPO_COLOR)!.push(p);
      }
      base = Array.from(porGrupo.entries())
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([grupo, pts]) => {
          const esMixto = grupo === "MIXTO";
          const nombre = esMixto ? "Mixto" : modo === "rama" ? grupo : modo === "cargo_real" ? grupo : pts[0].PERFIL_NOMBRE_SEMANTICO ?? `Cluster ${pts[0].CLUSTER_SEMANTICO}`;
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
        marker: { color: "#E63946", size: 16, opacity: 1, line: { width: 2, color: "#FFFFFF" } },
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
  }, [mapaSemanticoQuery.data, puntoResaltado, idResaltado, modo, hayBusquedaCargo, terminosCargo, colorPorCargo]);

  // Ver comentario equivalente en MapaEstatico: leyenda propia en HTML en vez de la nativa
  // de Plotly (no hace wrap real con muchas entradas).
  const leyendaItems = useMemo(() => {
    const relevantes = puntoResaltado ? traces.slice(0, -1) : traces;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return relevantes.map((t: any) => ({ nombre: t.name as string, color: t.marker.color as string }));
  }, [traces, puntoResaltado]);

  function togglePerfil(c: number) {
    setPerfilesFiltro((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  function cambiarModo(m: ModoSemantico) {
    setModo(m);
    setPerfilesFiltro([]);
    setTerminosCargo([]);
    setTerminoCargoActual("");
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

        <p className="text-xs text-slate-400">
          Clustering independiente sobre el espacio de embeddings (texto de trayectoria/formación/
          docencia/investigación), no sobre las variables estructuradas del Clustering estructurado — los
          IDs de cluster aquí no corresponden a las categorías de la otra pestaña. Rama y Cargo real
          son los mismos atributos de persona que en el Clustering estructurado, proyectados sobre este
          espacio para comparar ambas técnicas.
        </p>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
            Ver el mapa coloreado por
          </p>
          <div className="flex gap-2">
            {MODOS_SEMANTICO.map((m) => (
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
            {modo === "rama" && "Administrativo / Docente / Mixto (3 colores) — mismo criterio que el Clustering estructurado."}
            {modo === "cluster_semantico" && "Los clusters descubiertos en el espacio de embeddings."}
            {modo === "cargo_real" && "Cada cargo real tiene su propio color. Usa el buscador para ubicar uno."}
          </p>
        </div>

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

        {modo === "cluster_semantico" && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1.5">
              Clusters semánticos a mostrar (opcional)
            </p>
            <div className="flex flex-wrap gap-1.5">
              {perfilesSemanticos.map((p) => (
                <button
                  key={p.CLUSTER_SEMANTICO}
                  onClick={() => togglePerfil(p.CLUSTER_SEMANTICO)}
                  className={`px-2.5 py-1 text-xs rounded-md border transition-colors ${
                    perfilesFiltro.includes(p.CLUSTER_SEMANTICO)
                      ? "text-white border-transparent"
                      : "border-slate-300 text-slate-600 hover:bg-slate-50"
                  }`}
                  style={perfilesFiltro.includes(p.CLUSTER_SEMANTICO) ? { backgroundColor: p.COLOR } : undefined}
                >
                  {p.PERFIL_NOMBRE_SEMANTICO}
                </button>
              ))}
            </div>
          </div>
        )}

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
        {mapaSemanticoQuery.isLoading ? (
          <LoadingBlock label="Cargando mapa..." />
        ) : mapaSemanticoQuery.error || !mapaSemanticoQuery.data ? (
          <ErrorBlock message="No se pudo cargar el mapa." />
        ) : (
          <>
            <Plot
              data={traces}
              layout={{
                height: 640,
                // Leyenda nativa de Plotly desactivada (ver comentario equivalente en
                // MapaEstatico) - se reemplaza por <LeyendaMapa> (HTML + flex-wrap) debajo
                // del gráfico.
                showlegend: false,
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
            {modo !== "cargo_real" && <LeyendaMapa items={leyendaItems} />}
            <p className="text-xs text-slate-500 mt-1">
              {mapaSemanticoQuery.data.n_mostrados.toLocaleString()} personas mostradas de{" "}
              {mapaSemanticoQuery.data.total_modelo.toLocaleString()} en el modelo (clustering
              semántico). Usa la rueda del mouse o el pad para hacer zoom; arrastra para desplazarte.
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
