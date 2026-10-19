import { useLayoutEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NOMBRE_AMBITO } from "../lib/texto";
import { getPersona, type Ambito, type NavegacionFicha, type OrigenFicha } from "../api/client";
import IntensidadDimensiones from "./IntensidadDimensiones";
import TimelineTrayectoria from "./TimelineTrayectoria";
import PerfilCompleto from "./PerfilCompleto";
import DesgloseEvidencias from "./DesgloseEvidencias";

interface Props {
  ambito: Ambito;
  personaId: number;
  /** desde dónde se abrió: decide la pestaña inicial (dimensión → Dimensiones; perfil → Perfil completo; otra → Trayectoria) */
  origen: OrigenFicha;
  /** dimensión que se despliega al abrir la pestaña Dimensiones */
  dimensionInicial?: string;
  /** volver a la vista anterior del panel */
  onVolver: () => void;
  textoVolver: string;
  /** enlaces hacia otras personas, patrones globales y dimensiones (los que falten no se enlazan) */
  nav?: NavegacionFicha;
}

type Pestana = "trayectoria" | "dimensiones" | "perfil" | "evidencias";

const PESTANAS: { id: Pestana; texto: string }[] = [
  { id: "trayectoria", texto: "Trayectoria" },
  { id: "dimensiones", texto: "Dimensiones" },
  { id: "perfil", texto: "Perfil completo" },
  { id: "evidencias", texto: "Evidencias" },
];

const INICIAL: Record<OrigenFicha, Pestana> = { dimension: "dimensiones", perfil: "perfil", otra: "trayectoria" };

/** dónde estaba la ficha antes de saltar a otra pestaña (para "← Volver a …") */
interface Lugar {
  pestana: Pestana;
  /** desplazamiento del contenido, para volver al mismo punto */
  scroll: number;
  /** en Dimensiones, la dimensión abierta */
  dimension: string | null;
}

// Ficha de la persona en cuatro pestañas. La pestaña inicial sale del contexto de origen; quien
// la usa le da una `key` por persona y origen, así que abrir otra persona vuelve a calcularla y,
// mientras se navega dentro de la misma ficha, la pestaña elegida se conserva.
export default function FichaPersona({ ambito, personaId, origen, dimensionInicial, onVolver, textoVolver, nav = {} }: Props) {
  const { data, isLoading, isError } = useQuery({ queryKey: ["persona", ambito, personaId], queryFn: () => getPersona(personaId, ambito) });
  const [pestana, setPestana] = useState<Pestana>(INICIAL[origen]);
  const [dimensionEvidencias, setDimensionEvidencias] = useState<string | null>(null);
  // dimensión que se abre al mostrar la pestaña Dimensiones (la del origen, o la elegida en un salto)
  const [dimensionAbierta, setDimensionAbierta] = useState<string | null>(dimensionInicial ?? null);
  // saltos dentro de la ficha (p. ej. de un rasgo del perfil a su dimensión), para poder volver
  const [pila, setPila] = useState<Lugar[]>([]);
  const panel = useRef<HTMLDivElement | null>(null);
  const scrollPendiente = useRef<number | null>(null);
  useLayoutEffect(() => {
    if (scrollPendiente.current !== null && panel.current) {
      panel.current.scrollTop = scrollPendiente.current;
      scrollPendiente.current = null;
    }
  }, [pestana]);

  /** ir a otra pestaña recordando dónde se estaba; `dimension` = la que se abre en el destino */
  const saltar = (destino: Pestana, dimension: string | null, desdeDimension: string | null = null) => {
    setPila((p) => [...p, { pestana, scroll: panel.current?.scrollTop ?? 0, dimension: desdeDimension }]);
    if (destino === "dimensiones") setDimensionAbierta(dimension);
    if (destino === "evidencias") setDimensionEvidencias(dimension);
    setPestana(destino);
  };
  const volverAtras = () => {
    const l = pila[pila.length - 1];
    if (!l) return;
    setPila((p) => p.slice(0, -1));
    if (l.pestana === "dimensiones") setDimensionAbierta(l.dimension);
    scrollPendiente.current = l.scroll;
    setPestana(l.pestana);
  };

  const volver = (
    <button onClick={onVolver} className="text-[10px] text-espol-blue hover:underline px-5 pt-2 block text-left">
      ← {textoVolver}
    </button>
  );
  if (isLoading) return <div>{volver}<p className="p-5 text-sm text-slate-500">Cargando ficha…</p></div>;
  if (isError || !data)
    return <div>{volver}<p className="p-5 text-sm text-red-600">La persona seleccionada no está en {NOMBRE_AMBITO[ambito]}.</p></div>;

  // cabecera y pestañas fijas; solo el contenido de la pestaña hace scroll (el panel que la contiene
  // tiene alto fijo)
  return (
    <section className="h-full flex flex-col">
      <div className="shrink-0">{volver}</div>
      <header className="shrink-0 px-5 pt-0.5 pb-1.5">
        <h3 className="text-sm font-semibold leading-tight text-espol-navy">{data.nombre}</h3>
        {/* cargo_actual y unidad_actual son listas " / " alineadas, ya ordenadas por jerarquía de
            contrato (nombramiento, contrato, servicios); todas se muestran con el mismo peso */}
        {(() => {
          const cargos = (data.estado.cargo_actual ?? "").split(" / ").filter(Boolean);
          const unidades = (data.estado.unidad_actual ?? "").split(" / ");
          if (!cargos.length) return <p className="text-[11px] text-slate-700">Sin cargo actual</p>;
          return (
            <ul className="mt-0.5 space-y-0">
              {cargos.map((c, i) => (
                <li key={i} className="text-[11px] leading-tight text-slate-800 font-medium">
                  {c}
                  {unidades[i] && <span className="text-slate-500 font-normal"> · {unidades[i]}</span>}
                </li>
              ))}
            </ul>
          );
        })()}
        <p className="text-[10px] text-slate-500">
          {data.estado.tipo_empleado ?? "tipo desconocido"} · {data.estado.vigente ? "vigente" : "no vigente"}
        </p>
      </header>

      <div role="tablist" aria-label="Secciones de la ficha" className="shrink-0 bg-white border-y px-3 flex gap-1">
        {PESTANAS.map((p) => (
          <button
            key={p.id}
            role="tab"
            aria-selected={pestana === p.id}
            onClick={() => {
              setPestana(p.id);
              setPila([]);
              if (p.id === "evidencias") setDimensionEvidencias(null);
            }}
            className={`px-2.5 py-2 text-xs whitespace-nowrap border-b-2 -mb-px ${
              pestana === p.id ? "border-espol-blue text-espol-navy font-semibold" : "border-transparent text-slate-600 hover:text-slate-900"
            }`}
          >
            {p.texto}
          </button>
        ))}
      </div>

      <div ref={panel} role="tabpanel" className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
        {pila.length > 0 && (() => {
          const l = pila[pila.length - 1];
          const nombreDim = l.dimension ? data.dimensiones.find((x) => x.dimension === l.dimension)?.nombre : null;
          const destino = PESTANAS.find((x) => x.id === l.pestana)?.texto ?? "";
          // fijo arriba: la fila que se abre al saltar sube al inicio y no debe taparlo
          return (
            <div className="sticky -top-4 z-10 -mx-5 -mt-4 mb-3 px-5 pt-2 pb-2 bg-white/95 backdrop-blur-sm border-b border-slate-100">
              <button
                type="button"
                onClick={volverAtras}
                className="inline-flex items-center gap-1 rounded-md bg-blue-50 border border-blue-100 px-2 py-1 text-[11px] text-espol-blue hover:bg-blue-100"
              >
                ← Volver a {destino}
                {nombreDim ? ` · ${nombreDim}` : ""}
              </button>
            </div>
          );
        })()}
        {pestana === "trayectoria" && <TimelineTrayectoria personaId={data.persona_id} />}
        {pestana === "dimensiones" && (
          <IntensidadDimensiones
            key={dimensionAbierta ?? ""}
            ambito={ambito}
            dimensiones={data.dimensiones}
            dimensionInicial={dimensionAbierta ?? undefined}
            nav={nav}
            onVerEvidencias={(d) => saltar("evidencias", d, d)}
          />
        )}
        {pestana === "perfil" && (
          <PerfilCompleto ambito={ambito} persona={data} nav={nav} onVerDimension={(d) => saltar("dimensiones", d)} />
        )}
        {pestana === "evidencias" && <DesgloseEvidencias personaId={data.persona_id} dimensionInicial={dimensionEvidencias} />}
      </div>
    </section>
  );
}
